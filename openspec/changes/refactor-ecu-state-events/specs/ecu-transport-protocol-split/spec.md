## ADDED Requirements

### Requirement: EcuTransport encapsula exclusivamente o transporte de bytes
`EcuTransport` SHALL ser uma classe abstrata (ABC) com a seguinte interface exclusivamente de I/O:
- `open()` — abre a conexão física
- `close()` — fecha a conexão física
- `is_open() → bool`
- `read_line() → str` — bloqueante, retorna uma linha sem terminador
- `write(data: bytes)` — escreve bytes no canal

`EcuTransport` MUST NOT conter qualquer conhecimento de prefixos de comando, formato de frame, handshake, ou protocolo da ECU.

#### Scenario: EcuTransportSerial encapsula apenas a porta serial
- **WHEN** `EcuTransportSerial.read_line()` é chamado
- **THEN** SHALL executar `serial.readline().decode("utf-8").strip()` e retornar a string resultante sem qualquer interpretação

#### Scenario: EcuTransportMock encapsula apenas o replay de CSV
- **WHEN** `EcuTransportMock.read_line()` é chamado
- **THEN** SHALL retornar a próxima linha do arquivo CSV de replay com pacing baseado na coluna `Timestamp`, sem interpretar o conteúdo

#### Scenario: EcuTransport não conhece o protocolo
- **WHEN** qualquer implementação de `EcuTransport` está em execução
- **THEN** MUST NOT referenciar prefixos como `#D50`, `#D01`, `#F01` ou qualquer constante de protocolo

### Requirement: EcuProtocol encapsula exclusivamente o protocolo da ECU
`EcuProtocol` SHALL receber um `EcuTransport` no construtor e expor a seguinte API pública de métodos nomeados:
- `fetch_ecu_info() → EcuInfoResponse`
- `fetch_map_breakpoints() → BreakpointsResponse`
- `fetch_rpm_breakpoints() → BreakpointsResponse`
- `fetch_ve_row(row: int) → VeRowResponse`
- `start_streaming() → StreamingAckResponse`
- `set_ve_row(row: int, data: List[int]) → VeRowResponse`
- `open_lambda_loop() → LambdaResponse`
- `close_lambda_loop() → LambdaResponse`

`EcuProtocol` MUST NOT expor `EcuCommand` enum, strings de comando, ou qualquer dado bruto (str) como retorno de métodos públicos.

#### Scenario: EcuProtocol usa EcuTransport apenas via interface
- **WHEN** `EcuProtocol` envia ou recebe dados
- **THEN** SHALL chamar apenas `transport.write()` e `transport.read_line()` — nunca acessar a porta serial diretamente

#### Scenario: Método nomeado retorna dado estruturado
- **WHEN** `EcuProtocol.fetch_ve_row(3)` é chamado
- **THEN** SHALL retornar `VeRowResponse(row_index=3, values=[...])` — nunca a string bruta `"#F03;v1;v2;..."`

### Requirement: Estrutura de arquivos reflete a separação
Os arquivos SHALL ser organizados em `app/ecu_connection/`:
- `transport.py` — `EcuTransport` ABC
- `transport_serial.py` — `EcuTransportSerial`
- `transport_mock.py` — `EcuTransportMock`
- `ecu_protocol.py` — `EcuProtocol`
- `responses.py` — hierarquia de dataclasses `EcuResponse`
- `thread.py` — `EcuConnectionThread` (wraps `EcuProtocol`)

#### Scenario: Arquivos antigos são removidos
- **WHEN** a refatoração estiver completa
- **THEN** `ecu_connection.py` e `serial.py` (antigos) MUST NOT existir no repositório

### Requirement: Get e Set usam o mesmo cmd_prefix e retornam o mesmo tipo
Para qualquer operação que possua variante Get e Set (ex.: VE row), ambas SHALL usar o mesmo cmd_prefix e retornar o mesmo tipo de response. A ECU sempre responde com o estado atual da memória.

#### Scenario: Get e Set de VE row retornam VeRowResponse
- **WHEN** `fetch_ve_row(1)` é chamado (Get: envia `#F01\n`)
- **THEN** retorna `VeRowResponse(row_index=1, values=[...])`
- **WHEN** `set_ve_row(1, data)` é chamado (Set: envia `#F01;v1;...\n`)
- **THEN** retorna `VeRowResponse(row_index=1, values=[...])` — o estado confirmado pela ECU
