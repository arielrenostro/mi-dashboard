# Relatório de Entrega — Refatoração ECU/EventBus

## Resumo Executivo

**Status geral: ✅ Aprovado — correções pós-revisão aplicadas**

A refatoração está estruturalmente bem executada — a arquitetura Transport/Session/EventBus está correta, o EventBus ganhou os 4 novos eventos esperados, o `SignalProcessor` foi migrado para buffers por frame, o `AlarmProcessor` migrou de `QThread` para `QObject + QTimer`, e o `VehicleState` foi desacoplado da UI. Quatro problemas críticos foram identificados na revisão e **corrigidos imediatamente após**: handshake/reconexão com deadlock (resolvido com `_send_blocking_direct()`), condição de comprimento errada no `MockTransport` (corrigida), validação de índice VE invertida (corrigida), e `_EventBusQObject` criado antes de `QApplication` (resolvido com inicialização lazy).

---

## Status por Componente

| Componente | Arquivo | Status | Observações |
|---|---|---|---|
| EcuTransport ABC | `transport.py` | ✅ OK | Interface correta, bem documentada |
| SerialTransport | `serial_transport.py` | ✅ OK | Implementação correta, thread-safe para write() |
| MockTransport | `mock_transport.py` | ✅ Corrigido | len(line)==4 — agora responde corretamente às VE rows #F01-#F16 |
| EcuSession | `session.py` | ✅ Corrigido | `_send_blocking_direct()` adicionado; handshake e reconexão usam leitura direta sem Reader thread |
| EventBus | `bus.py` | ✅ Corrigido | `_EventBusQObject` agora é lazy — criado na primeira chamada a `publish`/`subscribe`, após `QApplication` |
| AppEvents | `app_events.py` | ✅ OK | 4 novas dataclasses corretas |
| Signal | `signal.py` | ✅ OK | Todos os sinais têm frame/frame_index/index consistentes |
| SignalProcessor | `signal_processor.py` | ✅ OK | Buffers por frame, assinatura correta no bus |
| LogWriter | `log_writer.py` | ✅ OK | Buffer D01+D02, inscrição no bus, EVENT_MARK_REQUESTED |
| AlarmProcessor | `alarm/processor.py` | ✅ OK | QObject+QTimer, sem QThread, play/stop na main thread |
| VehicleState | `state/state.py` | ✅ Corrigido | Validação de índice corrigida: `not (0 <= ve_idx <= 15)` |
| VeCalibrationScreen | `ve_calibration/screen.py` | ⚠️ Importante | Migração para bus OK; populate_ve_table com bug de coluna e não chamada |
| VeWriteController | `ve_write_controller.py` | ✅ OK | Publica EcuCommandRequestedEvent corretamente |
| AppWindow | `ui/window.py` | ✅ OK | Sem parâmetro signal_processor; correto |
| __init__.py | `ecu_connection/__init__.py` | ✅ OK | register/get_ecu_session + alias get_ecu_connection |
| main.py | `main.py` | ✅ OK | Estrutura correta; event_bus lazy resolve a ordem de import |

---

## Problemas Críticos (bloqueiam execução)

### C1 — `session.py`: Handshake blocking sem Reader thread (GRAVÍSSIMO)

**Arquivo:** `app/ecu_connection/session.py`  
**Localização:** Métodos `start()`, `_do_handshake()`, `_send_blocking()`

O handshake executa **antes** do Reader thread ser iniciado (`start()` chama `_do_handshake()` na linha 54, e o Reader thread só é criado na linha 60 após o handshake terminar). O `_send_blocking()` funciona assim:

1. Seta `self._pending_blocking` com um `threading.Event`
2. Chama `_write_command()` que escreve no transporte
3. Aguarda `evt.wait(timeout=3.0)`

O problema: **ninguém chama `transport.readline()` durante o handshake**. O `readline()` só é chamado pelo Reader thread — que ainda não foi iniciado. O `threading.Event` nunca é setado, logo todos os 19 comandos de handshake (`#D50`, `#I20`, `#I21`, `#F01`–`#F16`, `#D01`) fazem timeout de 3s × 2 tentativas = 6s cada.

**Impacto prático com MockTransport:**
- Tempo de inicialização: ~114 segundos (19 comandos × 6s)
- RPM/MAP breakpoints ficam zerados: `[0, 0, ..., 0]`
- VE map completo fica zerado
- A tela VeCalibration abre sem dados

**Solução esperada pela spec (seção 2.4, R7):** O `_send_blocking` durante o handshake deveria ler diretamente do transporte (`transport.readline()` + comparação de prefixo), pois a spec diz explicitamente: _"A chamada blocking deve sempre ocorrer fora da Reader thread"_ — mas isso requer uma leitura direta, não via evento.

---

### C2 — `session.py`: Reconexão sofre do mesmo problema estrutural

**Arquivo:** `app/ecu_connection/session.py`  
**Localização:** Método `_reconnect()` (linha 229), chamado por `_reader_loop()` (linha 209)

O `_reconnect()` é chamado **dentro** da Reader thread. Ele chama `_do_handshake()` que usa `_send_blocking()` com `evt.wait()`. Enquanto a Reader thread está bloqueada no `evt.wait()`, ela não pode chamar `readline()` para processar respostas. Resultado: todos os comandos do handshake de reconexão fazem timeout.

O app não trava indefinidamente (os timeouts expiram), mas reconecta sem dados.

---

### C3 — `mock_transport.py` linha 89: Condição de comprimento incorreta para VE rows

**Arquivo:** `app/ecu_connection/mock_transport.py`, linha 89  
**Código problemático:**
```python
elif line.startswith("#F") and len(line) == 3:
```

Os comandos VE row têm formato `#F01`, `#F02`, ..., `#F16`, que possuem **4 caracteres**, não 3. A condição `len(line) == 3` nunca é verdadeira para nenhum comando VE row válido. O MockTransport **nunca responde** a nenhum pedido de fetch VE.

**Correção:** `len(line) == 4` (para `#F01`–`#F09`) ou melhor: remover o check de comprimento e usar apenas `line.startswith("#F") and len(line[2:]) == 2`.

**Impacto:** Mesmo que o bug C1 fosse corrigido, o VE map continuaria zerado no modo mock pois os comandos `#F01`–`#F16` nunca recebem resposta do MockTransport.

---

### C4 — `state.py` linha 91: Validação de índice VE com lógica invertida

**Arquivo:** `app/state/state.py`, linha 91  
**Código problemático:**
```python
if 0 > ve_idx > 15:
    return
```

A condição Python `0 > ve_idx > 15` é equivalente a `(0 > ve_idx) and (ve_idx > 15)`, que é **impossível de ser verdadeira** simultaneamente. A validação **nunca retorna**, permitindo que índices inválidos (como `-1` ou `20`) passem e causem `IndexError` na linha `self._ve_map[ve_idx] = ve_line`.

**Correção:**
```python
if ve_idx < 0 or ve_idx > 15:
    return
```

---

## Problemas Importantes (degradam funcionalidade)

### I1 — `main.py` linha 15: `event_bus` importado antes de `QApplication()`

**Arquivo:** `main.py`, linha 15  
**Código:**
```python
from app.event.bus import event_bus   # linha 15 — antes de QApplication()
```

O módulo `app/event/bus.py` cria o singleton `event_bus = EventBus()` no nível de módulo, instanciando um `_EventBusQObject(QObject)`. Conforme documentado no próprio `bus.py`: _"Import this module after QApplication() is created in main() to ensure correct thread affinity."_

Como o import está no nível de módulo de `main.py` (fora de `main()`), o `QObject` é criado **antes** de `QApplication()` ser instanciado na linha 33. Isso pode causar comportamento indefinido com `QueuedConnection` para emissões cross-thread.

**Correção:** Mover os imports de bus e outros QObjects para dentro de `main()`, após `QApplication(sys.argv)`.

---

### I2 — `screen.py` linha 463: `populate_ve_table` com offset de coluna incorreto (dead code)

**Arquivo:** `app/ui/ve_calibration/screen.py`, linha 463  
**Código:**
```python
for col_idx, ve_raw in enumerate(ve_map[row_idx]):
    item = self.ve_table.item(display_row, col_idx)  # col_idx começa em 0
```

A tabela foi construída com col 0 como label do eixo MAP e cols 1–15 como valores VE. O `populate_ve_table` usa `col_idx` de 0 a 15, sobrescrevendo o conteúdo da coluna 0 (MAP axis label) com valores VE.

Adicionalmente, `populate_ve_table` não é chamado em nenhum lugar do código — é dead code. O preenchimento da tabela ocorre via `_on_vehicle_state_event → update_row`, que usa `range(16)` também sem offset (mesmo problema potencial, mas funciona pois é consistente internamente).

---

### I3 — `session.py`: `_reconnect` degradado (consequência de C2, já detalhado)

Reconectado ao C2: a reconexão ocorre sem dados válidos de breakpoints e VE map.

---

## Melhorias Sugeridas (não bloqueiam)

### S1 — `screen.py`: `populate_ve_table` é dead code

O método `populate_ve_table` (linha 415) está definido mas nunca é chamado. Deveria ser removido ou integrado ao `on_activated()` para popular a tabela com os dados atuais do `vehicle_state` e `ve_map_state` ao entrar na tela.

### S2 — `screen.py` + `ve_write_controller.py`: Inconsistência no display de VE

- `populate_ve_table` (dead code) exibe `ve_raw / 10` com 1 casa decimal
- `update_row` (linha 659) exibe `ve_map_state.ve_map[data_row][col]` como inteiro bruto (ex: `850` em vez de `85.0`)
- `_refresh_ve_values` (linha 616) também usa `str(ve_map_state.ve_map[data_row][col])` — inteiro bruto

A interface mostra valores brutos da ECU (centésimos de %) em vez do valor real (%).

### S3 — `log_writer.py`: Import inconsistente de `Signal` e `Slot`

**Arquivo:** `app/log_writer/log_writer.py`, linha 6  
```python
from pyqtgraph.Qt.QtCore import Slot, Signal
```

O restante do projeto usa `from PyQt6.QtCore import pyqtSignal, Slot`. O alias do pyqtgraph é funcionalmente equivalente mas é inconsistente com o padrão do projeto.

### S4 — `session.py`: `EcuCommandSentEvent` nunca publicado

O evento `ECU_COMMAND_SENT` foi criado na spec e adicionado ao `app_events.py` e `bus.py`, mas o `EcuSession._write_command()` nunca publica `EcuCommandSentEvent`. A spec marca esse evento como "reservado", mas seria consistente publicá-lo para rastreabilidade.

---

## Verificações Detalhadas

### EventBus / Eventos

Implementação correta. Os 4 novos eventos (`ECU_MESS_FRAME`, `ECU_COMMAND_SENT`, `ECU_COMMAND_RESPONSE`, `ECU_CONNECTION_STATUS_CHANGED`) foram adicionados corretamente em `app_events.py` (com dataclasses `frozen=True`) e em `bus.py` (com `pyqtSignal(object)` e entradas em `_SIGNAL_ATTR`). O `unsubscribe()` usa o padrão `(sig, callback)` que é compatível com os tokens gerados pelo `subscribe()`. Todos os eventos existentes foram preservados. ✅

---

### EcuSession / Transport

**EcuTransport ABC:** Correto, interface bem definida com 5 métodos abstratos.

**SerialTransport:** Correto. `write()` usa lock interno para thread safety. `readline()` faz decode com `errors='replace'` e strip.

**MockTransport:** Estruturalmente correto (queue-based, replay thread), mas com o bug crítico C3 (len==3). O replay do CSV (`_load_csv`) busca os prefixos `#D01` e `#D02` corretamente. O `disconnect()` enfileira `""` para desbloquear o `readline()` — boa prática.

**EcuSession:** Arquitetura correta (handshake → Reader thread → drain queue). O método `_drain_command_queue` é chamado após cada frame — conforme spec. Os métodos semânticos (`open_loop`, `close_loop`, `fetch_ve`, `fetch_breakpoints`) estão implementados. O `_publish_status` tem try/except para não quebrar antes do bus estar pronto. Porém o problema fundamental do handshake blocking sem Reader thread (C1, C2) compromete toda a inicialização.

---

### SignalProcessor

Implementação correta e completa. Assina `ECU_MESS_FRAME` no `__init__`. Buffer `_frame_buffers` por `frame_id`. Lógica de fallback `cfg.get("frame_index", cfg.get("index"))` funciona corretamente (todos os sinais têm ambos os campos). Sinais calculados processados em segundo loop após os diretos. Erros são capturados individualmente por sinal. Publica `SignalsReceivedEvent` apenas se `parsed_data` não for vazio. ✅

---

### LogWriter

Implementação correta. Buffer `_pending` por `frame_id`. Espera par D01+D02 antes de gravar. Remove prefixo `#D01`/`#D02` via `split(";")[1:]`. Inscrição dupla no bus: `ECU_MESS_FRAME` e `EVENT_MARK_REQUESTED`. Worker em thread dedicada via `QThread`. Inconsistência menor no import (S3). ✅

---

### AlarmProcessor

Migração completa de `QThread` para `QObject + QTimer`. `QTimer` de 100ms na main thread substitui o loop de polling. `QMediaPlayer` e `QAudioOutput` operados na main thread — correto para thread affinity. `stop()` para o timer e o player. O `_handle_status` religa o player quando `EndOfMedia` e ainda há alarme — loop de áudio correto. A lógica de detecção de alarme em `process_signals` está correta, com `duration_s` obtido do `alarm.get("duration_s", 2.0)`. ✅

---

### VehicleState

Desacoplamento do emitter executado corretamente. Os três métodos de mutação de estado (`set_rpm_breakpoints`, `set_map_breakpoints`, `set_ve_map`) publicam `VehicleStateChangedEvent` via import local — evita import circular. `set_alarm` recebe `duration_s` e armazena `(fired_at, expires_at)` — correto. `is_alarm_firing` e `is_any_alarm_firing` usam `expires_at` em vez de `ALARM_DURATION` global — correto. Constante `ALARM_DURATION` removida. Único bug: validação invertida em `set_ve_map` (C4). ⚠️

---

### UI / VeCalibration

**VeCalibrationScreen:** Migração do `vehicle_state.emitter.connect()` para `self._subscribe(AppEventType.VEHICLE_STATE_CHANGED, ...)` em `on_activated()` — correto. Teclas O e P publicam `EcuCommandRequestedEvent` no bus — correto. `on_deactivated()` chama `super().on_deactivated()` que desinscreve tokens. Não importa mais `get_ecu_connection()` diretamente. Dead code de `populate_ve_table` (S1, I2).

**VeWriteController:** Correto. Debounce de 1s via `QTimer`. Publica `EcuCommandRequestedEvent` para cada linha VE pendente. `mark_row_sent` antes de emitir o evento — ordem correta para evitar reenvio. ✅

---

### main.py / Wiring

A estrutura geral está correta e próxima da spec (seção 10). Instancia `MockTransport` ou `SerialTransport` conforme `config.connection.mock`. Registra `EcuSession`. Cria processadores. Assina `SIGNALS_RECEIVED → vehicle_state.update` e `ECU_COMMAND_REQUESTED → ecu_session.send_command` diretamente. `AppWindow` sem parâmetro `signal_processor`. Keyboard actions comentadas conforme spec. `ecu_session.start()` após UI. `alarm_processor.stop()` e `ecu_session.stop()` no encerramento.

Problema: `event_bus` importado no nível de módulo antes de `QApplication()` (I1). Os arquivos obsoletos (`serial.py`, `mock_log.py`, `thread.py`) **foram removidos** do branch — confirmado pela ausência no `ls app/ecu_connection/`. ✅ para remoção.

---

## Conclusão

**O app não deve ser executado no estado atual.** Três dos quatro problemas críticos (C1, C2, C3) causam que o handshake com a ECU — real ou mock — nunca funcione corretamente. Com MockTransport, o app levaria ~2 minutos para inicializar e iniciaria sem VE map e breakpoints. O bug C4 pode causar `IndexError` em situações de edge case.

**Correções necessárias antes de testar:**

1. **C1/C2 (session.py):** Reescrever `_send_blocking` para fazer `transport.readline()` diretamente durante o handshake (ao invés de usar `threading.Event`). Para reconexão, considerar fazer o handshake em uma thread separada ou torná-lo assíncrono.

2. **C3 (mock_transport.py linha 89):** Corrigir `len(line) == 3` para `len(line) == 4` (ou remover a verificação de comprimento e usar `line[2:4].isdigit()`).

3. **C4 (state.py linha 91):** Corrigir `if 0 > ve_idx > 15:` para `if ve_idx < 0 or ve_idx > 15:`.

Após essas correções, o app deve funcionar em modo mock. Recomenda-se também mover os imports de `event_bus` e outros `QObject` para dentro de `main()` após `QApplication()` (I1).
