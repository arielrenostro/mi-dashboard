## Context

A comunicação com a ECU é atualmente gerenciada por `EcuConnectionSerial` (uma única classe que mistura transporte serial, protocolo de handshake, framing e fila de comandos) e por `EcuConnectionThread` (QThread externo que deve ser instanciado e iniciado manualmente em `main.py`). Comandos só são enviados após um par `#D01+#D02` completo, introduzindo latência e bloqueio. O pipeline de dados usa caminhos diretos (`emitter(str)` conectado diretamente ao `SignalProcessor` e ao `LogWriter`) que contornam o bus. `AlarmProcessor` possui uma thread dedicada que faz polling a cada 100ms, mesmo sem alarmes ativos. `VehicleState` é compartilhado globalmente sem encapsulamento de ciclo de vida.

## Goals / Non-Goals

**Goals:**
- Separar transporte serial (`EcuTransport`) de protocolo de sessão (`EcuSession`)
- Leitura e escrita ocorrem concorrentemente, sem bloqueio mútuo
- Thread de I/O internalizada na `EcuSession`; não é necessário instanciar ou iniciar externamente
- Todo envio de comando aguarda resposta com mesmo código, com contrato tipado por tipo de comando
- Frames individuais (`#D01`, `#D02`, `#D03`) publicados como `ECU_MESS_FRAME` no bus
- `SignalProcessor` processa frames individualmente; emite dados parciais
- `LogWriter` acumula `#D01`+`#D02` via bus antes de gravar linha
- `AlarmProcessor` sem thread de polling; estado de alarme centralizado no `VehicleState`
- Todo evento entre componentes passa pelo bus; telas emitem/consomem eventos do bus

**Non-Goals:**
- Redesign de UI ou layout de telas
- Adição de novos sinais ou mapas além dos já existentes
- Suporte a múltiplas ECUs simultâneas
- Migração para asyncio (`async`/`await`) — threading com Qt é mantido

## Decisions

### D1 — Thread única de I/O com leitura não-bloqueante

**Escolha:** `EcuSession` gerencia uma única thread interna que lê com timeout curto (50 ms) e drena a fila de escrita entre leituras.

**Alternativas consideradas:**
- *Duas threads (reader + writer separados):* pyserial permite acesso concorrente, mas comportamento varia por driver/SO. Risco de corrupção de estado no buffer de linha.
- *asyncio:* exigiria bridge complexo com Qt event loop. Excesso de complexidade para um cliente serial simples.

**Rationale:** Uma thread com reads não-bloqueantes é a abordagem padrão para serial com Qt e elimina race conditions de I/O sem overhead.

---

### D2 — Command-Response pairing via threading.Event

**Escolha:** `send_command(cmd, args)` cria um `threading.Event` e uma slot de resposta, enfileira o comando, bloqueia com timeout até a thread de leitura resolver o Event ao receber linha com código correspondente.

```
send_command(cmd, args) → response_line: str
  1. Cria entry: (cmd_str, expected_code, event, result_box)
  2. Coloca na write_queue
  3. Bloqueia: event.wait(timeout=5s)
  4. Retorna result_box[0] ou levanta TimeoutError
  
Reader thread, ao receber linha:
  - Se pending_cmd e linha.startswith(pending_cmd.expected_code):
      pending_cmd.result_box[0] = linha
      pending_cmd.event.set()
      pending_cmd = None
```

**Alternativas consideradas:**
- *Future/Promise:* mais idiomático, mas requer executor ou asyncio.
- *Queue de resposta por comando:* similar, mas Event é mais leve para caso 1-1.

**Rationale:** Simples, sem dependências extras, seguro com Python GIL.

---

### D3 — Contrato de resposta por tipo de comando

Três contratos, derivados dos requisitos:

| Tipo | Exemplo | Resposta esperada |
|---|---|---|
| **SetData** (define dados na ECU) | `#F01;row;v1;v2...` | `#F01;row;v1;v2...` (eco completo) |
| **GetData** (lê dados da ECU) | `#F02` | `#F02;v1;v2...` (comando + payload) |
| **SetState** (define estado) | `#F10` (open loop) | `#F10` (comando sem args) |

`EcuCommand` enum passa a ter campo `response_contract: ResponseContract`.

---

### D4 — ECU_MESS_FRAME publicado imediatamente pelo reader

A thread de leitura publica `ECU_MESS_FRAME` no bus via `QMetaObject.invokeMethod` (QueuedConnection) a cada frame recebido, sem esperar pelo par. `SignalProcessor` e `LogWriter` recebem frames individualmente e acumulam/processam conforme necessário.

**Alternativa considerada:** manter o join D01+D02 no transport. Rejeitado: a proposta exige frames independentes para permitir extensão ao D03 e processamento parcial.

---

### D5 — AlarmProcessor sem thread de polling

**Escolha:** `AlarmProcessor` subscreve `SIGNALS_RECEIVED` no bus. A cada recebimento, chama `vehicle_state.set_alarm(signal, in_alarm)` para atualizar o estado. Transição off→on: inicia áudio via `QTimer.singleShot(0, ...)` (main thread). Transição on→off: para áudio. Repetição de faixa: `QMediaPlayer.mediaStatusChanged` conectado a restart lógico quando `EndOfMedia` e alarme ainda ativo.

**Alternativa considerada:** manter polling thread de 100ms. Rejeitado: cria thread sempre ativa mesmo sem alarmes; evento `SIGNALS_RECEIVED` já chega com frequência suficiente (≈10 Hz).

---

### D6 — VehicleState autocontido com RLock

`VehicleState` mantém `threading.RLock` e gerencia seu ciclo de vida independentemente. Expõe métodos: `update_signals(data)`, `set_alarm(signal, active)`, `is_alarm_firing(signal)`, `is_any_alarm_firing()`, `set_lambda_state(state)`, `get_lambda_state()`. Nenhuma tela acessa o estado diretamente para escrita; toda escrita passa por esses métodos. Leitura é permitida via getters.

---

### D7 — EventBus: eventos revisados

Eventos removidos/renomeados:

| Atual | Novo | Motivo |
|---|---|---|
| `VEHICLE_STATE_CHANGED` | removido | `VehicleState` notifica via bus diretamente quando necessário |
| — | `ECU_MESS_FRAME` | novo: frame individual de ECU |
| — | `ECU_COMMAND_SEND` | novo: qualquer comando enviado |
| — | `ECU_COMMAND_RESPONSE` | novo: qualquer resposta (exceto MESS_FRAME) |
| `SIGNALS_RECEIVED` | mantido | `SignalProcessor` → bus |
| `ALARM_FIRED` | mantido | `AlarmProcessor` → bus |
| `SCREEN_REQUESTED` | mantido | navegação |
| `ECU_COMMAND_REQUESTED` | mantido | UI → ECU |
| `EVENT_MARK_REQUESTED` | mantido | log mark |

## Risks / Trade-offs

- **Latência de command-response:** `send_command` bloqueia a thread chamadora por até 5 s. Se chamado da main thread (UI), congela a interface. → Mitigação: `VeWriteController` e `LambdaToggle` já rodam em contextos não-UI; garantir que nenhuma tela chame `send_command` diretamente.

- **Acumulação de frames no LogWriter:** se `#D02` nunca chegar (falha de ECU), a linha nunca é gravada. → Mitigação: timeout de 500 ms para gravar D01 isolado com flag de dados incompletos.

- **Frames D03 sem mapeamento de sinais:** `SignalProcessor` processa D01 e D02; D03 é publicado mas ignorado por ora. → Mitigação: design permite extensão sem mudança de arquitetura.

- **Mudança de contrato de `EcuConnection`:** `VeWriteController` chama `get_ecu_connection().send_command()` diretamente. Após o refactor, chama `get_ecu_session().send_ve_row(...)`. → Mitigação: mapear todos os call sites antes de iniciar implementação.

## Migration Plan

1. Criar `app/ecu/transport/` com `EcuTransport` (serial + mock) sem remover código antigo
2. Criar `app/ecu/session/` com `EcuSession` usando `EcuTransport`
3. Migrar `main.py` para usar `EcuSession` (inicializa e gerencia thread internamente)
4. Publicar `ECU_MESS_FRAME` na session; ajustar `SignalProcessor` para subscrever
5. Ajustar `LogWriter` para acumular frames via bus
6. Ajustar `AlarmProcessor` (remover thread, usar eventos)
7. Revisar eventos do bus e renomear/remover
8. Remover `app/ecu_connection/` antigo e `EcuConnectionThread`

**Rollback:** branch isolada; `app/ecu_connection/` não é deletado até o final da migração.

## Open Questions

- `#D03` possui definição de sinais? Se sim, quais índices? (Necessário para `SignalProcessor` extensível)
- O timeout de 5 s para command-response é adequado para a ECU física? (Pode precisar de ajuste em `config.json`)
