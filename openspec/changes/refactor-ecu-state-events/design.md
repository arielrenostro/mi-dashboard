## Context

O sistema atual possui acoplamentos que tornam o fluxo difícil de rastrear e estender:

1. **`EcuConnectionThread.emitter(str)`** — sinal Qt ponto-a-ponto conectado manualmente em `main.py`. Qualquer novo consumidor exige modificação lá.
2. **Transport e protocolo misturados** — `EcuConnectionSerial` abre a porta serial, faz handshake, busca breakpoints, busca VE map e inicia streaming numa só classe. Três níveis de abstração sem separação.
3. **Fire-and-forget sem tipagem** — `send_command(EcuCommand)` enfileirava comandos sem garantia de resposta e sem tipo de retorno.
4. **`VehicleState` passivo** — consultado por polling e atualizado diretamente pelo `SignalProcessor`, sem papel de controle.
5. **`ScreenRequestedEvent` no bus** — evento de navegação de UI circulando num bus de domínio.

Restrições: Python/PyQt6 single-process. Serial é full-duplex: escrita e leitura são independentes no nível de hardware.

## Goals / Non-Goals

**Goals:**
- Separar fisicamente transporte (`EcuTransport`) de protocolo (`EcuProtocol`).
- API tipada no protocolo: métodos nomeados, respostas estruturadas, sem texto bruto saindo do protocolo.
- Todo comando tem resposta; resposta sempre publicada no bus independente do chamador.
- `VehicleState` como único caller de `EcuProtocol`; mantém estado sincronizado via `EcuResponseReceivedEvent`.
- Frames D01/D02/D03 publicados imediatamente ao chegar, evento unificado por tipo.
- Eventos de tela fora do bus.

**Non-Goals:**
- Alterar o protocolo serial físico (formato de frame, prefixos).
- Refatorar UI interna (layouts, widgets, temas).
- Suportar múltiplas conexões ECU simultâneas.

## Decisions

### D1 — Separação física EcuTransport / EcuProtocol

**Decisão**: duas classes distintas com responsabilidades exclusivas.

```
EcuTransport (ABC)           EcuProtocol
  open() / close()             __init__(transport: EcuTransport)
  is_open() → bool             fetch_ecu_info() → EcuInfoResponse
  read_line() → str            fetch_map_breakpoints() → BreakpointsResponse
  write(bytes)                 fetch_ve_row(row) → VeRowResponse
                               set_ve_row(row, data) → VeRowResponse
EcuTransportSerial             start_streaming() → StreamingAckResponse
EcuTransportMock               open_lambda_loop() → LambdaResponse
                               close_lambda_loop() → LambdaResponse
```

`EcuTransport` não sabe nada de protocolo. `EcuProtocol` não sabe se está sobre serial ou mock.

**Motivação**: mock passa a ser uma implementação de transporte, não de conexão inteira. Testabilidade e extensibilidade melhoram.

---

### D2 — Métodos nomeados e tipados no EcuProtocol

**Decisão**: cada operação ECU é um método explícito com tipos de entrada e saída. `EcuCommand` enum torna-se detalhe interno do protocolo; callers nunca o veem.

**Get/Set são simétricos**: `fetch_ve_row(row)` envia `#F01\n`; `set_ve_row(row, data)` envia `#F01;v1;...\n`. A ECU sempre responde com o estado atual da memória — mesma resposta, mesmo tipo de retorno.

**cmd_prefix** é a chave de roteamento: identifica o comando enviado e o prefixo da resposta esperada. Toda resposta é parseada antes de sair do método.

**Alternativa considerada**: manter `send_command(EcuCommand, args)` genérico. Rejeitado: sem tipagem de retorno, sem garantia de parsing, callers precisam conhecer o enum.

---

### D3 — `send_and_wait`: bloqueia só o caller; escrita e leitura em paralelo

**Decisão**: `_send_and_wait(wire: str, prefix: str, timeout) → str` é o primitivo privado. Bloqueia o thread do caller via `threading.Event`. O read loop (ECU thread) continua independente — escrita e leitura são paralelas (full-duplex serial).

```
caller thread              ECU thread (read loop)
  acquire _write_lock        read_line() → D01 → EcuFrameReceivedEvent
  set _pending(prefix, ev)   read_line() → D02 → EcuFrameReceivedEvent
  transport.write(cmd)  ──►  read_line() → #FXX → pending.set()
  release _write_lock
  ev.wait()  ←─────────────────────────────────────────────────────┘
  return parsed result
```

`_write_lock` serializa apenas callers concorrentes (garante um único `_pending` ativo). Não bloqueia o read loop.

**Sem drain queue**: a fila de drenagem existia para sincronizar envios com o ciclo de frames. Com `_write_lock` e `send_and_wait`, o envio é imediato após adquirir o lock. A ECU processa o comando entre frames naturalmente.

---

### D4 — Toda resposta publicada no bus; VehicleState sempre atualiza via evento

**Decisão**: cada método do `EcuProtocol`, antes de retornar, publica `EcuResponseReceivedEvent(response: EcuResponse)` no bus. O valor de retorno do método é conveniente para o caller controlar sequenciamento; o estado real é sempre atualizado via assinatura no bus.

```python
# VehicleState setup thread — usa retorno apenas para sequenciar
protocol.fetch_map_breakpoints()   # bloqueia até resposta
protocol.fetch_rpm_breakpoints()   # bloqueia até resposta
...

# VehicleState bus subscriber — armazena o dado
def _on_ecu_response(event: EcuResponseReceivedEvent):
    match event.response:
        case BreakpointsResponse() as r: self.set_map_breakpoints(r.values)
        case VeRowResponse() as r:       self.set_ve_map_row(r.values, r.row_index)
        case LambdaResponse() as r:      ...
```

**Motivação**: VehicleState fica sincronizado com a ECU independente de quem enviou o comando (ele mesmo, VeWriteController, LambdaToggle via VehicleState).

---

### D5 — VehicleState é o único caller de EcuProtocol

**Decisão**: nenhum módulo além de `VehicleState` chama métodos do `EcuProtocol` diretamente. Módulos que precisam enviar comandos delegam a `VehicleState` (via método ou evento interno).

**Motivação**: mantém VehicleState como ponto central de controle da comunicação ECU ↔ sistema. Qualquer lógica de retry, throttle ou sequência fica num lugar só.

---

### D6 — EcuFrameReceivedEvent unificado (D01 / D02 / D03)

**Decisão**: evento único com discriminador de tipo:

```python
class EcuFrameType(Enum):
    D01 = "#D01"
    D02 = "#D02"
    D03 = "#D03"

@dataclass(frozen=True)
class EcuFrameReceivedEvent(AppEvent):
    frame_type: EcuFrameType
    values: List[str]   # split do raw, sem prefix
```

Cada frame é publicado imediatamente ao chegar — sem aguardar o par. D03 não é implementado ainda mas o enum já existe.

**LogWriter**: assina `EcuFrameReceivedEvent` com `frame_type == D01` e reconstrói a linha para CSV.

---

### D7 — Hierarquia EcuResponse; sem texto bruto fora do protocolo

**Decisão**: toda resposta é parseada dentro do método que a originou. Callers e assinantes do bus recebem apenas dataclasses.

```
EcuResponse (base, frozen)
├── EcuInfoResponse
├── BreakpointsResponse(values: List[int])
├── VeRowResponse(row_index: int, values: List[int])
├── StreamingAckResponse
└── LambdaResponse(state: LambdaState)
```

O formato de parsing de cada response type é responsabilidade do método nomeado correspondente no `EcuProtocol`. `EcuCommand` enum pode existir como constante interna de cmd strings.

---

### D8 — Eventos de tela fora do bus

**Decisão**: `ScreenRequestedEvent` removido do `EventBus`. `Screen` base class recebe `screen_requested = pyqtSignal(str)`. `HomeScreen` emite o sinal; `AppWindow` conecta o sinal de cada screen registrada diretamente ao `show_screen()`.

**Motivação**: navegação de UI é um contrato entre `Screen` e `AppWindow`, não um evento de domínio. Remover evita acoplamentos acidentais de componentes de backend à navegação.

## Risks / Trade-offs

- **[Risco] VehicleState setup thread vs. Qt event loop**: `_on_ecu_response` é entregue pelo Qt na main thread; setup thread pode avançar para o próximo comando antes do handler processar o anterior. Aceitável — sequência de comandos não depende do estado já armazenado.
- **[Risco] _pending_response com apenas um slot**: somente um `send_and_wait` ativo por vez. VehicleState e VeWriteController não devem chamar EcuProtocol concorrentemente. `_write_lock` garante isso.
- **[Trade-off] VehicleState mais pesado**: acumula responsabilidades de setup e mediação. Mitigação: extrair `EcuSessionSetup` se crescer demais, mas sem prematuridade.
- **[Risco] signal.py — mudança de índices**: separar D01 e D02 exige ajuste dos índices de todos os sinais. Risco de regressão silenciosa se algum índice estiver errado.

## Migration Plan

1. Criar `EcuTransport`, `EcuTransportSerial`, `EcuTransportMock` em `app/ecu_connection/`.
2. Criar `EcuProtocol` com `_send_and_wait`, `_write_lock`, read loop, métodos nomeados.
3. Criar hierarquia `EcuResponse` em `app/ecu_connection/responses.py`.
4. Adicionar `EcuFrameType`, `EcuFrameReceivedEvent`, `EcuHandshakeCompletedEvent`, `EcuResponseReceivedEvent` ao `app_events.py` e `bus.py`.
5. Remover `ScreenRequestedEvent` do bus; adicionar `screen_requested` pyqtSignal ao `Screen`.
6. Atualizar `signal.py`: adicionar `frame: EcuFrameType` e ajustar índices para relativos ao frame.
7. Atualizar `SignalProcessor` para consumir `EcuFrameReceivedEvent` e processar por frame_type.
8. Atualizar `VehicleState`: setup thread, assinatura de `EcuResponseReceivedEvent`.
9. Atualizar `LogWriter`: assinar `EcuFrameReceivedEvent` filtrado por D01.
10. Atualizar `VeWriteController` e `LambdaToggle` para delegar ao `VehicleState`.
11. Remover `ecu_connection.py`, `serial.py`, `mock_log.py`, `thread.py` (antigos); adaptar `thread.py` para `EcuProtocol`.
12. Simplificar `main.py`.

## Open Questions

- Formato exato da resposta de `open_lambda_loop` / `close_lambda_loop`: quais campos retorna `LambdaResponse`?
- `EcuD03` ainda não implementado — quando chegar, qual será o impacto em `signal.py`?
- `VeCalibrationScreen`: manter polling de 100 ms ou migrar para assinatura de `SignalsReceivedEvent`? (performance vs. throttle de UI)
