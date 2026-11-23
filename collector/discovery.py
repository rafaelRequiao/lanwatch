"""
discovery.py — Descoberta do coletor por multicast UDP (aula 09, "Descoberta de dispositivos").

Problema: IP do servidor "gravado" na configuração de cada PC deixa a arquitetura
frágil; se o coletor mudar de máquina, todos os agentes precisam ser reconfigurados.

Solução (descoberta ATIVA e DISTRIBUÍDA, como no exemplo da aula):
  - O coletor ingressa no grupo multicast 239.255.10.10 (escopo administrativo),
    porta UDP 50000. O ingresso (IP_ADD_MEMBERSHIP) é anunciado via IGMP.
  - O agente envia DISCOVER para o grupo com TTL = 1 (não sai da sub-rede).
  - O coletor responde em UNICAST para quem perguntou, informando a porta TCP.
  - O agente usa o IP de ORIGEM da resposta como endereço do coletor.

Por que UDP aqui e TCP nas métricas?
  - Multicast e broadcast só existem no UDP (o TCP é sempre ponto a ponto).
  - A sondagem pode se perder: o agente repete com intervalos crescentes.

Segurança: a descoberta revela o serviço na LAN (reconhecimento) e alguém
poderia responder se passando pelo coletor (falsificação). Isso é mitigado
porque, depois de descobrir, o agente só aceita o coletor cujo certificado TLS
confere — um coletor falso é recusado no handshake.
"""

import json
import logging
import os
import socket
import struct
import threading

GROUP = os.getenv("DISCOVERY_GROUP", "239.255.10.10")
PORT = int(os.getenv("DISCOVERY_PORT", "50000"))

log = logging.getLogger("collector")


def _responder(tcp_port: int, tls: bool):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", PORT))
    # Ingressa no grupo multicast em todas as interfaces (0.0.0.0) → mensagem IGMP "join"
    mreq = struct.pack("4s4s", socket.inet_aton(GROUP), socket.inet_aton("0.0.0.0"))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    log.info("descoberta: ouvindo multicast %s:%d/udp", GROUP, PORT)

    answer = json.dumps({"type": "collector", "port": tcp_port, "tls": tls,
                         "tls_name": "collector"}).encode()
    while True:
        try:
            data, origem = sock.recvfrom(1024)
            msg = json.loads(data.decode("utf-8"))
            if msg.get("type") != "discover":
                continue
            sock.sendto(answer, origem)  # resposta em unicast, só para quem perguntou
            log.info("descoberta: DISCOVER de %s:%d (%s) → respondido",
                     origem[0], origem[1], msg.get("host", "?"))
        except (ValueError, UnicodeDecodeError):
            continue  # datagrama inválido: ignora (UDP não tem conexão para encerrar)
        except OSError as exc:
            log.warning("descoberta: erro de socket: %s", exc)


def start_responder(tcp_port: int, tls: bool):
    threading.Thread(target=_responder, args=(tcp_port, tls), name="discovery", daemon=True).start()
