# Plano 02 — Pipeline de Dados: EventBus, LogWriter, SignalProcessor, AlarmProcessor

## Objetivo

Reestruturar o pipeline de dados para que:
- A ECU emita frames individuais (D01, D02, D03) como eventos tipados no bus
- O `LogWriter` acumule D01+D02 independentemente antes de gravar CSV
- O `SignalProcessor` processe cada frame individualmente com suporte a sinais parciais
- O `AlarmProcessor` e `VehicleState` compartilhem responsabilidades de alarme de forma clara
- `SIGNALS_RECEIVED` suporte envio parcial de sinais

---

## Visão Geral do Novo Fluxo

```
EcuSession.run()
  ├─ linha #D01/#D02/#D03
  │     └─► event_bus.publish(MessFrameEvent(frame_id, raw_line, parts))
  │               ├──► SignalProcessor._on_mess_frame()
  │               │         └─► vehicle_state.update(parsed_data)
  │               │         └─► event_bus.publish(SignalsReceivedEvent(data))
  │               │                   ├──► AlarmProcessor.process_signals()
  │               │                   │         └─► vehicle_state.set_alarm(signal, active)
  │               │                   │         └─► event_bus.publish(AlarmFiredEvent) [cooldown]
  │               │                   └──► DashboardScreen.on_signal_received() [quando ativa]
  │               └──► LogWriter._on_mess_frame()
  │                         acumula D01 e D02; quando ambos chegam → grava CSV
  └─ outras linhas (#D50, #I20, #F01, ...)
        └─► event_bus.publish(CommandResponseEvent(response_id, raw_line, parts))

AlarmProcessor.run() (poll 100ms)
  └─► vehicle_state.is_any_alarm_firing() → play/stop áudio

EventMarker.handle_key()
  └─► event_bus.publish(LogEventMarkRequestEvent())
            └──► LogWriter._on_mark() → _event_pending = True
```

---

## 1. Novos Eventos no Bus

### 1.1 `AppEventType` — adicionar valores

```python
class AppEventType(Enum):
    ECU_COMMAND_REQUESTED  = auto()
    ALARM_FIRED            = auto()
    LOG_EVENT_MARK_REQUEST = auto()   # renomeado de EVENT_MARK_REQUESTED
    SIGNALS_RECEIVED       = auto()
    MESS_FRAME             = auto()   # NOVO
    COMMAND_RESPONSE       = auto()   # NOVO
    # REMOVIDOS: SCREEN_REQUESTED, VEHICLE_STATE_CHANGED (ver Planos 03 e 04)
```

### 1.2 Dataclasses dos novos eventos

**`app/event/app_events.py`:**

```python
@dataclass(frozen=True)
class MessFrameEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.MESS_FRAME, init=False)
    frame_id: str = ""       # "#D01", "#D02", "#D03"
    raw_line: str = ""
    parts: tuple = field(default_factory=tuple)   # imutável

@dataclass(frozen=True)
class CommandResponseEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.COMMAND_RESPONSE, init=False)
    response_id: str = ""    # "#D50", "#I20", "#F01", etc.
    raw_line: str = ""
    parts: tuple = field(default_factory=tuple)
```

### 1.3 Registrar no `EventBus`

**`app/event/bus.py`:**

```python
_SIGNAL_ATTR = {
    # ... existentes ...
    AppEventType.MESS_FRAME:       "mess_frame",
    AppEventType.COMMAND_RESPONSE: "command_response",
}

class _EventBusQObject(QObject):
    # ...
    mess_frame        = pyqtSignal(object)
    command_response  = pyqtSignal(object)
```

---

## 2. `EcuSession` / `EcuConnectionSerial` — Emitir Frames Individuais

O join manual de D01+D02 é removido. Cada frame é emitido imediatamente como `MessFrameEvent`. Respostas de comando viram `CommandResponseEvent`.

```python
def _handle_line(self, line: str) -> None:
    if line.startswith(("#D01", "#D02", "#D03")):
        frame_id = line[:4]
        event_bus.publish(MessFrameEvent(
            frame_id=frame_id,
            raw_line=line,
            parts=tuple(line.split(";")),
        ))
        if frame_id == "#D01":
            self._drain_command_queue()
    else:
        parts = tuple(line.split(";"))
        event_bus.publish(CommandResponseEvent(
            response_id=parts[0] if parts else "",
            raw_line=line,
            parts=parts,
        ))
        self.emitter.emit(line)     # compatibilidade temporária com StateProcessorRegister
        self._drain_command_queue()
```

**Removidos de `serial.py`:** `self.d01`, `self.d02`, o join `f'{self.d01};{self.d02}'`.

---

## 3. `SignalProcessor` — Processar Frames Individuais

### 3.1 Campo `"frame"` em `signal.py`

Adicionar `"frame": "#D01"` como campo padrão em todos os sinais não calculados:

```python
RPM = {
    "name": "RPM",
    "frame": "#D01",   # novo campo
    "index": 1,
    # ...
}
```

Sinais `calculated: True` não precisam do campo `frame`.

### 3.2 Novo `signal_processor.py`

```python
class SignalProcessor(QObject):
    emitter = Signal(dict)   # mantido para compatibilidade com StateProcessorRegister

    def __init__(self):
        super().__init__()
        self._signals_by_frame: dict[str, list[SignalEnum]] = {}
        self._calculated_signals: list[SignalEnum] = []

        for sig in SignalEnum:
            if sig.value.get("calculated", False):
                self._calculated_signals.append(sig)
            else:
                frame = sig.value.get("frame", "#D01")
                self._signals_by_frame.setdefault(frame, []).append(sig)

        event_bus.subscribe(AppEventType.MESS_FRAME, self._on_mess_frame)

    def _on_mess_frame(self, event: MessFrameEvent):
        frame_signals = self._signals_by_frame.get(event.frame_id, [])
        if not frame_signals:
            return

        parsed_data: dict = {}
        for signal in frame_signals:
            try:
                idx = signal.value["index"]
                if idx >= len(event.parts):
                    continue
                raw = event.parts[idx]
                value = signal.value["converter"](raw)
                parsed_data[signal] = ParsedSignal(signal, raw, value)
            except Exception:
                logger.exception("Erro ao processar sinal %s", signal)

        # Sinais calculados: usa snapshot atual + sinais recém-chegados
        combined = {**vehicle_state.get_all(), **parsed_data}
        for signal in self._calculated_signals:
            try:
                raw = signal.value["value"](combined)
                parsed_data[signal] = ParsedSignal(signal, raw, raw)
            except Exception:
                pass  # dependências ainda não disponíveis

        if parsed_data:
            vehicle_state.update(parsed_data)
            self.emitter.emit(parsed_data)
            event_bus.publish(SignalsReceivedEvent(data=parsed_data))
```

**Ponto-chave:** `SignalsReceivedEvent` agora pode conter apenas um subconjunto de sinais. Todos os subscribers existentes já usam `.get()` e `.items()` — são tolerantes a parcialidade sem mudança.

---

## 4. `LogWriter` — Acumular D01+D02 e Gravar

O `LogWriter` passa a ser 100% orientado a eventos. O método `write(line)` público é removido.

```python
class LogWriter(QObject):
    task = Signal(list)

    def __init__(self, log_file):
        super().__init__()
        self._event_pending = False
        self._pending_d01: Optional[tuple] = None
        self._pending_d02: Optional[tuple] = None

        self.thread = QThread()
        self.worker = Worker(log_file)
        self.worker.moveToThread(self.thread)
        self.task.connect(self.worker.process_task)
        self.thread.start()

        event_bus.subscribe(AppEventType.LOG_EVENT_MARK_REQUEST, self._on_mark)
        event_bus.subscribe(AppEventType.MESS_FRAME, self._on_mess_frame)

    def _on_mark(self, _event):
        self._event_pending = True

    def _on_mess_frame(self, event: MessFrameEvent):
        if event.frame_id == "#D01":
            self._pending_d01 = event.parts
        elif event.frame_id == "#D02":
            self._pending_d02 = event.parts

        if self._pending_d01 and self._pending_d02:
            self._flush()

    def _flush(self):
        timestamp = int(time.time() * 1000)
        event_mark = "MARK" if self._event_pending else ""
        self._event_pending = False
        row = [timestamp, event_mark] + list(self._pending_d01) + list(self._pending_d02)
        self.task.emit(row)
        self._pending_d01 = None
        self._pending_d02 = None
```

**Remover de `main.py`:**
- `ecu_connection_thread.emitter.connect(log_writer.write)`
- Qualquer chamada a `log_writer.set_event_pending()`

---

## 5. `AlarmProcessor` + `VehicleState` — Estado de Alarme

### 5.1 Bug em `VehicleState.set_alarm` (correção obrigatória)

```python
# ATUAL (bugado — nunca remove):
def set_alarm(self, signal, active: bool) -> None:
    if active:
        self._alarm_timestamps[signal] = time.time()

# CORRETO — separar estado booleano de timestamp de cooldown:
def set_alarm(self, signal, active: bool) -> None:
    with self._lock:
        self._alarm_active[signal] = active
        if active:
            self._alarm_last_fired[signal] = time.time()

def is_alarm_firing(self, signal) -> bool:
    with self._lock:
        return self._alarm_active.get(signal, False)

def is_any_alarm_firing(self) -> bool:
    with self._lock:
        return any(self._alarm_active.values())
```

Substituir `_alarm_timestamps: dict` por:
- `_alarm_active: dict[Signal, bool]` — estado atual por sinal
- `_alarm_last_fired: dict[Signal, float]` — para auditoria/cooldown se necessário

### 5.2 Responsabilidades clarificadas

| Componente | Responsabilidade |
|-----------|----------------|
| `AlarmProcessor` | Detectar limites violados; publicar `AlarmFiredEvent` com cooldown; chamar `vehicle_state.set_alarm()` |
| `VehicleState` | Armazenar estado booleano atual de alarme; expor `is_alarm_firing()` e `is_any_alarm_firing()` |
| `DashboardScreen` | Reagir ao `AlarmFiredEvent` para animação; consultar `vehicle_state.is_alarm_firing()` para cor |
| `AlarmProcessor.run()` | Controlar play/stop do áudio via `vehicle_state.is_any_alarm_firing()` |

### 5.3 `AlarmProcessor` — compatibilidade com sinais parciais

`process_signals()` itera sobre `signals.items()` — sinais ausentes no batch simplesmente não são reavaliados naquele ciclo, mantendo o estado anterior. Isso é correto.

---

## 6. Renomeação `EVENT_MARK_REQUESTED` → `LOG_EVENT_MARK_REQUEST`

| Arquivo | O que muda |
|---------|-----------|
| `app/event/app_events.py` | Valor do enum + dataclass `EventMarkRequestedEvent` → `LogEventMarkRequestEvent` |
| `app/event/bus.py` | Chave em `_SIGNAL_ATTR` + atributo em `_EventBusQObject` |
| `app/event/marker.py` | Import + `event_bus.publish(LogEventMarkRequestEvent())` |
| `app/log_writer/log_writer.py` | Subscribe usa `AppEventType.LOG_EVENT_MARK_REQUEST` |

---

## 7. `SIGNALS_RECEIVED` — Suporte a Parcialidade

Nenhuma mudança de interface necessária. O campo `data: dict` continua sendo `Dict[Signal, ParsedSignal]`, mas agora pode ser subconjunto. Verificação de tolerância dos subscribers:

- `DashboardScreen.on_signal_received()`: usa `parsed_data.get(signal)` — tolerante ✓
- `AlarmProcessor.process_signals()`: itera `signals.items()` — tolerante ✓
- `LambdaLoopStateProcessor.on_signal_received()`: usa `signals.get(Signal.LAMBDA_LOOP)` — tolerante ✓

---

## 8. Passos de Implementação

```
FASE 1 — Preparação (sem breaking changes)
  [1] Adicionar MESS_FRAME, COMMAND_RESPONSE, LOG_EVENT_MARK_REQUEST ao AppEventType
      Adicionar MessFrameEvent, CommandResponseEvent, LogEventMarkRequestEvent
      Registrar novos sinais em bus.py
      Manter EVENT_MARK_REQUESTED ainda (remoção no Passo 6)
      ← Dependência: nenhuma. Pode ser commitado isolado.

  [2] Corrigir bug VehicleState.set_alarm (ver Plano 04)
      ← Dependência: nenhuma.

FASE 2 — Refatorar emissão na ECU
  [3] EcuSession/_handle_line: emitir MessFrameEvent e CommandResponseEvent
      Remover self.d01, self.d02, join manual
      ← Dependência: [1]

  [4] EcuConnectionMock: mesma lógica de emissão que [3]
      ← Dependência: [1]

FASE 3 — Refatorar consumidores (paralelo entre si)
  [5] signal.py: adicionar campo "frame": "#D01" em todos os sinais não calculados
  [6] signal_processor.py: subscrever MESS_FRAME, processar por frame
      ← Dependência: [1], [3], [4]

  [7] log_writer.py: subscrever MESS_FRAME e LOG_EVENT_MARK_REQUEST
      Remover write() e set_event_pending() públicos
      ← Dependência: [1], [3], [4]

  [8] marker.py: publicar LogEventMarkRequestEvent
      ← Dependência: [1]

FASE 4 — Remover wirings legados de main.py
  [9] Remover emitter.connect(signal_processor.process_line)
      Remover emitter.connect(log_writer.write)
      ← Dependência: [5], [6], [7] funcionando corretamente

FASE 5 — Limpeza
  [10] Remover EVENT_MARK_REQUESTED e EventMarkRequestedEvent
  [11] Remover VEHICLE_STATE_CHANGED (ver Plano 04 — pode ser em paralelo)
```

---

## 9. Comportamento para `#D03`

`EcuSession` emite `MessFrameEvent` para `#D03` (caso chegue). `SignalProcessor._signals_by_frame` não terá entradas para `"#D03"` — retorna sem processar. `LogWriter` ignora `#D03`. Comportamento intencional: dados do D03 não foram mapeados no `Signal` enum ainda. Adicionar comentário no código:

```python
# #D03 recebido via MessFrameEvent mas sem sinais mapeados — ignorado intencionalmente
```

---

## 10. Thread Safety do `LogWriter`

Os callbacks do bus (`_on_mess_frame`, `_on_mark`) são entregues via `pyqtSignal` com `QueuedConnection` na main thread. Não há concorrência entre chamadas — não é necessário lock no acumulador interno (`_pending_d01`, `_pending_d02`).

---

## 11. Limpeza do `SignalProcessor.emitter` Legado

Após a migração completa (todos os consumidores usando o bus), verificar:
```bash
grep -rn "signal_processor\.emitter\|SignalProcessor.*emitter" app/ main.py
```
Se sem consumidores, remover `emitter = Signal(dict)` e a chamada `self.emitter.emit(parsed_data)` como passo de limpeza final.

---

## 12. Notas de Risco

**`StateProcessorRegister`:** conecta `ecu_connection.emitter → processor.on_command_received`. O `LambdaLoopStateProcessor.on_command_received(cmd, args)` espera `EcuCommand` mas o sinal emite `str`. Este wiring já tem tipo errado. Considerar migrar `LambdaLoopStateProcessor` para subscrever `COMMAND_RESPONSE` e remover `StateProcessorRegister` em iteração futura.

**Sinais calculados na primeira frame:** `vehicle_state.get_all()` retorna `{}` na primeira iteração. `POWER`, `TORQUE`, `VE_LAMBDA` aparecerão como `-1` até a segunda frame. Comportamento aceitável — igual ao atual quando D01+D02 ainda não chegaram.

**Sincronização de mark com flush:** múltiplas marcações antes de D01+D02 completos → apenas uma "MARK" gravada. Mesmo comportamento do código atual.
