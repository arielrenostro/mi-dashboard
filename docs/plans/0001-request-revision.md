# 0001 - Revisão das Tarefas de Refatoração

## Objetivo

Revisar e expandir as tarefas originais de refatoração, identificando contradições entre seções, itens faltantes, dependências implícitas e ambiguidades antes de produzir uma especificação técnica detalhada.

---

## Seção 1: Comunicação com ECU (revisada e expandida)

### Tarefas originais preservadas

- Comunicação deve ser assíncrona.
- Read e Write devem acontecer em paralelo.
- Leituras realizadas sempre devem gerar eventos no Bus.
- Separar camada de transporte da camada de protocolo (Session) da ECU.
- Na camada de Session, devem existir métodos para solicitar dados da ECU (`open_loop`, `close_loop`, `fetch_ve`, `fetch_ignition`, etc.) para os comandos já definidos.
- A thread deve ser internalizada na Session, não sendo necessário instanciá-la externamente — a Session controla o ciclo de vida da thread.
- Os comandos e respostas da ECU devem estar estruturados no projeto.
- Emitir evento `ECU_COMMAND_SENT` *(corrigido de "SEND" para "SENT" — padrão past tense)* para qualquer comando enviado.
- Emitir evento `ECU_COMMAND_RESPONSE` para qualquer resposta da ECU, exceto frames de medição.
- Emitir evento `ECU_MESS_FRAME` para cada frame D01, D02, D03 recebido individualmente.
- Todo envio de comando deve esperar resposta da ECU cujo início de linha coincide com o código do comando enviado.
- Para comandos que definem dados (ex.: VE): aguardar resposta com o mesmo comando + args.
- Para comandos que leem dados (ex.: ler VE): aguardar resposta com o mesmo comando + args.
- Para comandos de estado (ex.: open/close loop): aguardar resposta com o mesmo comando, sem args.

### Problemas identificados e como foram resolvidos

**P1.1 — "Read e Write em paralelo" vs. protocolo síncrono de handshake**

**Resolução (confirmada pelo usuário):** O handshake não precisa de complexidade extra — pode continuar síncrono e simples. Após o handshake e início do streaming:
- **Read:** acontece de forma assíncrona em thread separada, publicando eventos no bus a cada frame recebido.
- **Write (dois modos):**
  - *Blocking (request/response):* a chamada enfileira o comando e aguarda a resposta correspondente chegar (usado para comandos que exigem confirmação, como fetch de dados).
  - *Fire-and-forget com response assíncrona:* o comando é enviado sem bloquear o chamador; a resposta chega via evento `ECU_COMMAND_RESPONSE` no bus (usado quando o chamador não precisa aguardar sincronamente).
- A fila `_command_queue` existente em `serial.py` é a base correta; apenas a semântica de espera de resposta precisa ser implementada nos dois modos.

**P1.2 — "A thread deve ser internalizada na Session" é contraditória com PyQt6 `QThread`**

**Resolução:** A Session internaliza a thread de leitura usando `threading.Thread` (não `QThread`). Comunicação com o Qt ocorre exclusivamente via `event_bus.publish()`, que usa `pyqtSignal.emit()` — thread-safe e entregue via `QueuedConnection`. O `EcuConnectionThread` é eliminado.

**P1.3 — Evento `ECU_MESS_FRAME` individual vs. acumulação no `LogWriter`**

**Resolução (confirmada pelo usuário):** O `LogWriter` mantém buffer interno que acumula D01 e D02 separadamente; só grava a linha CSV quando ambos chegaram. O flag de evento (`MARK`) e o timestamp são aplicados no momento da gravação completa do par.

**P1.4 — Faltam comandos no `EcuCommand` para as Session-methods propostas**

**Resolução (confirmada pelo usuário):** Os comandos `fetch_ignition` e similares utilizam o prefixo `#Ixx` — análogos aos `#Fxx` de VE. Os comandos `#I20` (RPM_BREAKPOINTS) e `#I21` (MAP_BREAKPOINTS) já existem em `protocol.py`. Comandos adicionais de ignição (ex.: `#I01`..`#I16` para linhas do mapa de ignição) devem ser adicionados ao `EcuCommand` seguindo o mesmo padrão. A implementação de `fetch_ignition` pode aguardar mapeamento completo do protocolo, mas a estrutura já está clara.

**P1.5 — Falta especificar timeout de resposta**

**Resolução (confirmada pelo usuário):** 1 retentativa, timeout de 3 segundos por tentativa. Após a retentativa falhar, logar warning e prosseguir sem bloquear.

**P1.6 — EcuConnectionMock precisa ser adaptado**

**Resolução (confirmada pelo usuário):** O `EcuConnectionMock` será reescrito como `MockTransport(EcuTransport)`. O mock deve simular o protocolo da ECU real: responder às requisições de handshake, de fetch de VE/breakpoints e de estado de loop, além de emitir frames D01/D02 com timing baseado em CSV. O TODO existente em `mock_log.py` é resolvido nesta refatoração.

### Itens adicionados

- A Session deve emitir evento `ECU_CONNECTION_STATUS_CHANGED` quando o status de conexão mudar.
- O `EcuConnectionMock` deve ser reescrito como `MockTransport` seguindo a interface `EcuTransport`.
- Timeout: 3 segundos; retentativas: 1 (total de 2 tentativas antes de desistir).

---

## Seção 2: Pipeline de Dados (EventBus) (revisada e expandida)

### Tarefas originais preservadas

- Todo e qualquer evento deve passar pelo EventBus, com exceção dos internos às telas.
- Telas (UI) devem se inscrever nos eventos do EventBus desejados.
- Telas (UI) devem emitir eventos pelo EventBus que impactem camadas fora da UI.
- Telas (UI) devem emitir eventos "locais" sem misturar comportamentos de UI com o restante da aplicação.
- Revisar eventos atuais: renomear, criar ou excluir os desnecessários.
- **LogWriter:** deve acumular frames D01 e D02 e então gravar uma nova linha do CSV; demais funcionalidades (timestamp, mark) devem continuar funcionando.
- **SignalProcessor:** não deve mais depender de receber frames D01 e D02 juntos; deve processá-los individualmente, inscrevendo-se no bus para receber `ECU_MESS_FRAME`; deve disparar sinais pelo bus após processamento, sempre permitindo envio parcial de dados.
- **AlarmProcessor:** deve conversar melhor com o `VehicleState` para popular o estado dos alertas; não deve ter thread rodando sempre — apenas tocar áudio quando necessário.

### Problemas identificados e como foram resolvidos

**P2.1 — `VeCalibrationScreen` usa `vehicle_state.emitter` diretamente, contornando o EventBus**

**Resolução (confirmada pelo usuário):** VeCalibrationScreen deve migrar para o bus. Remover `vehicle_state.emitter.connect(...)` do `__init__` e substituir por `self._subscribe(AppEventType.VEHICLE_STATE_CHANGED, ...)` em `on_activated()`.

**P2.2 — `VeCalibrationScreen` chama `get_ecu_connection().send_command()` diretamente**

**Resolução (confirmada pelo usuário):** Substituir por `event_bus.publish(EcuCommandRequestedEvent(...))`. Alinhado com P2.1.

**P2.3 — `VeWriteController` chama `get_ecu_connection().send_command()` diretamente**

**Resolução (confirmada pelo usuário):** `VeWriteController._send_pending_rows()` deve publicar `EcuCommandRequestedEvent` no bus ao invés de chamar a ECU diretamente.

**P2.4 — `SignalProcessor` ainda publica via `emitter` legado além do bus**

**Resolução:** Remover `self.emitter` após migração de todos os consumidores para o bus. O emitter legado sustentava `DashboardScreen` e `LambdaLoopStateProcessor` — ambos migram para bus nesta refatoração.

**P2.5 — `SignalProcessor` depende de índices absolutos combinados D01+D02**

**Resolução (confirmada pelo usuário):** Redefinir os índices em `signal.py` por frame. Cada `Signal` deve declarar explicitamente de qual frame vem (`"frame": "D01"` ou `"D02"`) e qual é o índice dentro daquele frame específico (contando a partir de 1, após o prefixo). O `SignalProcessor` mantém buffers separados por frame e processa cada Signal usando o frame e índice corretos ao invés de índice absoluto no frame combinado.

**P2.6 — `AlarmProcessor` é `QThread` — tarefa pede eliminação da thread contínua**

**Resolução:** `AlarmProcessor` deixa de ser `QThread` e torna-se `QObject` na main thread. Um `QTimer` (100ms) substitui o polling da thread para controle de play/stop de áudio. `QMediaPlayer` é chamado diretamente (mesmo thread), sem `QueuedConnection`.

**P2.7 — `StateProcessorRegister` e `LambdaLoopStateProcessor` não estão documentados na tarefa**

**Resolução (confirmada pelo usuário):** `StateProcessorRegister` e `LambdaLoopStateProcessor` foram intencionalmente desativados. Manter no estado atual — não refatorar, não ativar, não remover. Saída do escopo desta refatoração.

**P2.8 — Tarefa "eventos locais de UI" está ambígua**

**Resolução (confirmada pelo usuário):** Eventos que afetam apenas a UI (ex.: animação visual de alarme, navegação interna de tela) ficam como `pyqtSignal` internos da tela ou componente. Eventos que impactam camadas externas à UI (ex.: `EcuCommandRequestedEvent`, `ScreenRequestedEvent`) obrigatoriamente passam pelo bus.

**P2.9 — `EventMarker` está comentado no main.py — manter ou remover?**

**Resolução (confirmada pelo usuário):** Manter comentado. Não implementar, não remover. Fora do escopo desta refatoração.

### Itens adicionados

- Definição explícita de "evento local de UI" vs. "evento de bus" (ver P2.8).
- `signal.py` receberá dois novos campos por Signal: `"frame"` e `"frame_index"` para separar índices por frame.

---

## Seção 3: VehicleState (revisada e expandida)

### Tarefas originais preservadas

- Deve ser desacoplado da tela e controlar seu próprio estado independentemente.
- Deve representar o estado atual do veículo: últimos sinais, estado de alerta, estado de lambda loop, etc. — sempre presentes.

### Problemas identificados e como foram resolvidos

**P3.1 — `VehicleState` já é razoavelmente desacoplado, mas ainda possui `emitter` próprio**

**Resolução (confirmada pelo usuário):** O `emitter` interno do `VehicleState` é substituído por publicações no `event_bus`. O import circular é resolvido com **import local** dentro dos métodos que publicam (ex.: `from app.event.bus import event_bus` dentro de `set_rpm_breakpoints`). Contexto adicional: num futuro próximo, `VehicleState` servirá como camada de controle entre UI e `EcuSession`, guardando estado e respostas de itens já consultados na ECU — o desacoplamento atual já apoia essa evolução.

**P3.2 — `set_alarm` em `VehicleState` atualiza apenas um timestamp, sem expiração gerenciada**

**Resolução:** `VehicleState.set_alarm(signal, active, duration_s)` recebe duração configurável por sinal. `is_alarm_firing(signal)` usa `expires_at` armazenado junto ao timestamp. `ALARM_DURATION` global fixo é removido.

**P3.3 — `VehicleState.update()` parcial com separação de frames**

**Resolução:** Comportamento aceitável: `update()` pode ser chamado múltiplas vezes por ciclo com dados parciais (um snapshot D01 e depois um com D02). O lock existente (`RLock`) garante consistência. `get_all()` pode retornar snapshot com mistura de ciclos — isso é tolerável dado o intervalo de ~10ms entre D01 e D02 do mesmo ciclo.

**P3.4 — Estado de alarme não exporta duração configurável por sinal**

**Resolução:** `VehicleState.set_alarm` aceita `duration_s` (float). A estrutura interna muda de `_alarm_timestamps: dict[Signal, float]` para `_alarm_timestamps: dict[Signal, tuple[float, float]]` onde `(fired_at, expires_at)`.

### Itens adicionados

- `VehicleState.set_alarm(signal, active, duration_s)` com duração configurável.
- Import local de `event_bus` dentro dos métodos que publicam (sem import circular no nível de módulo).
- Remover `_VehicleStateEmitter` e `vehicle_state.emitter`.

---

## Resumo dos Problemas Encontrados

| ID | Categoria | Descrição resumida | Status |
|---|---|---|---|
| P1.1 | Contradição entre seções | "R/W paralelo" vs. protocolo síncrono de handshake | Resolvido: handshake simples; post-handshake com dois modos de write |
| P1.2 | Risco técnico | Internalizar thread na Session conflita com modelo QThread do Qt | Resolvido: threading.Thread + event_bus |
| P1.3 | Dependência implícita | ECU_MESS_FRAME individual exige buffer no LogWriter | Resolvido: buffer interno D01+D02 no LogWriter |
| P1.4 | Item faltante | `fetch_ignition` não tem comando definido no protocolo | Resolvido: prefixo #Ixx, análogos aos #Fxx |
| P1.5 | Ambiguidade | Timeout/retentativas não especificados | Resolvido: 1 retentativa, 3s timeout |
| P1.6 | Impacto não mencionado | EcuConnectionMock precisa seguir nova interface de Session | Resolvido: reescrever como MockTransport |
| P2.1 | Contradição com código atual | VeCalibrationScreen usa `vehicle_state.emitter` contornando o bus | Resolvido: migrar para bus |
| P2.2 | Contradição com regra de UI | VeCalibrationScreen chama ECU diretamente | Resolvido: EcuCommandRequestedEvent via bus |
| P2.3 | Contradição com regra de UI | VeWriteController chama ECU diretamente | Resolvido: EcuCommandRequestedEvent via bus |
| P2.4 | Item faltante | SignalProcessor tem emitter legado que precisa ser eliminado | Resolvido: remover após migração de consumidores |
| P2.5 | Risco técnico | Índices de sinais são absolutos no frame combinado — separação exige revisão de signal.py | Resolvido: adicionar campos "frame" e "frame_index" em signal.py |
| P2.6 | Contradição | AlarmProcessor é QThread mas tarefa pede sem thread contínua | Resolvido: QObject + QTimer |
| P2.7 | Impacto não mencionado | LambdaLoopStateProcessor e StateProcessorRegister precisam ser adaptados | Resolvido: manter desativados, fora do escopo |
| P2.8 | Ambiguidade | "eventos locais de UI" não está claramente definido | Resolvido: pyqtSignal para UI interna, bus para impacto externo |
| P2.9 | Ambiguidade | EventMarker está comentado no main.py — manter ou remover? | Resolvido: manter comentado, fora do escopo |
| P3.1 | Risco técnico | Substituir emitter do VehicleState por event_bus pode criar dependência circular | Resolvido: import local dentro dos métodos |
| P3.2 | Contradição | Lógica de expiração de alarme duplicada entre AlarmProcessor e VehicleState | Resolvido: VehicleState como fonte de verdade com duração configurável |
| P3.3 | Ambiguidade | Comportamento de update() parcial com separação de frames | Resolvido: comportamento parcial aceitável com RLock |
| P3.4 | Item faltante | VehicleState.set_alarm não aceita duração configurável por sinal | Resolvido: parâmetro duration_s |
