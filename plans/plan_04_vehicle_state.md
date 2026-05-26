# Plano 04 — Refatoração do VehicleState

## Objetivo

Tornar `VehicleState` a **fonte da verdade em tempo real** do estado do veículo, garantindo que:
- Últimos valores de sinais estejam sempre presentes e atualizados
- Estado de alarmes seja consultável em tempo real
- Estado do lambda loop esteja disponível
- Dados do mapa VE e breakpoints continuem acessíveis
- Nenhuma tela precise de polling por timer para ler sinais (event-driven quando possível)

---

## Estado Atual e Problemas

| Problema | Descrição |
|---------|-----------|
| `update()` não funciona | Declarado e chamado em `main.py`, mas o subscriber nunca dispara corretamente; telas usam dados direto do event_bus |
| Sinais sem notificação | Apenas breakpoints/mapa emitem eventos via `vehicle_state.emitter`; sinais dinâmicos não |
| Dupla fonte de alarmes | `VehicleState._alarm_timestamps` e `AlarmProcessor._alarm_until` rastreiam independentemente |
| `set_alarm(False)` não limpa | Alarme desativado espera timeout natural (2s) para `is_alarm_firing()` retornar False |
| Sem timestamp de atualização | Impossível saber se dados são frescos ou obsoletos |
| BUG: validação de ve_idx | `if 0 > ve_idx > 15` sempre False — nunca valida |
| `VehicleStateChangeEvent` | Classe simples sem type hints, contrasta com dataclasses do restante |

---

## Novo Contrato de VehicleState

```
VehicleState é a fonte de verdade de leitura para todo estado do veículo.
Quem escreve: SignalProcessor (sinais), AlarmProcessor (alarmes), 
              EcuProtocol (breakpoints/mapa), LambdaLoopStateProcessor (lambda loop).
Quem lê: Telas, LambdaToggle, AlarmProcessor.run().
```

---

## Mudanças na Classe

### Novos Campos

```python
class VehicleState:
    def __init__(self):
        self._lock = threading.RLock()
        
        # Sinais dinâmicos
        self._signals: dict[Signal, ParsedSignal] = {}
        self._signal_last_updated: dict[Signal, float] = {}   # NOVO: timestamp por sinal
        
        # Alarmes
        self._alarm_active: dict[Signal, bool] = {}            # NOVO: estado booleano limpo
        self._alarm_timestamps: dict[Signal, float] = {}       # Mantido: para is_alarm_firing()
        
        # Lambda loop
        self._lambda_loop_closed: bool = False
        
        # Dados estáticos da ECU
        self._rpm_breakpoints: list[int] = []
        self._map_breakpoints: list[int] = []
        self._ve_map: list[list[int]] = []
        
        # Emitter (inicialização direta, não lazy)
        self._emitter = _VehicleStateEmitter()
```

### `update()` — Corrigido e Funcional

```python
def update(self, parsed_data: dict[Signal, ParsedSignal]) -> None:
    """Atualiza sinais e emite SIGNAL_CHANGED para cada sinal novo/alterado."""
    now = time.time()
    changed: dict[Signal, ParsedSignal] = {}
    
    with self._lock:
        for signal, data in parsed_data.items():
            prev = self._signals.get(signal)
            self._signals[signal] = data
            self._signal_last_updated[signal] = now
            # Notifica apenas se valor mudou (evita ruído)
            if prev is None or prev.raw != data.raw:
                changed[signal] = data
    
    if changed:
        # Emite um único evento com todos os sinais alterados
        self._emitter.signals_changed.emit(changed)
```

### `set_alarm()` — Limpa Estado Imediatamente

```python
def set_alarm(self, signal: Signal, active: bool) -> None:
    with self._lock:
        self._alarm_active[signal] = active
        if active:
            self._alarm_timestamps[signal] = time.time()
        else:
            self._alarm_timestamps.pop(signal, None)   # Limpa imediatamente

def is_alarm_firing(self, signal: Signal) -> bool:
    with self._lock:
        return self._alarm_active.get(signal, False)

def is_any_alarm_firing(self) -> bool:
    with self._lock:
        return any(self._alarm_active.values())
```

### `set_ve_map()` — Bug Corrigido

```python
def set_ve_map(self, ve_line: list[int], ve_idx: int) -> None:
    with self._lock:
        if ve_idx < 0 or ve_idx > 15:        # Corrigido de: if 0 > ve_idx > 15
            logger.warning("ve_idx inválido: %d", ve_idx)
            return
        if len(ve_line) != 16:
            logger.warning("ve_line com %d valores, esperado 16", len(ve_line))
            return
        while len(self._ve_map) <= ve_idx:
            self._ve_map.append([])
        self._ve_map[ve_idx] = list(ve_line)
    self._emitter.state_changed.emit(VehicleStateChangeEvent(EventType.FUEL_MAP, (ve_idx, ve_line)))
```

---

## Atualização do Emitter

### Atual

`vehicle_state.emitter` emite `VehicleStateChangeEvent` para breakpoints e mapa VE (via `state_changed = pyqtSignal(object)`).

### Novo

Adicionar sinal dedicado para sinais dinâmicos:

```python
# app/state/state.py (ou app/state/emitter.py separado)
class _VehicleStateEmitter(QObject):
    state_changed  = pyqtSignal(object)   # VehicleStateChangeEvent (breakpoints, mapa)
    signals_changed = pyqtSignal(dict)    # dict[Signal, ParsedSignal] — sinais alterados
```

### VehicleStateChangeEvent — Tipado

```python
# app/state/event.py

class EventType(Enum):
    MAP_BREAKPOINTS  = 0
    RPM_BREAKPOINTS  = 1
    FUEL_MAP         = 3
    SIGNAL_CHANGED   = 4   # NOVO (opcional — coberto por signals_changed)

@dataclass
class VehicleStateChangeEvent:
    type_: EventType
    args: tuple
```

---

## Integração com CommandResponseEvent (Breakpoints e Mapa VE)

Após o Plano 01, `EcuProtocol` não mais atualiza `vehicle_state` diretamente. Em vez disso, emite `CommandResponseEvent(command, data)` via `EcuConnectionThread.command_response_received`. Quem consome esse evento e atualiza o `VehicleState` é o `main.py`:

```python
def _on_command_response(event: CommandResponseEvent) -> None:
    cmd = event.command
    data = event.data
    if cmd == EcuCommand.RPM_BREAKPOINTS:
        vehicle_state.set_rpm_breakpoints(data["breakpoints"])
    elif cmd == EcuCommand.MAP_BREAKPOINTS:
        vehicle_state.set_map_breakpoints(data["breakpoints"])
    elif cmd.name.startswith("VE_ROW_"):
        row_idx = int(cmd.name.split("_")[-1]) - 1
        vehicle_state.set_ve_map(data["values"], row_idx)

event_bus.subscribe(AppEventType.COMMAND_RESPONSE,
    lambda e: _on_command_response(e))
```

O campo `data` é estruturado pelo `parse_response()` do serializer correspondente (ver Plano 01):
- `BreakpointsSerializer.parse_response()` → `{"breakpoints": list[int]}`
- `VeRowSerializer.parse_response()` → `{"values": list[int]}`

Adicionar `main.py` à lista de arquivos a modificar neste plano.

---

## Integração com SignalProcessor

`SignalProcessor` deve chamar `vehicle_state.update()` além de publicar `SIGNALS_RECEIVED`:

```python
# signal_processor.py
def on_mess_frame(self, frame_num: int, line: str) -> None:
    # ... processa sinais em new_data ...
    
    if new_data:
        vehicle_state.update(new_data)                           # Atualiza estado
        event_bus.publish(SignalsReceivedEvent(data=new_data))  # Notifica demais
```

Com isso, o subscriber em `main.py` (`lambda e: vehicle_state.update(e.data)`) pode ser removido.

---

## Integração com Telas

### VeCalibrationScreen — Remover Timer de Top Bar

Atualmente: timer 100ms chama `_update_top_bar()` que faz pull de `vehicle_state.get(signal)`.

Nova abordagem (opcional nesta fase):

```python
def on_activated(self):
    # ...
    vehicle_state.emitter.signals_changed.connect(self._on_signals_changed)

def on_deactivated(self):
    # ...
    vehicle_state.emitter.signals_changed.disconnect(self._on_signals_changed)

def _on_signals_changed(self, changed: dict[Signal, ParsedSignal]) -> None:
    for signal, card in self._top_bar_labels.items():
        if signal in changed:
            card.set_value(changed[signal].value_str)
```

**Nota:** O timer de highlight (que calcula a célula do mapa destacada) pode permanecer, pois envolve cálculo de interpolação que pode ser caro demais para cada sinal recebido.

### DashboardScreen — Sem Mudança Necessária

Já usa `SIGNALS_RECEIVED` event-driven. Pode opcionalmente migrar para `vehicle_state.emitter.signals_changed` no futuro.

---

## Limpeza de Código Morto

| Item | Ação |
|------|------|
| `vehicle_state.get_all()` | Manter — útil para dump de estado |
| Subscriber `vehicle_state.update(e.data)` em main.py (linha 46-49) | Remover — atualização agora feita por `SignalProcessor` diretamente |
| `VEHICLE_STATE_CHANGED` no event_bus | Remover (ver Plano 03) |
| `LambdaLoopStateProcessor` em `app/state/processors/` | Manter, já está correto |

---

## Arquivos a Criar/Modificar

| Ação | Arquivo | Mudança |
|------|---------|---------|
| **Modificar** | `app/state/state.py` | Novos campos; `update()` funcional com emissão; `set_alarm()` limpa; bug `set_ve_map()` corrigido; emitter com `signals_changed` |
| **Modificar** | `app/state/event.py` | `VehicleStateChangeEvent` com `@dataclass`; adiciona `SIGNAL_CHANGED` ao `EventType` |
| **Modificar** | `app/masterinjection/signal_processor.py` | Chama `vehicle_state.update(new_data)` após processar |
| **Modificar** | `main.py` | Remove subscriber redundante de `SIGNALS_RECEIVED → vehicle_state.update`; adiciona subscriber de `COMMAND_RESPONSE → vehicle_state.set_*` |
| **Modificar** | `app/ui/ve_calibration/screen.py` | Conecta `vehicle_state.emitter.signals_changed` para top bar (remove timer de top bar) |

---

## Ordem de Execução

1. Corrigir bug `set_ve_map()` (mudança segura, sem dependências)
2. Corrigir `set_alarm()` para limpar estado imediatamente
3. Adicionar `signal_last_updated` e tornar `update()` funcional com emissão
4. Adicionar `signals_changed` ao emitter
5. Atualizar `SignalProcessor` para chamar `vehicle_state.update()`
6. Remover subscriber redundante de `main.py`
7. Atualizar `VeCalibrationScreen` top bar para usar `signals_changed` em vez de timer

---

## Critérios de Aceite

- [ ] `vehicle_state.get(Signal.RPM)` retorna o último valor recebido da ECU (não `None` após a primeira leitura)
- [ ] `vehicle_state.is_alarm_firing(signal)` retorna `False` imediatamente quando alarme é resolvido
- [ ] `vehicle_state.is_any_alarm_firing()` retorna `False` imediatamente quando todos os alarmes são resolvidos
- [ ] `set_ve_map()` não aceita `ve_idx` inválido (0 > idx > 15 corrigido)
- [ ] `VeCalibrationScreen` top bar atualiza sem timer de polling
- [ ] `vehicle_state.emitter.signals_changed` é emitido apenas quando sinais efetivamente mudam (não em cada frame idêntico)
- [ ] Nenhuma tela precisa importar `SignalProcessor` ou `AlarmProcessor` para obter dados de sinal
