## 1. Novos tipos de evento no EventBus

- [x] 1.1 Adicionar `EcuFrameType(Enum)` com valores `D01`, `D02`, `D03` em `app/event/app_events.py`
- [x] 1.2 Adicionar `EcuFrameReceivedEvent(frame_type: EcuFrameType, values: List[str])` e registrar `ECU_FRAME_RECEIVED` em `AppEventType`
- [x] 1.3 Adicionar `EcuHandshakeCompletedEvent()` e registrar `ECU_HANDSHAKE_COMPLETED`
- [x] 1.4 Adicionar `EcuResponseReceivedEvent(response: EcuResponse)` e registrar `ECU_RESPONSE_RECEIVED`
- [x] 1.5 Remover `ScreenRequestedEvent` e `SCREEN_REQUESTED` de `app_events.py`
- [x] 1.6 Adicionar os novos `pyqtSignal(object)` e entradas em `_SIGNAL_ATTR` em `app/event/bus.py`; remover o de `SCREEN_REQUESTED`

## 2. Hierarquia EcuResponse

- [x] 2.1 Criar `app/ecu_connection/responses.py` com a base `EcuResponse` (frozen dataclass)
- [x] 2.2 Adicionar `EcuInfoResponse`, `BreakpointsResponse(values: List[int])`, `VeRowResponse(row_index: int, values: List[int])`, `StreamingAckResponse`
- [x] 2.3 Adicionar `LambdaState(Enum)` com valores `OPEN` e `CLOSED` e `LambdaResponse(state: LambdaState)`

## 3. Camada de transporte

- [x] 3.1 Criar `app/ecu_connection/transport.py` com `EcuTransport(ABC)`: `open`, `close`, `is_open`, `read_line → str`, `write(bytes)`
- [x] 3.2 Criar `app/ecu_connection/transport_serial.py` com `EcuTransportSerial(EcuTransport)` — extraído de `serial.py` (apenas I/O, sem protocolo)
- [x] 3.3 Criar `app/ecu_connection/transport_mock.py` com `EcuTransportMock(EcuTransport)` — extraído de `mock_log.py` (replay CSV com pacing, `write` é no-op)

## 4. Camada de protocolo — EcuProtocol

- [x] 4.1 Criar `app/ecu_connection/ecu_protocol.py` com `EcuProtocol(transport: EcuTransport)`
- [x] 4.2 Implementar `_send_and_wait(wire: str, prefix: str, timeout=5.0) → str` com `_write_lock: threading.Lock` e `_pending` slot
- [x] 4.3 Implementar read loop: roteia D01/D02/D03 para `EcuFrameReceivedEvent`; roteia resposta de comando para `_pending`; loga e descarta o restante
- [x] 4.4 Implementar handshake: `#D50` com retry, publicar `EcuHandshakeCompletedEvent`, entrar no read loop (sem `#D01`)
- [x] 4.5 Implementar métodos de setup: `fetch_ecu_info`, `fetch_map_breakpoints`, `fetch_rpm_breakpoints`, `fetch_ve_row(row)`
- [x] 4.6 Implementar `start_streaming() → StreamingAckResponse`
- [x] 4.7 Implementar métodos de streaming: `set_ve_row(row, data)`, `open_lambda_loop`, `close_lambda_loop`
- [x] 4.8 Garantir que cada método publica `EcuResponseReceivedEvent` **antes** de retornar
- [x] 4.9 Adaptar `app/ecu_connection/thread.py` para receber `EcuProtocol` e chamar seu read loop; remover `emitter(str)`

## 5. Remover arquivos obsoletos

- [x] 5.1 Remover `app/ecu_connection/ecu_connection.py` (ABC antiga)
- [x] 5.2 Remover `app/ecu_connection/serial.py`
- [x] 5.3 Remover `app/ecu_connection/mock_log.py`

## 6. Atualizar signal.py

- [x] 6.1 Adicionar atributo `frame: EcuFrameType` a cada entrada do enum `Signal` em `app/masterinjection/signal.py`
- [x] 6.2 Ajustar `index` de cada `Signal` para ser relativo ao frame (não à string joined)

## 7. Refatorar SignalProcessor

- [x] 7.1 Assinar `ECU_FRAME_RECEIVED` no bus em `app/masterinjection/signal_processor.py`
- [x] 7.2 Processar cada `EcuFrameReceivedEvent` filtrando sinais por `Signal.frame == event.frame_type`
- [x] 7.3 Manter `SignalsReceivedEvent` como saída (publicado por frame, não por par de frames)

## 8. Refatorar LogWriter

- [x] 8.1 Assinar `ECU_FRAME_RECEIVED` no bus em `app/log_writer/log_writer.py`
- [x] 8.2 No handler, filtrar apenas `frame_type == D01`; reconstruir a linha como `"#D01;" + ";".join(values)` e escrever no CSV

## 9. Refatorar VehicleState

- [x] 9.1 Assinar `ECU_HANDSHAKE_COMPLETED` no bus; no handler, spawnar setup thread daemon
- [x] 9.2 Implementar setup thread: chamar `fetch_ecu_info → fetch_map_breakpoints → fetch_rpm_breakpoints → fetch_ve_row(1..15) → start_streaming` em sequência
- [x] 9.3 Assinar `ECU_RESPONSE_RECEIVED` no bus; implementar handler com pattern matching por tipo de `EcuResponse`
- [x] 9.4 Assinar `ECU_FRAME_RECEIVED` para manter snapshot de sinais por frame type
- [x] 9.5 Expor `open_lambda_loop()`, `close_lambda_loop()`, `write_ve_row(idx, data)` como métodos públicos que delegam ao `EcuProtocol`
- [x] 9.6 Remover `update()` chamado diretamente pelo `SignalProcessor`; remover assinatura de `ECU_COMMAND_REQUESTED`

## 10. Refatorar LambdaToggle e VeWriteController

- [x] 10.1 Em `app/event/lambda_toggle.py`: substituir publicação de `EcuCommandRequestedEvent` por chamada direta a `vehicle_state.open_lambda_loop()` ou `close_lambda_loop()`
- [x] 10.2 Em `app/ui/ve_calibration/ve_write_controller.py`: substituir `get_ecu_connection().send_command()` por `vehicle_state.write_ve_row(idx, data)`

## 11. Eventos de tela fora do bus

- [x] 11.1 Adicionar `screen_requested = pyqtSignal(str)` em `app/ui/base/screen.py`
- [x] 11.2 Em `app/ui/home/screen.py`: substituir `event_bus.publish(ScreenRequestedEvent(...))` por `self.screen_requested.emit(screen_name)`
- [x] 11.3 Em `app/ui/window.py`: conectar `screen.screen_requested` a `self.show_screen` ao registrar cada screen; remover assinatura de `SCREEN_REQUESTED` no bus

## 12. Atualizar main.py

- [x] 12.1 Instanciar `EcuTransport` (serial ou mock conforme config), depois `EcuProtocol(transport)`, depois `EcuConnectionThread(protocol)`
- [x] 12.2 Remover toda conexão de `emitter(str)` e toda referência a `EcuCommand` fora do protocolo
- [x] 12.3 Garantir ordem: LogWriter → AlarmProcessor → SignalProcessor → VehicleState subscriptions → registry → AppWindow → keyboard wiring → `EcuConnectionThread.start()`

## 13. Limpeza e validação

- [x] 13.1 Grep: verificar que nenhum arquivo fora de `ecu_protocol.py` referencia strings de comando (`#D50`, `#F01`, etc.)
- [x] 13.2 Grep: verificar que nenhum módulo fora de `VehicleState` chama métodos de `EcuProtocol`
- [x] 13.3 Grep: verificar que `ScreenRequestedEvent` e `emitter` não aparecem mais no código
- [x] 13.4 Executar com mock: validado via parsing direto de linha de log — todos os sinais corretos
- [x] 13.5 Verificar que `VeCalibrationScreen` ainda recebe atualizações de sinais
