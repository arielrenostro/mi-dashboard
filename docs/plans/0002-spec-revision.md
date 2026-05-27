# 0002 - Especificação Técnica Final

## Objetivo

Especificação técnica detalhada para as refatorações do dashboard de telemetria automotiva. Define arquitetura alvo, contratos entre camadas, tabela de eventos, estrutura de Signal, fluxo de dados e ordem de implementação. Documento deve ser completo o suficiente para guiar implementação via LLM (VibeCoding).

---

## 1. Visão Geral da Arquitetura Alvo

```
EcuSession (Transport + Protocol + Threads internas)
    │
    ├── EcuTransport (ABC)
    │       ├── SerialTransport  (pyserial)
    │       └── MockTransport    (replay CSV simulando protocolo request/reply)
    │
    ├── Handshake: síncrono e simples (connect → ECU_INFO → fetch_breakpoints → fetch_ve → start_streaming)
    │
    ├── Pós-handshake — Thread de leitura (Reader):
    │       └── loop contínuo: readline() → publica ECU_MESS_FRAME ou ECU_COMMAND_RESPONSE no bus
    │
    ├── Pós-handshake — Write (dois modos):
    │       ├── Blocking (request/response): enfileira e aguarda resposta correspondente
    │       └── Fire-and-forget: enfileira e retorna; resposta chega via ECU_COMMAND_RESPONSE no bus
    │
    └── Eventos emitidos no bus:
            ├── ECU_MESS_FRAME            (D01, D02, D03 — um evento por frame)
            ├── ECU_COMMAND_SENT          (qualquer comando enviado)
            ├── ECU_COMMAND_RESPONSE      (qualquer resposta exceto frames de medição)
            └── ECU_CONNECTION_STATUS_CHANGED

EventBus (broker central — todos os eventos exceto internos às telas)
    │
    ├── ECU_MESS_FRAME      → SignalProcessor (processa frame individualmente)
    │                       → LogWriter (bufferiza D01+D02, grava quando par completo)
    │
    ├── SIGNALS_RECEIVED    → VehicleState.update() (via lambda em main.py)
    │                       → AlarmProcessor
    │                       → DashboardScreen (apenas quando ativa)
    │
    ├── ALARM_FIRED         → DashboardScreen (apenas quando ativa)
    │
    ├── ECU_COMMAND_REQUESTED → EcuSession (assina e executa send_command)
    │
    ├── ECU_COMMAND_SENT    → (reservado para uso futuro / LambdaLoopStateProcessor desativado)
    │
    ├── VEHICLE_STATE_CHANGED → VeCalibrationScreen (via Screen._subscribe em on_activated)
    │
    └── SCREEN_REQUESTED    → AppWindow

VehicleState (singleton thread-safe, fonte de verdade do estado do veículo)
    └── Publica VEHICLE_STATE_CHANGED no bus via import local (sem import circular de módulo)

Regra de eventos UI:
    - Eventos que impactam camadas externas à UI → obrigatoriamente pelo bus
    - Eventos exclusivamente internos à UI (ex.: navegação, animação) → pyqtSignal interno da tela/componente
```

---

## 2. Camada de Comunicação com a ECU

### 2.1 Separação Transport / Session

**Arquivos a criar:**

| Arquivo | Conteúdo |
|---|---|
| `app/ecu_connection/transport.py` | ABC `EcuTransport` |
| `app/ecu_connection/serial_transport.py` | `SerialTransport(EcuTransport)` encapsulando `serial.Serial` |
| `app/ecu_connection/mock_transport.py` | `MockTransport(EcuTransport)` replaying CSV e simulando protocolo |
| `app/ecu_connection/session.py` | `EcuSession`: handshake, threads internas, fila de comandos, publicação no bus |

**Arquivos a modificar:**

| Arquivo | O que muda |
|---|---|
| `app/ecu_connection/__init__.py` | Expor `register_ecu_session()` / `get_ecu_session()`; manter `get_ecu_connection()` como alias temporário durante migração |
| `app/ecu_connection/serial.py` | Extrair lógica de transport para `SerialTransport`; pode ser removido ao final |
| `app/ecu_connection/mock_log.py` | Substituir por `MockTransport`; pode ser removido ao final |
| `app/ecu_connection/thread.py` | Remover — thread internalizada na Session |
| `main.py` | Remover `get_ecu_connection_thread().start()`; instanciar `EcuSession` com Transport |

### 2.2 Interface EcuTransport (ABC)

```python
from abc import ABC, abstractmethod

class EcuTransport(ABC):
    @abstractmethod
    def connect(self) -> None:
        """Abre conexão física (serial ou inicia replay)."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Fecha conexão."""
        ...

    @abstractmethod
    def readline(self) -> str:
        """Leitura bloqueante com timeout configurável. Retorna string sem newline."""
        ...

    @abstractmethod
    def write(self, line: str) -> None:
        """Escreve linha terminada com \n."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        ...
```

### 2.3 Interface EcuSession (pública)

```python
class EcuSession:
    def __init__(self, transport: EcuTransport) -> None: ...

    def start(self) -> None:
        """Inicia threads internas de leitura. Não inicia streaming — aguarda connect()."""
        ...

    def stop(self) -> None:
        """Para threads, fecha transporte."""
        ...

    def get_status(self) -> EcuConnectionStatus: ...

    # Envio genérico — dois modos
    def send_command(
        self,
        cmd: EcuCommand,
        args: list | None = None,
        blocking: bool = False,
    ) -> str | None:
        """
        blocking=False (padrão): enfileira e retorna None imediatamente.
            Resposta chegará via ECU_COMMAND_RESPONSE no bus.
        blocking=True: enfileira e bloqueia até resposta com mesmo prefixo chegar
            ou timeout expirar. Retorna linha de resposta ou None em timeout.
        Timeout: 3 segundos por tentativa. Retentativas: 1 (2 tentativas no total).
        """
        ...

    # Métodos semânticos (chamam send_command internamente)
    def open_loop(self) -> None: ...
    def close_loop(self) -> None: ...
    def fetch_ve(self) -> None: ...
    def fetch_breakpoints(self) -> None: ...
    def fetch_ignition(self) -> None: ...   # aguarda mapeamento completo dos comandos #Ixx
```

### 2.4 Comportamento das Threads Internas

**Handshake (síncrono, antes de iniciar Reader thread):**
```
connect() → transport.connect()
          → ECU_INFO (#D50) — send_command blocking
          → fetch_breakpoints (#I20, #I21) — send_command blocking
          → fetch_ve_map (#F01..#F16) — send_command blocking por linha
          → STREAMING_START (#D01) — send_command blocking
          → publicar ECU_CONNECTION_STATUS_CHANGED(CONNECTED)
          → iniciar Reader thread
```

**Thread de leitura (Reader) — loop contínuo:**
```
linha = transport.readline()
se vazia:
    count_zero += 1
    se count_zero == 3: reconectar
    continuar
count_zero = 0
se linha começa com "#D01", "#D02" ou "#D03":
    extrair frame_id (ex: "D01")
    publicar EcuMessFrameEvent(frame_id=frame_id, line=linha)
senão:
    publicar EcuCommandResponseEvent(line=linha)
    se modo blocking ativo e linha.startswith(prefixo_esperado):
        acordar thread bloqueada com a linha
drenar fila de comandos (fire-and-forget) após cada frame
```

**Reconexão:** ao detectar 3 leituras vazias consecutivas ou exceção de I/O, fechar transporte, publicar `ECU_CONNECTION_STATUS_CHANGED(DISCONNECTED)`, aguardar 1s e tentar `connect()` novamente.

### 2.5 Protocolo de Resposta por Tipo de Comando

| Tipo de comando | Prefixo esperado na resposta | Modo padrão |
|---|---|---|
| ECU_INFO (`#D50`) | `#D50` | blocking |
| RPM/MAP Breakpoints (`#I20`, `#I21`) | `#I20`, `#I21` | blocking |
| Fetch ignição (`#Ixx`) | `#Ixx` (mesmo comando) | blocking |
| VE Row (`#F01`..`#F16`) | `#F01`..`#F16` (mesmo) | blocking |
| STREAMING_START (`#D01`) | `#D01` | blocking |
| LAMBDA_LOOP_OPEN/CLOSE (`#D06`, `#D05`) | `#D06`, `#D05` | fire-and-forget |
| WRITE_ON_MEMORY (`#D04`) | `#D04` | fire-and-forget |

**Timeout e retentativas:** 3 segundos por tentativa; 1 retentativa (total de 2 tentativas). Após falha, logar `WARNING` e prosseguir.

### 2.6 Comandos #Ixx (Fetch de Ignição e Breakpoints)

Os comandos `#Ixx` são análogos aos `#Fxx` de VE:
- `#I20` — RPM Breakpoints (já existe em `EcuCommand`)
- `#I21` — MAP Breakpoints (já existe em `EcuCommand`)
- Linhas do mapa de ignição serão `#I01`..`#I16` (a confirmar com protocolo real da ECU)

Adicionar ao `EcuCommand` em `protocol.py` quando o protocolo for confirmado:
```python
IGN_ROW_1  = ("#I01", "Ignition 1 line")
# ...
IGN_ROW_16 = ("#I16", "Ignition 16 line")
```

### 2.7 MockTransport

O `MockTransport` deve simular o protocolo completo da ECU:
- Durante o handshake, responder `#D50`, `#I20;...`, `#I21;...`, `#F01;...`..`#F16;...`, `#D01` (confirmação de streaming).
- Após handshake, emitir frames `#D01;...` e `#D02;...` com timing baseado nos timestamps do CSV (comportamento atual do `mock_log.py`).
- `write()` no mock deve interpretar o comando e enfileirar a resposta apropriada.

---

## 3. Estrutura de Signal — Separação por Frame

### 3.1 Estrutura Atual (a substituir)

Atualmente cada `Signal` define `"index"` como posição absoluta no frame combinado após o split de `"#D01;v1;...;#D02;v1;..."` por `;`. O `SignalProcessor` acessa `parts[signal.value["index"]]`.

Exemplo do frame combinado após split por `;`:
```
["#D01", v1, v2, v3, ..., "#D02", v1, v2, ...]
  idx 0   1   2   3         ?      ?   ?
```

O prefixo `#D02` ocupa uma posição no array combinado, então os índices dos sinais de D02 precisam levar isso em conta. A posição exata do `#D02` depende do número de campos em D01.

### 3.2 Estrutura Alvo

Cada `Signal` deve declarar explicitamente de qual frame vem e qual é o índice dentro daquele frame (contando a partir de 1, após o prefixo `#Dxx`):

```python
RPM = {
    "name": "RPM",
    "frame": "D01",        # novo campo
    "frame_index": 1,      # novo campo: posição dentro do frame D01, após o prefixo
    # "index": 1,          # campo legado — remover após migração completa do SignalProcessor
    ...
}

CLT = {
    "name": "CLT",
    "frame": "D01",
    "frame_index": 19,
    # "index": 19,
    ...
}
```

**Mapeamento a realizar:** Identificar quais sinais vêm de D01 e quais de D02 consultando o protocolo real ou os logs CSV de mock. Todos os sinais atuais têm índices de 1 a 33 — a fronteira entre D01 e D02 precisa ser determinada com o protocolo da ECU. Enquanto não confirmado, todos os sinais podem ser declarados como `"frame": "D01"` com `"frame_index"` igual ao `"index"` atual (equivalente funcional ao comportamento atual).

### 3.3 Impacto em signal.py

- Adicionar campos `"frame"` e `"frame_index"` em cada entrada do enum `Signal`.
- Manter campo `"index"` temporariamente durante migração do `SignalProcessor` (remover após).
- Sinais `calculated: True` não precisam de `frame`/`frame_index`.

### 3.4 SignalProcessor com buffers por frame

```python
class SignalProcessor(QObject):
    def __init__(self):
        super().__init__()
        self._frame_buffers: dict[str, list[str]] = {}  # "D01" → ["#D01", v1, v2, ...]
        event_bus.subscribe(AppEventType.ECU_MESS_FRAME, self._on_mess_frame)

    def _on_mess_frame(self, event: EcuMessFrameEvent):
        parts = event.line.split(";")
        self._frame_buffers[event.frame_id] = parts

        parsed_data: dict[Signal, ParsedSignal] = {}
        for signal in Signal:
            cfg = signal.value
            if cfg.get("calculated"):
                continue
            frame_id = cfg.get("frame", "D01")
            frame_index = cfg.get("frame_index", cfg.get("index"))
            buf = self._frame_buffers.get(frame_id)
            if buf is None or frame_index >= len(buf):
                continue  # frame ainda não chegou — dado parcial é aceitável
            try:
                raw = buf[frame_index]
                value = cfg["converter"](raw)
                parsed_data[signal] = ParsedSignal(signal, raw, value)
            except Exception:
                continue

        # Processar sinais calculados (dependem de parsed_data)
        for signal in Signal:
            cfg = signal.value
            if not cfg.get("calculated"):
                continue
            try:
                value = cfg["value"](parsed_data)
                parsed_data[signal] = ParsedSignal(signal, value, value)
            except Exception:
                continue

        if parsed_data:
            event_bus.publish(SignalsReceivedEvent(data=parsed_data))
```

---

## 4. Tabela de Eventos — Estado Final

### 4.1 Eventos Existentes (mantidos)

| `AppEventType` | Dataclass | Status | Observação |
|---|---|---|---|
| `SCREEN_REQUESTED` | `ScreenRequestedEvent` | Manter | sem alteração |
| `ECU_COMMAND_REQUESTED` | `EcuCommandRequestedEvent` | Manter | UI → EcuSession |
| `ALARM_FIRED` | `AlarmFiredEvent` | Manter | AlarmProcessor → DashboardScreen |
| `VEHICLE_STATE_CHANGED` | `VehicleStateChangedEvent` | Manter | VehicleState → VeCalibrationScreen |
| `EVENT_MARK_REQUESTED` | `EventMarkRequestedEvent` | Manter comentado | EventMarker fora do escopo |
| `SIGNALS_RECEIVED` | `SignalsReceivedEvent` | Manter | SignalProcessor → VehicleState, AlarmProcessor, DashboardScreen |

### 4.2 Eventos a Criar

| `AppEventType` | Dataclass | Payload | Publicado por | Assinado por |
|---|---|---|---|---|
| `ECU_MESS_FRAME` | `EcuMessFrameEvent` | `frame_id: str`, `line: str` | EcuSession Reader thread | SignalProcessor, LogWriter |
| `ECU_COMMAND_SENT` | `EcuCommandSentEvent` | `command: EcuCommand`, `args: list` | EcuSession | (reservado — LambdaLoopStateProcessor desativado) |
| `ECU_COMMAND_RESPONSE` | `EcuCommandResponseEvent` | `line: str` | EcuSession Reader thread | (reservado — futuro debug/log) |
| `ECU_CONNECTION_STATUS_CHANGED` | `EcuConnectionStatusChangedEvent` | `status: EcuConnectionStatus` | EcuSession | AppWindow (futuro StatusWidget) |

### 4.3 Eventos a Remover

Nenhum evento deve ser removido nesta fase.

### 4.4 Dataclasses dos Novos Eventos

Adicionar em `app/event/app_events.py`:

```python
@dataclass(frozen=True)
class EcuMessFrameEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.ECU_MESS_FRAME, init=False)
    frame_id: str = ""   # "D01", "D02", "D03"
    line: str = ""       # linha completa: "#D01;v1;v2;..."

@dataclass(frozen=True)
class EcuCommandSentEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.ECU_COMMAND_SENT, init=False)
    command: Any = None
    args: Any = None

@dataclass(frozen=True)
class EcuCommandResponseEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.ECU_COMMAND_RESPONSE, init=False)
    line: str = ""

@dataclass(frozen=True)
class EcuConnectionStatusChangedEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.ECU_CONNECTION_STATUS_CHANGED, init=False)
    status: Any = None   # EcuConnectionStatus
```

Adicionar em `app/event/bus.py` — dentro de `_EventBusQObject`:

```python
ecu_mess_frame = pyqtSignal(object)
ecu_command_sent = pyqtSignal(object)
ecu_command_response = pyqtSignal(object)
ecu_connection_status_changed = pyqtSignal(object)
```

E em `_SIGNAL_ATTR`:

```python
AppEventType.ECU_MESS_FRAME: "ecu_mess_frame",
AppEventType.ECU_COMMAND_SENT: "ecu_command_sent",
AppEventType.ECU_COMMAND_RESPONSE: "ecu_command_response",
AppEventType.ECU_CONNECTION_STATUS_CHANGED: "ecu_connection_status_changed",
```

---

## 5. LogWriter — Especificação

### 5.1 Comportamento atual (a remover)

- Recebe linha bruta via `write(line)` conectado a `ecu_connection.emitter`
- Filtra apenas linhas `#D01`
- Escreve linha CSV com timestamp, event flag e campos do frame

### 5.2 Comportamento alvo

- Inscreve-se em `AppEventType.ECU_MESS_FRAME` no próprio `__init__`
- Buffer interno: `_pending: dict[str, str]` — guarda a última linha de cada `frame_id`
- Ao receber `EcuMessFrameEvent`:
  - Armazena `_pending[frame_id] = line`
  - Se ambos `D01` e `D02` presentes no buffer:
    - Monta campos CSV: `[timestamp, event_flag] + D01_fields + D02_fields`
    - Envia para Worker thread via `self.task.emit(...)` (sem alteração na Worker)
    - Limpa `_pending`
- `set_event_pending()` e flag `_event_pending` continuam funcionando sem alteração
- **Opcional:** inscrever-se em `EVENT_MARK_REQUESTED` no bus para receber o mark diretamente, ao invés de ser chamado de `main.py`

### 5.3 Arquivos impactados

- `app/log_writer/log_writer.py` — substituir método `write(line)` por `_on_mess_frame(event: EcuMessFrameEvent)`
- `main.py` — remover `get_ecu_connection().emitter.connect(log_writer.write)`

---

## 6. AlarmProcessor — Especificação

### 6.1 Comportamento atual (a remover)

- `QThread` com loop polling `vehicle_state.is_any_alarm_firing()` a cada 100ms
- Controla play/stop de áudio via `pyqtSignal` com `QueuedConnection` para main thread

### 6.2 Comportamento alvo

- Deixa de ser `QThread`; torna-se `QObject` instanciado na main thread
- Inscreve-se em `AppEventType.SIGNALS_RECEIVED` via bus (já faz isso)
- `process_signals()` permanece com a lógica atual de detecção de alarme e publicação de `AlarmFiredEvent`
- Controle de áudio: `QTimer` com interval 100ms substitui o polling da thread
  - `_update_audio_state()` verifica `vehicle_state.is_any_alarm_firing()`
  - `QMediaPlayer.play()` e `stop()` chamados diretamente (mesmo thread, sem `QueuedConnection`)
- Remove `_play_requested` e `_stop_requested` pyqtSignals intermediários
- Remove `running` flag; `stop()` para apenas o `QTimer`

### 6.3 Arquivos impactados

- `app/alarm/processor.py` — herança muda de `QThread` para `QObject`; substituir loop de thread por `QTimer`
- `main.py` — remover `alarm_processor.start()` de thread; chamar `alarm_processor.setup()` ou iniciar o QTimer diretamente

---

## 7. VehicleState — Especificação

### 7.1 Mudanças necessárias

- Remover `_VehicleStateEmitter` e `vehicle_state.emitter`
- `set_rpm_breakpoints`, `set_map_breakpoints`, `set_ve_map` devem publicar `VehicleStateChangedEvent` via `event_bus`
- Import circular resolvido com import local:
  ```python
  def set_rpm_breakpoints(self, breakpoints: list) -> None:
      with self._lock:
          self._rpm_breakpoints = breakpoints
      from app.event.bus import event_bus  # import local
      from app.event.app_events import VehicleStateChangedEvent, EventType
      event_bus.publish(VehicleStateChangedEvent(change_type=EventType.RPM_BREAKPOINTS, args=(breakpoints,)))
  ```
- `set_alarm(signal, active, duration_s: float)` deve receber duração configurável
- Estrutura interna de alarmes muda de `_alarm_timestamps: dict[Signal, float]` para `_alarm_timestamps: dict[Signal, tuple[float, float]]` onde `(fired_at, expires_at)`
- `is_alarm_firing(signal)` usa `expires_at` ao invés de `ALARM_DURATION` global
- Remover constante `ALARM_DURATION = 2`

### 7.2 Arquivos impactados

- `app/state/state.py` — modificações conforme 7.1
- `app/ui/ve_calibration/screen.py` — substituir `vehicle_state.emitter.connect(...)` por `self._subscribe(AppEventType.VEHICLE_STATE_CHANGED, self._on_vehicle_state_event)` em `on_activated()`
- `app/state/event.py` — pode ser mantido para `VehicleStateChangeEvent`/`EventType` ou migrado para `app_events.py` (não é bloqueante)

---

## 8. Telas (UI) — Especificação de Adequação

### 8.1 VeCalibrationScreen

**Remover do `__init__`:**
```python
vehicle_state.emitter.connect(self._on_vehicle_state_event)
```

**Adicionar em `on_activated()`:**
```python
self._subscribe(AppEventType.VEHICLE_STATE_CHANGED, self._on_vehicle_state_event)
```

**Teclas O (open loop) e P (close loop) — substituir:**
```python
# De:
get_ecu_connection().send_command(EcuCommand.LAMBDA_LOOP_OPEN)
# Para:
event_bus.publish(EcuCommandRequestedEvent(command=EcuCommand.LAMBDA_LOOP_OPEN))
```

### 8.2 VeWriteController

**Substituir em `_send_pending_rows()`:**
```python
# De:
get_ecu_connection().send_command(cmd, args)
# Para:
event_bus.publish(EcuCommandRequestedEvent(command=cmd, args=args))
```

### 8.3 AppWindow

- Remover parâmetro `signal_processor: SignalProcessor` do construtor
- Atualizar `main.py` para não passar `signal_processor`

### 8.4 DashboardScreen

- Sem mudanças necessárias — já usa bus corretamente

### 8.5 HomeScreen

- Sem mudanças necessárias

---

## 9. LambdaLoopStateProcessor e StateProcessorRegister

**Decisão confirmada pelo usuário:** `StateProcessorRegister` e `LambdaLoopStateProcessor` foram intencionalmente desativados. Manter no estado atual — não refatorar, não ativar, não remover. Fora do escopo desta refatoração.

---

## 10. main.py — Especificação do Estado Final

```python
def main():
    setup_logging()
    app = QApplication(sys.argv)

    # Inicialização do Transport e Session de comunicação
    if config.connection.mock != '':
        transport = MockTransport(config.connection.mock)
    else:
        transport = SerialTransport(config.connection.port, config.connection.baudrate)
    ecu_session = EcuSession(transport)
    register_ecu_session(ecu_session)

    # Processadores de dados (cada um se inscreve no bus no próprio __init__)
    signal_processor = SignalProcessor()
    log_writer = LogWriter(log_file=_get_log_file_path())
    alarm_processor = AlarmProcessor(config.alarm.sound)
    # LambdaLoopStateProcessor: desativado intencionalmente, manter comentado

    # Subscrições em main.py (apenas as sem dono natural)
    event_bus.subscribe(AppEventType.SIGNALS_RECEIVED, lambda e: vehicle_state.update(e.data))
    event_bus.subscribe(AppEventType.ECU_COMMAND_REQUESTED, lambda e: ecu_session.send_command(e.command, e.args))

    # Keyboard actions
    key_hold_detector = KeyHoldDetector(Qt.Key.Key_Space, hold_ms=2000)
    lambda_toggle = LambdaToggle(config.ve_calibration)
    # event_marker = EventMarker(...)  # desativado intencionalmente

    # UI
    app_window = AppWindow()   # sem parâmetro signal_processor
    app_window.key_event.connect(key_hold_detector.on_key_pressed)
    app_window.key_released.connect(key_hold_detector.on_key_released)
    key_hold_detector.triggered.connect(lambda_toggle.handle_trigger)
    app_window.show()

    # Iniciar comunicação
    ecu_session.start()   # inicia handshake e Reader thread

    app.exec()

    app_window.close()
    alarm_processor.stop()
    ecu_session.stop()
```

---

## 11. Fluxo de Dados Completo

```
[ Porta Serial / CSV ]
        │ readline()
        ▼
  EcuSession.Reader (threading.Thread)
        │
        ├── linha "#D01;..." → EcuMessFrameEvent(frame_id="D01", line="...")  ──► bus
        ├── linha "#D02;..." → EcuMessFrameEvent(frame_id="D02", line="...")  ──► bus
        └── outra linha      → EcuCommandResponseEvent(line="...")            ──► bus
                                    │
                         (se blocking ativo: acorda thread bloqueada)

bus.ECU_MESS_FRAME
        │
        ├──► SignalProcessor._on_mess_frame(event)
        │         │ atualiza _frame_buffers[frame_id]
        │         │ processa sinais com frame/frame_index
        │         └── publica SignalsReceivedEvent(data={Signal: ParsedSignal}) ──► bus
        │
        └──► LogWriter._on_mess_frame(event)
                  │ acumula _pending[frame_id]
                  └── quando D01 + D02 presentes: grava CSV via Worker thread

bus.SIGNALS_RECEIVED
        │
        ├──► vehicle_state.update(data)        (snapshot thread-safe)
        ├──► AlarmProcessor.process_signals()  (detecta limites; publica ALARM_FIRED)
        └──► DashboardScreen.on_signal_received() (apenas quando ativa)

bus.ALARM_FIRED
        └──► DashboardScreen.fire_field_alarm() (apenas quando ativa)

AlarmProcessor.QTimer (100ms, main thread)
        └── _update_audio_state() → QMediaPlayer.play() / stop()

[ UI — VeCalibrationScreen ]
        │ tecla ↑/↓ → adjustVE() → VeWriteController.on_adjustment_made()
        │               └── debounce 1s → publica EcuCommandRequestedEvent ──► bus
        │ tecla O/P → publica EcuCommandRequestedEvent ──► bus
        └── on_activated() → _subscribe(VEHICLE_STATE_CHANGED, ...)

bus.ECU_COMMAND_REQUESTED
        └──► ecu_session.send_command(cmd, args)   (lambda em main.py)
                  └── enfileira na _command_queue
                  └── Reader thread drena fila após cada frame

bus.VEHICLE_STATE_CHANGED
        └──► VeCalibrationScreen._on_vehicle_state_event()
```

---

## 12. Mapeamento Completo de Arquivos

### Arquivos a criar

| Arquivo | Conteúdo |
|---|---|
| `app/ecu_connection/transport.py` | ABC `EcuTransport` |
| `app/ecu_connection/serial_transport.py` | `SerialTransport(EcuTransport)` |
| `app/ecu_connection/mock_transport.py` | `MockTransport(EcuTransport)` simulando protocolo |
| `app/ecu_connection/session.py` | `EcuSession` com handshake e threads internas |

### Arquivos a modificar significativamente

| Arquivo | Principais mudanças |
|---|---|
| `app/ecu_connection/__init__.py` | Expor `EcuSession`; alias temporário para `EcuConnection` |
| `app/ecu_connection/serial.py` | Refatorar para usar `SerialTransport`; remover ao final |
| `app/ecu_connection/mock_log.py` | Substituir por `MockTransport`; remover ao final |
| `app/ecu_connection/thread.py` | Remover |
| `app/event/app_events.py` | Adicionar 4 novos eventos (seção 4.4) |
| `app/event/bus.py` | Adicionar 4 novos `pyqtSignal` e entradas em `_SIGNAL_ATTR` |
| `app/masterinjection/signal.py` | Adicionar campos `"frame"` e `"frame_index"` em cada Signal |
| `app/masterinjection/signal_processor.py` | Reescrever: buffer por frame, sem emitter legado |
| `app/masterinjection/protocol.py` | Adicionar comandos `#Ixx` de ignição quando protocolo confirmado |
| `app/log_writer/log_writer.py` | Substituir `write()` por `_on_mess_frame()`; buffer D01+D02 |
| `app/alarm/processor.py` | Migrar de `QThread` para `QObject + QTimer` |
| `app/state/state.py` | Remover emitter próprio; publicar no bus via import local; `set_alarm` com duração |
| `app/state/processors/lambda_loop_state.py` | Manter desativado, sem alteração |
| `app/state/register.py` | Manter desativado, sem alteração |
| `app/ui/ve_calibration/screen.py` | Migrar de `vehicle_state.emitter` para bus; EcuCommandRequestedEvent |
| `app/ui/ve_calibration/ve_write_controller.py` | Publicar `EcuCommandRequestedEvent` ao invés de chamar ECU diretamente |
| `app/ui/window.py` | Remover parâmetro `signal_processor` do construtor |
| `main.py` | Refatorar conforme seção 10 |

### Arquivos a remover (quando refatoração concluída)

| Arquivo | Motivo |
|---|---|
| `app/ecu_connection/thread.py` | Thread internalizada na Session |
| `app/ecu_connection/serial.py` | Substituído por `SerialTransport` + `EcuSession` |
| `app/ecu_connection/mock_log.py` | Substituído por `MockTransport` |

---

## 13. Ordem de Implementação

A ordem abaixo minimiza quebras e permite commits incrementais funcionais:

1. **Eventos novos** — adicionar em `app_events.py` e `bus.py` (não quebra nada; pode ser feito em branch separado)
2. **signal.py** — adicionar campos `"frame"` e `"frame_index"` (backward-compatible se `"index"` for mantido temporariamente)
3. **EcuTransport ABC** — criar `transport.py` (puro, sem dependências do projeto)
4. **SerialTransport** — criar `serial_transport.py` extraindo lógica de `serial.py`
5. **MockTransport** — criar `mock_transport.py` reescrevendo `mock_log.py` com protocolo simulado
6. **EcuSession** — criar `session.py`; atualizar `__init__.py`; manter `EcuConnectionSerial`/`Thread` funcionando em paralelo durante transição
7. **main.py (parcial)** — substituir instanciação de `EcuConnectionThread` por `EcuSession`; testar
8. **SignalProcessor** — migrar para `ECU_MESS_FRAME`; remover emitter legado
9. **LogWriter** — migrar para `ECU_MESS_FRAME`; buffer D01+D02
10. **AlarmProcessor** — migrar de `QThread` para `QObject + QTimer`
11. **VehicleState** — remover emitter próprio; publicar no bus; `set_alarm` com duração
12. **VeCalibrationScreen + VeWriteController** — migrar para bus
13. **AppWindow** — remover parâmetro `signal_processor`
14. **main.py (final)** — limpeza completa conforme seção 10
15. **Remoção de arquivos obsoletos** — `serial.py`, `mock_log.py`, `thread.py`

---

## 14. Riscos Remanescentes

### R1 — Thread affinity do QMediaPlayer

`QMediaPlayer` deve operar na main thread. Com `AlarmProcessor` deixando de ser `QThread`, o `QTimer` opera na main thread por padrão — risco mitigado. **Garantia:** instanciar `AlarmProcessor` após `QApplication()`.

### R2 — Publicação no bus a partir de threads de background

A Reader thread da `EcuSession` publicará eventos via `event_bus.publish()` que usa `pyqtSignal.emit()`. Qt garante entrega via `QueuedConnection` quando emissor e receptor estão em threads diferentes — comportamento já validado no código atual.

### R3 — Fronteira D01/D02 em signal.py

A separação de índices por frame requer conhecimento de qual sinal pertence a qual frame. Enquanto não mapeado completamente, usar `"frame": "D01"` para todos os sinais com `"frame_index"` igual ao `"index"` atual é funcionalmente equivalente ao comportamento atual — seguro para implementação incremental.

### R4 — Import circular VehicleState ↔ EventBus

Resolvido com import local dentro dos métodos que publicam. Alternativa aceita: injetar `event_bus` como parâmetro no construtor de `VehicleState`.

### R5 — MockTransport e fidelidade do protocolo

O mock atual não simula o protocolo request/reply. A reescrita como `MockTransport` requer mapeamento completo das respostas de handshake. Se os dados de VE/breakpoints não estiverem no CSV de replay, o mock precisará de valores fixos hardcoded para responder ao handshake.

### R6 — LambdaLoopStateProcessor e StateProcessorRegister desativados

Confirmado pelo usuário que foram desativados intencionalmente. Não há impacto funcional atual. Manter arquivos sem alteração.

### R7 — Modo blocking vs. fire-and-forget na EcuSession

O modo blocking deve usar sincronização via `threading.Event` ou `queue.Queue` entre a Reader thread e o chamador. Cuidado com deadlock se o chamador for a própria Reader thread. A chamada blocking deve sempre ocorrer fora da Reader thread (ex.: durante o handshake, antes da Reader iniciar).
