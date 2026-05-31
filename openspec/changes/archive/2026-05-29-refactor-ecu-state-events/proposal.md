## Why

A arquitetura atual mistura responsabilidades: a conexão ECU inicia streaming diretamente, o `SignalProcessor` é acionado por sinal Qt ponto-a-ponto, o `VehicleState` é consultado por polling, e a camada de conexão combina transporte de bytes com lógica de protocolo. Isso cria acoplamento rígido e dificulta rastrear o fluxo de dados ou estender o sistema. A refatoração introduz separação de camadas físicas (transporte vs. protocolo), uma API tipada no protocolo, e centraliza toda comunicação no `EventBus` com o `VehicleState` como mediador de estado.

## What Changes

- **ECU — camada de transporte**: nova classe `EcuTransport` (ABC) responsável exclusivamente por bytes: `open/close/read_line/write`. Implementações: `EcuTransportSerial` e `EcuTransportMock`.
- **ECU — camada de protocolo**: nova classe `EcuProtocol` que senta sobre `EcuTransport`. Possui métodos nomeados e tipados (`fetch_ve_row`, `set_ve_row`, `open_lambda_loop`, etc.). Toda comunicação com a ECU ocorre via esses métodos — sem `EcuCommand` enum exposto ao chamador. Cada método usa `_send_and_wait` internamente, que bloqueia apenas o caller; escrita e leitura ocorrem em paralelo (full-duplex). Todo comando recebe resposta; não existe fire-and-forget.
- **ECU — respostas estruturadas**: o protocolo parseia respostas brutas em dataclasses (`VeRowResponse`, `BreakpointsResponse`, `LambdaResponse`, etc.). Nenhum texto bruto sai do protocolo. Toda resposta é sempre publicada como `EcuResponseReceivedEvent(response: EcuResponse)` no bus — independente de quem solicitou o comando.
- **ECU — frames de streaming**: D01, D02 e D03 são publicados imediatamente ao chegar, sem aguardar o par. Evento unificado `EcuFrameReceivedEvent(frame_type: EcuFrameType, values: List[str])`. Sem join de frames, sem fila de drenagem.
- **VehicleState** (mediador central): é o único módulo que chama métodos do `EcuProtocol`. Após o handshake, spawna uma setup thread que executa a sequência `fetch_ecu_info → fetch_map_breakpoints → fetch_rpm_breakpoints → fetch_ve_row (×15) → start_streaming`. Assina `EcuResponseReceivedEvent` no bus para manter o estado sempre sincronizado com a memória da ECU — mesmo quando foi o próprio VehicleState quem enviou o comando.
- **SignalProcessor**: assina `EcuFrameReceivedEvent` no bus (substituindo o `emitter(str)` direto). Processa D01, D02 e D03 independentemente, publicando `SignalsReceivedEvent` por frame.
- **UI — eventos de tela**: `ScreenRequestedEvent` é removido do `EventBus`. `Screen` base class ganha `screen_requested = pyqtSignal(str)`; `AppWindow` conecta o sinal de cada screen registrada diretamente.
- **BREAKING**: `EcuConnection` e `EcuConnectionThread` com `emitter(str)` são substituídos por `EcuTransport` + `EcuProtocol`.
- **BREAKING**: `EcuCommand` enum deixa de ser API pública; callers usam os métodos nomeados do `EcuProtocol`.
- **BREAKING**: `ScreenRequestedEvent` e `SCREEN_REQUESTED` removidos do `EventBus`.

## Capabilities

### New Capabilities

- `ecu-transport-protocol-split`: separação física entre `EcuTransport` (bytes) e `EcuProtocol` (protocolo, métodos nomeados, eventos).
- `ecu-event-layer`: `EcuProtocol` emite eventos estruturados no bus (`EcuFrameReceivedEvent`, `EcuHandshakeCompletedEvent`, `EcuResponseReceivedEvent`).
- `state-as-mediator`: `VehicleState` torna-se o mediador central — única interface com o `EcuProtocol`, controla ciclo de vida de coleta e mantém estado sincronizado via bus.

### Modified Capabilities

- `ecu-protocol`: handshake limitado ao `#D50`; streaming e fetches iniciados pelo `VehicleState`; sem fila de comandos.
- `data-pipeline`: pipeline inbound usa `EcuFrameReceivedEvent` separado por tipo de frame; outbound passa pelo `VehicleState`; eventos de tela saem do bus.

## Impact

- `app/ecu_connection/`: reestruturação completa — `EcuTransport`, `EcuTransportSerial`, `EcuTransportMock`, `EcuProtocol`, `EcuConnectionThread` (adaptado). `ecu_connection.py` e `serial.py` removidos ou absorvidos.
- `app/event/app_events.py` e `bus.py`: novos tipos `EcuFrameReceivedEvent`, `EcuHandshakeCompletedEvent`, `EcuResponseReceivedEvent`; `ScreenRequestedEvent` removido.
- `app/state/state.py`: setup thread, assinatura de `EcuResponseReceivedEvent`, remoção de polling.
- `app/masterinjection/signal_processor.py`: assina `EcuFrameReceivedEvent`, processa por frame_type.
- `app/masterinjection/signal.py`: cada `Signal` declara `frame: EcuFrameType` e índice relativo ao frame.
- `app/ui/base/screen.py`: `screen_requested = pyqtSignal(str)`.
- `app/ui/window.py`: conecta `screen.screen_requested` diretamente; remove assinatura de `SCREEN_REQUESTED`.
- `main.py`: simplificação significativa do wiring.
