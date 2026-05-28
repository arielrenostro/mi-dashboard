## Why

A camada de comunicação com a ECU é síncrona e mistura transporte, protocolo de sessão e fiação de threads — dificultando extensão, teste e reutilização. O pipeline de eventos passa por caminhos mistos (sinais diretos + bus), impedindo rastreabilidade e controle de fluxo uniforme por toda a aplicação.

## What Changes

- **BREAKING** Separar `EcuConnection` em camada de transporte (`EcuTransport`) e camada de sessão (`EcuSession`); a session gerencia sua própria thread internamente.
- **BREAKING** Comunicação com a ECU passa a ser assíncrona: leitura e escrita ocorrem em paralelo; cada envio aguarda resposta do mesmo código de comando.
- **BREAKING** Frames de ECU (`#D01`, `#D02`, `#D03`) passam a ser emitidos individualmente via `ECU_MESS_FRAME` no bus, em vez de um frame combinado.
- **BREAKING** `SignalProcessor` passa a se inscrever no bus (`ECU_MESS_FRAME`) em vez de receber string direta; processa frames individuais e emite `SIGNALS_RECEIVED` com dados parciais permitidos.
- **BREAKING** `LogWriter` acumula `#D01` e `#D02` via bus antes de gravar uma linha CSV.
- **BREAKING** `AlarmProcessor` elimina polling thread; conversa diretamente com `VehicleState` para estado de alarme; dispara áudio sob demanda.
- **BREAKING** `VehicleState` desacoplado de telas; controla seu próprio estado (sinais, alarmes, lambda loop, dados de mapa) de forma independente.
- Novos eventos no bus: `ECU_COMMAND_SEND`, `ECU_COMMAND_RESPONSE`, `ECU_MESS_FRAME`; revisão de eventos existentes (renomear/remover desnecessários).
- Telas (UI) emitem e consomem eventos do bus; eventos puramente de UI permanecem locais.

## Capabilities

### New Capabilities

- `ecu-transport`: Camada de transporte serial pura (serial/mock): leitura e escrita de linhas brutas, sem conhecimento de protocolo.
- `ecu-session`: Camada de sessão sobre o transporte — handshake, framing, envio/recebimento assíncrono de comandos, publicação de `ECU_MESS_FRAME`, `ECU_COMMAND_SEND` e `ECU_COMMAND_RESPONSE` no bus. Thread gerenciada internamente.
- `ecu-commands`: Estruturação de todos os comandos e respostas da ECU (open_loop, close_loop, fetch_ve, fetch_ignition, etc.) com tipagem e contrato de resposta esperada.

### Modified Capabilities

- `ecu-protocol`: Protocolo reformulado — frames emitidos individualmente; envio de comando aguarda resposta com mesmo código; regras de confirmação por tipo de comando.
- `data-pipeline`: Pipeline passa inteiramente pelo bus (`ECU_MESS_FRAME` → `SignalProcessor` → `SIGNALS_RECEIVED`); `LogWriter` acumula frames via bus; sem caminhos diretos fora da UI.
- `alarm-system`: `AlarmProcessor` sem polling thread; estado de alarme gerenciado pelo `VehicleState`; áudio sob demanda.
- `logging`: `LogWriter` recebe frames individuais via bus e acumula antes de gravar linha CSV.

## Impact

- `app/ecu_connection/`: substituído por `app/ecu/transport/` e `app/ecu/session/`
- `app/masterinjection/signal_processor.py`: depende de `ECU_MESS_FRAME` no bus
- `app/masterinjection/protocol.py`: expande `EcuCommand`/`EcuResponse` com contratos de resposta
- `app/alarm/processor.py`: remove thread de polling; delega estado ao `VehicleState`
- `app/state/state.py`: passa a centralizar estado de alarmes e lambda loop independentemente
- `app/log_writer/log_writer.py`: recebe frames via bus, acumula antes de gravar
- `app/event/app_events.py` / `app/event/bus.py`: novos eventos, revisão/remoção de eventos obsoletos
- `main.py`: simplificado — fiação de thread removida; inicialização da session gerenciada internamente
