# Plano 02 — Refatoração do Pipeline de Dados

## Objetivo

Reestruturar o pipeline de dados para que:
- A ECU emita eventos tipados por frame (`MESS_FRAME` com campo `frame=1/2/3`) e por resposta de comando (`COMMAND_RESPONSE`)
- `LogWriter` acumule frame 1 e 2 antes de gravar uma linha CSV
- `SignalProcessor` processe frames individualmente e emita `SIGNALS_RECEIVED` com dados parciais
- `AlarmProcessor` alimente `VehicleState` com estado de alarme e não emita eventos redundantes
- Telas se inscrevam apenas nos eventos que precisam

---

## Estado Atual e Problemas

| Componente | Problema |
|------------|---------|
| `EcuConnectionSerial` | Acumula D01+D02 e emite string combinada única |
| `LogWriter.write()` | Filtra apenas `#D01`, ignora D02; cabeçalho CSV hardcoded |
| `SignalProcessor` | Filtra por `#D01`, processa string combinada, emite todos os sinais de uma vez |
| `AlarmProcessor` | Correto em popular `VehicleState`, mas ainda emite `AlarmFiredEvent` redundantemente |
| Telas | `DashboardScreen` recebe todos os sinais; `VeCalibrationScreen` faz pull em timer |

---

## Pipeline Proposto

```
ECU (Protocol Layer — Plano 01)
    │
    ├── MessFrameEvent(frame=1, line="#D01;...")  ──► LogWriter._on_frame1()
    │                                             ──► SignalProcessor._process_frame1()
    │
    ├── MessFrameEvent(frame=2, line="#D02;...")  ──► LogWriter._on_frame2()
    │                                             ──► SignalProcessor._process_frame2()
    │
    └── CommandResponseEvent(cmd, data)           ──► VehicleState._on_command_response()
```

---

## 1. LogWriter — Acumulação de Frames

### Comportamento Atual

`write(line)` filtra `#D01`, grava imediatamente com timestamp e event mark.

### Comportamento Novo

```python
class LogWriter(QObject):
    def __init__(self, ...):
        self._frame1: str | None = None
        self._frame2: str | None = None
        self._event_pending = False
    
    @Slot(int, str)
    def on_mess_frame(self, frame_num: int, line: str) -> None:
        if frame_num == 1:
            self._frame1 = line
        elif frame_num == 2:
            self._frame2 = line
        
        if self._frame1 and self._frame2:
            self._write_row(self._frame1, self._frame2)
            self._frame1 = None
            self._frame2 = None
    
    def _write_row(self, frame1: str, frame2: str) -> None:
        timestamp = int(time.time() * 1000)
        event = "MARK" if self._event_pending else ""
        self._event_pending = False
        
        parts1 = frame1.split(";")[1:]   # remove "#D01"
        parts2 = frame2.split(";")[1:]   # remove "#D02"
        
        self.task.emit([timestamp, event] + parts1 + parts2)
    
    def set_event_pending(self) -> None:
        self._event_pending = True
```

**Cabeçalho CSV:** Gerado dinamicamente uma vez na inicialização do Worker, iterando `Signal` em ordem de índice para mapear colunas.

**Subscrição (main.py):**
```python
event_bus.subscribe(AppEventType.MESS_FRAME, 
    lambda e: log_writer.on_mess_frame(e.frame, e.line))
```

---

## 2. SignalProcessor — Processamento por Frame

### Comportamento Atual

Aguarda string combinada `#D01;...;#D02;...`, itera todos os `Signal`, emite dict completo.

### Comportamento Novo

```python
class SignalProcessor(QObject):
    def __init__(self):
        super().__init__()
        self._partial: dict[Signal, ParsedSignal] = {}
    
    @Slot(int, str)
    def on_mess_frame(self, frame_num: int, line: str) -> None:
        """Processa cada frame individualmente."""
        parts = line.split(";")
        new_data: dict[Signal, ParsedSignal] = {}
        
        for signal in Signal:
            if signal.value.get("calculated", False):
                continue  # Calculados depois
            idx = signal.value.get("index")
            if idx is None or idx >= len(parts):
                continue
            try:
                raw = parts[idx]
                value = signal.value["converter"](raw)
                new_data[signal] = ParsedSignal(signal, raw, value)
            except Exception:
                logger.exception("Erro ao processar sinal %s", signal)
        
        # Atualiza partial com dados novos
        self._partial.update(new_data)
        
        # Processa calculados com o que temos disponível
        for signal in Signal:
            if not signal.value.get("calculated", False):
                continue
            try:
                raw = signal.value["value"](self._partial)
                new_data[signal] = ParsedSignal(signal, raw, raw)
                self._partial[signal] = new_data[signal]
            except Exception:
                pass  # Dependência ausente, tenta no próximo frame
        
        if new_data:
            vehicle_state.update(new_data)                          # Atualiza estado (ver Plano 04)
            event_bus.publish(SignalsReceivedEvent(data=new_data))
```

**Nota:** `signal_processor.emitter = Signal(dict)` e o método `process_line()` são removidos nesta refatoração. `AppWindow` recebe `signal_processor` no construtor (`main.py` linha 67) — verificar se `AppWindow.__init__` usa `emitter` e remover a dependência se necessário.

**Entrega via `QueuedConnection`:** A subscrição via `event_bus.subscribe` usa `pyqtSignal`, que entrega com `QueuedConnection` implícita. A thread-safety do `LogWriter.Worker` é preservada.

**Subscrição (main.py):**
```python
event_bus.subscribe(AppEventType.MESS_FRAME,
    lambda e: signal_processor.on_mess_frame(e.frame, e.line))
```

### Nota sobre índices de frame

O `Signal` enum deve ser anotado com o frame de origem **e com o índice local ao frame** para que o processador filtre corretamente.

```python
RPM = {
    "name": "RPM",
    "frame": 1,        # Novo campo: 1 = #D01, 2 = #D02
    "index": 1,        # Índice DENTRO do frame (posição 0 = prefixo "#D01")
    ...
}
```

**Pré-requisito de execução:** Levantar o número de campos de `#D01` (ex: 17 campos) e `#D02` antes de recalcular os índices locais. Os índices absolutos atuais que ficam acima do limite do frame 1 pertencem ao frame 2 com offset subtraído.

O `SignalProcessor` deve **filtrar por frame** antes de processar (não apenas silenciosamente pular):

```python
for signal in Signal:
    if signal.value.get("frame") != frame_num:
        continue   # Pertence a outro frame — ignora explicitamente
    ...
```

**Ação necessária:** Mapear cada sinal ao seu frame e recalcular índices locais em `signal.py`.

---

## 3. AlarmProcessor — Integração com VehicleState

### Comportamento Atual

- Subscreve `SIGNALS_RECEIVED` → processa → chama `vehicle_state.set_alarm()` → publica `AlarmFiredEvent`
- Loop thread lê `vehicle_state.is_any_alarm_firing()` para controlar áudio

Isso está **essencialmente correto**. O `AlarmFiredEvent` serve para a `DashboardScreen` piscar os cards de alarme.

### Ajuste Necessário

Garantir que `AlarmProcessor` receba `SignalsReceivedEvent` com dados **parciais** corretamente:

```python
def process_signals(self, signals: dict[Signal, ParsedSignal]) -> None:
    now = time.time()
    for signal, data in signals.items():
        alarm = signal.value.get("alarm", {})
        if not alarm.get("enabled", False):
            vehicle_state.set_alarm(signal, False)
            continue
        
        in_alarm = self._check_in_alarm(alarm, data)
        vehicle_state.set_alarm(signal, in_alarm)
        
        if in_alarm:
            duration = alarm.get("duration_s", 2.0)
            until = self._alarm_until.get(signal, 0.0)
            if now >= until:
                new_until = now + duration
                self._alarm_until[signal] = new_until
                event_bus.publish(AlarmFiredEvent(signal=signal, until=new_until))
```

Sem grandes mudanças — já funciona com dados parciais porque itera `signals.items()`.

### Estado de Alarme em VehicleState

A correção de `set_alarm()` para limpar o estado imediatamente quando `active=False` está definida no **Plano 04** (seção `set_alarm()` — Limpa Estado Imediatamente). O `AlarmProcessor` não precisa ser alterado além da tolerância a dados parciais descrita acima.

---

## 4. Telas — Subscrições Limpas

### DashboardScreen

Mantém a subscrição atual em `SIGNALS_RECEIVED`. Já tolera dados parciais (`parsed_data.get(signal)` retorna `None` se ausente).

Subscrição em `ALARM_FIRED` também permanece.

### VeCalibrationScreen

Atualmente usa timer de 100ms para pull de `vehicle_state.get(signal)`. Isso pode continuar enquanto o restante é refatorado — é uma tela secundária.

Futuramente: subscrever `SIGNALS_RECEIVED` para top bar (remover o timer).

---

## Arquivos a Criar/Modificar

| Ação | Arquivo | Mudança |
|------|---------|---------|
| **Modificar** | `app/log_writer/log_writer.py` | Método `on_mess_frame()`, acumula frame 1+2 |
| **Modificar** | `app/masterinjection/signal_processor.py` | `on_mess_frame()`, processa por frame, emite parcial |
| **Modificar** | `app/masterinjection/signal.py` | Adiciona campo `"frame": 1 ou 2` por sinal; recalcula índices locais |
| **Modificar** | `app/alarm/processor.py` | Garantir `alarm.get("enabled", False)` antes de `set_alarm` |
| **Modificar** | `app/ui/window.py` | Remover dependência de `signal_processor.emitter` se presente |
| **Modificar** | `main.py` | Atualiza subscrições para `MESS_FRAME`; remove conexões de `emitter` legado; remove subscriber redundante `vehicle_state.update(e.data)` (ver Plano 04) |

---

## Ordem de Execução

1. Adicionar campo `"frame"` e recalcular índices locais em `signal.py` (sem quebrar nada ainda — índices antigos permanecem como fallback)
2. Modificar `LogWriter` para `on_mess_frame()` com acumulação de frames
3. Modificar `SignalProcessor` para `on_mess_frame()` e emissão parcial
4. Corrigir `set_alarm()` para limpar estado imediatamente
5. Atualizar `main.py` com novas subscrições
6. Remover conexões diretas de `emitter` que eram usadas antes

---

## Critérios de Aceite

- [ ] LogWriter grava uma linha CSV por par (frame1 + frame2), não por frame individual
- [ ] SignalProcessor emite `SIGNALS_RECEIVED` com apenas os sinais do frame recebido (filtro explícito por `"frame"`)
- [ ] SignalProcessor chama `vehicle_state.update(new_data)` a cada processamento (ver Plano 04)
- [ ] Sinais calculados são recomputados quando suas dependências chegam (mesmo que em frames diferentes)
- [ ] `signal_processor.emitter` legado e `process_line()` removidos; `AppWindow` não depende deles
- [ ] `DashboardScreen` continua funcionando sem alteração (dados parciais já são tolerados)
- [ ] Nenhum índice de sinal quebra após recalcular índices locais por frame
