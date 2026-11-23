"""
web.py — Painel web (HTTP) do LANWatch, feito com Flask.

Rotas:
  GET /                      página do painel (HTML + JS que consulta a API a cada 2 s)
  GET /api/hosts             estado atual de todos os PCs (JSON)
  GET /api/history/<host>    últimos N minutos de um PC (JSON) — para os gráficos
  GET /api/alerts            últimos alertas (JSON)
  GET /health                usado para testar se o serviço HTTP está de pé

O Flask roda numa thread separada do servidor TCP, no mesmo processo, então
lê o mesmo estado em memória (protegido pelos mesmos Locks).
"""

import logging
import time

from flask import Flask, abort, jsonify, render_template, request


def create_app(snapshot_fn, history_fn, alerts_fn):
    app = Flask(__name__)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)  # não poluir o log com cada GET

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/hosts")
    def api_hosts():
        return jsonify({"server_time": time.time(), "hosts": snapshot_fn()})

    @app.get("/api/history/<host>")
    def api_history(host):
        if not (1 <= len(host) <= 32 and all(c.isalnum() or c in "-_" for c in host)):
            abort(400, "host inválido")  # validação de entrada também no HTTP
        minutes = request.args.get("minutes", default=5, type=int)
        minutes = max(1, min(minutes, 60))
        return jsonify(history_fn(host, minutes))

    @app.get("/api/alerts")
    def api_alerts():
        return jsonify(alerts_fn())

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app
