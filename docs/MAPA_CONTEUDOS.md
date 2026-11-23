# LANWatch × conteúdos da disciplina (PSI129A)

Para cada aula: o conceito do slide, onde ele aparece no LANWatch e como provar (comando ou arquivo).
Serve para o documento-resumo, para o vídeo e para a arguição: **todos os três precisam saber responder qualquer linha daqui.**

---

## Aula 02 — LAN

| Conceito do slide | No LANWatch | Como mostrar |
|---|---|---|
| **Switch** encaminha quadros pelo MAC; um conjunto de switches forma **um domínio de broadcast** | A rede `lan` do Docker é uma **bridge Linux**, um switch virtual. Os 6 containers estão na mesma LAN, no mesmo domínio de broadcast | `docker network inspect lanwatch_lan` |
| **Endereço MAC** (48 bits) identifica a NIC | Cada container tem uma interface `eth0` com MAC próprio | `docker exec pc01 ip link show eth0` |
| **"Redes LAN não escalam"**: broadcast chega a todos | Por isso a descoberta usa **multicast** (só os membros do grupo processam) e não broadcast | ver aula 09 |

## Aula 03 — Internetworking (IP, ARP, ICMP, endereçamento)

| Conceito do slide | No LANWatch | Como mostrar |
|---|---|---|
| **Faixa privada** 172.16.0.0 a 172.31.255.255 | Rede **172.28.10.0/24**, dentro da faixa privada | `docker exec collector ip -4 addr show eth0` |
| **CIDR /24**: máscara 255.255.255.0; o primeiro endereço é a rede, o último é o broadcast | Rede = 172.28.10.0 · broadcast = 172.28.10.255 · gateway = .1 · 254 hosts utilizáveis | plano de rede (`CHECKPOINT1.md`, seção 5) |
| **Default gateway** | 172.28.10.1 (a bridge no host), que dá saída para fora da LAN | `docker exec pc01 ip route` |
| **ARP**: tabela IP ↔ MAC em memória | O agente só fala com o coletor depois de resolver o MAC dele | `docker exec pc01 ip neigh` → `172.28.10.10 … lladdr c6:50:… REACHABLE` |
| **ICMP / ping** (echo request/reply) | Teste básico de alcance antes de testar a aplicação | `docker exec pc01 ping -c 3 collector` |
| **IGMP**: controla a entrada e a saída de grupos multicast | O coletor **ingressa** no grupo 239.255.10.10 (`IP_ADD_MEMBERSHIP`) | `docker exec collector ip maddr show dev eth0` → `inet 239.255.10.10` |
| **NAT** | A porta 5000 do host é redirecionada para o container (port forwarding), e é assim que o agente do Windows entra | `docker compose ps` (coluna PORTS) |

## Aula 04 — TCP e UDP

| Conceito do slide | No LANWatch | Como mostrar |
|---|---|---|
| TCP: **orientado à conexão, confiável, entrega ordenada, full duplex** | Métricas e alertas não podem se perder nem chegar fora de ordem → **TCP na porta 5000** | `ss -tnp` mostra as conexões ESTABLISHED |
| Socket = **IP + porta** | `172.28.10.21:41264 → 172.28.10.10:5000` | `ss -tn` |
| Portas **0–1023 só com privilégio** | O coletor roda **sem root**, por isso usa 5000/8080, e o Mailpit usa 1025 em vez da 25 | `ps -o user` mostra `lanwatch` |
| TCP **não faz broadcast nem multicast** | Para a descoberta do coletor, que precisa de multicast, usamos **UDP** | `discovery.py` |
| UDP: sem conexão, sem garantia; se precisar de garantia, a aplicação faz timeout e retransmissão | O agente **repete o DISCOVER** com intervalos crescentes (1 s, 2 s, 4 s) | log do agente: `DISCOVER sem resposta em 1s…` |
| **Flags** SYN, ACK, FIN, RST | Coletor caiu → o agente recebe FIN ("coletor fechou a conexão") ou RST ("connection reset") | `docs/evidencias/T02_*` |

**Frase para a arguição:** "Usamos os dois. TCP para as métricas, porque precisamos de entrega confiável e ordenada, e a conexão persistente ainda serve para detectar o PC offline. UDP para a descoberta, porque multicast só existe no UDP e perder uma sondagem não é grave: a gente repete."

## Aula 05 — API de Sockets

| Conceito do slide | No LANWatch | Onde |
|---|---|---|
| Servidor: `socket → bind → listen → accept`; cliente: `socket → connect` | Exatamente isso, sem framework | `server.py:main()`, `agent.py:session()` |
| **bind em 0.0.0.0** (e não em 127.0.0.1) para aceitar conexões de outras interfaces | `COLLECTOR_BIND=0.0.0.0` | `server.py` |
| **"Protocolo de mensagem"**: o `recv(1024)` pode cortar ou juntar mensagens | Mensagem terminada em `\n` (JSON Lines) + buffer na classe `LineReader`. A alternativa do slide seria **enviar o tamanho antes**; escolhemos o delimitador porque o JSON nunca contém `\n` cru e fica legível no tcpdump | `common/protocol.py` |
| Opções de socket: **timeouts** | `settimeout(15)` no coletor (detecta PC travado) e `timeout=5` no agente | `server.py`, `agent.py` |
| Opções de socket: **TCP_NODELAY** | Ligado nos dois lados: as mensagens são pequenas e o ping mede latência, então o Nagle atrasaria | `setsockopt(... TCP_NODELAY, 1)` |
| **SO_REUSEADDR** contra "Address already in use" | Ligado no servidor | `server.py:main()` |
| **TLS com certificado autoassinado** via `ssl` | O coletor gera o certificado com o openssl; o agente confere o certificado e o nome `collector` | `ensure_certificate()`, `docs/evidencias/T10_tls.txt` |
| Troubleshooting **"Connection refused"** | Tratado: o agente loga e tenta de novo com backoff | `T03_conexao_recusada.txt` |
| Ferramentas Windows: `Test-NetConnection`, `Get-NetTCPConnection`, `netstat -ano` | Para o agente rodando no PC real | `Test-NetConnection 127.0.0.1 -Port 5000` |

## Aula 06 — Processos e Threads

| Conceito do slide | No LANWatch |
|---|---|
| **Thread** = fluxo de execução dentro do processo; compartilha memória | O coletor é **um processo com várias threads**: `MainThread` (accept), uma `agent-pcXX` por PC, `status`, `mailer`, `discovery` e `web`. `ps -o nlwp` mostra a contagem |
| **Modelo 1:1** + **GIL** no CPython; o GIL é liberado em E/S | O servidor é **I/O-bound**: passa o tempo em `recv`, então as threads rodam em paralelo de verdade nesse trecho. Por isso threads, e não processos |
| Threads × processos: com threads, **um erro pode afetar todas** | Cada `handle_client` trata as próprias exceções; um agente com defeito derruba só a thread dele (`T05_entrada_invalida.txt`) |
| **Condição de corrida** e exclusão mútua | `hosts_lock` e `db_lock` (`threading.Lock`), `BoundedSemaphore` limitando a 50 agentes |
| **Produtor/consumidor** | Threads dos agentes produzem alertas numa `queue.Queue`; a thread `mailer` consome e envia por SMTP |
| **Criação de processo** (fork + exec) | O coletor cria um **processo filho** para rodar o `openssl` (`subprocess.run`), que gera o certificado |
| **Sinais** | `SIGTERM` tratado: `docker stop` encerra em 0,15 s (`T07_sigterm.txt`) |

## Aula 07 — Protocolos de aplicação

| Conceito do slide | No LANWatch |
|---|---|
| **SNMP: gerente e agente**, com funções de gerenciamento de **falhas** (detecção, isolamento, registro) e de **desempenho** (tempo de resposta) | **É a arquitetura do LANWatch.** O coletor é o *gerente*; cada PC roda um *agente*; o conjunto de métricas (cpu, mem, disk, rtt…) funciona como uma "MIB" simplificada. Falhas: detecção de offline, alerta e registro no log/SQLite. Desempenho: CPU e latência |
| **E-mail: UA, MTA, SMTP** | O coletor age como cliente SMTP (`smtplib`) e entrega ao **Mailpit**, que faz o papel de MTA e caixa de entrada |
| SMTP na porta 25 | Usamos 1025, porque o processo não é root (aula 04: portas < 1024 exigem privilégio) |
| **HTTP**: documento **dinâmico** (gerado pelo servidor a cada pedido) × documento **ativo** (código que roda no cliente) | `/api/hosts` é dinâmico (Flask gera o JSON na hora). O painel é **ativo**: o JavaScript faz `fetch` a cada 2 s |
| **URL** `protocolo://host:porta/path` | `http://localhost:8080/api/history/pc01?minutes=5` |
| **Paradigmas**: Request/Response × Pub/Sub × Streaming | Request/Response: HTTP do painel e ping/pong. Streaming (envio contínuo): as métricas que o agente empurra a cada 2 s |

## Aula 08 — DNS e DHCP

| Conceito do slide | No LANWatch | Como mostrar |
|---|---|---|
| **DNS**: nome → IP; **registro A**; **TTL** do cache | O Docker tem um DNS embutido (127.0.0.11), e `collector` vira um registro A apontando para 172.28.10.10 | `docker exec pc01 dig collector` → `collector. 600 IN A 172.28.10.10` |
| DNS sobre **UDP 53** | Consultas do `dig` / `getent` | `tcpdump -ni eth0 udp port 53` |
| Problema descoberto | Quando o container do coletor para, o registro **some** do DNS do Docker (o nome deixa de resolver) | `T02` do CP1 |
| **DHCP**: concessão dinâmica × **reserva** | Os IPs são **fixos** no compose (equivale a uma reserva de DHCP): o gerente precisa de endereço estável. Os agentes poderiam ser dinâmicos, até porque agora descobrem o coletor sozinhos | `docker-compose.yml` (`ipv4_address`) |

## Aula 09 — Transmissão confiável e descoberta de dispositivos

| Conceito do slide | No LANWatch | Como mostrar |
|---|---|---|
| **Pares inativos**: "o TCP não percebe sozinho a queda do outro lado"; o keepalive padrão do Linux é de 2 horas; o MQTT tem seu próprio Keep Alive | É o nosso **ping/pong a cada 2 s + `settimeout(15)`**: um keep-alive de aplicação. PC congelado é detectado em 15 s, não em 2 h | `docker pause pc03` → OFFLINE (`T06`) |
| **MQTT Last Will**: o broker avisa quando um cliente some | Equivale ao nosso **alerta "PC OFFLINE"** por e-mail | Mailpit |
| **Argumento fim a fim**: o ACK do TCP só garante que o dado chegou ao buffer do SO | O **pong** é a confirmação **da aplicação**: o coletor recebeu, processou e respondeu. Por isso medimos o RTT com ele, e não confiamos só no TCP | `agent.py`: ping/pong |
| **RTO**, **RTT**, **cwnd**; no Linux o RTO mínimo é de 200 ms | Visível por conexão | `docker exec collector ss -ti` → `rto:204 rtt:0.737 cwnd:27` |
| **Backoff exponencial** (RTO dobra; CoAP espera 2, 4, 8, 16 s) | Reconexão do agente: 1 → 2 → 4 → 8 → … → 30 s, com *jitter* | `T03_conexao_recusada.txt` |
| **Algoritmo de Nagle / TCP_NODELAY** | Desligado nos dois lados (ver aula 05) | código |
| **Emular perda/atraso** com `tc qdisc … netem` | O kernel do nosso ambiente não tinha o `sch_netem` → escrevemos o **netsim** (proxy TCP em Python que atrasa os dados) | `P01_netem_indisponivel_no_kernel.txt`, `netsim/netsim.py` |
| **Descoberta**: IP gravado na configuração deixa a arquitetura frágil; descoberta **ativa** por **multicast** 239.255.x.x, **TTL = 1**, resposta em **unicast**, repetir com intervalos crescentes | Implementado igual ao exemplo da aula: o coletor responde no grupo **239.255.10.10:50000/udp**; o agente usa `COLLECTOR_HOST=auto` | `docker logs pc01` → "coletor descoberto em 172.28.10.10" |
| **Riscos da descoberta**: reconhecimento e falsificação; contramedida: TLS | Um coletor falso pode até responder ao DISCOVER, mas é recusado no handshake TLS (o certificado não confere) | `T10_tls.txt` |

## Aula 10 — Sistemas de arquivos e controle de acesso

| Conceito do slide | No LANWatch | Como mostrar |
|---|---|---|
| **Permissões rwx** para dono / grupo / outros | `/data` = **750** (`rwxr-x---`) · `collector.key` = **600** (`rw-------`, só o dono) · `collector.crt` = **644** (`rw-r--r--`, público) | `docker exec collector ls -l /certs` e `ls -ld /data` |
| **Usuários e grupos**, mínimo privilégio | Processos rodam como o usuário `lanwatch` (UID 10001), não root. Os agentes montam os certificados **só para leitura** (`:ro`) | `ps -o user`, `docker-compose.yml` |
| Abertura em modo **append** (`'a'`) | Os logs são abertos em append e **rotacionados** a cada 1 MB, guardando 3 arquivos (`RotatingFileHandler`) | `/data/logs/collector.log*` |
| Arquivo **texto** × **binário** | Log = texto (linhas com `\n`) · `lanwatch.db` (SQLite) = binário | `ls -l /data` |
| **Journaling** | O SQLite usa um *journal* para não corromper o banco se o processo morrer no meio de uma escrita | — |

---

## O que o LANWatch NÃO cobre (e o que dizer se perguntarem)

- **VLAN / Packet Tracer:** não usamos. "Numa LAN house real, separaríamos os PCs de jogo da rede de administração com VLANs."
- **FTP:** não usamos. "O FTP usa duas conexões, controle na 21 e dados na 20; o nosso protocolo usa uma conexão só, como o HTTP."
- **IPv6:** só IPv4. "Para migrar, trocaríamos `AF_INET` por `AF_INET6` e `IP_ADD_MEMBERSHIP` por `IPV6_JOIN_GROUP`, e no IPv6 não existe broadcast."
- **systemd/journalctl:** os serviços são gerenciados pelo Docker (`restart: unless-stopped`) e os logs saem no `docker logs`, que faz o papel do `journalctl`.
