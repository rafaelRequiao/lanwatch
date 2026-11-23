"""
netsim.py — Simulador de "rede ruim" do LANWatch (proxy TCP com atraso).

Usado para PROVOCAR uma falha de latência na demonstração quando o kernel não
tem o módulo sch_netem (o `tc qdisc ... netem` dá "qdisc kind is unknown").

Funcionamento:
  pc02 ──TCP──► netsim:5000 ──TCP──► collector:5000
  Para cada conexão aceita, abre uma conexão com o coletor e cria DUAS threads,
  uma para cada sentido, que repassam os bytes. Antes de repassar cada bloco,
  a thread dorme DELAY ms. Como ping e pong passam pelo proxy, o RTT medido
  pelo agente sobe cerca de 2 × DELAY.

  O proxy só repassa bytes, sem abrir nada: o TLS continua fim a fim entre
  agente e coletor (o proxy vê somente dados cifrados).

Controle em tempo real (sem reiniciar nada):
  docker exec netsim sh -c 'echo 60 > /tmp/delay_ms'   # 60 ms por sentido
  docker exec netsim sh -c 'echo 0  > /tmp/delay_ms'   # rede normal
"""

import logging
import os
import socket
import sys
import threading
import time

LISTEN_PORT = int(os.getenv("LISTEN_PORT", "5000"))
TARGET = (os.getenv("TARGET_HOST", "collector"), int(os.getenv("TARGET_PORT", "5000")))
CONTROL_FILE = os.getenv("CONTROL_FILE", "/tmp/delay_ms")

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s [%(levelname)s] [netsim] %(message)s")
log = logging.getLogger("netsim")
_last_delay = None


def current_delay() -> float:
    """Lê o atraso (ms) do arquivo de controle; inválido ou ausente = 0."""
    global _last_delay
    try:
        with open(CONTROL_FILE) as f:
            ms = max(0, min(int(f.read().strip() or 0), 5000))
    except (OSError, ValueError):
        ms = 0
    if ms != _last_delay:
        log.info("atraso agora é %d ms por sentido (~%d ms de RTT)", ms, 2 * ms)
        _last_delay = ms
    return ms / 1000


def pipe(src: socket.socket, dst: socket.socket, label: str):
    """Repassa bytes de src para dst, atrasando cada bloco."""
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            time.sleep(current_delay())
            dst.sendall(data)
    except OSError as exc:
        log.info("%s encerrado: %s", label, exc)
    finally:
        for s in (src, dst):  # fecha os dois lados para a outra thread também sair
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def handle(client: socket.socket, addr):
    try:
        upstream = socket.create_connection(TARGET, timeout=5)
        upstream.settimeout(None)
    except OSError as exc:
        log.warning("não consegui conectar ao coletor %s:%d: %s", *TARGET, exc)
        client.close()
        return
    log.info("nova conexão %s:%d ⇄ %s:%d", *addr, *TARGET)
    a = threading.Thread(target=pipe, args=(client, upstream, "agente→coletor"), daemon=True)
    b = threading.Thread(target=pipe, args=(upstream, client, "coletor→agente"), daemon=True)
    a.start(); b.start(); a.join(); b.join()
    client.close(); upstream.close()


def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", LISTEN_PORT))
    srv.listen(16)
    log.info("netsim ouvindo em :%d → %s:%d", LISTEN_PORT, *TARGET)
    current_delay()
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()
