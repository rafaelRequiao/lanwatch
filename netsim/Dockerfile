# Simulador de rede ruim (proxy TCP com atraso controlável) — só biblioteca padrão
FROM python:3.12-slim
RUN useradd --system --uid 10003 lanwatch
WORKDIR /app
COPY netsim/ netsim/
USER lanwatch
ENV PYTHONUNBUFFERED=1
CMD ["python", "netsim/netsim.py"]
