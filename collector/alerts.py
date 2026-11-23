"""
alerts.py — Regras de alerta e envio de e-mail (SMTP) do LANWatch.

Modelo produtor/consumidor:
  - As threads dos agentes (produtoras) só avaliam as regras e colocam o
    alerta numa fila (queue.Queue, que já é thread-safe).
  - UMA thread consumidora tira da fila e fala com o servidor SMTP.
  - Assim, se o servidor de e-mail estiver lento ou fora do ar, nenhum
    agente fica travado esperando o e-mail sair.

Histerese: um alerta dispara quando a métrica CRUZA o limite e só volta a
disparar depois de ela normalizar. Sem isso, um PC a 95% de CPU mandaria um
e-mail a cada 2 segundos.
"""

import logging
import os
import queue
import smtplib
import threading
import time
from email.message import EmailMessage

log = logging.getLogger("collector.alerts")

SMTP_HOST = os.getenv("SMTP_HOST", "")          # vazio = alertas só no log/painel
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
ALERT_FROM = os.getenv("ALERT_FROM", "lanwatch@lanhouse.local")
ALERT_TO = os.getenv("ALERT_TO", "admin@lanhouse.local")

# métrica -> (limite, descrição)
THRESHOLDS = {
    "cpu": (float(os.getenv("ALERT_CPU", "90")), "CPU acima de {lim:.0f}%: {val:.1f}%"),
    "mem": (float(os.getenv("ALERT_MEM", "90")), "Memória acima de {lim:.0f}%: {val:.1f}%"),
    "disk": (float(os.getenv("ALERT_DISK", "90")), "Disco acima de {lim:.0f}%: {val:.1f}%"),
    "rtt_ms": (float(os.getenv("ALERT_RTT_MS", "50")), "Latência acima de {lim:.0f} ms: {val:.1f} ms"),
}


LABELS = {"cpu": ("CPU", "%"), "mem": ("Memória", "%"), "disk": ("Disco", "%"), "rtt_ms": ("Latência", " ms")}


class AlertManager:
    def __init__(self):
        self._active: set[tuple[str, str]] = set()  # (host, tipo) com alerta em aberto
        self._lock = threading.Lock()
        self._outbox: queue.Queue = queue.Queue(maxsize=200)
        self.recent: list[dict] = []                 # últimos alertas, para o painel
        threading.Thread(target=self._mailer, name="mailer", daemon=True).start()

    # ------------------------------------------------ chamadas pelas threads dos agentes
    def check_metrics(self, host: str, m: dict):
        for key, (limit, text) in THRESHOLDS.items():
            val = m.get(key)
            if val is None:
                continue
            if val > limit:
                self._fire(host, key, "CRÍTICO", text.format(lim=limit, val=val))
            elif val < limit * 0.9:  # só normaliza 10% abaixo do limite (histerese)
                label, unit = LABELS[key]
                self._clear(host, key, f"{label} normalizada: {val:.1f}{unit}")

    def host_offline(self, host: str, reason: str):
        self._fire(host, "offline", "CRÍTICO", f"PC OFFLINE ({reason})")

    def host_online(self, host: str):
        self._clear(host, "offline", "PC voltou a ficar ONLINE")

    # ------------------------------------------------ interno
    def _fire(self, host, kind, level, text):
        with self._lock:
            if (host, kind) in self._active:
                return
            self._active.add((host, kind))
        self._emit(host, level, text)

    def _clear(self, host, kind, text):
        with self._lock:
            if (host, kind) not in self._active:
                return
            self._active.discard((host, kind))
        self._emit(host, "RESOLVIDO", text)

    def _emit(self, host, level, text):
        alert = {"ts": time.time(), "host": host, "level": level, "text": text}
        log.warning("ALERTA [%s] %s: %s", level, host, text)
        with self._lock:
            self.recent = ([alert] + self.recent)[:30]
        try:
            self._outbox.put_nowait(alert)
        except queue.Full:
            log.error("fila de e-mails cheia; alerta não enviado por e-mail")

    def _mailer(self):
        """Thread consumidora: envia os e-mails da fila, com nova tentativa."""
        while True:
            alert = self._outbox.get()
            if not SMTP_HOST:
                continue
            msg = EmailMessage()
            msg["From"] = ALERT_FROM
            msg["To"] = ALERT_TO
            msg["Subject"] = f"[LANWatch] {alert['level']} — {alert['host']}: {alert['text']}"
            msg.set_content(
                f"Máquina: {alert['host']}\n"
                f"Nível:   {alert['level']}\n"
                f"Evento:  {alert['text']}\n"
                f"Horário: {time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(alert['ts']))}\n"
            )
            for attempt in range(1, 4):
                try:
                    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5) as smtp:
                        smtp.send_message(msg)
                    log.info("e-mail de alerta enviado para %s (%s)", ALERT_TO, alert["host"])
                    break
                except (OSError, smtplib.SMTPException) as exc:
                    log.warning("falha SMTP (tentativa %d/3): %s", attempt, exc)
                    time.sleep(2 * attempt)
