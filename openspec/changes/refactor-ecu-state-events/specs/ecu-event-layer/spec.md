## ADDED Requirements

### Requirement: EcuProtocol publica EcuFrameReceivedEvent para cada frame recebido
A cada frame D01, D02 ou D03 recebido no read loop, `EcuProtocol` SHALL publicar imediatamente `EcuFrameReceivedEvent(frame_type, values)` no `EventBus`. Os frames MUST NOT ser acumulados ou aguardar o par — cada um é publicado assim que chega.

```python
class EcuFrameType(Enum):
    D01 = "#D01"
    D02 = "#D02"
    D03 = "#D03"

@dataclass(frozen=True)
class EcuFrameReceivedEvent(AppEvent):
    frame_type: EcuFrameType
    values: List[str]   # campos após o prefix, split por ";"
```

#### Scenario: D01 é publicado imediatamente ao chegar
- **WHEN** o read loop lê uma linha iniciando com `#D01`
- **THEN** `EcuFrameReceivedEvent(frame_type=D01, values=[...])` SHALL ser publicado antes de qualquer outra leitura

#### Scenario: D02 é publicado independentemente do D01
- **WHEN** o read loop lê uma linha iniciando com `#D02`
- **THEN** `EcuFrameReceivedEvent(frame_type=D02, values=[...])` SHALL ser publicado, independente de D01 já ter chegado ou não

#### Scenario: Frame não é publicado como string bruta
- **WHEN** qualquer frame ECU é recebido
- **THEN** nenhum assinante SHALL receber a string bruta `"#D01;v1;v2;..."` — apenas o evento com `values: List[str]`

### Requirement: EcuProtocol publica EcuHandshakeCompletedEvent após #D50
Após receber resposta válida ao handshake `#D50`, `EcuProtocol` SHALL publicar `EcuHandshakeCompletedEvent()` no bus antes de entrar no read loop de streaming.

#### Scenario: Handshake bem-sucedido gera exatamente um evento
- **WHEN** a ECU responde ao `#D50` com linha iniciando em `#D50`
- **THEN** `EcuHandshakeCompletedEvent()` SHALL ser publicado exatamente uma vez

#### Scenario: Retry não duplica o evento
- **WHEN** o `#D50` requer retry antes da resposta válida
- **THEN** `EcuHandshakeCompletedEvent` SHALL ser publicado apenas após o sucesso, nunca durante os retries

### Requirement: EcuProtocol publica EcuResponseReceivedEvent para toda resposta de comando
Cada método nomeado do `EcuProtocol` SHALL, após parsear a resposta bruta, publicar `EcuResponseReceivedEvent(response: EcuResponse)` no bus **antes** de retornar ao caller.

```python
@dataclass(frozen=True)
class EcuResponseReceivedEvent(AppEvent):
    response: EcuResponse   # subclasse tipada
```

#### Scenario: set_ve_row publica evento antes de retornar
- **WHEN** `EcuProtocol.set_ve_row(1, data)` é chamado e a ECU responde
- **THEN** `EcuResponseReceivedEvent(VeRowResponse(row_index=1, values=[...]))` SHALL ser publicado no bus
- **AND** o método SHALL retornar o mesmo `VeRowResponse` ao caller

#### Scenario: Evento é publicado mesmo quando caller ignora o retorno
- **WHEN** qualquer método de `EcuProtocol` recebe resposta da ECU
- **THEN** `EcuResponseReceivedEvent` SHALL ser publicado independente do caller usar ou não o valor de retorno

### Requirement: Hierarquia EcuResponse — sem texto bruto fora do protocolo
Toda resposta parseada SHALL ser uma subclasse frozen dataclass de `EcuResponse`. Nenhum método público de `EcuProtocol` SHALL retornar `str`.

```
EcuResponse (base, frozen dataclass)
├── EcuInfoResponse
├── BreakpointsResponse(values: List[int])
├── VeRowResponse(row_index: int, values: List[int])
├── StreamingAckResponse
└── LambdaResponse(state: LambdaState)
```

#### Scenario: Parsing ocorre dentro do método do protocolo
- **WHEN** a ECU responde `"#F01;45;67;89;..."` ao comando `set_ve_row`
- **THEN** `EcuProtocol` SHALL parsear internamente e publicar/retornar `VeRowResponse(row_index=1, values=[45, 67, 89, ...])`
- **AND** a string `"#F01;45;67;89;..."` MUST NOT ser acessível fora de `EcuProtocol`

### Requirement: pyqtSignal emitter(str) é removido
`EcuConnectionThread` MUST NOT expor `pyqtSignal emitter(str)`. Nenhum slot em `main.py` SHALL ser conectado a esse sinal.

#### Scenario: Consumidores usam apenas o bus
- **WHEN** a aplicação está em execução
- **THEN** `SignalProcessor`, `LogWriter` e `VehicleState` SHALL receber dados ECU exclusivamente via assinaturas no `EventBus`
