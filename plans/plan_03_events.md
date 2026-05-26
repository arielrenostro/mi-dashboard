# Plano 03 — Refatoração dos Eventos

## Objetivo

- Remover `SCREEN_REQUESTED` e substituir por navegação direta e localizada
- Remover `VEHICLE_STATE_CHANGED` (código morto)
- Renomear `EVENT_MARK_REQUESTED` → `LOG_EVENT_MARK_REQUEST`
- Garantir que `SIGNALS_RECEIVED` suporte envio parcial de sinais
- Introduzir eventos "locais" de UI sem misturar com domínio

---

## Inventário Atual de Eventos

| Evento | Status | Consumidores | Ação |
|--------|--------|-------------|------|
| `SCREEN_REQUESTED` | Ativo | `AppWindow` | **Remover** |
| `ECU_COMMAND_REQUESTED` | Ativo | `main.py` | Manter igual |
| `ALARM_FIRED` | Ativo | `DashboardScreen` | Manter igual |
| `VEHICLE_STATE_CHANGED` | Morto (nunca publicado via bus) | Nenhum | **Remover** |
| `EVENT_MARK_REQUESTED` | Parcialmente ativo (desabilitado em main) | `main.py` | **Renomear** |
| `SIGNALS_RECEIVED` | Ativo | `DashboardScreen`, `AlarmProcessor`, `main.py` | Suporte a parcial |

---

## 1. Remover `SCREEN_REQUESTED`

### Problema

`HomeScreen` publica `ScreenRequestedEvent(screen_name="dashboard")` via event_bus global. `AppWindow` se inscreve e chama `show_screen(name)`. Isso cria acoplamento indireto e dificulta rastrear o fluxo de navegação.

### Solução: Navegação por Injeção de Dependência

**Criar interface de navegação:**

```python
# app/ui/navigation.py
from typing import Protocol

class Navigator(Protocol):
    def go_to(self, screen_name: str) -> None: ...
    def go_home(self) -> None: ...
```

**`AppWindow` implementa `Navigator`:**

```python
class AppWindow(QWidget):
    def go_to(self, screen_name: str) -> None:
        self.show_screen(screen_name)
    
    def go_home(self) -> None:
        self.show_screen("home")
```

**Telas recebem `navigator` no construtor:**

```python
class HomeScreen(Screen):
    def __init__(self, navigator: Navigator, close_fn: Callable):
        super().__init__(close_fn)
        self._navigator = navigator
    
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            _, screen_name = self._menu_items[self._selected]
            self._navigator.go_to(screen_name)   # Direto, sem event_bus
```

**`main.py` / `AppWindow._register_screens()`:**
```python
home_screen = HomeScreen(navigator=self, close_fn=self.close)
ve_calibration_screen = VeCalibrationScreen(navigator=self, close_fn=self.go_home)
dashboard_screen = DashboardScreen(navigator=self, close_fn=self.go_home, ...)
```

### Arquivos Afetados

| Arquivo | Mudança |
|---------|---------|
| `app/event/app_events.py` | Remover `SCREEN_REQUESTED = auto()`, remover `ScreenRequestedEvent` |
| `app/event/bus.py` | Remover `SCREEN_REQUESTED` de `_SIGNAL_ATTR` e `screen_requested = pyqtSignal(object)` |
| `app/ui/window.py` | Remover subscriber de `SCREEN_REQUESTED` (linhas 31-32); implementar `go_to`/`go_home` |
| `app/ui/home/screen.py` | Remover import de `ScreenRequestedEvent`; usar `self._navigator.go_to(name)` |
| `app/ui/base/screen.py` | `close_fn` vira `navigator: Navigator` (ou mantém ambos) |
| `app/ui/navigation.py` | **Criar** `Navigator` protocol |
| `app/ui/dashboard/screen.py` | Substituir `close_fn` por `navigator.go_home()` |
| `app/ui/ve_calibration/screen.py` | Substituir `close_fn` por `navigator.go_home()` |

---

## 2. Remover `VEHICLE_STATE_CHANGED`

### Problema

`AppEventType.VEHICLE_STATE_CHANGED` e `VehicleStateChangedEvent` existem mas **nunca são publicados** nem consumidos via event_bus. A funcionalidade real é coberta por `vehicle_state.emitter` (sinal PyQt direto em `app/state/state.py`).

### Solução: Remover sem substituição

```python
# app/event/app_events.py — REMOVER:
VEHICLE_STATE_CHANGED = auto()   # linha 12

@dataclass(frozen=True)
class VehicleStateChangedEvent(AppEvent):   # linhas 43-46
    ...
```

```python
# app/event/bus.py — REMOVER:
AppEventType.VEHICLE_STATE_CHANGED: "vehicle_state_changed",   # linha 16
vehicle_state_changed = pyqtSignal(object)   # linha 26
```

`VeCalibrationScreen` usa `vehicle_state.emitter.connect()` diretamente — não é afetada.

---

## 3. Renomear `EVENT_MARK_REQUESTED` → `LOG_EVENT_MARK_REQUEST`

### Motivação

O nome atual é genérico demais. "Log Event Mark" expressa que é uma requisição para marcar um evento no log CSV.

### Mudanças

**`app/event/app_events.py`:**
```python
# Antes:
EVENT_MARK_REQUESTED = auto()

@dataclass(frozen=True)
class EventMarkRequestedEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.EVENT_MARK_REQUESTED, init=False)

# Depois:
LOG_EVENT_MARK_REQUEST = auto()

@dataclass(frozen=True)
class LogEventMarkRequestEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.LOG_EVENT_MARK_REQUEST, init=False)
```

**`app/event/bus.py`:**
```python
# Antes:
AppEventType.EVENT_MARK_REQUESTED: "event_mark_requested"
event_mark_requested = pyqtSignal(object)

# Depois:
AppEventType.LOG_EVENT_MARK_REQUEST: "log_event_mark_request"
log_event_mark_request = pyqtSignal(object)
```

**`app/event/marker.py`:**
```python
# Antes:
event_bus.publish(EventMarkRequestedEvent())

# Depois:
event_bus.publish(LogEventMarkRequestEvent())
```

**`main.py`:**
```python
# Antes:
event_bus.subscribe(AppEventType.EVENT_MARK_REQUESTED, ...)

# Depois:
event_bus.subscribe(AppEventType.LOG_EVENT_MARK_REQUEST, ...)
```

**Reabilitar conexão do EventMarker em `main.py`:** O `EventMarker` **já está instanciado** e a subscrição ao bus já ocorre (linhas 56-60). O que está comentado é apenas a linha que conecta `app_window.key_event` ao `event_marker.handle_key` (linha 75). Basta descomentar:

```python
app_window.key_event.connect(event_marker.handle_key)
```

---

## 4. `SIGNALS_RECEIVED` com Suporte a Dados Parciais

### Estado Atual

`SignalsReceivedEvent.data` é `Dict[Signal, ParsedSignal]` com todos os sinais ou falha silenciosa (`-1`) para os ausentes.

### Mudança

O dataclass já aceita qualquer dict — a mudança é **semântica e de contrato**:

```python
@dataclass(frozen=True)
class SignalsReceivedEvent(AppEvent):
    data: Dict[Signal, ParsedSignal]
    # Pode conter subset dos sinais. Consumidores devem usar .get()
```

Atualizar docstring e garantir que todos os consumidores usem `data.get(signal)` em vez de `data[signal]`.

**Verificação dos consumidores atuais:**

| Consumidor | Uso | Tolerante a parcial? |
|------------|-----|---------------------|
| `DashboardScreen.on_signal_received()` | `parsed_data.get(signal)` | ✅ Sim |
| `AlarmProcessor.process_signals()` | `for signal, data in signals.items()` | ✅ Sim |
| `main.py` subscriber | `vehicle_state.update(e.data)` | ✅ Sim (update faz merge) |

Nenhuma mudança funcional necessária nos consumidores.

---

## 5. Eventos Locais de UI

### Problema

`SCREEN_REQUESTED` misturava navegação (UI) com o event_bus de domínio. Após removê-lo, o event_bus fica com apenas eventos de domínio.

### Regra a Seguir

> **Eventos no `event_bus` são de domínio.** Eventos de navegação, animação, e interação de teclado são locais às telas.

Implementação atual que já segue a regra:
- Teclado → `pyqtSignal` direto em `AppWindow` → `keyPressEvent` nas telas
- Sem passar por event_bus ✅

Reforços:
- Remover `SCREEN_REQUESTED` ✅ (já planejado)
- `close_fn` / `navigator` — injeção direta, sem bus ✅

---

## 6. Novos Eventos do Plano 01 (ECU)

Adicionar ao event_bus os eventos da camada ECU:

```python
class AppEventType(Enum):
    MESS_FRAME              = auto()   # MessFrameEvent
    COMMAND_RESPONSE        = auto()   # CommandResponseEvent
    ECU_COMMAND_REQUESTED   = auto()   # Mantido
    ALARM_FIRED             = auto()   # Mantido
    LOG_EVENT_MARK_REQUEST  = auto()   # Renomeado
    SIGNALS_RECEIVED        = auto()   # Mantido (suporte parcial)
```

---

## Arquivos a Criar/Modificar

| Ação | Arquivo | Mudança |
|------|---------|---------|
| **Criar** | `app/ui/navigation.py` | `Navigator` protocol |
| **Modificar** | `app/event/app_events.py` | Remove `SCREEN_REQUESTED`, `VEHICLE_STATE_CHANGED`; renomeia `EVENT_MARK_REQUESTED`; adiciona `MESS_FRAME`, `COMMAND_RESPONSE` |
| **Modificar** | `app/event/bus.py` | Sincroniza `_SIGNAL_ATTR` e `_EventBusQObject` com as mudanças acima |
| **Modificar** | `app/event/marker.py` | Usa `LogEventMarkRequestEvent` |
| **Modificar** | `app/ui/window.py` | Implementa `Navigator`; remove subscriber de `SCREEN_REQUESTED` |
| **Modificar** | `app/ui/base/screen.py` | Recebe `navigator: Navigator` |
| **Modificar** | `app/ui/home/screen.py` | Usa `navigator.go_to()` |
| **Modificar** | `app/ui/dashboard/screen.py` | Usa `navigator.go_home()` |
| **Modificar** | `app/ui/ve_calibration/screen.py` | Usa `navigator.go_home()` |
| **Modificar** | `main.py` | Atualiza subscrições; reabilita `EventMarker`; reabilita `KeyHoldDetector`+`LambdaToggle` |

---

## Ordem de Execução

1. Remover `VEHICLE_STATE_CHANGED` (sem risco — código morto)
2. Renomear `EVENT_MARK_REQUESTED` → `LOG_EVENT_MARK_REQUEST` e reabilitar EventMarker
3. Criar `Navigator` protocol + implementar em `AppWindow`
4. Atualizar telas para receber `navigator` e chamar diretamente
5. Remover `SCREEN_REQUESTED` de eventos e bus
6. Adicionar `MESS_FRAME` e `COMMAND_RESPONSE` (junto com Plano 01)
7. Reabilitar `KeyHoldDetector` + `LambdaToggle` em `main.py`

---

## Critérios de Aceite

- [ ] Nenhum evento de navegação passa pelo event_bus global
- [ ] `VEHICLE_STATE_CHANGED` removido sem quebrar nenhuma funcionalidade
- [ ] `EventMarker` publicando `LogEventMarkRequestEvent` e conectado em `main.py`
- [ ] `DashboardScreen`, `VeCalibrationScreen` navegam via `navigator.go_home()` sem event_bus
- [ ] `HomeScreen` navega via `navigator.go_to("dashboard")` sem event_bus
- [ ] `SIGNALS_RECEIVED` documentado como suporte parcial; todos os consumidores usam `.get()`
- [ ] `KeyHoldDetector` + `LambdaToggle` reabilitados e funcionais
