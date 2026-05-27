# Plano 04 — VehicleState: Consulta em Tempo Real e Estado Completo

## Objetivo

Transformar `VehicleState` em fonte de verdade do estado do veículo em tempo real:
- Corrigir bug que impede alarmes de serem desativados
- Reestruturar armazenamento de alarme para estado booleano + timestamp
- Remover `VEHICLE_STATE_CHANGED` do EventBus global (nunca foi publicado)
- Mover conexão do `emitter` para `on_activated`/`on_deactivated` em `VeCalibrationScreen`
- Corrigir emissão de signal dentro de lock (potencial bloqueio de UI)

---

## Análise do Estado Atual

**Bug confirmado em `set_alarm`** (`state.py:57-60`):
quando `active=False` a chave nunca é removida de `_alarm_timestamps`. Isso faz `is_alarm_firing` retornar `True` para sempre após o primeiro alarme, e `is_any_alarm_firing` nunca retornar `False` — o som de alarme jamais para.

**`VEHICLE_STATE_CHANGED` nunca é publicado via bus:**
- `AppEventType.VEHICLE_STATE_CHANGED` existe em `app_events.py` e `bus.py`
- O mecanismo real é `vehicle_state.emitter` (pyqtSignal em `_VehicleStateEmitter`)
- `VeCalibrationScreen` conecta-se diretamente via `vehicle_state.emitter.connect(...)` no `__init__`
- A dataclass `VehicleStateChangedEvent` em `app_events.py` nunca é instanciada

**Emissão de signal dentro de lock:**
`set_rpm_breakpoints`, `set_map_breakpoints` e `set_ve_map` emitem `vehicle_state.emitter` dentro do bloco `with self._lock`. Como é `RLock`, não há deadlock reentrante, mas se o slot na main thread tentar acessar `VehicleState` com lock (ex: `get_rpm_breakpoints()`), haverá bloqueio de UI enquanto a thread serial segura o lock.

---

## 1. Passo 1 — Corrigir Bug `set_alarm` e Reestruturar Estado de Alarme

Substituir `_alarm_timestamps: dict` por dois campos com semânticas distintas:

**`app/state/state.py`:**

```python
class VehicleState:

    def __init__(self):
        self._lock = threading.RLock()
        self._signals: dict = {}
        self._alarm_active: dict = {}      # signal → bool (estado atual)
        self._alarm_last_fired: dict = {}  # signal → float (último timestamp ativo)
        self._lambda_loop_closed: bool = False
        self._rpm_breakpoints: list[int] = [0 for _ in range(16)]
        self._map_breakpoints: list[int] = [0 for _ in range(16)]
        self._ve_map: list[list[int]] = [[0 for _ in range(16)] for _ in range(16)]

    def set_alarm(self, signal, active: bool) -> None:
        with self._lock:
            self._alarm_active[signal] = active
            if active:
                self._alarm_last_fired[signal] = time.time()
        # Quando active=False: _alarm_active[signal] = False
        # _alarm_last_fired preserva o último timestamp para auditoria se necessário

    def is_alarm_firing(self, signal) -> bool:
        """Retorna True se o sinal está ATUALMENTE em alarme."""
        with self._lock:
            return self._alarm_active.get(signal, False)

    def is_any_alarm_firing(self) -> bool:
        """Retorna True se há qualquer alarme ativo no momento."""
        with self._lock:
            return any(self._alarm_active.values())
```

**Impacto nos consumidores:**

| Consumidor | Método usado | Mudança necessária |
|-----------|-------------|-------------------|
| `AlarmProcessor.run()` | `is_any_alarm_firing()` | Nenhuma — semântica preservada, agora correta |
| `AlarmProcessor._handle_status()` | `is_any_alarm_firing()` | Nenhuma |
| `DashboardScreen.fire_field_alarm()` | `is_alarm_firing(signal)` | Nenhuma — agora retorna estado real |
| `DashboardScreen.update_display()` | `is_alarm_firing(signal)` | Nenhuma |

---

## 2. Passo 2 — Corrigir Emissão de Signal Fora do Lock

**`app/state/state.py`** — para `set_rpm_breakpoints`, `set_map_breakpoints`, `set_ve_map`:

```python
# ANTES (problemático):
def set_rpm_breakpoints(self, breakpoints: list[int]) -> None:
    with self._lock:
        self._rpm_breakpoints = breakpoints
        self.emitter.emit(VehicleStateChangeEvent(EventType.RPM_BREAKPOINTS, [breakpoints]))
        #                  ^^ emissão com lock adquirido

# DEPOIS (correto):
def set_rpm_breakpoints(self, breakpoints: list[int]) -> None:
    with self._lock:
        self._rpm_breakpoints = breakpoints
    # Emit FORA do lock — evita bloqueio da UI se o slot acessar vehicle_state
    self.emitter.emit(VehicleStateChangeEvent(EventType.RPM_BREAKPOINTS, [breakpoints]))
```

Aplicar o mesmo padrão para `set_map_breakpoints` e `set_ve_map`.

---

## 3. Passo 3 — Remover `VEHICLE_STATE_CHANGED` do EventBus Global

**Verificar antes de remover:**
```bash
grep -rn "VEHICLE_STATE_CHANGED\|VehicleStateChangedEvent" app/
# Deve retornar apenas app_events.py e bus.py — zero consumidores
```

**`app/event/app_events.py`** — remover:
```python
# REMOVER da enum:
VEHICLE_STATE_CHANGED = auto()

# REMOVER a dataclass:
@dataclass(frozen=True)
class VehicleStateChangedEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.VEHICLE_STATE_CHANGED, init=False)
    change_type: Any = None
    args: tuple = field(default_factory=tuple)
```

**`app/event/bus.py`** — remover:
```python
# REMOVER de _SIGNAL_ATTR:
AppEventType.VEHICLE_STATE_CHANGED: "vehicle_state_changed",

# REMOVER de _EventBusQObject:
vehicle_state_changed = pyqtSignal(object)
```

**`app/state/event.py` e `_VehicleStateEmitter`:** manter — ainda são o mecanismo real de notificação usado por `VeCalibrationScreen`.

---

## 4. Passo 4 — Mover Conexão do `emitter` para `on_activated`/`on_deactivated`

Problema: `vehicle_state.emitter.connect(self._on_vehicle_state_event)` no `__init__` de `VeCalibrationScreen` é permanente. O handler é chamado mesmo quando a tela está inativa.

**`app/ui/ve_calibration/screen.py`:**

```python
def __init__(self):    # sem close_fn
    super().__init__()
    # REMOVER: vehicle_state.emitter.connect(self._on_vehicle_state_event)
    # ... resto do __init__ igual ...

def on_activated(self):
    self._highlight_timer.start(100)
    vehicle_state.emitter.connect(self._on_vehicle_state_event)
    self._load_initial_state()   # carrega estado já disponível (handshake já ocorreu)

def on_deactivated(self):
    self._highlight_timer.stop()
    try:
        vehicle_state.emitter.disconnect(self._on_vehicle_state_event)
    except TypeError:
        pass
    super().on_deactivated()

def _load_initial_state(self):
    """Carrega breakpoints e VE map do vehicle_state no momento da ativação.

    Necessário porque o handshake ocorre antes da tela ser visitada — os dados
    já estão no vehicle_state mas o emitter não vai re-emiti-los.
    """
    rpm_bp = vehicle_state.get_rpm_breakpoints()
    map_bp = vehicle_state.get_map_breakpoints()
    ve = vehicle_state.get_ve_map()
    if any(v != 0 for v in rpm_bp):
        self._on_vehicle_state_event(
            VehicleStateChangeEvent(EventType.RPM_BREAKPOINTS, [rpm_bp])
        )
    if any(v != 0 for v in map_bp):
        self._on_vehicle_state_event(
            VehicleStateChangeEvent(EventType.MAP_BREAKPOINTS, [map_bp])
        )
    for row_idx, row_data in enumerate(ve):
        if any(v != 0 for v in row_data):
            self._on_vehicle_state_event(
                VehicleStateChangeEvent(EventType.FUEL_MAP, [row_idx, row_data])
            )
```

---

## 5. Análise de Thread Safety

| Método | Chamado de | Lock | Risco |
|--------|-----------|------|-------|
| `update(parsed_data)` | Main thread (via pyqtSignal) | OK |  |
| `set_alarm()` | Main thread (AlarmProcessor) | OK |  |
| `is_alarm_firing()` | Main thread (DashboardScreen) | OK |  |
| `is_any_alarm_firing()` | Worker thread (AlarmProcessor.run) | OK |  |
| `set_lambda_loop_state()` | Main thread | OK |  |
| `set_rpm_breakpoints()` | Thread serial (EcuSession) | **RISCO** — emit dentro do lock (corrigido no Passo 2) |
| `set_map_breakpoints()` | Thread serial | **RISCO** — idem |
| `set_ve_map()` | Thread serial | **RISCO** — idem |
| `get_rpm_breakpoints()` | Main thread (VeCalibrationScreen timer) | OK |  |

---

## 6. Verificar `vehicle_state.update()` (Limpeza Opcional)

```bash
grep -rn "vehicle_state.update" app/
```

Se retornar vazio (possível — o wiring legado via `emitter(dict)` pode já estar inativo), `VehicleState.update()` pode ser removido em iteração futura. Não é bloqueante para este plano.

---

## 7. Passos de Implementação

```
[1] Corrigir bug set_alarm + reestruturar _alarm_active/_alarm_last_fired
    Arquivo: app/state/state.py
    Dependências: nenhuma
    Risco: baixo — assinatura pública preservada

[2] Corrigir emissão fora do lock em set_rpm_breakpoints, set_map_breakpoints, set_ve_map
    Arquivo: app/state/state.py
    Dependências: nenhuma (pode ser feito junto com [1])
    Risco: baixo

[3] Remover VEHICLE_STATE_CHANGED do EventBus
    Arquivos: app/event/app_events.py, app/event/bus.py
    Dependências: confirmar zero consumidores com grep
    Risco: baixo — nunca foi publicado via bus

[4] Mover vehicle_state.emitter.connect para on_activated/on_deactivated
    Arquivo: app/ui/ve_calibration/screen.py
    Dependências: nenhuma (pode ser feito independentemente)
    Risco: baixo — adicionar _load_initial_state para não perder dados do handshake

[5] (opcional) Remover vehicle_state.update() se não tiver consumidores
    Arquivo: app/state/state.py
    Dependências: grep confirmando ausência de uso
```

**Ordem recomendada:** `[1+2]` (mesmo commit) → `[3]` → `[4]` → `[5]` (opcional)

---

## 8. Resumo de Arquivos Impactados

| Arquivo | Mudança |
|---------|---------|
| `app/state/state.py` | Bug fix `set_alarm`; `_alarm_active`/`_alarm_last_fired`; emit fora do lock |
| `app/event/app_events.py` | Remover `VEHICLE_STATE_CHANGED` e `VehicleStateChangedEvent` |
| `app/event/bus.py` | Remover `vehicle_state_changed` signal e entrada em `_SIGNAL_ATTR` |
| `app/ui/ve_calibration/screen.py` | Mover `emitter.connect` para `on_activated`; `on_deactivated` desconecta; `_load_initial_state` |
| `app/state/event.py` | Manter sem alteração |

---

## 9. Notas Finais

**`VeMapState.__init__`** lê `vehicle_state` na construção. Se o handshake ainda não ocorreu, `rpm_axis` e `map_axis` serão listas de zeros. O `_load_initial_state` no Passo 4 mitiga isso ao recarregar na ativação da tela.

**`DashboardScreen.update_display()`** recalcula a condição de alarme localmente (linhas 181-190) redundando com `AlarmProcessor`. Após o Passo 1, `is_alarm_firing()` passa a ser booleano direto — a lógica duplicada na dashboard pode ser simplificada em iteração futura, mas não é bloqueante.
