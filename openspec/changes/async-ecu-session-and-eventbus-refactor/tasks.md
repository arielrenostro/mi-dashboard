## 1. EcuTransport — Camada de transporte

- [x] 1.1 Criar `app/ecu/transport/base.py` com classe abstrata `EcuTransport` (`read_line`, `write_line`, `open`, `close`)
- [x] 1.2 Criar `app/ecu/transport/serial_transport.py` com `SerialTransport` usando pyserial (port/baudrate de config, timeout 1 s, UTF-8/LF)
- [x] 1.3 Criar `app/ecu/transport/mock_transport.py` com `MockTransport` que replica CSV log emitindo D01 e D02 como reads separados, paginados por Timestamp
- [x] 1.4 Criar `app/ecu/transport/__init__.py` com factory `create_transport() -> EcuTransport` baseada em `config.connection.mock`

## 2. EcuCommand — Enum de comandos com contratos

- [x] 2.1 Criar `app/ecu/commands.py` com `ResponseContract` enum (`ECHO_FULL`, `ECHO_CMD_ONLY`, `DATA_RESPONSE`)
- [x] 2.2 Expandir `EcuCommand` em `app/ecu/commands.py` com campo `response_contract: ResponseContract` para todos os comandos existentes (ECU_INFO, STREAMING_START, OPEN_LOOP, CLOSE_LOOP, FETCH_VE, SET_VE_ROW, FETCH_IGNITION, SET_IGNITION_ROW)
- [x] 2.3 Mover ou reexportar `EcuCommand` de `app/masterinjection/protocol.py` para o novo módulo; manter retrocompatibilidade de importação durante migração

## 3. EventBus — Novos eventos e revisão

- [x] 3.1 Adicionar `ECU_MESS_FRAME` / `EcuMessFrameEvent(frame_type: str, line: str)` em `app/event/app_events.py` e `app/event/bus.py`
- [x] 3.2 Adicionar `ECU_COMMAND_SEND` / `EcuCommandSendEvent(cmd: str, args: Any)` em `app/event/app_events.py` e `app/event/bus.py`
- [x] 3.3 Adicionar `ECU_COMMAND_RESPONSE` / `EcuCommandResponseEvent(cmd: str, response_line: str)` em `app/event/app_events.py` e `app/event/bus.py`
- [x] 3.4 Remover `VEHICLE_STATE_CHANGED` / `VehicleStateChangedEvent` de `app/event/app_events.py` e `app/event/bus.py`; atualizar todos os call sites

## 4. EcuSession — Camada de sessão com thread interna

- [x] 4.1 Criar `app/ecu/session.py` com `EcuSession` e thread interna de I/O (não herda de `QThread`)
- [x] 4.2 Implementar handshake em `EcuSession._run()`: envio de `#D50`, aguardar resposta, enviar `#D01`, entrar no read loop (retries conforme spec)
- [x] 4.3 Implementar read loop com read timeout de 50 ms; classificar linhas em MESS_FRAME vs response; publicar `ECU_MESS_FRAME` via `QMetaObject.invokeMethod` (QueuedConnection)
- [x] 4.4 Implementar write queue (`threading.Queue`) com drain entre reads; enviar comandos em FIFO
- [x] 4.5 Implementar command-response pairing com `threading.Event` e `result_box`; publicar `ECU_COMMAND_SEND` e `ECU_COMMAND_RESPONSE` no bus
- [x] 4.6 Implementar reconexão após 3 reads consecutivos vazios (fechar transport, reiniciar handshake)
- [x] 4.7 Implementar métodos de alto nível: `open_loop()`, `close_loop()`, `fetch_ve()`, `fetch_ignition()`, `set_ve_row()`, `set_ignition_row()`
- [x] 4.8 Criar `app/ecu/__init__.py` com registry `register_ecu_session()` / `get_ecu_session()`

## 5. VehicleState — Desacoplamento e autogestão

- [x] 5.1 Adicionar métodos `set_alarm(signal, active: bool)`, `is_alarm_firing(signal)`, `is_any_alarm_firing()` em `app/state/state.py` sob `threading.RLock`
- [x] 5.2 Remover dependências de telas do `VehicleState`; garantir que nenhuma tela acesse `vehicle_state` para escrita direta
- [x] 5.3 Remover `VehicleStateChangedEvent` de todos os emissores em `VehicleState`; substituir por callbacks internos onde necessário

## 6. SignalProcessor — Processamento por frame individual

- [x] 6.1 Remover conexão direta `EcuConnection.emitter → SignalProcessor.process_line`
- [x] 6.2 Fazer `SignalProcessor` subscrever `ECU_MESS_FRAME` no bus em `on_activated()` / `__init__`
- [x] 6.3 Adaptar `process_line()` para processar apenas sinais do frame recebido (`frame_type`), publicar `SIGNALS_RECEIVED` com dict parcial
- [x] 6.4 Garantir que sinais calculados (POWER, TORQUE) funcionem com dados parciais (aguardar dependências via `VehicleState` se necessário)

## 7. LogWriter — Acumulação de frames via bus

- [x] 7.1 Remover conexão direta `EcuConnection.emitter → LogWriter.write`
- [x] 7.2 Fazer `LogWriter` subscrever `ECU_MESS_FRAME` no bus; acumular D01 e D02 internamente no worker thread
- [x] 7.3 Implementar timer de 500 ms para gravação de linha parcial (apenas D01) com flag `"PARTIAL"` no Event
- [x] 7.4 Garantir que `"MARK"` tenha precedência sobre `"PARTIAL"` na coluna Event
- [x] 7.5 Ignorar frames D03 no `LogWriter`

## 8. AlarmProcessor — Sem thread de polling

- [x] 8.1 Remover thread de polling de 100 ms do `AlarmProcessor`
- [x] 8.2 Fazer `AlarmProcessor` chamar `vehicle_state.set_alarm(signal, in_alarm)` após cada verificação
- [x] 8.3 Implementar lógica de transição de estado (off→on, on→off) para disparar play/stop de áudio via `QTimer.singleShot(0, ...)` no main thread
- [x] 8.4 Conectar `QMediaPlayer.mediaStatusChanged` para restart automático de áudio quando `EndOfMedia` e alarme ainda ativo

## 9. main.py — Inicialização simplificada

- [x] 9.1 Remover instanciação de `EcuConnectionThread`; substituir por `EcuSession.start()`
- [x] 9.2 Remover conexão direta `emitter → SignalProcessor` e `emitter → LogWriter`
- [x] 9.3 Registrar `EcuSession` via `register_ecu_session()` e wiring de `ECU_COMMAND_REQUESTED → session.send_command`
- [x] 9.4 Garantir ordem de inicialização conforme spec (LogWriter → AlarmProcessor → SignalProcessor → VehicleState subs → EcuSession → AppWindow → session.start)
- [x] 9.5 Atualizar shutdown: `session.stop()` em vez de `EcuConnectionThread.stop()`

## 10. VeWriteController — Migração para EcuSession

- [x] 10.1 Substituir chamada `get_ecu_connection().send_command(...)` por `get_ecu_session().set_ve_row(...)` em `app/ui/ve_calibration/ve_write_controller.py`
- [x] 10.2 Garantir que `VeCalibrationScreen` não chame a session diretamente; verificar que usa `VeWriteController` como intermediário

## 11. Limpeza de código legado

- [x] 11.1 Remover `app/ecu_connection/` após confirmar que todos os consumidores foram migrados
- [x] 11.2 Remover `app/masterinjection/protocol.py` ou manter apenas reexportação para compatibilidade (decidir no momento da remoção)
- [x] 11.3 Remover `EcuConnectionThread` e quaisquer referências residuais
- [x] 11.4 Verificar e remover imports obsoletos em todos os módulos afetados
