## ADDED Requirements

### Requirement: VehicleState é o único caller de EcuProtocol
Nenhum módulo exceto `VehicleState` SHALL chamar métodos de `EcuProtocol` diretamente. Módulos que precisam enviar comandos à ECU MUST delegar ao `VehicleState`.

#### Scenario: VeWriteController não acessa EcuProtocol diretamente
- **WHEN** `VeWriteController` precisa gravar uma linha de VE
- **THEN** MUST chamar `vehicle_state.write_ve_row(idx, data)` — nunca `get_ecu_protocol().set_ve_row()`

#### Scenario: LambdaToggle não acessa EcuProtocol diretamente
- **WHEN** `LambdaToggle` precisa abrir ou fechar o loop lambda
- **THEN** MUST chamar `vehicle_state.open_lambda_loop()` ou `vehicle_state.close_lambda_loop()`

### Requirement: VehicleState spawna setup thread após handshake
Ao receber `EcuHandshakeCompletedEvent` no bus, `VehicleState` SHALL iniciar uma thread worker (daemon) que executa a sequência de setup de forma bloqueante.

A sequência SHALL ser:
1. `protocol.fetch_ecu_info()`
2. `protocol.fetch_map_breakpoints()`
3. `protocol.fetch_rpm_breakpoints()`
4. `protocol.fetch_ve_row(1)` … `protocol.fetch_ve_row(15)`
5. `protocol.start_streaming()`

Cada chamada bloqueia a setup thread até a resposta chegar. Os dados são armazenados via assinatura de `EcuResponseReceivedEvent` (não pelo valor de retorno).

#### Scenario: Setup thread executa a sequência na ordem correta
- **WHEN** `EcuHandshakeCompletedEvent` é recebido
- **THEN** VehicleState SHALL spawnar uma thread que executa MAP_BREAKPOINTS antes de RPM_BREAKPOINTS, e todos os VE_ROW antes de STREAMING_START

#### Scenario: VehicleState não inicia setup antes do handshake
- **WHEN** a aplicação inicia mas o handshake ainda não concluiu
- **THEN** VehicleState SHALL NOT chamar nenhum método de `EcuProtocol`

#### Scenario: Setup thread encerra após start_streaming
- **WHEN** `protocol.start_streaming()` retorna
- **THEN** a setup thread SHALL encerrar — é one-shot, não permanente

### Requirement: VehicleState atualiza estado via EcuResponseReceivedEvent
`VehicleState` SHALL assinar `ECU_RESPONSE_RECEIVED` no bus. O handler SHALL atualizar o estado interno com base no tipo da response, usando structural pattern matching.

#### Scenario: BreakpointsResponse atualiza breakpoints
- **WHEN** `EcuResponseReceivedEvent(BreakpointsResponse(values=[...]))` é recebido
- **THEN** VehicleState SHALL armazenar os valores como breakpoints de MAP ou RPM (conforme contexto do evento)

#### Scenario: VeRowResponse atualiza VE map
- **WHEN** `EcuResponseReceivedEvent(VeRowResponse(row_index=3, values=[...]))` é recebido
- **THEN** VehicleState SHALL atualizar a linha 3 do VE map interno

#### Scenario: Estado é atualizado mesmo quando VehicleState foi o caller
- **WHEN** VehicleState chama `protocol.set_ve_row()` e a resposta chega
- **THEN** o handler de `EcuResponseReceivedEvent` SHALL ser acionado e atualizar o estado — o valor de retorno do método NÃO é usado para armazenar

### Requirement: VehicleState atualiza snapshot de sinais via EcuFrameReceivedEvent
`VehicleState` SHALL assinar `ECU_FRAME_RECEIVED` no bus para manter snapshot dos últimos valores de sinais recebidos por frame type.

#### Scenario: Snapshot de D01 atualizado ao receber frame D01
- **WHEN** `EcuFrameReceivedEvent(frame_type=D01, values=[...])` é publicado
- **THEN** VehicleState SHALL atualizar seu snapshot dos sinais provenientes de D01
