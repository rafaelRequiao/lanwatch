"""
server.py — Coletor central do LANWatch.

Recebe métricas dos agentes (um por PC da LAN house) via TCP + TLS, porta 5000,
e serve o painel web (HTTP, Flask) na porta 8080.

Threads deste processo:
  MainThread    accept() na porta 5000 e cria uma thread por agente
  agent-<pc>    uma por agente conectado: handshake TLS, autenticação, métricas
  status        a cada 10 s escreve no log quem está online/offline
  mailer        consome a fila de alertas e envia e-mails por SMTP (alerts.py)
  web           servidor HTTP do Flask (web.py)

  discovery     responde à descoberta multicast UDP (discovery.py)

Estado compartilhado (dict `hosts` e o banco SQLite) é protegido por Lock,
porque várias threads escrevem nele ao mesmo tempo (condição de corrida).

Por que threads e não processos ou asyncio? (aula 06)
  - No CPython cada threading.Thread é uma thread do SO (modelo 1:1). O GIL
    impede duas threads de executarem bytecode ao mesmo tempo, MAS é liberado
    durante E/S (recv, send, sleep). Nosso servidor passa quase todo o tempo
    esperando a rede (E/S), então as threads atendem os agentes em paralelo.
  - Threads compartilham memória: o painel lê o mesmo dict `hosts` sem precisar
    de IPC. Com processos teríamos de trocar dados por pipes/filas entre eles.
  - Custo: um erro numa thread pode afetar o processo todo; por isso cada
    handle_client trata as próprias exceções.

Por que TCP e não UDP?
  - Métricas precisam chegar completas e em ordem para os gráficos/alertas.
  - A conexão persistente é usada como "sinal de vida": se ela cai (FIN, RST ou
    timeout), sabemos na hora que o PC caiu — com UDP teríamos que inventar isso.
"""

import hmac
import logging
import logging.handlers
import os
import signal
import socket
import sqlite3
import ssl
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
from protocol import PROTOCOL_VERSION, LineReader, ProtocolError, encode  # noqa: E402

# ---------------------------------------------------------------- configuração
HOST = os.getenv("COLLECTOR_BIND", "0.0.0.0")
PORT = int(os.getenv("COLLECTOR_PORT", "5000"))
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))
TOKEN = os.getenv("AGENT_TOKEN", "")
DATA_DIR = os.getenv("DATA_DIR", "./data")
CERT_DIR = os.getenv("CERT_DIR", "")  # vazio = sem TLS (só para testes locais)
CLIENT_TIMEOUT = float(os.getenv("CLIENT_TIMEOUT", "15"))  # s sem mensagem = agente morto
MAX_CLIENTS = int(os.getenv("MAX_CLIENTS", "50"))

if not TOKEN:
    sys.exit("ERRO: defina AGENT_TOKEN (veja .env.example)")

# Diretório de dados com permissão 750: dono lê/escreve, grupo lê, outros nada.
os.makedirs(os.path.join(DATA_DIR, "logs"), exist_ok=True)
os.chmod(DATA_DIR, 0o750)

# ---------------------------------------------------------------- logs
log = logging.getLogger("collector")
log.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s")
_console = logging.StreamHandler(sys.stdout)
_console.setFormatter(_fmt)
_file = logging.handlers.RotatingFileHandler(  # arquivo gira ao chegar em 1 MB, guarda 3
    os.path.join(DATA_DIR, "logs", "collector.log"), maxBytes=1_000_000, backupCount=3
)
_file.setFormatter(_fmt)
for _name in ("collector", "collector.alerts"):
    logging.getLogger(_name).addHandler(_console)
    logging.getLogger(_name).addHandler(_file)
logging.getLogger("collector.alerts").setLevel(logging.INFO)
logging.getLogger("collector.alerts").propagate = False

from alerts import AlertManager  # noqa: E402  (depois dos logs configurados)
from discovery import start_responder  # noqa: E402
from web import create_app  # noqa: E402

# ---------------------------------------------------------------- estado compartilhado
db_lock = threading.Lock()
db = sqlite3.connect(os.path.join(DATA_DIR, "lanwatch.db"), check_same_thread=False)
db.execute(
    """CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        host TEXT NOT NULL, ts REAL NOT NULL,
        cpu REAL, mem REAL, disk REAL,
        net_tx INTEGER, net_rx INTEGER, procs INTEGER, rtt_ms REAL
    )"""
)
db.execute("CREATE INDEX IF NOT EXISTS idx_metrics_host_ts ON metrics(host, ts)")
db.commit()

hosts_lock = threading.Lock()
hosts: dict[str, dict] = {}  # host -> {"addr", "online", "last_seen", "last"}

client_slots = threading.BoundedSemaphore(MAX_CLIENTS)  # limita threads simultâneas
alerts = AlertManager()


# ---------------------------------------------------------------- TLS
def ensure_certificate() -> ssl.SSLContext | None:
    """
    Gera (uma vez) um certificado autoassinado com o openssl e devolve o
    contexto TLS do servidor. A chave privada fica com permissão 600.
    O certificado vai num volume que os agentes montam só para leitura.
    """
    if not CERT_DIR:
        log.warning("CERT_DIR vazio: TLS DESLIGADO (tráfego em texto puro)")
        return None
    crt, key = os.path.join(CERT_DIR, "collector.crt"), os.path.join(CERT_DIR, "collector.key")
    if not (os.path.exists(crt) and os.path.exists(key)):
        log.info("gerando certificado autoassinado em %s", CERT_DIR)
        subprocess.run(  # processo filho: o openssl roda fora do Python e retorna
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "365",
             "-keyout", key, "-out", crt, "-subj", "/CN=collector/O=LANWatch",
             "-addext", "subjectAltName=DNS:collector,DNS:localhost,IP:127.0.0.1"],
            check=True, capture_output=True,
        )
        os.chmod(key, 0o600)
        os.chmod(crt, 0o644)
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(crt, key)
    return ctx


# ---------------------------------------------------------------- validação
def _num(msg, key, lo, hi):
    """Lê um campo numérico e garante que está no intervalo [lo, hi]."""
    v = msg.get(key)
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi:
        raise ProtocolError(f"campo '{key}' inválido: {v!r}")
    return v


def validate_metrics(msg: dict) -> dict:
    return {
        "ts": _num(msg, "ts", 0, 1e11),
        "cpu": _num(msg, "cpu", 0, 100),
        "mem": _num(msg, "mem", 0, 100),
        "disk": _num(msg, "disk", 0, 100),
        "net_tx": int(_num(msg, "net_tx", 0, 2**63)),
        "net_rx": int(_num(msg, "net_rx", 0, 2**63)),
        "procs": int(_num(msg, "procs", 0, 1_000_000)),
        "rtt_ms": _num(msg, "rtt_ms", 0, 60_000) if msg.get("rtt_ms") is not None else None,
    }


def valid_hostname(name) -> bool:
    return isinstance(name, str) and 1 <= len(name) <= 32 and all(
        c.isalnum() or c in "-_" for c in name
    )


# ---------------------------------------------------------------- atendimento
def handle_client(conn: socket.socket, addr, tls_ctx):
    """Roda em uma thread própria: atende UM agente do hello até a desconexão."""
    host = None
    conn.settimeout(CLIENT_TIMEOUT)  # temporizador da aplicação: detecta "par inativo" (aula 09)
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # sem Nagle: pong sai na hora
    offline_reason = "conexão encerrada"
    try:
        # 0) Handshake TLS feito AQUI, na thread do agente, e não no accept():
        #    assim um cliente lento no handshake não trava a thread principal.
        if tls_ctx:
            conn = tls_ctx.wrap_socket(conn, server_side=True)
        reader = LineReader(conn)

        # 1) Autenticação: a primeira mensagem TEM que ser hello com token válido.
        hello = reader.read_message()
        if hello is None:
            return
        if hello.get("type") != "hello" or not valid_hostname(hello.get("host")):
            conn.sendall(encode({"type": "error", "reason": "esperado hello válido"}))
            log.warning("%s:%d handshake inválido: %r", *addr, hello)
            return
        # compare_digest compara em tempo constante (evita ataque de temporização)
        if not hmac.compare_digest(str(hello.get("token", "")), TOKEN):
            conn.sendall(encode({"type": "error", "reason": "token inválido"}))
            log.warning("%s:%d AUTENTICAÇÃO RECUSADA (host=%s)", *addr, hello.get("host"))
            return

        host = hello["host"]
        threading.current_thread().name = f"agent-{host}"
        with hosts_lock:
            # conn_id identifica ESTA conexão: se o PC reconectar antes de a conexão
            # antiga dar timeout, a thread antiga não pode marcá-lo como offline.
            hosts[host] = {"addr": f"{addr[0]}:{addr[1]}", "online": True,
                           "last_seen": time.time(), "last": None, "conn_id": id(conn)}
        conn.sendall(encode({"type": "welcome", "version": PROTOCOL_VERSION,
                             "server_time": time.time()}))
        log.info("agente %s conectado de %s:%d (%s)", host, *addr,
                 conn.version() if tls_ctx else "sem TLS")
        alerts.host_online(host)

        # 2) Loop principal: ping/pong e métricas.
        while True:
            msg = reader.read_message()
            if msg is None:
                log.info("agente %s encerrou a conexão", host)
                return
            mtype = msg.get("type")
            if mtype == "ping":
                conn.sendall(encode({"type": "pong", "t": msg.get("t")}))
            elif mtype == "metrics":
                try:
                    m = validate_metrics(msg)
                except ProtocolError as exc:
                    log.warning("métrica descartada de %s: %s", host, exc)
                    continue  # descarta só essa mensagem, mantém a conexão
                with db_lock:
                    db.execute(
                        "INSERT INTO metrics (host, ts, cpu, mem, disk, net_tx, net_rx, procs, rtt_ms)"
                        " VALUES (?,?,?,?,?,?,?,?,?)",
                        (host, m["ts"], m["cpu"], m["mem"], m["disk"],
                         m["net_tx"], m["net_rx"], m["procs"], m["rtt_ms"]),
                    )
                    db.commit()
                with hosts_lock:
                    hosts[host].update(last_seen=time.time(), last=m)
                alerts.check_metrics(host, m)
                log.info("%s cpu=%.1f%% mem=%.1f%% disk=%.1f%% rtt=%sms",
                         host, m["cpu"], m["mem"], m["disk"],
                         f"{m['rtt_ms']:.2f}" if m["rtt_ms"] is not None else "-")
            else:
                log.warning("tipo desconhecido de %s: %r", host, mtype)

    except socket.timeout:
        offline_reason = f"sem resposta há {CLIENT_TIMEOUT:.0f}s"
        log.warning("agente %s %s — considerado OFFLINE", host or addr, offline_reason)
    except ssl.SSLError as exc:
        log.warning("falha no handshake TLS com %s:%d: %s", *addr, exc.reason or exc)
    except ProtocolError as exc:
        offline_reason = "violação de protocolo"
        log.warning("violação de protocolo de %s: %s", host or addr, exc)
    except (ConnectionResetError, BrokenPipeError) as exc:
        offline_reason = "conexão perdida"
        log.warning("conexão com %s perdida: %s", host or addr, exc)
    finally:
        if host:
            with hosts_lock:
                still_mine = hosts[host].get("conn_id") == id(conn)
                if still_mine:
                    hosts[host]["online"] = False
            if still_mine:
                alerts.host_offline(host, offline_reason)
        conn.close()
        client_slots.release()


# ---------------------------------------------------------------- funções usadas pelo painel
def snapshot() -> dict:
    with hosts_lock:
        # devolve uma CÓPIA: o Flask usa os dados depois que o lock já foi liberado
        return {h: {k: v for k, v in s.items() if k != "conn_id"} for h, s in hosts.items()}


def history(host: str, minutes: int) -> list[dict]:
    since = time.time() - minutes * 60
    with db_lock:
        rows = db.execute(
            "SELECT ts, cpu, mem, disk, rtt_ms FROM metrics WHERE host=? AND ts>=? ORDER BY ts",
            (host, since),
        ).fetchall()
    return [dict(zip(("ts", "cpu", "mem", "disk", "rtt_ms"), r)) for r in rows]


def status_reporter():
    """Thread de fundo: a cada 10 s escreve no log um resumo de quem está online."""
    while True:
        time.sleep(10)
        with hosts_lock:
            online = sorted(h for h, s in hosts.items() if s["online"])
            offline = sorted(h for h, s in hosts.items() if not s["online"])
        log.info("RESUMO online=%s offline=%s threads_ativas=%d",
                 online, offline, threading.active_count())


def _on_sigterm(signum, frame):
    """docker stop / systemctl stop mandam SIGTERM: encerramos de forma limpa."""
    raise KeyboardInterrupt


def main():
    signal.signal(signal.SIGTERM, _on_sigterm)
    tls_ctx = ensure_certificate()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # SO_REUSEADDR: permite reiniciar o servidor sem esperar o TIME_WAIT da porta
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(MAX_CLIENTS)
    log.info("coletor LANWatch ouvindo em %s:%d (TLS %s, pid=%d)",
             HOST, PORT, "ligado" if tls_ctx else "DESLIGADO", os.getpid())

    threading.Thread(target=status_reporter, name="status", daemon=True).start()
    start_responder(PORT, tls_ctx is not None)
    app = create_app(snapshot, history, lambda: list(alerts.recent))
    threading.Thread(target=lambda: app.run(host=HOST, port=WEB_PORT, threaded=True),
                     name="web", daemon=True).start()
    log.info("painel web em http://%s:%d", HOST, WEB_PORT)

    try:
        while True:
            conn, addr = srv.accept()
            if not client_slots.acquire(blocking=False):
                log.warning("limite de %d agentes atingido, recusando %s:%d", MAX_CLIENTS, *addr)
                conn.close()
                continue
            threading.Thread(target=handle_client, args=(conn, addr, tls_ctx), daemon=True).start()
    except KeyboardInterrupt:
        log.info("encerrando coletor")
    finally:
        srv.close()
        db.close()


if __name__ == "__main__":
    main()
