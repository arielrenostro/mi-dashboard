# Plano 03 — Eventos e UI: Remoção de SCREEN_REQUESTED, Eventos Locais de Tela

## Objetivo

Reestruturar o sistema de eventos de UI para que:
- Navegação entre telas use `pyqtSignal` locais em vez do `EventBus` global
- `SCREEN_REQUESTED` seja removido do bus
- `VEHICLE_STATE_CHANGED` seja removido do bus (nunca foi publicado via bus)
- `EVENT_MARK_REQUESTED` seja renomeado para `LOG_EVENT_MARK_REQUEST`
- Telas não misturem comportamentos de UI com o restante da aplicação

---

## Estado Final dos Eventos do Bus

```python
class AppEventType(Enum):
    ECU_COMMAND_REQUESTED  = auto()
    ALARM_FIRED            = auto()
    LOG_EVENT_MARK_REQUEST = auto()   # renomeado de EVENT_MARK_REQUESTED
    SIGNALS_RECEIVED       = auto()
    MESS_FRAME             = auto()   # novo (ver Plano 02)
    COMMAND_RESPONSE       = auto()   # novo (ver Plano 02)
    # REMOVIDOS: SCREEN_REQUESTED, VEHICLE_STATE_CHANGED
```

---

## 1. Passo 1 — Renomear `EVENT_MARK_REQUESTED` → `LOG_EVENT_MARK_REQUEST`

Mudança isolada, zero dependências, pode ser feita primeiro.

| Arquivo | O que muda |
|---------|-----------|
| `app/event/app_events.py` | Valor enum `LOG_EVENT_MARK_REQUEST` + classe `LogEventMarkRequestEvent` |
| `app/event/bus.py` | `_SIGNAL_ATTR` e atributo `log_event_mark_request` em `_EventBusQObject` |
| `app/event/marker.py` | `event_bus.publish(LogEventMarkRequestEvent())` |
| `app/log_writer/log_writer.py` | Subscribe em `AppEventType.LOG_EVENT_MARK_REQUEST` |

```python
# app/event/app_events.py
@dataclass(frozen=True)
class LogEventMarkRequestEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.LOG_EVENT_MARK_REQUEST, init=False)
```

---

## 2. Passo 2 — Adicionar `pyqtSignal` de Navegação à Classe Base `Screen`

> **Nota:** a remoção de `VEHICLE_STATE_CHANGED` e a migração de `vehicle_state.emitter.connect`
> estão no **Plano 04**, não aqui. O Plano 03 trata apenas de navegação e SCREEN_REQUESTED.



A navegação entre telas deixa de passar pelo bus global. Telas expõem sinais Qt locais que o `AppWindow` conecta diretamente.

**`app/ui/base/screen.py`:**

```python
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget
from app.event.app_events import AppEventType
from app.event.bus import event_bus


class Screen(QWidget):
    """Base class para todas as telas."""

    navigate_to = pyqtSignal(str)  # emite o nome da tela de destino
    go_home     = pyqtSignal()     # atalho semântico para "voltar"
    quit_app    = pyqtSignal()     # emite quando o usuário quer fechar a aplicação

    def __init__(self):
        super().__init__()
        self._bus_tokens: list = []
        # close_fn REMOVIDO — telas não recebem mais callbacks de navegação

    def _subscribe(self, event_type: AppEventType, callback) -> None:
        token = event_bus.subscribe(event_type, callback)
        self._bus_tokens.append(token)

    def on_activated(self):
        pass

    def on_deactivated(self):
        for token in self._bus_tokens:
            event_bus.unsubscribe(token)
        self._bus_tokens.clear()
```

**Por que dois sinais?**
- `navigate_to(str)` — `HomeScreen` sabe o nome exato da tela de destino
- `go_home()` — `DashboardScreen` e `VeCalibrationScreen` só querem "voltar"; não precisam hardcodar "home"

---

## 3. Passo 3 — Atualizar as Telas

### `app/ui/home/screen.py`

```python
# REMOVER:
# from app.event.app_events import ScreenRequestedEvent
# from app.event.bus import event_bus

class HomeScreen(Screen):
    def __init__(self):    # sem close_fn
        super().__init__()
        # ... resto igual ...

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return
        if event.key() == Qt.Key.Key_Up:
            self._selected = (self._selected - 1) % len(self._menu_items)
            self._update_selection_ui()
        elif event.key() == Qt.Key.Key_Down:
            self._selected = (self._selected + 1) % len(self._menu_items)
            self._update_selection_ui()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            _, screen_name = self._menu_items[self._selected]
            self.navigate_to.emit(screen_name)   # NOVO: sinal local
        else:
            super().keyPressEvent(event)
```

### `app/ui/dashboard/screen.py`

```python
class DashboardScreen(Screen):
    def __init__(self, grid, graphs, graph_x_size):   # sem close_fn
        super().__init__()
        # ... resto igual ...

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.go_home.emit()    # NOVO: sinal local
```

### `app/ui/ve_calibration/screen.py`

```python
class VeCalibrationScreen(Screen):
    def __init__(self):    # sem close_fn
        super().__init__()
        # REMOVER: vehicle_state.emitter.connect(...) do __init__
        # (migrado para on_activated — ver Plano 04)
        # ... resto igual ...

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.go_home.emit()    # NOVO: sinal local
        # ... resto igual ...
```

---

## 4. Passo 4 — Atualizar `AppWindow`

`AppWindow` passa a conectar os sinais locais das telas e remove a subscrição ao bus.

```python
class AppWindow(QWidget):
    key_event    = pyqtSignal(int)
    key_released = pyqtSignal(int)

    def __init__(self, signal_processor: SignalProcessor):
        super().__init__()
        self._signal_processor = signal_processor
        self.stacked_widget = QStackedWidget()
        self.setLayout(self._create_layout())
        self._screens = {}
        self._current_screen_name = None
        self._register_screens()
        # REMOVER: event_bus.subscribe(AppEventType.SCREEN_REQUESTED, ...)
        self.showFullScreen()
        self.show_screen("home")

    def _register_screens(self):
        home_screen = HomeScreen()        # sem close_fn
        dashboard_screen = DashboardScreen(
            grid=config.dashboard.grid,
            graphs=config.dashboard.graph,
            graph_x_size=config.dashboard.graph_x_size,
        )                                 # sem close_fn
        ve_calibration_screen = VeCalibrationScreen()   # sem close_fn

        # Conectar sinais locais de navegação diretamente
        home_screen.navigate_to.connect(self.show_screen)
        home_screen.quit_app.connect(self.close)         # fechar a aplicação
        dashboard_screen.go_home.connect(lambda: self.show_screen("home"))
        ve_calibration_screen.go_home.connect(lambda: self.show_screen("home"))

        self._register_screen("home", home_screen)
        self._register_screen("dashboard", dashboard_screen)
        self._register_screen("ve_calibration", ve_calibration_screen)

    # show_screen() permanece sem alteração
```

`AppWindow` já importa todas as telas — conectar os sinais aqui não viola separação de responsabilidades. O conhecimento da topologia de navegação fica centralizado em quem já conhece todos os atores.

---

## 5. Passo 5 — Remover `SCREEN_REQUESTED` do Bus (VEHICLE_STATE_CHANGED é responsabilidade do Plano 04)

Remover `SCREEN_REQUESTED` do bus (feito após Passos 3 e 4).

A migração de `vehicle_state.emitter.connect` para `on_activated`/`on_deactivated` está no **Plano 04, Passo 4**. Os dois passos devem ser executados no mesmo PR.

Para confirmar zero consumidores antes de remover:
```bash
grep -r "SCREEN_REQUESTED\|ScreenRequestedEvent" app/
```

---

## 6. Passo 6 — Remover `SCREEN_REQUESTED` do Bus

**Verificar antes de remover:**
```bash
grep -r "SCREEN_REQUESTED\|ScreenRequestedEvent" app/
```

Após passos anteriores, deve retornar zero consumidores.

**`app/event/app_events.py`** — remover:
- `SCREEN_REQUESTED` do enum
- `ScreenRequestedEvent` dataclass

**`app/event/bus.py`** — remover:
- Entrada `screen_requested` em `_SIGNAL_ATTR`
- Atributo `screen_requested` em `_EventBusQObject`

> Remoção de `VEHICLE_STATE_CHANGED` e `VehicleStateChangedEvent` está no **Plano 04**.

---

## 7. Passo 7 — Revisar `main.py`

```python
# Remover se ainda presente:
# event_bus.subscribe(AppEventType.SCREEN_REQUESTED, ...)  ← estava em AppWindow

# Atualizar (já coberto no Passo 1):
event_bus.subscribe(
    event_type=AppEventType.LOG_EVENT_MARK_REQUEST,
    callback=lambda _: log_writer.set_event_pending(),
)
```

---

## 8. Ordem de Execução

```
[1] Renomear EVENT_MARK_REQUESTED → LOG_EVENT_MARK_REQUEST
    Arquivos: app_events.py, bus.py, marker.py, log_writer.py
    Dependências: nenhuma | Risco: baixo

[2] Adicionar navigate_to, go_home, quit_app em Screen; remover close_fn
    Arquivo: app/ui/base/screen.py
    Dependências: nenhuma | Risco: médio

[3] Atualizar HomeScreen, DashboardScreen, VeCalibrationScreen
    Arquivos: home/screen.py, dashboard/screen.py, ve_calibration/screen.py
    Dependências: [2] concluído | Risco: médio — fazer tudo de uma vez
    NOTA: migração de vehicle_state.emitter.connect é responsabilidade do Plano 04

[4] Atualizar AppWindow (conectar navigate_to, go_home, quit_app)
    Arquivo: app/ui/window.py
    Dependências: [2] e [3] concluídos | Risco: baixo

[5] Remover SCREEN_REQUESTED do bus (VEHICLE_STATE_CHANGED: ver Plano 04)
    Arquivos: app_events.py, bus.py
    Dependências: [3], [4] concluídos + grep confirmando zero consumidores | Risco: baixo

[6] Revisar main.py
    Arquivo: main.py
    Dependências: [1] e [5] concluídos | Risco: baixo
```

**Sequência recomendada para commit limpo:** `[1] → [2] → [3] → [4] → [5] → [6]`

**Executar junto com Plano 04 (Passo 4):** a migração de `vehicle_state.emitter.connect` em `VeCalibrationScreen` deve ser feita no mesmo PR que os passos [3]-[5] deste plano.

---

## 9. Invariantes Preservadas

- `vehicle_state.emitter` (pyqtSignal direto em `VehicleState`) permanece — não vai para o bus global
- `ECU_COMMAND_REQUESTED`, `ALARM_FIRED`, `SIGNALS_RECEIVED` permanecem no bus sem alteração
- `on_activated()` / `on_deactivated()` continuam sendo o lugar exclusivo para subscrever/cancelar eventos de domínio
- Teclado continua sendo roteado via `pyqtSignal` em `AppWindow` direto para telas, sem passar pelo bus
- `AppWindow` é o único lugar que conhece os nomes de tela e a topologia de navegação
