# Plano 05 — Ajustes e Consolidação Arquitetural

Este documento identifica inconsistências, omissões e problemas nos Planos 01–04 e define
as resoluções definitivas. Deve ser lido junto com os planos anteriores, e suas decisões
**prevalecem** sobre qualquer trecho conflitante neles.

---

## Visão Geral: Camadas Limpas

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1 — Transport (pure Python, sem Qt, sem bus)              │
│   EcuTransport (ABC)                                            │
│     ├── SerialTransport    ← pyserial                           │
│     └── MockTransport      ← CSV replay + respostas hardcoded   │
└───────────────────────┬─────────────────────────────────────────┘
                        │ open/close/readline/writeline
┌───────────────────────▼─────────────────────────────────────────┐
│ Layer 2 — Session (pure Python, sem Qt, sem bus)                │
│   EcuSession                                                    │
│     ├── handshake / fetch breakpoints+VE map → vehicle_state.*  │
│     ├── send_command / send_and_wait                            │
│     └── on_line: Callable[[str], None]  (injetado pelo thread)  │
└───────────────────────┬─────────────────────────────────────────┘
                        │ on_line(raw_str) para TODA linha recebida
┌───────────────────────▼─────────────────────────────────────────┐
│ Layer 3 — Qt Bridge                                             │
│   EcuSessionThread (QThread)                                    │
│     └── _on_line(line): classifica e publica no EventBus        │
│           ├── #D01/#D02/#D03  → MessFrameEvent                  │
│           └── outros          → CommandResponseEvent            │
└───────────────────────┬─────────────────────────────────────────┘
                        │ EventBus (pyqtSignal por tipo)
┌───────────────────────▼─────────────────────────────────────────┐
│ Layer 4 — Domain Processors (QObject, main thread via bus)      │
│   SignalProcessor       ← MESS_FRAME → SignalsReceivedEvent     │
│   AlarmProcessor        ← SIGNALS_RECEIVED → AlarmFiredEvent    │
│   LambdaLoopStateProcessor ← SIGNALS_RECEIVED + ECU_COMMAND_REQUESTED │
│   LogWriter             ← MESS_FRAME + LOG_EVENT_MARK_REQUEST   │
└───────────────────────┬─────────────────────────────────────────┘
                        │ escrita direta (thread-safe via RLock)
┌───────────────────────▼─────────────────────────────────────────┐
│ Layer 5 — State                                                 │
│   VehicleState (singleton)                                      │
│     ├── _alarm_active / _alarm_last_fired (bug fix)             │
│     ├── emit fora do lock (set_rpm_breakpoints, etc.)           │
│     └── vehicle_state.emitter → VeCalibrationScreen            │
└───────────────────────┬─────────────────────────────────────────┘
                        │ pyqtSignal / bus
┌───────────────────────▼─────────────────────────────────────────┐
│ Layer 6 — UI                                                    │
│   AppWindow → HomeScreen, DashboardScreen, VeCalibrationScreen  │
│     navigate_to / go_home / quit_app  pyqtSignal (sem bus)      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Estado Final do EventBus

```python
class AppEventType(Enum):
    ECU_COMMAND_REQUESTED  = auto()   # mantido — desacopla LambdaToggle da sessão
    ALARM_FIRED            = auto()   # mantido
    LOG_EVENT_MARK_REQUEST = auto()   # renomeado de EVENT_MARK_REQUESTED
    SIGNALS_RECEIVED       = auto()   # mantido
    MESS_FRAME             = auto()   # novo (Plano 02)
    COMMAND_RESPONSE       = auto()   # novo (Plano 02) — sem subscriber inicial, disponível para extensão

    # REMOVIDOS:
    # SCREEN_REQUESTED      → pyqtSignal local (Plano 03)
    # VEHICLE_STATE_CHANGED → nunca foi publicado (Plano 04)
    # EVENT_MARK_REQUESTED  → renomeado para LOG_EVENT_MARK_REQUEST
```

---

## Ajuste A — Quem classifica linhas e publica no bus (afeta Plano 01 + 02)

**Problema:** O Plano 02 seção 2 mostra código de `_handle_line` dentro de `EcuSession` chamando
`event_bus.publish(MessFrameEvent(...))`. Isso viola a filosofia do próprio Plano 01 ("EcuSession
não conhece VehicleState"), já que `EventBus` é infraestrutura Qt da aplicação.

**Resolução definitiva:**

`EcuSession` é **pure Python**. Ele expõe apenas `on_line: Callable[[str], None]` — um callback
injetado pelo `EcuSessionThread`. `EcuSession` não importa nada de `app.event.*`.

A classificação e publicação no bus pertencem ao `EcuSessionThread`, que é Qt-aware por design:

```python
class EcuSessionThread(QThread):
    def __init__(self, session: EcuSession):
        super().__init__()
        self._session = session
        self._session.on_line = self._on_line  # injeção

    def _on_line(self, line: str) -> None:
        """Chamado no _reader_thread — pyqtSignal.emit() é thread-safe."""
        if line.startswith(("#D01", "#D02", "#D03")):
            frame_id = line[:4]
            event_bus.publish(MessFrameEvent(
                frame_id=frame_id,
                raw_line=line,
                parts=tuple(line.split(";")),
            ))
        else:
            parts = tuple(line.split(";"))
            event_bus.publish(CommandResponseEvent(
                response_id=parts[0] if parts else "",
                raw_line=line,
                parts=parts,
            ))

    def run(self):
        while not self.isInterruptionRequested():
            try:
                self._session.start()
                self._session.wait_until_disconnected()
            except Exception:
                pass  # loga e tenta reconectar
```

**O pyqtSignal `emitter` de `EcuConnectionThread` é removido** — não existe mais em
`EcuSessionThread`. Toda entrega é via `event_bus`.

---

## Ajuste B — Quem popula `vehicle_state` com breakpoints/VE map (afeta Plano 01)

**Problema:** Plano 01 seção 9 diz "EcuSession não conhece VehicleState — SignalProcessor trata
#I20/#I21". Porém, `send_and_wait` bloqueia a thread da sessão aguardando resposta. Com
`QueuedConnection`, o subscriber do bus só executaria depois do retorno de `send_and_wait` —
criando deadlock: a sessão aguarda a resposta, mas o handler que popularia `vehicle_state` só
roda depois que a sessão desbloqueou. O documento de resolução 00 reconhece isso e corretamente
determina manter o acoplamento direto.

**Resolução definitiva:**

`EcuSession._fetch_breakpoints()` e `_fetch_ve_map()` **chamam `vehicle_state.set_*` diretamente**
no contexto de `_connect()` (chamado pelo `EcuSessionThread`). Isso é correto porque:
- Ocorre antes do streaming → não há concorrência com main thread
- `VehicleState` usa `RLock` → acessos cross-thread são seguros
- `_emit fora do lock` (Ajuste F) elimina o risco de bloqueio da UI

```python
# em EcuSession:

def _fetch_breakpoints(self) -> None:
    from app.ecu_protocol.commands import commands
    from app.ecu_protocol.responses import responses
    from app.state.state import vehicle_state

    rpm_line = self.send_and_wait(commands.RPM_BREAKPOINTS, [responses.RPM_BREAKPOINTS])
    if rpm_line:
        vehicle_state.set_rpm_breakpoints([int(v) for v in rpm_line.split(";")[1:]])

    map_line = self.send_and_wait(commands.MAP_BREAKPOINTS, [responses.MAP_BREAKPOINTS])
    if map_line:
        vehicle_state.set_map_breakpoints([int(v) for v in map_line.split(";")[1:]])

def _fetch_ve_map(self) -> None:
    from app.ecu_protocol.commands import commands
    from app.ecu_protocol.responses import responses
    from app.state.state import vehicle_state

    for i in range(1, 17):   # 16 linhas: FIX do bug range(1,16) do código atual
        line = self.send_and_wait(commands[f"VE_ROW_{i}"], [responses[f"VE_ROW_{i}"]])
        if line:
            ve_line = [int(v) for v in line.split(";")[1:]]
            vehicle_state.set_ve_map(ve_line, i - 1)
```

**Consequência:** `SignalProcessor` subscreve apenas `MESS_FRAME`. Ele **não** processa
`COMMAND_RESPONSE` para #I20/#I21/#F01-#F16. Esses prefixos chegam ao bus via `CommandResponseEvent`
(publicado por `EcuSessionThread._on_line`), mas ninguém os consome por ora — comportamento aceito,
disponível para extensão futura sem breaking change.

---

## Ajuste C — `EcuSession._start_streaming` deve usar `send_command` (afeta Plano 01)

**Problema:** O Plano 01 seção 5 usa `_write_lock` diretamente em `_start_streaming`, bypassing
`send_command`.

**Resolução:**

```python
def _start_streaming(self) -> None:
    from app.ecu_protocol.commands import commands
    self.send_command(commands.STREAMING_START)
```

`send_command` já gerencia o lock internamente. Consistência > brevidade.

---

## Ajuste D — `StateProcessorRegister` e `Processor` base class são removidos (novo)

**Problema:** `StateProcessorRegister` conecta `signal_processor.emitter` e
`ecu_connection.emitter` a processadores. Com a nova arquitetura, ambos os emitters desaparecem.
A classe `Processor` define `on_command_received(cmd: EcuCommand, args)` mas o sinal
`ecu_connection.emitter` emite `str` — type mismatch que nunca funcionou corretamente.

**Resolução:** Deletar:
- `app/state/processors/base.py` — `Processor` ABC
- `app/state/register.py` — `StateProcessorRegister`

`LambdaLoopStateProcessor` migra para subscrever o bus diretamente (Ajuste E).

---

## Ajuste E — `LambdaLoopStateProcessor` migra para o bus (afeta Plano 02)

**Problema:** O Plano 02 seção 12 menciona a migração como "iteração futura", mas isso deve
acontecer junto com a remoção do `StateProcessorRegister` para não deixar um componente sem wiring.

**Resolução:** `LambdaLoopStateProcessor` torna-se `QObject` puro (sem `Processor` ABC) e
subscreve o bus diretamente em seu `__init__`:

```python
class LambdaLoopStateProcessor(QObject):

    def __init__(self):
        super().__init__()
        event_bus.subscribe(AppEventType.SIGNALS_RECEIVED, self._on_signals_received)
        event_bus.subscribe(AppEventType.ECU_COMMAND_REQUESTED, self._on_command_requested)

    def _on_signals_received(self, event: SignalsReceivedEvent) -> None:
        # mesma lógica de on_signal_received atual
        ...

    def _on_command_requested(self, event: EcuCommandRequestedEvent) -> None:
        from app.ecu_protocol.commands import commands
        if event.command == commands.LAMBDA_LOOP_OPEN:
            vehicle_state.set_lambda_loop_state(False)
        elif event.command == commands.LAMBDA_LOOP_CLOSE:
            vehicle_state.set_lambda_loop_state(True)
```

Instanciado e mantido vivo em `main.py` (sem precisar de register):

```python
lambda_loop_processor = LambdaLoopStateProcessor()
```

---

## Ajuste F — `EcuCommandRequestedEvent.command` type hint (afeta Plano 01)

**Resolução (Contradição C do doc 00):**

```python
# app/event/app_events.py
from app.ecu_protocol.commands import EcuCommand

@dataclass(frozen=True)
class EcuCommandRequestedEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.ECU_COMMAND_REQUESTED, init=False)
    command: Optional[EcuCommand] = None
    args: Any = None
```

O subscriber em `main.py` que traduz para a sessão:

```python
event_bus.subscribe(
    event_type=AppEventType.ECU_COMMAND_REQUESTED,
    callback=lambda e: get_ecu_connection().send_command(e.command, e.args),
)
```

`EcuSession.send_command(cmd: EcuCommand, args)` é público e thread-safe — adequado para ser
chamado da main thread via bus.

---

## Ajuste G — `SignalProcessor.emitter` legado é removido imediatamente (afeta Plano 02)

**Problema:** O Plano 02 mantém `emitter = Signal(dict)` para "compatibilidade com
StateProcessorRegister". Com a remoção do `StateProcessorRegister` (Ajuste D), não há mais
consumidores do emitter legado.

**Resolução:** `SignalProcessor.emitter` é removido na mesma fase que `StateProcessorRegister`.
`SignalProcessor` publica apenas via `event_bus.publish(SignalsReceivedEvent(...))`.

---

## Ajuste H — `vehicle_state.update()` sai do `main.py` (afeta Plano 02)

**Problema:** `main.py` tem:
```python
event_bus.subscribe(AppEventType.SIGNALS_RECEIVED, lambda e: vehicle_state.update(e.data))
```

Com o novo `SignalProcessor._on_mess_frame()` chamando `vehicle_state.update(parsed_data)`
diretamente, isso causaria dupla atualização.

**Resolução:** Remover esse subscriber de `main.py`. `SignalProcessor` é o único responsável
por chamar `vehicle_state.update()`.

---

## Ajuste I — `MockTransport`: respostas para handshake (afeta Plano 01)

O Plano 01 diz que `MockTransport.writeline()` "injeta respostas via fila interna quando chamado
com os prefixos conhecidos". Especificação detalhada:

```python
class MockTransport(EcuTransport):
    """Reproduz CSV e responde a comandos de handshake com dados hardcoded."""

    # Respostas padrão hardcoded (mesmas do EcuConnectionMock atual)
    _DEFAULT_RESPONSES = {
        "#D50": "#D50;MasterInjection;1.0",
        "#I20": "#I20;400;800;1200;1600;2000;2400;2800;3200;3600;4000;4400;4800;5200;5600;6200;6800",
        "#I21": "#I21;20;30;40;50;60;70;80;90;100;120;140;160;180;200;220;240",
        # #F01–#F16: gerado no __init__ a partir dos dados hardcoded do mock atual
    }

    def __init__(self, mock_file: str):
        self._mock_file = mock_file
        self._rx_queue: queue.Queue = queue.Queue()
        self._ve_responses = self._build_ve_responses()
        self._feed_thread: Optional[threading.Thread] = None
        self._open = False

    def writeline(self, data: str) -> None:
        """Quando um comando de handshake é enviado, injeta resposta fake na fila."""
        prefix = data.split(";")[0]
        if prefix in self._DEFAULT_RESPONSES:
            self._rx_queue.put(self._DEFAULT_RESPONSES[prefix])
        elif prefix in self._ve_responses:
            self._rx_queue.put(self._ve_responses[prefix])
        # Outros comandos (STREAMING_START, etc.) são ignorados silenciosamente

    def readline(self) -> str:
        try:
            return self._rx_queue.get(timeout=1.0)
        except queue.Empty:
            return ""
```

A lógica de replay do CSV migra para `_feed_loop()` (thread daemon que faz `_rx_queue.put(line)`)
e começa junto com `open()`.

---

## Ajuste J — `HomeScreen`: item "Sair" e sinal `quit_app` (afeta Plano 03)

O Plano 03 omissão D define o sinal `quit_app` mas não mostra onde `HomeScreen` o emite.

**Resolução:**

Adicionar "Sair" como terceiro item no menu de `HomeScreen`:

```python
self._menu_items = [
    ("Dashboard",        "dashboard",       "navigate"),
    ("Calibração de VE", "ve_calibration",  "navigate"),
    ("Sair",             None,              "quit"),
]
```

No `keyPressEvent`:

```python
elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
    _, target, action = self._menu_items[self._selected]
    if action == "navigate":
        self.navigate_to.emit(target)
    elif action == "quit":
        self.quit_app.emit()
```

`AppWindow._register_screens()` conecta `home_screen.quit_app.connect(self.close)`.

---

## Ajuste K — `AppWindow.showFullScreen()` sai do `__init__` (novo)

**Problema:** `AppWindow.__init__` chama `self.showFullScreen()`. `main.py` chama
`app_window.show()` em seguida, o que em algumas plataformas sobrepõe a configuração de
tela cheia. Decisão de modo de exibição pertence ao `main.py`.

**Resolução:** Remover `self.showFullScreen()` do `AppWindow.__init__`. `main.py` decide:

```python
app_window = AppWindow(...)
app_window.showFullScreen()   # ou show() em desenvolvimento
```

---

## Ajuste L — `LogWriter._flush()` não deve incluir frame ID nas partes (afeta Plano 02)

**Problema:** O Plano 02 seção 4 propõe:
```python
row = [timestamp, event_mark] + list(self._pending_d01) + list(self._pending_d02)
```
Onde `_pending_d01 = event.parts` e `parts = tuple("#D01;val1;...".split(";"))`.
Logo `parts[0] = "#D01"` e `parts[0]` de D02 = `"#D02"`. Isso é **correto** — o CSV atual
tem colunas "Mess 1" e "Mess 2" que recebem justamente `#D01` e `#D02`. O formato do CSV
não muda.

**Confirmação:** Comportamento aceito — não é bug, só confirmação para evitar confusão na
implementação.

---

## Ajuste M — Fluxo de dados completo revisado

```
EcuSessionThread._on_line(line)  [reader thread — thread-safe emit]
  ├─ linha #D01/#D02/#D03
  │     └─► event_bus.publish(MessFrameEvent(frame_id, raw_line, parts))
  │               ├──► SignalProcessor._on_mess_frame()
  │               │         ├─ parseia sinais do frame
  │               │         ├─ vehicle_state.update(parsed_data)
  │               │         └─► event_bus.publish(SignalsReceivedEvent(data))
  │               │                   ├──► AlarmProcessor._on_signals_received()
  │               │                   │         ├─ vehicle_state.set_alarm(signal, active)
  │               │                   │         └─► event_bus.publish(AlarmFiredEvent) [cooldown]
  │               │                   ├──► LambdaLoopStateProcessor._on_signals_received()
  │               │                   │         └─ vehicle_state.set_lambda_loop_state()
  │               │                   └──► DashboardScreen.on_signal_received() [quando ativa]
  │               └──► LogWriter._on_mess_frame()
  │                         acumula D01+D02; quando ambos chegam → grava CSV
  └─ outras linhas (#D50, #I20, #I21, #F01–#F16)
        └─► event_bus.publish(CommandResponseEvent(response_id, raw_line, parts))
              [sem subscriber — disponível para extensão futura]

EcuSession._fetch_breakpoints() / _fetch_ve_map()  [no EcuSessionThread, durante handshake]
  └─ vehicle_state.set_rpm_breakpoints() / set_map_breakpoints() / set_ve_map()
        └─► vehicle_state.emitter.emit(VehicleStateChangeEvent)  [fora do lock]
                  └──► VeCalibrationScreen._on_vehicle_state_event() [quando ativa]

AlarmProcessor.run() (poll 100ms, QThread)
  └─► vehicle_state.is_any_alarm_firing() → play/stop áudio

LambdaToggle.handle_trigger()
  └─► event_bus.publish(EcuCommandRequestedEvent(commands.LAMBDA_LOOP_CLOSE/OPEN))
            ├──► main.py subscriber → get_ecu_connection().send_command(e.command, e.args)
            └──► LambdaLoopStateProcessor._on_command_requested()

EventMarker.handle_key()
  └─► event_bus.publish(LogEventMarkRequestEvent())
            └──► LogWriter._on_mark()

HomeScreen.navigate_to(screen_name)  [pyqtSignal local]
  └──► AppWindow.show_screen(name)

HomeScreen.quit_app()  [pyqtSignal local]
  └──► AppWindow.close()

DashboardScreen.go_home()  [pyqtSignal local]
  └──► AppWindow.show_screen("home")

VeCalibrationScreen.go_home()  [pyqtSignal local]
  └──► AppWindow.show_screen("home")
```

---

## Arquivos a Criar (novo)

| Arquivo | Conteúdo |
|---------|---------|
| `app/ecu_protocol/__init__.py` | — |
| `app/ecu_protocol/commands.py` | `EcuCommand` dataclass + `_CommandRegistry` + instância `commands` |
| `app/ecu_protocol/responses.py` | `EcuResponse` dataclass + `_ResponseRegistry` + instância `responses` |
| `app/ecu_connection/transport.py` | `EcuTransport` ABC |
| `app/ecu_connection/transport_serial.py` | `SerialTransport` |
| `app/ecu_connection/transport_mock.py` | `MockTransport` |
| `app/ecu_connection/session.py` | `EcuSession` |

---

## Ajuste N — `EcuConnectionStatus` sobrevive, `EcuConnection` ABC não (afeta Plano 01)

**Problema:** Plano 01 diz "ecu_connection.py: MANTER: EcuConnectionStatus". Mas a lista de
deleção abaixo inclui `ecu_connection.py`. Precisa de clareza.

**Resolução:**
- `EcuConnection` ABC: **deletar** — substituído por `EcuTransport` + `EcuSession`
- `EcuConnectionStatus` enum: **manter** em `app/ecu_connection/ecu_connection.py` (apenas o enum,
  classe base deletada) **ou** mover para `app/ecu_connection/session.py`
- `EcuSession.get_status() -> EcuConnectionStatus` expõe o estado atual
- `get_ecu_connection()` no `__init__.py` retorna `EcuSession` (manter nome para retrocompat com
  `HomeScreen` e o subscriber de `ECU_COMMAND_REQUESTED` em `main.py`)

---

## Ajuste O — `AppWindow` não recebe `SignalProcessor` como parâmetro (novo)

**Problema:** `AppWindow.__init__(self, signal_processor: SignalProcessor)` recebe e armazena
`signal_processor`, mas não o passa para nenhuma tela nem o usa. É dead weight.

**Resolução:** Remover o parâmetro. `AppWindow.__init__(self)`. Telas e processadores se conectam
via bus — `AppWindow` não precisa conhecer `SignalProcessor`.

---

## Arquivos a Deletar (após migração completa)

| Arquivo | O que dele sobrevive | Motivo da deleção |
|---------|---------------------|-------------------|
| `app/ecu_connection/serial.py` | — | Substituído por `SerialTransport` + `EcuSession` |
| `app/ecu_connection/mock_log.py` | — | Substituído por `MockTransport` + `EcuSession` |
| `app/ecu_connection/ecu_connection.py` | `EcuConnectionStatus` → mover para `session.py` | `EcuConnection` ABC substituída |
| `app/ecu_connection/thread.py` | — | Reescrito do zero como `EcuSessionThread` |
| `app/masterinjection/protocol.py` | — | Substituído por `app/ecu_protocol/` |
| `app/state/processors/base.py` | — | `Processor` ABC removida |
| `app/state/register.py` | — | `StateProcessorRegister` removida |

---

## Ordem Global de Execução Revisada

```
FASE 1 — Correções críticas independentes (Plano 04)
  [1a] Corrigir bug VehicleState.set_alarm: _alarm_active + _alarm_last_fired
  [1b] Corrigir emit fora do lock: set_rpm_breakpoints, set_map_breakpoints, set_ve_map
  [1c] Corrigir bug range(1,16) → range(1,17) em _fetch_ve_map do serial.py (fix imediato)

FASE 2 — Protocolo ECU e Transport (Plano 01 + Ajustes A/B/C)
  [2a] Criar app/ecu_protocol/commands.py + responses.py + __init__.py
  [2b] Criar app/ecu_connection/transport.py (EcuTransport ABC)
  [2c] Criar transport_serial.py + transport_mock.py  ← paralelo
  [2d] Criar session.py (EcuSession com _fetch_* → vehicle_state.set_* direto)
  [2e] Atualizar thread.py → EcuSessionThread com _on_line() publicando no bus
  [2f] Atualizar __init__.py → register_ecu_session

FASE 3 — Pipeline de dados (Plano 02 + Ajustes A/G/H)
  [3a] Adicionar MESS_FRAME, COMMAND_RESPONSE, LOG_EVENT_MARK_REQUEST ao AppEventType
       Adicionar MessFrameEvent, CommandResponseEvent, LogEventMarkRequestEvent
       Registrar no bus.py
  [3b] Corrigir bug set_alarm (Fase 1 já feito) — confirmar antes de avançar
  [3c] signal.py: adicionar campo "frame": "#D01" em todos os sinais não calculados
  [3d] signal_processor.py: subscrever MESS_FRAME, remover emitter legado, remover process_line()
  [3e] log_writer.py: subscrever MESS_FRAME + LOG_EVENT_MARK_REQUEST, remover write()
  [3f] marker.py: publicar LogEventMarkRequestEvent
  [3g] alarm/processor.py: manter sem mudança estrutural (já usa bus)

FASE 4 — Remoção de infraestrutura legada (Ajustes D/E/H)
  [4a] Criar LambdaLoopStateProcessor sem Processor ABC, subscrever bus diretamente
  [4b] Deletar app/state/processors/base.py + app/state/register.py
  [4c] Remover subscriber SIGNALS_RECEIVED → vehicle_state.update() de main.py
  [4d] Atualizar EcuCommandRequestedEvent.command para Optional[EcuCommand] (dataclass)
  [4e] Remover wirings legados de main.py:
         - emitter.connect(signal_processor.process_line)
         - emitter.connect(log_writer.write)
         - event_bus.subscribe(SIGNALS_RECEIVED, vehicle_state.update)

FASE 5 — UI e navegação (Plano 03 + Ajustes J/K)
  [5a] Screen base: adicionar navigate_to, go_home, quit_app; remover close_fn
  [5b] HomeScreen: remover close_fn, adicionar item "Sair", emitir navigate_to/quit_app
  [5c] DashboardScreen + VeCalibrationScreen: remover close_fn, emitir go_home
  [5d] AppWindow: conectar sinais locais, remover subscribe SCREEN_REQUESTED
  [5e] Remover SCREEN_REQUESTED + ScreenRequestedEvent do bus
  [5f] AppWindow: mover showFullScreen() para main.py

FASE 6 — VehicleState e VeCalibrationScreen (Plano 04 restante)
  [6a] VeCalibrationScreen: mover emitter.connect para on_activated/on_deactivated
  [6b] VeCalibrationScreen: adicionar _load_initial_state()
  [6c] Remover VEHICLE_STATE_CHANGED + VehicleStateChangedEvent do bus

FASE 7 — Limpeza final
  [7a] Deletar serial.py, mock_log.py, ecu_connection.py, thread.py (legado), protocol.py
  [7b] Verificar zero consumidores antes de cada deleção com grep
```

---

## Checklist de Invariantes

- `EcuSession` não importa nada de `app.event.*`, `app.ui.*`, ou `app.state.*` (exceto `vehicle_state` em `_fetch_*`)
- `EcuTransport` não importa nada além de `abc` e `typing`
- Toda entrega cross-thread de dados de sinal vai via `pyqtSignal`/`QueuedConnection`
- `vehicle_state.*` só é chamado da main thread, exceto `set_rpm_breakpoints`/`set_map_breakpoints`/`set_ve_map` que são chamados do `EcuSessionThread` (protected por `RLock`, emit fora do lock)
- Teclado é roteado via `pyqtSignal` em `AppWindow` direto para telas — não passa pelo bus
- Subscrições no bus em telas são feitas em `on_activated()` e canceladas em `on_deactivated()`
- `vehicle_state.emitter` (pyqtSignal direto) permanece para `VeCalibrationScreen` — não vai para o bus global
