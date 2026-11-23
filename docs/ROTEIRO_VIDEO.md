# LANWatch — Roteiro do vídeo (3 integrantes, máx. 10:00, meta ~9:35)

**Formato:**
- **Abertura e fechamento:** cada um grava, em casa, um vídeo curto falando para a câmera, e eu junto os trechos.
- **Miolo:** gravação da tela do Rafael com a solução rodando de verdade, narrada com a voz de cada um.
- **Montagem:** quem edita sou eu (Claude). Vocês só gravam e me mandam os arquivos.

| Quem | Câmera | Narra |
|---|---|---|
| **Rafael** | Blocos 1 e 6 | Bloco 3 (demo e código), ao vivo enquanto grava a tela |
| **Integrante A** | Blocos 1 e 6 | Blocos 2 (arquitetura) e 5 (segurança) |
| **Integrante B** | Blocos 1 e 6 | Bloco 4 (falhas provocadas) |

Cada um fala cerca de 3 minutos no total e aparece em câmera, o que cumpre a seção 11 do enunciado por completo.

---

## Ordem de produção (importante: a narração vem ANTES da tela)

1. **A e B gravam as narrações no celular** (gravador de voz), um arquivo por bloco, e mandam para o Rafael.
   - Lugar silencioso, celular a uns 20 cm da boca, leitura sem correria.
   - Leiam o texto da seção *Narração* do bloco; as marcações **[2.3]** etc. não são lidas em voz alta.
2. **O Rafael grava a tela ouvindo a narração no fone.** Quando a voz chega em **[2.3]**, ele faz a tomada 2.3. Assim a tela já sai sincronizada com a fala.
   - Blocos 2, 4 e 5: OBS **sem microfone**.
   - Bloco 3: OBS **com microfone**, porque o Rafael narra ao vivo enquanto grava.
3. **Cada um grava em casa os seus dois trechos em câmera**, um da abertura e um do fechamento (detalhes abaixo).
4. **Mandam tudo para mim** com os nomes da *Lista de entrega* e eu devolvo o vídeo pronto.

---

## Como gravar os trechos em câmera (cada um em casa)

- **Celular na HORIZONTAL**, apoiado em algo (pilha de livros, copo, suporte), não na mão. Câmera traseira, se der para se enquadrar, ou a frontal mesmo, em 1080p.
- **Enquadramento:** do peito para cima, olhando para a lente (não para a tela).
- **Luz:** janela ou luminária **na frente** de você, nunca atrás.
- **Som:** quarto fechado, sem ventilador ou TV ligada, celular a cerca de 1 metro.
- **Na hora de gravar:** aperte REC, espere 2 segundos, fale, espere mais 2 segundos e pare. Eu corto as pontas.
- **Se errar:** grave de novo inteiro. Mandem só a melhor versão.
- **Tom:** podem falar de forma natural, com as próprias palavras. Não precisa decorar o texto, só manter a ideia e o tempo.

Na montagem eu coloco uma legenda com o nome de cada um quando ele aparece pela primeira vez.

## Bloco 1 — Abertura em câmera (0:00–0:50) · um trecho de cada, nesta ordem

**Falas (~45 s):**
> **Integrante A (`B1_A.mp4`, ~10 s):** "Oi, eu sou o [nome de A]. Junto com o [nome de B] e o Rafael, a gente fez o LANWatch."
>
> **Integrante B (`B1_B.mp4`, ~20 s):** "Oi, eu sou o [nome de B]. Pensa numa LAN house com uns trinta PCs, que recebe campeonato amador de Valorant e CS. No meio da partida, um PC trava, outro está com o disco cheio, outro com o ping lá em cima. E o dono só fica sabendo quando o jogador reclama."
>
> **Rafael (`B1_R.mp4`, ~20 s):** "Eu sou o Rafael. O LANWatch resolve isso. Cada PC manda o próprio estado, CPU, memória, disco e latência, para um servidor central, que mostra tudo num painel e avisa por e-mail quando algo dá errado. O dono fica sabendo antes do jogador. Bora ver funcionando."

---

## Bloco 2 — Arquitetura e rede (0:50–3:00) · narração **Integrante A**

### Lista de tomadas (Rafael)
| # | Tela | Duração |
|---|---|---|
| 2.1 | Slide/imagem do diagrama (seção 4 do `CHECKPOINT1.md`) | 25 s |
| 2.2 | Tabela do plano de rede (seção 5 do `CHECKPOINT1.md`) | 20 s |
| 2.3 | Terminal: `docker compose ps` | 8 s |
| 2.4 | `docker exec collector ip -4 addr show eth0` | 8 s |
| 2.5 | `docker exec pc01 dig collector` (mostrar a ANSWER SECTION) e depois `docker exec pc01 ip neigh` | 14 s |
| 2.6 | `docker exec collector ss -tnp state established "( sport = :5000 )"` | 12 s |
| 2.7 | Volta ao diagrama (fundo enquanto a explicação do TCP e do UDP) | 30 s |

### Narração Integrante A (~2:05)
> **[2.1]** "A arquitetura é a de gerente e agente, a mesma do SNMP: o coletor é o gerente e cada PC roda um agente. Tudo roda em Docker Compose, numa rede privada, a 172.28.10.0/24, com o gateway no .1. O coletor fica no .10. Os três PCs simulados ficam no .21, .22 e .23. Temos também o Mailpit, um servidor de e-mail de teste, no .30, e o netsim, um simulador de rede ruim que a gente escreveu, no .40.
> **[2.2]** Os agentes falam com o coletor na porta 5000, por TCP com TLS. O painel web fica na porta 8080, e o e-mail usa SMTP na 1025. Ficamos acima da 1024 porque nada roda como root, e as portas baixas exigem privilégio.
> **[2.3 a 2.6]** No terminal dá para ver os containers rodando, o IP do coletor, o DNS interno do Docker devolvendo o registro A de *collector*, a tabela ARP do pc01 com o MAC do coletor, e as três conexões TCP estabelecidas na porta 5000, uma de cada PC. A do pc02 aparece vindo do .40 porque ele passa pelo netsim; já, já a gente mostra o motivo.
> **[2.7]** Escolhemos TCP e não UDP por dois motivos. Primeiro, uma métrica perdida ou fora de ordem gera gráfico errado e alerta falso, e o TCP garante entrega e ordem. Segundo, a própria conexão serve de sinal de vida: se o PC desliga, o servidor recebe o fechamento da conexão; se ele trava, estoura o tempo limite. Com UDP a gente teria que inventar isso. O volume é pequeno, então o custo extra do TCP não pesa.
> Mas o UDP também aparece: é com ele que o agente **descobre** o coletor. Ele manda um DISCOVER para um grupo multicast, e multicast só existe no UDP. Os protocolos de aplicação são três: o nosso, em JSON uma mensagem por linha, HTTP no painel e SMTP nos alertas."

---

## Bloco 3 — Demonstração e código (3:00–6:05) · narração **Rafael** (ao vivo, com o microfone ligado no OBS)

### Lista de tomadas
| # | Tela | Duração |
|---|---|---|
| 3.1 | Terminal: `docker compose logs -f --tail 15 collector` (deixar rolar) | 20 s |
| 3.2 | VS Code `collector/server.py`: o loop do `accept()` em `main()` | 20 s |
| 3.3 | `handle_client`: o `wrap_socket` do TLS, o hello com `hmac.compare_digest`, o `with db_lock` | 35 s |
| 3.4 | `common/protocol.py`: a classe `LineReader` | 25 s |
| 3.5 | `agent/agent.py`: `discover()` (multicast), `collect()` com psutil e o backoff em `main()` | 30 s |
| 3.6 | Navegador em `localhost:8080`: o painel com os 3 PCs | 25 s |
| 3.7 | Aba `pc-real`: rodar o agente do Windows (comando do README) | 15 s |
| 3.8 | Painel com o card novo `pc-rafael` aparecendo | 20 s |

### Narração Rafael (~2:45 de fala + ações) — fale enquanto grava
> **[3.1]** "Esse é o log do coletor. Cada linha é uma métrica que chegou, e entre colchetes aparece a thread que processou: agent-pc01, agent-pc02, e assim por diante.
> **[3.2]** O servidor usa uma thread por agente. A thread principal só fica parada no *accept*, esperando conexão. Quando um PC conecta, ela cria uma thread nova só para ele e volta a esperar. No Python cada thread é uma thread do sistema, no modelo um para um, e o GIL é liberado enquanto a thread espera a rede. Como o servidor passa quase todo o tempo esperando E/S, as threads funcionam bem aqui.
> **[3.3]** Dentro da thread do agente, primeiro acontece o handshake do TLS. Ele é feito aqui, e não no accept, justamente para um cliente lento não travar a thread principal. Depois vem a autenticação: a primeira mensagem tem que ser um *hello* com o token certo, comparado em tempo constante. Na hora de gravar no banco, a thread pega um *lock*, porque várias threads escrevem ao mesmo tempo.
> **[3.4]** Uma coisa importante que a gente aprendeu: o TCP entrega um fluxo de bytes, não mensagens. Um *recv* pode trazer meia mensagem, ou três grudadas. Por isso criamos um protocolo de mensagem: cada mensagem termina com uma quebra de linha, e essa classe vai juntando os bytes num buffer até encontrar a quebra. Também desligamos o algoritmo de Nagle com TCP_NODELAY, porque as mensagens são pequenas e a gente mede latência.
> **[3.5]** No agente, a função *discover* acha o coletor sozinha: manda o DISCOVER para o grupo multicast com TTL 1, para não sair da rede local, e repete com espera crescente, porque o UDP não garante entrega. A função *collect* usa a biblioteca psutil para ler CPU, memória, disco e rede do sistema operacional. Se o servidor cair, o agente não morre: ele espera e tenta de novo, dobrando o tempo de espera a cada falha, até no máximo trinta segundos.
> **[3.6]** Esse é o painel, feito em Flask. Ele roda numa outra thread do mesmo processo, e a página consulta a API a cada dois segundos. Os três PCs simulados mostram valores parecidos porque, dentro do container, o sistema enxerga os números da máquina hospedeira.
> **[3.7]** Por isso a gente roda também um agente numa máquina real: o meu PC, com Windows, fora do Docker. Ele conecta, fecha o TLS conferindo o certificado do coletor…
> **[3.8]** …e aparece no painel com os valores reais da minha máquina."

---

## Bloco 4 — Falhas provocadas (6:05–8:10) · narração **Integrante B**

### Lista de tomadas
| # | Tela | Duração |
|---|---|---|
| 4.1 | Terminal + painel lado a lado. Rodar `docker exec netsim sh -c "echo 60 > /tmp/delay_ms"` | 10 s |
| 4.2 | Painel: latência do pc02 subindo e o card/alerta ficando vermelho | 20 s |
| 4.3 | `localhost:8025` (Mailpit): abrir o e-mail "CRÍTICO — pc02: Latência…" | 12 s |
| 4.4 | Rodar `docker exec netsim sh -c "echo 0 > /tmp/delay_ms"` e mostrar o e-mail "RESOLVIDO" chegando | 15 s |
| 4.5 | `docker pause pc03` e esperar o card ficar OFFLINE (pode acelerar 2× na edição, com o texto "2×") | 25 s |
| 4.6 | Mailpit: e-mail "PC OFFLINE"; depois `docker unpause pc03` | 12 s |
| 4.7 | `docker stop collector`, esperar uns 10 s, `docker logs --tail 8 pc01` (DISCOVER sem resposta + backoff), depois `docker start collector` | 30 s |
| 4.8 | Painel: todos voltando a ficar online | 10 s |

### Narração Integrante B (~1:50 de fala + esperas)
> **[4.1]** "Agora vamos provocar falhas. A primeira é uma rede ruim. O pc02 não fala direto com o servidor: ele passa pelo netsim, um proxy TCP que a gente escreveu em Python, com duas threads por conexão, uma para cada sentido. Com esse comando, ele passa a atrasar sessenta milissegundos em cada sentido.
> **[4.2]** No painel, a latência do pc02 sobe para uns cento e vinte milissegundos, passa do limite de cinquenta e o alerta dispara.
> **[4.3]** E o administrador recebe o e-mail, enviado por SMTP. O envio é feito por uma thread separada, que consome uma fila; se o servidor de e-mail estiver lento, nenhum agente fica esperando.
> **[4.4]** Quando a rede volta ao normal, chega o e-mail de resolvido. O alerta tem histerese: ele não manda e-mail a cada dois segundos, só quando cruza o limite e quando normaliza.
> **[4.5]** Segunda falha: congelamos o pc03, como um Windows travado. A conexão continua aberta, mas não chega mais nada. O TCP sozinho não perceberia isso: o keepalive padrão do Linux leva duas horas. Por isso a gente tem um keep-alive na aplicação, o ping a cada dois segundos. Depois de quinze segundos sem nada, o tempo limite estoura e o PC é marcado como offline. *(fique uns 3 segundos em silêncio aqui)*
> **[4.6]** Chega o e-mail de PC offline. Ao descongelar, ele reconecta sozinho.
> **[4.7]** Terceira falha: derrubamos o próprio servidor. O agente percebe a conexão fechada, volta a procurar o coletor por multicast e, sem resposta, espera cada vez mais antes de tentar de novo: é o backoff exponencial, a mesma ideia do RTO do TCP.
> **[4.8]** Quando o servidor volta, todos os PCs reconectam sozinhos."

---

## Bloco 5 — Monitoramento e segurança (8:10–8:55) · narração **Integrante A**

### Lista de tomadas
| # | Tela | Duração |
|---|---|---|
| 5.1 | `docker exec collector ps -o user,pid,nlwp,cmd -C python` | 10 s |
| 5.1b | `docker exec collector ls -l /certs` e `docker exec collector ls -ld /data` | 10 s |
| 5.1c | `docker exec collector ss -ti state established "( sport = :5000 )"` (destaque o `rto:` e o `rtt:`) | 12 s |
| 5.2 | `docker exec -u root collector tcpdump -i eth0 -nn -A -c 2 "tcp port 5000 and host 172.28.10.21"` | 15 s |

### Narração Integrante A (~40 s)
> **[5.1]** "O processo do coletor roda com o usuário *lanwatch*, sem privilégio de root, e a coluna NLWP mostra quantas threads ele tem naquele momento.
> **[5.1b]** A chave privada do TLS tem permissão 600, só o dono lê; o certificado é 644, porque é público; e a pasta de dados é 750, sem acesso para outros usuários.
> **[5.1c]** E o *ss -ti* mostra o que o kernel sabe de cada conexão TCP: o RTT e o RTO, que está em duzentos milissegundos, o mínimo do Linux.
> **[5.2]** E capturando o tráfego com tcpdump, só aparecem bytes ilegíveis, porque o canal é cifrado com TLS."

---

## Bloco 6 — Fechamento em câmera (8:55–9:35) · um trecho de cada, nesta ordem

Gravem do mesmo jeito do Bloco 1, de preferência logo em seguida e no mesmo lugar.

> **Integrante A (`B6_A.mp4`, ~12 s):** "Um problema que tivemos: o *tc netem*, que simula atraso na rede do Linux, não funcionava no nosso ambiente, porque faltava o módulo no kernel. A solução foi escrever o nosso próprio simulador em Python, o netsim."
>
> **Integrante B (`B6_B.mp4`, ~12 s):** "Outro problema: no primeiro checkpoint, o tcpdump mostrava o token em texto puro. Resolvemos com TLS, com o certificado gerado pelo próprio coletor."
>
> **Rafael (`B6_R.mp4`, ~15 s):** "E o maior aprendizado foi que TCP é fluxo de bytes: sem um delimitador, as mensagens chegam grudadas ou pela metade. O código, as instruções e os testes estão no repositório, no link da descrição. Valeu!"

Depois disso eu coloco um cartão final de 4 segundos com os nomes e o link do repositório.

---

## Gravação da tela (Rafael)

**Preparação, uns 15 minutos antes:**
```powershell
cd lanwatch
docker compose down -v
docker compose up -d --build
docker exec netsim sh -c "echo 0 > /tmp/delay_ms"
docker cp collector:/certs/collector.crt .
```
- **Windows Terminal:** fonte 20 ou maior, com abas `logs`, `comandos` e `pc-real`.
- **Navegador:** zoom de 125%, com abas `localhost:8080` e `localhost:8025`.
- **VS Code:** fonte 18, com `server.py`, `protocol.py` e `agent.py` abertos.
- **Antes de gravar:** "Não perturbe" ligado e notificações fechadas.

**OBS (Configurações → Saída → modo Avançado → Gravação):**
- Formato **MKV**, encoder **NVENC H.264** (sua RTX), controle de taxa **CBR**, **4000 kbps**.
- Em Vídeo: 1920×1080 e 30 fps.
- Isso dá cerca de 30 MB por minuto, o que fica fácil de me mandar.
- Depois de gravar, use Arquivo → *Remux Recordings* para gerar o MP4.

**Ritmo:**
- Comece a gravar, espere 2 segundos e só então dê play na narração do fone.
- Mexa o mouse devagar e, no VS Code, selecione o trecho de que a voz está falando.
- Se errar, pare e grave o bloco inteiro de novo. Não precisa ficar perfeito, eu corto o início e ajusto o fim.

---

## Lista de entrega (mandem aqui no chat)

| Arquivo | O que é |
|---|---|
| `B1_A.mp4`, `B1_B.mp4`, `B1_R.mp4` | abertura em câmera, um de cada |
| `B2_tela.mp4` + `B2_narracao_A.m4a` | arquitetura |
| `B3_tela.mp4` | demo, com a voz do Rafael embutida |
| `B4_tela.mp4` + `B4_narracao_B.m4a` | falhas provocadas |
| `B5_tela.mp4` + `B5_narracao_A.m4a` | segurança |
| `B6_A.mp4`, `B6_B.mp4`, `B6_R.mp4` | fechamento em câmera, um de cada |
| texto no chat | nome completo e matrícula dos três + link do repositório no GitHub |

**Jeito mais fácil:** A e B mandam os arquivos para o Rafael (WhatsApp como *documento*, não como vídeo, senão ele comprime; ou Google Drive). O Rafael junta tudo numa pasta `video-lanwatch` no PC dele e me conecta essa pasta pelo app desktop do Claude, que eu puxo direto. Se preferir, anexe aqui no chat. Se algum arquivo passar do limite de upload, comprima no HandBrake (preset "Fast 1080p30").

**Eu devolvo:** o MP4 final em 1080p, com etiqueta de bloco, legenda "Narração: Nome" em cada trecho de tela, volumes igualados entre as vozes e o cartão final, conferido para ficar abaixo de 10:00. Daí vocês só sobem no YouTube como **Não listado**, testam o link numa janela anônima e colam no documento e no Canvas.

## Declaração de IA (para o documento-resumo)

> "Durante a preparação deste projeto (código, documentação e vídeo), os autores usaram Claude (Anthropic) para apoio no desenvolvimento, depuração, revisão de texto, elaboração do roteiro e edição do vídeo. Após usar essa ferramenta, os autores revisaram e editaram o conteúdo conforme necessário e assumem total responsabilidade pelo conteúdo."
