# 0001 — Revisão de Requisitos (Request Revision)

Análise interna dos requisitos propostos nas três seções. Identifica contradições,
ambiguidades e dependências entre seções antes de confrontar com o código.

---

## Seção 1 — Comunicação com ECU

### Requisitos listados

1. Comunicação deve ser **async**.
2. Read e Write devem acontecer **em paralelo**.
3. Leituras devem gerar **eventos no Bus**.
4. Separar **camada de transporte** da **camada de protocolo/session**.
5. Session deve expor métodos de negócio (`open_loop`, `close_loop`, `fetch_ve`, `fetch_ignition`, etc.).
6. A **thread deve ser internalizada na Session** — não instanciada externamente.
7. Comandos e respostas devem estar **estruturados no projeto**.
8. Emitir `ECU_COMMAND_SEND` para qualquer comando enviado.
9. Emitir `ECU_COMMAND_RESPONSE` para qualquer resposta, exceto `MESS_FRAME`.
10. Emitir `ECU_MESS_FRAME` para cada D01/D02/D03 recebido, **individualmente**.
11. Todo envio de comando deve **aguardar resposta** da ECU com o mesmo código do comando.
12. Para comandos que **definem dados** na ECU (ex.: VE): aguardar resposta com mesmo comando + args.
13. Para comandos que **leem dados** da ECU (ex.: fetch VE): aguardar resposta com comando + args.
14. Para comandos que **definem estado** na ECU (ex.: open loop): aguardar resposta com mesmo comando, sem args.

### Análise interna — Seção 1

**[AMBIGUITY-1.1]** "Async" não está definido em termos de tecnologia:
- Pode significar `asyncio`, threads separadas para read/write, ou simplesmente que
  o caller não bloqueia (fire-and-forget via fila).
- O requisito 2 (read e write em paralelo) sugere duas threads ou um loop de evento.
- O requisito 11 (aguardar resposta) implica bloqueio no lado da session. Se a session
  tem somente uma thread, read e write não podem ser realmente paralelos durante
  o `send_and_wait`. Precisa de esclarecimento sobre como o "paralelo" se manifesta
  durante a fase de request/response.

**[AMBIGUITY-1.2]** Requisito 10 diz que `ECU_MESS_FRAME` deve ser emitido para cada frame
D01/D02/D03 **independentemente** (um por recebimento). Requisito 9 diz que `ECU_COMMAND_RESPONSE`
cobre **qualquer resposta exceto MESS_FRAME**. Não fica claro:
- O D03 existe no protocolo real? `EcuResponse.MESS_DATA_3` existe no código mas nunca
  é emitido individualmente no `run()` atual.
- Se D01 e D02 chegam separados, cada um gera um `ECU_MESS_FRAME` individual. Isso
  implica que `SignalProcessor` (Seção 2) precisa processar frames parciais.

**[CONTRADICTION-1.1]** Requisito 11 diz que "todo envio de comando deve esperar por uma resposta".
Mas o requisito 3 diz que "leituras devem gerar eventos no Bus". Se a session bloqueia esperando
resposta, ela não pode continuar lendo e emitindo `ECU_MESS_FRAME` simultaneamente — a menos
que read e write sejam em threads separadas (requisito 2). A resolução natural é duas threads,
mas isso aumenta complexidade de sincronização e não está explicitado.

**[AMBIGUITY-1.3]** Requisito 12 e 13 são quase idênticos ("definir dados" vs. "ler dados",
ambos esperam resposta com comando + args). A diferença real de comportamento não está clara;
pode ser apenas documentação de casos de uso distintos do mesmo mecanismo de confirmação.

**[MISSING-1.1]** Não há menção ao que fazer em caso de **timeout** ao aguardar resposta.
O código atual tem retry (a cada 3 tentativas reenvia o comando). O novo design deve
especificar: timeout, número de retries, comportamento em caso de falha definitiva.

**[MISSING-1.2]** Não está especificado como o **handshake de conexão** (`ECU_INFO`, fetch
breakpoints, fetch VE map, start streaming) se encaixa nos novos métodos de session.
Os métodos `fetch_ve`, `fetch_ignition` sugeridos parecem ser de demanda, mas o handshake
atual ocorre na conexão. Precisa definir se o handshake é responsabilidade da Session
ou chamado externamente.

**[MISSING-1.3]** A **EcuConnectionMock** precisa de tratamento especial. Atualmente ela
simula breakpoints e VE map diretamente. Com a nova arquitetura de session, a mock
deve simular o protocolo completo de request/response ou haverá caminhos paralelos.

**[DECISION_NEEDED-1.1]** O requisito 6 (thread internalizada na Session) conflita com
o padrão atual onde `EcuConnectionThread(QThread)` é instanciado em `__init__.py`.
Decisão necessária: a Session será um `QThread` ou usará threads Python puras?
Se `QThread`, a Session precisa ser um `QObject`, o que traz restrições de thread affinity.
Se thread Python pura, os sinais para o Bus precisam de mecanismo de cross-thread seguro.

**[DECISION_NEEDED-1.2]** Requisito 5 lista métodos de negócio na Session (`open_loop`,
`close_loop`, `fetch_ve`, `fetch_ignition`). Precisa definir a lista completa de comandos
que terão métodos nomeados vs. os que serão enviados via API genérica.

---

## Seção 2 — Pipeline de dados (EventBus)

### Requisitos listados

1. Todo e qualquer evento deve passar pelo EventBus, **exceto eventos locais de UI**.
2. Telas devem se inscrever no EventBus para receber eventos.
3. Telas devem emitir eventos pelo EventBus para ações que impactem camadas externas à UI.
4. Telas devem emitir eventos "locais" (intra-UI) sem misturar com o restante da aplicação.
5. Revisar eventos atuais (renomear, criar, excluir desnecessários).
6. **LogWriter**: acumular frames 1 e 2, gravar uma linha CSV; timestamp e mark continuam.
7. **SignalProcessor**: inscrever-se no Bus em `ECU_MESS_FRAME`; processar frames individualmente; emitir sinais parciais.
8. **AlarmProcessor**: conversar com VehicleState para popular estado de alertas; não ter thread rodando sem necessidade; tocar áudio apenas quando necessário.

### Análise interna — Seção 2

**[AMBIGUITY-2.1]** "Eventos locais de UI" não estão definidos. Quais eventos são
"locais" vs. "globais"? Exemplo: `SCREEN_REQUESTED` atualmente cruza camadas (UI → AppWindow).
Deveria ser local? A definição precisa ser explicitada por evento.

**[CONTRADICTION-2.1]** Requisito 7 (SignalProcessor processa frames individualmente via
`ECU_MESS_FRAME`) entra em contradição parcial com requisito 6 (LogWriter acumula frames
1 e 2 antes de gravar). Se o Bus emite um evento por frame, ambos os consumidores recebem
eventos individuais. O SignalProcessor pode processar individualmente. O LogWriter precisa
acumular, o que significa que ele precisa manter estado interno (buffer de D01 até D02 chegar).
Isso é viável, mas significa que o LogWriter tem lógica de acumulação — **não há contradição
real** aqui, mas é uma **dependência de ordem implícita**: LogWriter deve guardar D01
até D02 antes de gravar. Porém se D03 também existir, deve LogWriter acumular D01+D02+D03?

**[MISSING-2.1]** O requisito de revisão de eventos (item 5) não especifica quais eventos
devem ser renomeados, criados ou excluídos. Deixa aberto. Os novos eventos (`ECU_COMMAND_SEND`,
`ECU_COMMAND_RESPONSE`, `ECU_MESS_FRAME`) precisam ser adicionados ao Bus. `SIGNALS_RECEIVED`
deve ser mantido, renomeado ou substituído?

**[AMBIGUITY-2.2]** "AlarmProcessor não deve possuir thread rodando sempre sem necessidade".
O AlarmProcessor atual é um `QThread` que roda loop de 100ms para controlar áudio.
O requisito sugere eliminação do thread, mas não especifica o mecanismo alternativo.
Opções: timer Qt, sinal direto do VehicleState quando o estado de alarme muda, ou
reação ao `ALARM_FIRED`. Precisa ser definido.

**[AMBIGUITY-2.3]** "AlarmProcessor deve conversar melhor com VehicleState para popular
o estado dos alertas, permitindo consulta em tempo real". Atualmente o AlarmProcessor
já chama `vehicle_state.set_alarm()` e o VehicleState tem `is_alarm_firing()`. Não fica
claro o que "melhor" significa — talvez o VehicleState deva emitir um evento/sinal quando
o estado de alarme muda, eliminando a necessidade de polling.

**[DECISION_NEEDED-2.1]** O atual `ECU_COMMAND_REQUESTED` é publicado pela UI/LambdaToggle
e consumido em `main.py` para chamar `send_command`. Com a nova Session que tem métodos
de negócio, esse evento ainda é necessário, ou a Session deve ser chamada diretamente?
Se a Session tiver métodos nomeados, o evento pode virar um intermediário desnecessário.

**[DECISION_NEEDED-2.2]** O `VehicleStateChangedEvent` atual usa o sistema interno
`vehicle_state.emitter` (pyqtSignal direto no VehicleState, fora do EventBus). Deve
ser migrado para o EventBus? Se sim, o VEHICLE_STATE_CHANGED precisa chegar ao Bus.

---

## Seção 3 — VehicleState

### Requisitos listados

1. Deve ser **desacoplado da tela** e controlar seu próprio estado independentemente.
2. Deve representar o estado atual do veículo, expondo: últimos sinais, estado de alerta,
   estado de lambda loop etc.

### Análise interna — Seção 3

**[AMBIGUITY-3.1]** "Desacoplado da tela" — atualmente o VehicleState tem um `emitter`
pyqtSignal que é conectado diretamente em `VeCalibrationScreen._on_vehicle_state_event`.
O desacoplamento exige que o VehicleState emita via EventBus, não via sinal direto.

**[MISSING-3.1]** O requisito não especifica se VehicleState deve ser **reativo** (emitindo
eventos quando estado muda) ou apenas **consultável** (estado passivo lido por quem precisar).
Atualmente é misto: emite sinais para breakpoints/VE map, mas é consultado por polling
para sinais e alarmes. O novo design deve definir qual modelo predomina.

**[MISSING-3.2]** Não há especificação sobre o que acontece com o `ALARM_DURATION` hardcoded
em `state.py`. O AlarmProcessor define o `until` e o VehicleState usa ALARM_DURATION=2s para
`is_alarm_firing()`. Há duplicidade de lógica de duração — AlarmProcessor calcula `until`,
VehicleState recalcula baseado em timestamp. O requisito de "conversar melhor com VehicleState"
deveria resolver isso, mas não especifica como.

---

## Análise de Interdependências entre Seções

### ECU ↔ Pipeline

- A Seção 1 introduz três novos eventos (`ECU_COMMAND_SEND`, `ECU_COMMAND_RESPONSE`, `ECU_MESS_FRAME`).
  A Seção 2 consome `ECU_MESS_FRAME` no SignalProcessor e LogWriter.
- **[DEPENDENCY-A]** Se ECU_MESS_FRAME emite D01 e D02 separadamente, o LogWriter (Seção 2)
  precisa acumular ambos antes de gravar. Isso exige que o formato do evento carregue um
  identificador de qual frame é (D01, D02, D03).
- **[DEPENDENCY-B]** O SignalProcessor, ao processar frames individualmente, vai emitir sinais
  parciais. O VehicleState (Seção 3) que faz `update(parsed_data)` deve aceitar atualizações
  parciais sem sobrescrever sinais anteriores com dados ausentes. Atualmente já usa `.update()`
  no dict, portanto funciona parcialmente — mas precisa confirmação explícita.

### ECU ↔ VehicleState

- **[DEPENDENCY-C]** O handshake de conexão (fetch breakpoints, fetch VE) atualmente popula
  o VehicleState diretamente via `vehicle_state.set_map_breakpoints()` etc., **dentro da
  camada de conexão**. Com a nova Session, isso deve continuar ou deve ser feito via evento?
  A Seção 1 não menciona, a Seção 3 exige desacoplamento.

### Pipeline ↔ VehicleState

- **[DEPENDENCY-D]** AlarmProcessor (Seção 2) chama `vehicle_state.set_alarm()`. VehicleState
  (Seção 3) deve expor essa interface. O requisito de "desacoplamento" da Seção 3 não proíbe
  essa chamada direta, mas o requisito de emitir via Bus pode implicar que o AlarmProcessor
  publique um evento e o VehicleState reaja.
- **[DEPENDENCY-E]** LambdaLoopStateProcessor (em `app/state/processors/`) conecta-se ao
  `signal_processor.emitter` e ao `ecu_connection.emitter` via `StateProcessorRegister`.
  Com a nova arquitetura de Bus e Session, esses dois pontos de conexão precisam ser
  reavaliados: o processador deve ouvir eventos do Bus em vez de sinais diretos.

### UI ↔ Tudo

- **[DEPENDENCY-F]** `VeCalibrationScreen` chama `get_ecu_connection().send_command()` diretamente
  (teclas O e P) e `VeWriteController` também chama `get_ecu_connection().send_command()`.
  Com a nova Session e o requisito de "telas emitem eventos pelo EventBus", essas chamadas
  diretas devem ser substituídas por publicação de evento.
- **[DEPENDENCY-G]** `VeCalibrationScreen` conecta-se a `vehicle_state.emitter` diretamente.
  Com o desacoplamento do VehicleState (Seção 3), deve usar o EventBus.

---

## Resumo dos Pontos Abertos

| ID | Tipo | Seção | Descrição curta |
|---|---|---|---|
| AMBIGUITY-1.1 | AMBIGUITY | ECU | "Async" não definido tecnicamente |
| AMBIGUITY-1.2 | AMBIGUITY | ECU | D03 existe no protocolo? ECU_MESS_FRAME individual implica frames parciais |
| CONTRADICTION-1.1 | CONTRADICTION | ECU | "Aguardar resposta" bloqueia read simultâneo sem duas threads |
| AMBIGUITY-1.3 | AMBIGUITY | ECU | Req 12 e 13 parecem idênticos |
| MISSING-1.1 | MISSING | ECU | Timeout e retry ao aguardar resposta não especificados |
| MISSING-1.2 | MISSING | ECU | Handshake de conexão não mapeado para novos métodos de session |
| MISSING-1.3 | MISSING | ECU | EcuConnectionMock não abordada na nova arquitetura |
| DECISION_NEEDED-1.1 | DECISION_NEEDED | ECU | Session: QThread vs. thread Python; thread affinity |
| DECISION_NEEDED-1.2 | DECISION_NEEDED | ECU | Lista completa de métodos nomeados na Session |
| AMBIGUITY-2.1 | AMBIGUITY | Pipeline | "Eventos locais de UI" não definidos por evento |
| CONTRADICTION-2.1 | CONTRADICTION | Pipeline | LogWriter acumula frames vs. SignalProcessor processa individualmente — implica estado em LogWriter |
| MISSING-2.1 | MISSING | Pipeline | Lista de eventos a renomear/criar/excluir não fornecida |
| AMBIGUITY-2.2 | AMBIGUITY | Pipeline | Mecanismo alternativo ao thread do AlarmProcessor não especificado |
| AMBIGUITY-2.3 | AMBIGUITY | Pipeline | "Conversar melhor com VehicleState" não é acionável sem definição |
| DECISION_NEEDED-2.1 | DECISION_NEEDED | Pipeline | ECU_COMMAND_REQUESTED ainda necessário com Session com métodos nomeados? |
| DECISION_NEEDED-2.2 | DECISION_NEEDED | Pipeline | VehicleStateChangedEvent deve migrar para EventBus? |
| AMBIGUITY-3.1 | AMBIGUITY | VehicleState | "Desacoplado da tela" exige migração do emitter para o Bus |
| MISSING-3.1 | MISSING | VehicleState | Modelo reativo vs. consultável não definido |
| MISSING-3.2 | MISSING | VehicleState | Duplicidade ALARM_DURATION em state.py e AlarmProcessor não resolvida |
| DEPENDENCY-A | DEPENDENCY | ECU↔Pipeline | ECU_MESS_FRAME individual requer identificação de frame no payload |
| DEPENDENCY-B | DEPENDENCY | Pipeline↔VehicleState | VehicleState.update() deve aceitar dados parciais explicitamente |
| DEPENDENCY-C | DEPENDENCY | ECU↔VehicleState | Handshake popula VehicleState diretamente — deve ser via evento? |
| DEPENDENCY-D | DEPENDENCY | Pipeline↔VehicleState | AlarmProcessor chama set_alarm() — deve virar evento? |
| DEPENDENCY-E | DEPENDENCY | ECU↔Pipeline | LambdaLoopStateProcessor conecta-se por sinais diretos — deve migrar para Bus |
| DEPENDENCY-F | DEPENDENCY | UI↔ECU | VeCalibrationScreen chama send_command() diretamente — deve usar evento |
| DEPENDENCY-G | DEPENDENCY | UI↔VehicleState | VeCalibrationScreen conecta-se a vehicle_state.emitter diretamente |
