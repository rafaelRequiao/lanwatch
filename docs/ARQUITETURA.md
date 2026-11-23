# LANWatch — Arquitetura, rede e testes

PSI129A – Conectividade em Sistemas Ciberfísicos · Prof. Luis Gonzaga de Paulo · PUCPR 2026/2
Equipe: Guilherme · Gustavo · Rafael Henrique Requião Borges dos Reis

---

## 1. Tema

**Projeto aplicado nº 9 — Coletor de métricas de servidores**, aplicado a uma **LAN house / arena de e-sports**.

Cada PC roda um **agente Python** que lê CPU, memória, disco, rede e processos do sistema operacional (psutil) e envia esses dados, por **TCP com TLS**, a um **coletor central** multithread. O coletor:
- guarda o histórico em SQLite;
- mostra tudo num **painel web (HTTP)**;
- manda **alertas por e-mail (SMTP)** quando um PC cai, trava ou passa de um limite.

Os agentes **descobrem o coletor sozinhos**, por **multicast UDP**.

## 2. Cenário de uso

**Quem usa:** o administrador de uma LAN house / arena de e-sports com cerca de 30 PCs gamer, que também recebe campeonatos amadores (Valorant, CS2, LoL).

**Problema:** ele só descobre que um PC travou, ficou sem disco ou está com ping alto quando o jogador reclama, às vezes no meio de uma partida de campeonato. Não existe visão central do estado das máquinas.

**Resultado:**
- um painel com o estado de cada PC em tempo real (online/offline, CPU, RAM, disco e latência até o servidor);
- histórico salvo;
- e-mail de alerta quando algo dá errado e quando volta ao normal;

tudo sem depender de serviço externo.

## 3. Alinhamento com os RAs

| RA | Onde aparece no projeto |
|---|---|
| **RA1** – funções do SO (processos, threads, memória, arquivos, permissões) | O agente lê CPU, memória, processos e disco do SO via psutil. O coletor é um processo com várias threads (8 no teste), com `Lock`, semáforo e fila produtor/consumidor, e cria um processo filho (openssl). Permissões `750`/`600`/`644`; processos sem root; tratamento de `SIGTERM`; logs rotativos |
| **RA2** – TCP/IP com sockets | Sockets TCP puros, com protocolo próprio JSON Lines e TLS, um servidor multithread e o agente cliente. Sockets UDP multicast para a descoberta. Escolha de TCP × UDP justificada |
| **RA3** – Linux e protocolos de aplicação | Ambiente Linux em containers com rede e IPs planejados. Diagnóstico com `ip`, `ss`, `ping`, `dig`, `ip neigh`, `tcpdump` e `ps`. HTTP (painel), SMTP (alertas) e DNS (resolução de nomes) |

## 4. Arquitetura

O LANWatch segue o modelo **gerente/agente** (o mesmo do SNMP): o coletor é o *gerente* e cada PC roda um *agente*.

```
            PC com Docker (Windows 11 + Docker Desktop)
 ┌──────────────────────────────────────────────────────────────────┐
 │ rede "lan" (bridge = switch virtual) 172.28.10.0/24, gateway .1  │
 │                                                                  │
 │   ┌────────┐   ┌────────┐   ┌────────┐                           │
 │   │  pc01  │   │  pc02  │   │  pc03  │   agentes (psutil)        │
 │   │  .21   │   │  .22   │   │  .23   │                           │
 │   └───┬────┘   └───┬────┘   └───┬────┘                           │
 │       │       ┌────▼─────┐      │   ① DISCOVER multicast UDP     │
 │       │       │ netsim   │      │      239.255.10.10:50000       │
 │       │       │ .40      │      │   ② métricas: TCP 5000 + TLS   │
 │       │       │ atraso   │      │      hello → ping/pong →       │
 │       │       └────┬─────┘      │      metrics (JSON Lines)      │
 │       └────────────┼────────────┘                                │
 │             ┌──────▼───────────────┐                             │
 │             │ collector  .10       │  thread por agente          │
 │             │ 5000/tcp  ingestão   │  SQLite + logs em /data     │
 │             │ 8080/tcp  painel HTTP│                             │
 │             │ 50000/udp descoberta │──SMTP 1025──► mailpit .30   │
 │             └──────▲───────────────┘               (e-mail)      │
 └────────────────────┼─────────────────────────────────────────────┘
                      │ porta 15000 do PC → 5000 do coletor (NAT)
               agente "pc-rafael" no Windows real, fora do Docker
```

**Componentes**

| Componente | Arquivo | Papel |
|---|---|---|
| Coletor | `collector/server.py` | Servidor TCP+TLS, uma thread por agente, autenticação, validação, SQLite, logs |
| Alertas | `collector/alerts.py` | Regras com histerese; fila + thread que envia e-mail por SMTP |
| Painel | `collector/web.py` + `templates/index.html` | API HTTP (Flask) e página que se atualiza a cada 2 s |
| Descoberta | `collector/discovery.py` | Responde ao DISCOVER multicast com a porta TCP do coletor |
| Agente | `agent/agent.py` | Descobre o coletor, mede o RTT (ping/pong), lê métricas, reconecta com backoff |
| Protocolo | `common/protocol.py` | Delimitação das mensagens (JSON + `\n`) sobre o fluxo de bytes do TCP |
| netsim | `netsim/netsim.py` | Proxy TCP que atrasa os dados para simular rede ruim (falha provocada) |
| Mailpit | imagem `axllent/mailpit` | Servidor SMTP de teste com caixa de entrada web |

## 5. Plano de rede

| Nó | Tipo | SO / imagem | IP / máscara | Gateway | Portas | Função |
|---|---|---|---|---|---|---|
| collector | contêiner | Debian 12 · python:3.12-slim | 172.28.10.10/24 | 172.28.10.1 | 5000/tcp (ingestão TLS), 8080/tcp (painel), 50000/udp (descoberta) | gerente |
| pc01 | contêiner | Debian 12 · python:3.12-slim | 172.28.10.21/24 | 172.28.10.1 | porta efêmera → 5000 | agente |
| pc02 | contêiner | idem | 172.28.10.22/24 | 172.28.10.1 | porta efêmera → netsim:5000 | agente (via rede ruim) |
| pc03 | contêiner | idem | 172.28.10.23/24 | 172.28.10.1 | porta efêmera → 5000 | agente |
| mailpit | contêiner | axllent/mailpit | 172.28.10.30/24 | 172.28.10.1 | 1025/tcp (SMTP), 8025/tcp (web) | servidor de e-mail |
| netsim | contêiner | python:3.12-slim | 172.28.10.40/24 | 172.28.10.1 | 5000/tcp (proxy) | simulador de rede ruim |
| pc-rafael | PC real | Windows 11 | IP do host | — | → localhost:15000 | agente fora do Docker |
| DNS | embutido no Docker | — | 127.0.0.11 | — | 53/udp | resolve `collector` → .10 |

**Endereçamento:**
- Rede **172.28.10.0/24**, dentro da faixa privada 172.16.0.0/12, com máscara 255.255.255.0.
- Endereço de rede .0, broadcast .255, gateway .1, 254 hosts utilizáveis.
- IPs fixos no compose, o equivalente a reservas de DHCP: o gerente precisa de um endereço estável.
- Faixas: `.10–.19` serviços, `.20–.29` agentes, `.30` e-mail, `.40` netsim.

**Portas publicadas no PC:**
- `15000` → ingestão (a 5000 estava reservada pelo Windows/Hyper-V);
- `8080` → painel;
- `8025` → caixa de e-mail.

## 6. Protocolos

### 6.1 Protocolo de aplicação do LANWatch (JSON Lines sobre TCP + TLS)

Cada mensagem é um objeto JSON terminado em `\n`. O `\n` faz a delimitação das mensagens, porque o TCP entrega um **fluxo de bytes**: um `recv()` pode trazer meia mensagem ou várias grudadas.

```
agente                                                   coletor
  │══ handshake TLS 1.3 (o agente confere certificado e nome) ══│
  │── {"type":"hello","host":"pc01","token":"…","version":1} ──►│ valida token (tempo constante)
  │◄── {"type":"welcome","version":1,"server_time":…} ──────────│   ou {"type":"error",…} e fecha
  │── {"type":"ping","t":563.71} ──────────────────────────────►│ a cada 2 s
  │◄── {"type":"pong","t":563.71} ──────────────────────────────│ → o agente calcula o RTT
  │── {"type":"metrics","host":"pc01","ts":…,"cpu":5.8,         │
  │     "mem":7.5,"disk":29.5,"net_tx":…,"net_rx":…,            │ valida tipos e faixas
  │     "procs":1,"rtt_ms":0.33} ──────────────────────────────►│ → SQLite, painel, alertas
```

### 6.2 Descoberta (UDP multicast)

```
agente ── {"type":"discover","host":"pc01"} ──► 239.255.10.10:50000  (TTL = 1)
agente ◄── {"type":"collector","port":5000,"tls":true} ── coletor   (resposta em unicast)
```
O agente usa o **IP de origem** da resposta como endereço do coletor. Sem resposta, ele repete após 1 s, 2 s e 4 s.

### 6.3 Por que TCP nas métricas e UDP na descoberta

**TCP para as métricas:**
- **Confiabilidade e ordem:** uma métrica perdida ou fora de ordem gera gráfico errado e alerta falso.
- **A conexão serve de sinal de vida:** se o PC desliga, chega FIN/RST; se ele trava, o tempo limite de 15 s estoura. Nos dois casos o PC fica OFFLINE na hora. O keepalive do próprio TCP levaria 2 horas, por isso temos o ping/pong na aplicação.
- **Custo pequeno:** cerca de 150 bytes a cada 2 s por PC, numa conexão persistente; o handshake não se repete.

**UDP para a descoberta:**
- **Multicast só existe no UDP.** O TCP é sempre ponto a ponto.
- **Perder uma sondagem não é grave:** o agente repete.

### 6.4 Outros protocolos usados

| Protocolo | Camada | Uso |
|---|---|---|
| HTTP | aplicação | Painel (`/`) e API (`/api/hosts`, `/api/history/<pc>`, `/api/alerts`) |
| SMTP | aplicação | O coletor envia os alertas ao Mailpit (porta 1025; a 25 exigiria root) |
| DNS | aplicação (UDP 53) | O DNS do Docker resolve `collector` → 172.28.10.10 (registro A) |
| TLS 1.3 | entre aplicação e TCP | Cifra o canal agente → coletor |
| IGMP | rede | O coletor ingressa no grupo 239.255.10.10 |
| ARP / ICMP | enlace / rede | Resolução IP → MAC; `ping` |

## 7. Bibliotecas

| Biblioteca | Onde | Para quê |
|---|---|---|
| `socket` | todos | Sockets TCP e UDP de baixo nível (`bind/listen/accept/connect`, `sendto/recvfrom`) |
| `ssl` | coletor, agente | TLS 1.2+; o agente confia só no certificado do coletor |
| `threading`, `queue` | coletor, netsim | Thread por conexão, `Lock`, `BoundedSemaphore`, fila produtor/consumidor |
| `subprocess` | coletor | Processo filho `openssl` que gera o certificado |
| `psutil` | agente | Lê CPU, memória, disco, rede e processos do SO |
| `sqlite3` | coletor | Histórico de métricas em arquivo |
| `json` | todos | Mensagens legíveis |
| `hmac` | coletor | `compare_digest`: comparação do token em tempo constante |
| `smtplib`, `email` | coletor | Envio dos alertas |
| `Flask` | coletor | Painel e API HTTP |
| `logging` | todos | Logs com nome da thread; arquivo rotativo de 1 MB × 3 |
| `signal` | coletor, agente | Encerramento limpo no `SIGTERM` |

## 8. Segurança

| Medida | Como |
|---|---|
| Canal cifrado | TLS 1.3. O certificado é gerado pelo coletor; a chave privada fica com permissão `600`; o agente confere certificado e nome |
| Autenticação | Token compartilhado no `hello`, comparado em tempo constante |
| Mínimo privilégio | Nenhum processo roda como root (usuário `lanwatch`); certificados montados só para leitura nos agentes |
| Permissões | `/data` = `750`, `collector.key` = `600`, `collector.crt` = `644` |
| Validação de entrada | Tipo e faixa de cada campo; linha de no máximo 64 KB; nome de host `[A-Za-z0-9_-]`; também nas rotas HTTP |
| Limite de recursos | No máximo 50 agentes simultâneos (`BoundedSemaphore`) |
| Descoberta | Um coletor falso pode responder ao DISCOVER, mas é recusado no handshake TLS |

## 9. Testes realizados

Saídas completas em `docs/evidencias/`.

| ID | Objetivo | Procedimento | Resultado obtido |
|---|---|---|---|
| T00 | Rede e endereçamento | `ip addr`, `ss -tnp`, `ping`, `getent hosts` | IPs conforme o plano; 3 conexões ESTABLISHED na :5000; ping de 0,06 ms |
| T01 | Vários clientes simultâneos | `docker compose up` | 3 agentes atendidos em paralelo, cada um na sua thread; ~130 métricas por PC gravadas |
| T02 | Servidor fora do ar | `docker stop collector`, esperar, `start` | O agente detecta o fechamento, repete o DISCOVER (1, 2, 4 s) com backoff e reconecta sozinho |
| T03 | Conexão recusada | Agente apontado para uma porta sem servidor | Erro tratado; backoff exponencial até 30 s |
| T04 | Token inválido | Agente com token errado | Coletor loga "AUTENTICAÇÃO RECUSADA" e fecha; o agente espera 30 s |
| T05 | Entrada inválida | `cpu=250`, `cpu="DROP TABLE"` e texto que não é JSON | As métricas inválidas são descartadas com a conexão mantida; o lixo fecha só aquela conexão; os outros agentes não são afetados |
| T06 | PC congelado | `docker pause pc03` | OFFLINE após 15 s + e-mail; volta a ONLINE sozinho após o `unpause` |
| T07 | Encerramento limpo | `docker stop collector` | Encerra em 0,15 s pelo `SIGTERM` (antes levava 10 s, até o SIGKILL) |
| T08 | Formato na rede, sem TLS | `tcpdump -A` na :5000 | JSON e **token legíveis**: motivou a adoção de TLS |
| T09 | Latência alta | netsim com 60 ms por sentido no pc02 | RTT de ~121 ms → alerta CRÍTICO + e-mail; ao normalizar → e-mail RESOLVIDO |
| T10 | TLS | Agente com certificado correto, com certificado falso, e tcpdump | Conecta com TLS 1.3; o certificado falso é recusado; o tcpdump fica ilegível |
| T11 | Diagnóstico | `dig`, `ip neigh`, `ip maddr`, `ss -ti`, `ls -l`, `ps -o nlwp` | Registro A, ARP, grupo multicast, RTO de 204 ms, permissões e 8 threads conferidos |
| T12 | Redescoberta | `docker restart collector` | O agente redescobre o coletor por multicast em ~1 s |

## 10. Problemas encontrados e soluções

| Problema | Causa | Solução |
|---|---|---|
| Token aparecia em texto puro no tcpdump (T08) | O canal não era cifrado | TLS com certificado gerado pelo próprio coletor |
| `tc qdisc … netem` falhou com "qdisc kind is unknown" (P01) | O kernel do ambiente não tinha o módulo `sch_netem` | Escrevemos o **netsim**, um proxy TCP em Python que atrasa os dados |
| Ao parar o coletor, o agente dava erro de DNS | O DNS do Docker remove o nome de um container parado | Tratado como falha temporária; hoje o agente descobre o coletor por multicast |
| `docker stop` levava 10 s | O Python não tratava `SIGTERM` | Tratamento do sinal → encerramento em 0,15 s |
| Porta 5000 recusada no Windows ("forbidden by its access permissions") | O Windows/Hyper-V reserva faixas de portas | Porta publicada mudada para 15000 (dentro do Docker continua 5000) |
| Primeira leitura de CPU sempre 0% | O `psutil.cpu_percent` mede a diferença desde a chamada anterior | Uma leitura de "aquecimento" logo após conectar |
| Uma thread antiga podia marcar como OFFLINE um PC que já tinha reconectado | Corrida entre a conexão velha (em timeout) e a nova | Cada conexão tem um id; só a conexão atual altera o estado |

## 11. Limitações

1. **Métricas de contêiner refletem o host:** dentro do contêiner, `/proc` mostra a CPU e a memória da máquina hospedeira, então pc01–03 mostram valores parecidos (e `procs=1` por causa do PID namespace). Por isso também rodamos um agente no Windows real.
2. **SQLite com um lock global:** basta para cerca de 30 PCs a cada 2 s (~15 escritas/s). Para centenas de PCs seriam necessárias escritas em lote ou outro banco.
3. **A descoberta multicast funciona só dentro da rede do Docker:** o multicast não atravessa o NAT do Docker Desktop, então o agente do Windows usa o endereço configurado (`127.0.0.1:15000`).
4. **O painel não tem login:** numa instalação real, ficaria atrás de autenticação ou acessível só na rede da administração.