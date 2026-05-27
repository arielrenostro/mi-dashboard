# 0002 — Revisão de Especificação vs. Código (Spec Revision)

Confronto de cada requisito proposto com a implementação atual lida dos arquivos.
Organizado por seção. Cada item classifica o estado: ALINHADO, CRIAR, MODIFICAR ou CONFLITO.

---

## Seção 1 — Comunicação com ECU

### Estado atual (lido do código)

| Arquivo | Papel atual |
|---|---|
| `app/ecu_connection/ecu_connection.py` | Classe abstrata `EcuConnection`. Define `send_command`, `run`, `start`, `stop`, `is_connected`, `get_connection_status`. |
| `app/ecu_connection/serial.py` | `EcuConnectionSerial` — lê uma linha por iteração de `run()`, acumula D01+D02, emite string combinada via `self.emitter`. Envia comandos via `_drain_command_queue()` após cada frame completo. |
| `app/ecu_connection/mock_log.py` | `EcuConnectionMock` — replay de CSV; popula VehicleState diretamente; sem protocolo de request/response. |
| `app/ecu_connection/thread.py` | `EcuConnectionThread(QThread)` — chama `ecu_connection.run()` em loop. |
| `app/ecu_connection/__init__.py` | Registry global: `register_ecu_connection`, `get_ecu_connection`, `get_ecu_connection_thread`. |
| `app/masterinjection/protocol.py` | `EcuCommand` e `EcuResponse` enums com todos os comandos definidos. |

**Fluxo de dado atual:**
```
EcuConnectionThread.run() → EcuConnection.run() [loop]
    → emitter.emit(f"{d01};{d02}")           ← string combinada, um evento por par
    → _drain_command_queue()                 ← comandos enviados após frame, sem await
```

---

### Requisito 1 — Comunicação async

**Estado: MODIFICAR**

Atualmente a comunicação não é async: `EcuConnectionThread` roda um loop síncrono
(`while self.running: self.ecu_connection.run()`). A camada de serial é bloqueante
(`serial.readline()` com timeout=1s).

**O que mudar:**
- Introduzir lógica de read/write em paralelo (ver Req 2).
- A natureza "async" no contexto Qt/Python pode ser satisfeita com duas threads
  (uma para read, uma para write/response) dentro da Session.

**[DECISION_NEEDED]** Definir se async = duas threads separadas ou algum mecanismo
de I/O não-bloqueante (ex.: `asyncio`). `asyncio` com PyQt6 é viável via
`qasync` mas traz dependência adicional não presente no `requirements.txt`.

---

### Requisito 2 — Read e Write em paralelo

**Estado: CRIAR**

Atualmente read e write são sequenciais: `run()` lê uma linha, e `_drain_command_queue()`
envia comandos na mesma thread, após o read. Não há paralelismo real.

**O que mudar:**
- Criar thread de leitura e thread de escrita separadas, ou usar mecanismo de I/O assíncrono.
- A thread de escrita deve aguardar a resposta antes de retornar (Req 11), enquanto a
  thread de leitura continua emitindo frames de streaming (`ECU_MESS_FRAME`).

**[CONFLICT]** Se o protocolo serial é half-duplex (único canal físico), read e write
"em paralelo" deve ser interpretado como "logicamente paralelo": durante streaming,
a thread de escrita envia um comando e fica aguardando resposta enquanto a thread de
leitura drena linhas e as classifica (ECU_MESS_FRAME vs. resposta de comando).
Esse modelo exige uma fila de respostas esperadas e sincronização entre threads.

---

### Requisito 3 — Leituras devem gerar eventos no Bus

**Estado: MODIFICAR**

Atualmente `EcuConnectionSerial.run()` emite via `self.emitter` (pyqtSignal de
`EcuConnectionThread`), conectado em `main.py` diretamente ao `signal_processor.process_line`
e `log_writer.write`. Isso não passa pelo EventBus.

**O que mudar:**
- A Session (ou Transport) deve publicar `ECU_MESS_FRAME` no EventBus para cada frame
  D01, D02 (e D03 se existir) recebido individualmente.
- Remover a conexão direta `emitter → signal_processor.process_line` e `emitter → log_writer.write`.
- Adicionar `ECU_MESS_FRAME` ao `AppEventType` e ao EventBus.

**[RISK]** A conexão direta via pyqtSignal é automaticamente cross-thread safe (QueuedConnection).
Migrar para EventBus mantém essa segurança pois o Bus também usa pyqtSignal internamente.

---

### Requisito 4 — Separar camada de transporte da camada de protocolo/session

**Estado: CRIAR**

Atualmente não há separação: `EcuConnectionSerial` mistura transporte (abrir serial, readline)
com protocolo (interpretar prefixos #D01, #D02, #F*, #I*, handshake, retry).

**O que criar:**
- `EcuTransport` (ou `SerialTransport`): responsável apenas por abrir/fechar porta,
  `readline()`, `writeline()`. Sem conhecimento de comandos.
- `EcuSession`: responsável pelo protocolo (handshake, request/response, streaming,
  threading interna). Usa o Transport para I/O.

**[RISK]** A `EcuConnectionMock` precisará de um `MockTransport` equivalente ou
implementar a Session diretamente com comportamento simulado.

---

### Requisito 5 — Session expõe métodos de negócio

**Estado: CRIAR**

Não existe Session. Os métodos privados `_fetch_breakpoints`, `_fetch_ve_map`,
`_start_streaming`, `_start_communication` em `EcuConnectionSerial` são análogos
mas internos ao processo de conexão, não disponíveis externamente.

**O que criar:**
- `EcuSession.open_loop()` → envia `LAMBDA_LOOP_OPEN`, aguarda confirmação.
- `EcuSession.close_loop()` → envia `LAMBDA_LOOP_CLOSE`, aguarda confirmação.
- `EcuSession.fetch_ve(row?)` → envia `VE_ROW_*`, aguarda e retorna dados.
- `EcuSession.fetch_ignition()` → não existe comando no enum atual.
- `EcuSession.fetch_breakpoints()` → envia `MAP_BREAKPOINTS` + `RPM_BREAKPOINTS`.
- `EcuSession.write_ve_row(row, values)` → envia `VE_ROW_*;values`, aguarda eco.

**[MISSING]** `fetch_ignition` é mencionado nos requisitos mas não existe nenhum
`EcuCommand` equivalente no `protocol.py`. Precisa ser definido antes de implementar.

**[DECISION_NEEDED]** O que os métodos retornam? Valor direto (bloqueante), Future,
ou apenas disparam e o resultado vem via evento (`ECU_COMMAND_RESPONSE`)? Se o
requisito 9 (`ECU_COMMAND_RESPONSE`) é o canal de retorno, os métodos são fire-and-forget
e a Session emite o evento com os dados.

---

### Requisito 6 — Thread internalizada na Session

**Estado: MODIFICAR**

Atualmente a thread é `EcuConnectionThread(QThread)` instanciada em
`app/ecu_connection/__init__.py` e iniciada em `main.py`.

**O que mudar:**
- A Session deve iniciar e gerenciar suas próprias threads internamente.
- `get_ecu_connection_thread()` e `EcuConnectionThread` podem ser removidos.
- O registry em `__init__.py` pode ser simplificado para expor apenas a Session.
- `main.py` chamaria `ecu_session.start()` / `ecu_session.stop()`.

**[RISK]** Se a Session for um `QObject` com thread própria (não `QThread`), a afinidade
de thread dos pyqtSignals pode causar problemas. Recomendado: Session usa `threading.Thread`
internamente e publica no EventBus (thread-safe via pyqtSignal do Bus).

---

### Requisito 7 — Comandos e respostas estruturados

**Estado: ALINHADO (parcial)**

`EcuCommand` e `EcuResponse` já existem em `app/masterinjection/protocol.py`.
`EcuCommand` tem `cmd` (string wire) e `description`. `EcuResponse` tem apenas o valor
(prefixo string).

**O que complementar:**
- `EcuResponse` não tem `description` nem associação explícita com `EcuCommand`.
  Para o modelo de request/response, seria útil uma tabela de mapeamento
  `EcuCommand → EcuResponse esperada`.
- LAMBDA_LOOP_OPEN e LAMBDA_LOOP_CLOSE existem em `EcuCommand` mas não há
  `EcuResponse` correspondente para confirmação de estado (Req 14 exige eco sem args).
  **[MISSING]** Faltam entradas em `EcuResponse` para confirmação de LAMBDA_LOOP_OPEN/CLOSE.

---

### Requisitos 8, 9, 10 — Novos eventos ECU_COMMAND_SEND, ECU_COMMAND_RESPONSE, ECU_MESS_FRAME

**Estado: CRIAR**

Nenhum desses eventos existe atualmente.

**O que criar em `app/event/app_events.py`:**
```python
ECU_COMMAND_SEND     → EcuCommandSentEvent(command: EcuCommand, args: Any)
ECU_COMMAND_RESPONSE → EcuCommandResponseEvent(command: EcuCommand, raw_line: str, data: Any)
ECU_MESS_FRAME       → EcuMessFrameEvent(frame_id: str, raw_line: str)
  # frame_id = "D01", "D02", "D03"
```

**O que adicionar em `app/event/bus.py`:**
- Três novos atributos `pyqtSignal` em `_EventBusQObject`.
- Três entradas em `_SIGNAL_ATTR`.

**[RISK]** `ECU_COMMAND_REQUESTED` atual serve para a UI solicitar um comando.
Com os novos eventos, há agora três camadas de eventos relacionados a comandos:
REQUESTED (UI pede), SEND (Session envia), RESPONSE (ECU confirma).
O evento REQUESTED pode ser mantido ou os métodos de Session podem ser chamados diretamente.
Ver DECISION_NEEDED-2.1 do documento 0001.

---

### Requisitos 11, 12, 13, 14 — Protocolo de request/response

**Estado: MODIFICAR**

O método `_send_and_retry` em `EcuConnectionSerial` já implementa request/response,
mas apenas durante o handshake de conexão. Após o `STREAMING_START`, os comandos são
enfileirados e enviados sem await de resposta.

**O que mudar:**
- Generalizar o mecanismo de request/response para todos os comandos durante streaming.
- Distinguir os três casos:
  - **Req 12** (define dados): aguardar eco com mesmo comando + args enviados.
  - **Req 13** (lê dados): aguardar resposta com comando + args (payload da ECU).
  - **Req 14** (define estado): aguardar eco com mesmo comando, sem args.
- A thread de leitura deve identificar linhas como "resposta esperada" vs.
  "frame de streaming" e rotear adequadamente.

**[CONFLICT]** Requisitos 12 e 13 descrevem comportamentos diferentes (definir vs. ler),
mas a mecânica de "aguardar resposta com comando + args" é idêntica. A distinção real
é a **direção do fluxo de dados** (enviado pela ECU nos dados vs. enviado pelo app),
não o mecanismo de confirmação. Isso é um detalhe de implementação, não de protocolo.

---

## Seção 2 — Pipeline de dados (EventBus)

### Estado atual (lido do código)

| Componente | Comportamento atual |
|---|---|
| `SignalProcessor` | Recebe string combinada "D01;...;D02;..." via pyqtSignal direto. Processa apenas se começa com `#D01`. Emite `dict` via `emitter` (legacy) e publica `SignalsReceivedEvent`. |
| `LogWriter` | Recebe string combinada via pyqtSignal direto. Filtra apenas `#D01`. Grava CSV com dados combinados (hardcoded header). |
| `AlarmProcessor` | `QThread` com loop de 100ms verificando `vehicle_state.is_any_alarm_firing()`. Inscreve-se em `SIGNALS_RECEIVED` via Bus para processar alarmes. |
| `LambdaLoopStateProcessor` | Conectado via `StateProcessorRegister` ao `signal_processor.emitter` (legacy dict) e ao `ecu_connection.emitter` (string raw). |
| EventBus | 6 tipos de evento; todos usam pyqtSignal thread-safe. |

---

### Requisito 2.1 — Todo evento pelo EventBus, exceto UI local

**Estado: MODIFICAR**

Há três conexões diretas (fora do Bus) que precisam migrar:
1. `ecu_connection.emitter → signal_processor.process_line` (em `main.py`).
2. `ecu_connection.emitter → log_writer.write` (em `main.py`).
3. `signal_processor.emitter → LambdaLoopStateProcessor.on_signal_received` (em `StateProcessorRegister`).
4. `ecu_connection.emitter → LambdaLoopStateProcessor.on_command_received` (em `StateProcessorRegister`).
5. `vehicle_state.emitter → VeCalibrationScreen._on_vehicle_state_event` (direto, fora do Bus).

**[CONFLICT]** A conexão direta `ecu_connection.emitter` usada em `LambdaLoopStateProcessor.on_command_received`
recebe a string raw da ECU. Após a reestruturação, o processador deveria ouvir
`ECU_COMMAND_RESPONSE` do Bus, não a string raw.

---

### Requisito 2.2-2.4 — Telas usam EventBus corretamente

**Estado: PARCIALMENTE ALINHADO**

- `DashboardScreen`: correto — usa `_subscribe(SIGNALS_RECEIVED)` e `_subscribe(ALARM_FIRED)` no `on_activated()`.
- `HomeScreen`: correto — publica `ScreenRequestedEvent` via Bus na tecla Enter.
- `VeCalibrationScreen`: **incorreto** em dois pontos:
  1. Chama `get_ecu_connection().send_command()` diretamente nas teclas O e P (LAMBDA_LOOP_OPEN/CLOSE).
     Deve publicar evento no Bus.
  2. Conecta-se a `vehicle_state.emitter` diretamente (não via Bus).

**[CONFLICT]** `VeWriteController` (que pertence à camada UI em `app/ui/ve_calibration/`) também
chama `get_ecu_connection().send_command()` diretamente. Deve publicar evento ou chamar
método da Session.

---

### Requisito 2.5 — Revisão dos eventos atuais

**Estado: MODIFICAR (análise detalhada)**

| Evento atual | Análise | Ação sugerida |
|---|---|---|
| `SCREEN_REQUESTED` | Usado por `HomeScreen` (publica) e `AppWindow` (consome). Comportamento de UI puro — poderia ser "local". | MANTER ou reclassificar como local |
| `ECU_COMMAND_REQUESTED` | UI/LambdaToggle publica; `main.py` consome e chama `send_command`. Com Session com métodos nomeados, pode tornar-se desnecessário. | DECISION_NEEDED |
| `ALARM_FIRED` | AlarmProcessor publica; DashboardScreen consome para animar. Correto. | MANTER |
| `VEHICLE_STATE_CHANGED` | Existe no enum mas o `VehicleState` emite via `vehicle_state.emitter` (pyqtSignal fora do Bus). Não está conectado ao Bus de fato. | CONFLITO — migrar para Bus ou remover do enum |
| `EVENT_MARK_REQUESTED` | EventMarker publica; LogWriter consome via `main.py`. EventMarker está comentado em `main.py` (código dead). | REVISAR se ainda necessário |
| `SIGNALS_RECEIVED` | SignalProcessor publica; DashboardScreen, AlarmProcessor, VehicleState (via main.py) consomem. Funciona. | MANTER, renomear para SIGNALS_PROCESSED? |
| `ECU_COMMAND_SEND` | Não existe. Requisito cria. | CRIAR |
| `ECU_COMMAND_RESPONSE` | Não existe. Requisito cria. | CRIAR |
| `ECU_MESS_FRAME` | Não existe. Requisito cria. | CRIAR |

**[CONFLICT]** `VEHICLE_STATE_CHANGED` está declarado em `AppEventType` mas **nunca é publicado
no EventBus**. O `VehicleState` tem seu próprio `_VehicleStateEmitter(QObject)` com pyqtSignal
separado, conectado diretamente em `VeCalibrationScreen`. Isso viola o princípio de "tudo
pelo Bus". Há dois sistemas de eventos paralelos.

**[CONFLICT]** `EventMarker` e a infra de `EventMarkRequestedEvent` estão **comentados em `main.py`**
(linhas 71-75 são comentário). O LogWriter ainda tem `set_event_pending()` e a subscrição existe
em `main.py` (linha 58-59), mas o `EventMarker` que publicaria o evento está desativado.
O sistema de mark funciona parcialmente (subscrição existe, publisher desativado).

---

### Requisito 2.6 — LogWriter: acumular D01 e D02 antes de gravar

**Estado: MODIFICAR**

Atualmente o `LogWriter.write()` recebe a string **combinada** "D01;...;D02;..." diretamente.
Com `ECU_MESS_FRAME` emitindo cada frame individualmente, o LogWriter deve:
1. Inscrever-se em `ECU_MESS_FRAME`.
2. Acumular D01 quando chegar.
3. Ao receber D02 (com D01 em buffer), gravar a linha CSV.
4. Descartar D03 (ou incluir se necessário).

**[RISK]** Se D01 chegar mas D02 não chegar (perda de frame), o buffer do LogWriter
ficará pendente indefinidamente. É necessário um timeout ou política de descarte.

**[CONFLICT]** O header CSV hardcoded em `LogWriter.Worker.__init__` lista campos específicos
de D01 e D02 combinados. Com frames individuais e possível processamento parcial, o header
precisa ser revisado. Além disso, o LogWriter grava os campos raw da ECU (não processados),
portanto a separação em D01/D02 mantém os dados corretos desde que a ordem de colunas seja preservada.

---

### Requisito 2.7 — SignalProcessor: inscrever-se em ECU_MESS_FRAME, processar individualmente

**Estado: MODIFICAR (significativo)**

Atualmente `SignalProcessor.process_line()`:
- Recebe string combinada "D01;...;D02;..." via pyqtSignal direto.
- Filtra apenas linhas que começam com `#D01`.
- Processa todos os sinais de uma vez (D01 e D02 no mesmo parse).

**O que mudar:**
- `SignalProcessor` deve se inscrever em `ECU_MESS_FRAME` via Bus.
- Para frame D01: processar sinais com `index` no range de D01.
- Para frame D02: processar sinais com `index` no range de D02.
- Emitir `SIGNALS_RECEIVED` com o subconjunto de sinais do frame recebido (dado parcial).

**[RISK]** O `Signal` enum usa índices absolutos (1, 2, 3... para D01; e continuação para D02).
Com a string combinada atual, `parts[idx]` funciona diretamente. Com frames separados,
os índices de D02 precisam de um offset ou o Signal enum precisa indicar qual frame pertence
ao índice. Isso é uma mudança significativa em `signal.py`.

**[CONFLICT]** O `Signal.POWER` e `Signal.TORQUE` têm `"calculated": True` e dependem de
sinais de ambos os frames. Se os frames chegam separados, os sinais calculados não podem
ser computados até que os dois frames estejam disponíveis. O SignalProcessor precisaria
de um estado parcial: acumula sinais do D01, recebe D02, computa os calculados, emite tudo.
Isso contradiz o requisito de "processar individualmente" — na prática, os calculados forçam
acumulação mesmo que os dados brutos sejam emitidos parcialmente.

---

### Requisito 2.8 — AlarmProcessor: sem thread permanente, áudio reativo

**Estado: MODIFICAR**

Atualmente `AlarmProcessor` é um `QThread` com:
- Loop de 100ms verificando `vehicle_state.is_any_alarm_firing()`.
- Evento `SIGNALS_RECEIVED` para processar alarmes (na thread Qt/main).

**O que mudar:**
- Eliminar o `QThread` / loop de 100ms.
- A reprodução de áudio deve ser reativa: quando `vehicle_state` muda o estado de alarme,
  o AlarmProcessor deve ser notificado.
- Duas opções:
  1. VehicleState emite evento no Bus quando `set_alarm()` muda de estado → AlarmProcessor
     reage via `on_alarm_state_changed()`.
  2. AlarmProcessor usa `QTimer` no lugar do `QThread` (menos invasivo).

**[RISK]** `QMediaPlayer` e `QAudioOutput` têm afinidade de thread com a main thread.
O loop atual do `QThread` delega `play()`/`stop()` via `QueuedConnection` justamente
por isso. Com `QTimer` (que roda na main thread), a chamada pode ser direta.

**[CONFLICT]** "Deve apenas conseguir tocar um áudio quando necessário" implica que o
AlarmProcessor não deve fazer polling. Mas `_handle_status` (callback de fim de mídia)
atualmente verifica `vehicle_state.is_any_alarm_firing()` para fazer loop de áudio.
Essa verificação continuará sendo necessária — é polling pontual (quando a mídia termina),
não contínuo.

---

## Seção 3 — VehicleState

### Estado atual (lido do código)

`app/state/state.py` — `VehicleState` singleton com:
- `threading.RLock` para thread safety.
- `_signals: dict` — últimos sinais processados.
- `_alarm_timestamps: dict` — timestamp do último alarme por sinal.
- `_lambda_loop_closed: bool`.
- `_rpm_breakpoints`, `_map_breakpoints`, `_ve_map` — dados de mapa da ECU.
- `_VehicleStateEmitter` — QObject com pyqtSignal separado do Bus, emite em `set_rpm_breakpoints`, `set_map_breakpoints`, `set_ve_map`.
- `ALARM_DURATION = 2` hardcoded.

---

### Requisito 3.1 — Desacoplado da tela

**Estado: MODIFICAR**

O acoplamento atual é via `vehicle_state.emitter.connect(...)` em `VeCalibrationScreen.__init__`.
Isso conecta o `_VehicleStateEmitter` diretamente à tela.

**O que mudar:**
- Substituir `_VehicleStateEmitter` por publicação no EventBus.
- Quando `set_rpm_breakpoints`, `set_map_breakpoints`, `set_ve_map` forem chamados,
  publicar `VehicleStateChangedEvent` no EventBus em vez de usar `self.emitter.emit()`.
- `VeCalibrationScreen` deve se inscrever em `VEHICLE_STATE_CHANGED` via Bus (via `_subscribe()`
  no `on_activated()`).

**[RISK]** A mudança é cirúrgica mas requer que `VehicleState` importe o `event_bus`.
Atualmente não o importa (para evitar dependência circular). O VehicleState está em
`app/state/` e o bus em `app/event/`. Não há circularidade estrutural, mas deve-se
verificar se o import de `event_bus` no momento de import do módulo (antes do `QApplication`)
é seguro. O bus instancia `_EventBusQObject(QObject)` no import — requer `QApplication`
existente. Isso pode causar problema se `vehicle_state = VehicleState()` for instanciado
antes de `QApplication`. Verificar ordem de imports em `main.py`.

**[CONFLICT]** `VehicleStateChangedEvent` já existe em `app_events.py` mas nunca é
publicado no Bus (o emitter interno faz o papel). Com a migração, o campo `change_type: Any`
e `args: tuple` devem ser mapeados para os três casos: MAP_BREAKPOINTS, RPM_BREAKPOINTS, FUEL_MAP
(de `app/state/event.py`). Porém, `app/state/event.py` define `EventType` e `VehicleStateChangeEvent`
separados dos `AppEventType` e `VehicleStateChangedEvent` — há dois sistemas de tipos paralelos
para o mesmo conceito.

**[DECISION_NEEDED]** Manter `app/state/event.py` com seu próprio `EventType` ou unificar
com `AppEventType`? Se unificar, MAP_BREAKPOINTS, RPM_BREAKPOINTS e FUEL_MAP entram em
`AppEventType`, o que expande o escopo do Bus para eventos muito granulares de estado.

---

### Requisito 3.2 — Representa estado atual, consulta em tempo real

**Estado: ALINHADO (parcial)**

O VehicleState já expõe:
- `get(signal)` — último valor de um sinal.
- `get_all()` — snapshot de todos os sinais.
- `is_alarm_firing(signal)` — estado de alarme por sinal.
- `is_any_alarm_firing()` — qualquer alarme ativo.
- `is_lambda_loop_closed()` — estado do loop lambda.
- `get_rpm_breakpoints()`, `get_map_breakpoints()`, `get_ve_map()`.

O que está incompleto ou problemático:

**[CONFLICT]** `is_alarm_firing()` e `is_any_alarm_firing()` usam `ALARM_DURATION = 2` hardcoded
em `state.py`. O `AlarmProcessor` calcula `until = now + duration` onde `duration` vem do
`Signal.alarm["duration_s"]` (default 2.0). O `VehicleState.set_alarm(signal, active)` apenas
salva `time.time()` se `active=True` — descarta o `until` calculado pelo AlarmProcessor.
Portanto o VehicleState recalcula a duração usando o valor hardcoded, ignorando o `duration_s`
por sinal. **Isso é um bug real**: sinais com `duration_s` diferente de 2.0 terão duração
incorreta no VehicleState.

**[MISSING]** O VehicleState não expõe o estado de `lambda_loop` baseado nos sinais da ECU
(apenas o `_lambda_loop_closed` booleano controlado pelo `LambdaLoopStateProcessor`). Para
outros consumidores que querem saber o estado real da ECU vs. o estado comandado, não há
distinção.

---

## Riscos e Impactos Globais

### Risco 1 — Indices de Signal enum

**Alto impacto.** O `Signal` enum usa índices absolutos na string combinada D01+D02.
Com frames separados (ECU_MESS_FRAME individual), os índices de D02 precisam de ajuste.
Exemplo: se D01 tem 18 campos e D02 começa no índice 19, ao processar D02 isoladamente
o `parts[19]` não existirá — D02 terá apenas seus próprios campos, indexados de 1.
**Toda a lógica de indexação em `signal.py` deve ser revisada.**

Solução possível: adicionar campo `"frame"` ao Signal enum indicando "D01" ou "D02",
e o offset relativo dentro do frame. O SignalProcessor aplica o offset correto.

### Risco 2 — Dependência circular e ordem de inicialização

**Médio impacto.** Se `VehicleState` importar `event_bus`, e `event_bus` ou qualquer
de seus dependentes importar `vehicle_state`, haverá ciclo. Verificar: `event_bus`
importa apenas `PyQt6` e `app/event/app_events`. Não importa `vehicle_state`.
Portanto a dependência `vehicle_state → event_bus` é segura estruturalmente,
mas requer `QApplication` antes do primeiro import de `event_bus` (que instancia
`_EventBusQObject`). Atualmente `vehicle_state = VehicleState()` ocorre no import
de `app/state/state.py`, que pode acontecer antes do `QApplication()` em `main.py`.
**Risco real de crash na inicialização.**

### Risco 3 — EcuConnectionMock incompatibilidade

**Médio impacto.** A `EcuConnectionMock` não implementa protocolo request/response.
Emite linhas raw do CSV diretamente via `emitter`. Com a nova Session que aguarda
resposta para cada comando, a Mock precisará simular respostas. Atualmente já tem
lógica manual para `MAP_BREAKPOINTS` e `RPM_BREAKPOINTS`. Com a Session, precisará
de um `MockTransport` ou de lógica equivalente completa.

### Risco 4 — LambdaLoopStateProcessor desconexão

**Médio impacto.** `StateProcessorRegister.register()` conecta `signal_processor.emitter`
(sinal legacy dict) e `ecu_connection.emitter` (string raw) ao `LambdaLoopStateProcessor`.
Ambas essas conexões são fora do Bus. Com a reestruturação:
- `on_signal_received` deve vir de `SIGNALS_RECEIVED` do Bus.
- `on_command_received` deve vir de `ECU_COMMAND_RESPONSE` do Bus (quando LAMBDA_LOOP_OPEN/CLOSE
  for confirmado).
O `StateProcessorRegister` pode ser eliminado.

### Risco 5 — AlarmProcessor e thread affinity de QMediaPlayer

**Baixo impacto (já mitigado).** A remoção do `QThread` do AlarmProcessor simplifica
o thread affinity problem. Com `QTimer` na main thread, `player.play()` pode ser chamado
diretamente sem `QueuedConnection`.

### Risco 6 — VeWriteController bypass do Bus

**Baixo impacto.** `VeWriteController` chama `get_ecu_connection().send_command()`.
Após a reestruturação, deve publicar evento no Bus ou chamar método da Session.
Como a `VeWriteController` aguarda confirmação de ECU (via debounce), a mudança é
principalmente de qual canal usa para enviar.

---

## Mapa de Mudanças Necessárias

### CRIAR (novo código)

| Item | Localização sugerida | Notas |
|---|---|---|
| `EcuTransport` (abstract + SerialTransport + MockTransport) | `app/ecu_connection/transport.py` | Apenas I/O de bytes |
| `EcuSession` | `app/ecu_connection/session.py` | Protocolo, threading, request/response |
| `ECU_COMMAND_SEND` event + dataclass | `app/event/app_events.py` | |
| `ECU_COMMAND_RESPONSE` event + dataclass | `app/event/app_events.py` | |
| `ECU_MESS_FRAME` event + dataclass | `app/event/app_events.py` | payload: frame_id, raw_line |
| Métodos nomeados na Session | `EcuSession` | open_loop, close_loop, fetch_ve, etc. |
| EcuResponse para LAMBDA_LOOP_OPEN/CLOSE | `app/masterinjection/protocol.py` | Confirmação de estado |

### MODIFICAR (código existente)

| Item | Localização | O que muda |
|---|---|---|
| `SignalProcessor` | `app/masterinjection/signal_processor.py` | Inscrever em `ECU_MESS_FRAME`; processar por frame; emitir parcial |
| `Signal` enum | `app/masterinjection/signal.py` | Adicionar campo `"frame"` e offset relativo por sinal |
| `LogWriter` | `app/log_writer/log_writer.py` | Inscrever em `ECU_MESS_FRAME`; acumular D01+D02; gravar ao completar |
| `AlarmProcessor` | `app/alarm/processor.py` | Remover QThread; usar QTimer ou reatividade via Bus |
| `VehicleState` | `app/state/state.py` | Substituir `_VehicleStateEmitter` por publicação no EventBus; corrigir bug ALARM_DURATION |
| `VeCalibrationScreen` | `app/ui/ve_calibration/screen.py` | Usar Bus para VEHICLE_STATE_CHANGED; publicar evento para lambda loop |
| `VeWriteController` | `app/ui/ve_calibration/ve_write_controller.py` | Publicar evento ao invés de chamar send_command diretamente |
| `EventBus` | `app/event/bus.py` | Adicionar 3 novos sinais e entradas em `_SIGNAL_ATTR` |
| `main.py` | `main.py` | Remover conexões diretas; instanciar Session; simplificar fiação |
| `LambdaLoopStateProcessor` | `app/state/processors/lambda_loop_state.py` | Inscrever via Bus em SIGNALS_RECEIVED e ECU_COMMAND_RESPONSE |
| `StateProcessorRegister` | `app/state/register.py` | Eliminar ou simplificar (sem mais conexões diretas) |

### AVALIAR REMOÇÃO

| Item | Localização | Motivo |
|---|---|---|
| `EcuConnectionThread` | `app/ecu_connection/thread.py` | Thread passa para a Session |
| `get_ecu_connection_thread()` | `app/ecu_connection/__init__.py` | Desnecessário com Session |
| `app/state/event.py` (EventType + VehicleStateChangeEvent) | `app/state/event.py` | Substituível por AppEventType + VehicleStateChangedEvent do Bus |
| `StateProcessorRegister` | `app/state/register.py` | Conexões migram para Bus |
| `signal_processor.emitter` (legacy dict) | `signal_processor.py` | Substituído por SIGNALS_RECEIVED no Bus |
