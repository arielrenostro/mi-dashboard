# 0003 — Plano de Execução

Plano de execução paralelizável para o refactor de arquitetura do mi-dashboard. Gerado a partir da análise dos documentos `0001-request-revision.md` e `0002-spec-revision.md` confrontados com o código real.

---

## Histórias / Atividades

| ID | Arquivo | Título | Grupo | Complexidade |
|---|---|---|---|---|
| HIST-01 | `0004-hist-01.md` | Criar EcuTransport — Camada de Transporte Serial Abstrata | A — ECU | Baixa |
| HIST-02 | `0005-hist-02.md` | Criar EcuSession — Protocolo com Threading Internalizada | A — ECU | Alta |
| HIST-03 | `0006-hist-03.md` | Refatorar EcuConnectionMock para MockEcuTransport | A — ECU | Média |
| HIST-04 | `0007-hist-04.md` | Adicionar Novos Eventos ECU ao EventBus | B — Bus | Baixa |
| HIST-05 | `0008-hist-05.md` | Refatorar SignalProcessor para ECU_MESS_FRAME | B — Bus | Média |
| HIST-06 | `0009-hist-06.md` | Refatorar LogWriter para Acumular ECU_MESS_FRAME | B — Bus | Baixa |
| HIST-07 | `0010-hist-07.md` | Desacoplar VehicleState do Emitter Direto | C — State | Média |
| HIST-08 | `0011-hist-08.md` | Adaptar VeCalibrationScreen e VeWriteController ao Bus | D — UI | Média |
| HIST-09 | `0012-hist-09.md` | Refatorar AlarmProcessor e LambdaLoopStateProcessor | B — Bus | Média |
| HIST-10 | `0013-hist-10.md` | Atualizar main.py — Remover Conexões Diretas | E — Wiring | Baixa |
| HIST-11 | `0014-hist-11.md` | Remover Código Legado e Arquivos Obsoletos | E — Cleanup | Baixa |

---

## Grafo de Dependências

```
HIST-01 ──┬──► HIST-02 ──┬──► HIST-03
           │              ├──► HIST-10 (após todas)
           │              └──► (permite HIST-08 via get_ecu_session)
           └──► HIST-03

HIST-04 ──┬──► HIST-02 (EcuSession publica eventos)
           ├──► HIST-05 (SignalProcessor subscreve ECU_MESS_FRAME)
           ├──► HIST-06 (LogWriter subscreve ECU_MESS_FRAME)
           └──► HIST-09 (LambdaLoopStateProcessor subscreve ECU_COMMAND_RESPONSE)

HIST-05 ──► HIST-10 (main.py remove conexão direta)
HIST-06 ──► HIST-10 (main.py remove conexão direta)

HIST-07 ──┬──► HIST-08 (VeCalibrationScreen usa Bus em vez de emitter)
           └──► HIST-09 (set_alarm com until)

HIST-08 ──► HIST-11 (remoção de app/state/event.py)
HIST-09 ──► HIST-11 (remoção de StateProcessorRegister)
HIST-10 ──► HIST-11 (tudo wired antes do cleanup)
```

### Tabela de dependências

| História | Depende de | Permite |
|---|---|---|
| HIST-01 | — | HIST-02, HIST-03 |
| HIST-02 | HIST-01, HIST-04 | HIST-03, HIST-05*, HIST-08, HIST-10 |
| HIST-03 | HIST-01, HIST-02 | HIST-10 |
| HIST-04 | — | HIST-02, HIST-05, HIST-06, HIST-09 |
| HIST-05 | HIST-04 | HIST-10 |
| HIST-06 | HIST-04 | HIST-10 |
| HIST-07 | — | HIST-08, HIST-09 |
| HIST-08 | HIST-07, HIST-02 | HIST-11 |
| HIST-09 | HIST-04, HIST-07 | HIST-10, HIST-11 |
| HIST-10 | HIST-01–09 (todos) | HIST-11 |
| HIST-11 | HIST-10 | — |

*HIST-05 depende de HIST-04 (ECU_MESS_FRAME no Bus) e de HIST-02 indiretamente (Session emite os eventos).

---

## Ondas de Execução (Batches Paralelizáveis)

### Onda 1 — Fundações Independentes

Podem ser executadas em paralelo. Nenhuma depende da outra.

| História | O que faz | Estimativa |
|---|---|---|
| **HIST-01** | Criar `EcuTransport` (abstract, SerialTransport, MockTransport) | 2–3h |
| **HIST-04** | Adicionar 3 novos eventos ao EventBus e dataclasses | 1–2h |
| **HIST-07** | Desacoplar VehicleState: publicar via Bus + corrigir bug ALARM_DURATION | 3–4h |

**Pré-requisitos para esta onda:** nenhum (código limpo de partida).

**Pontos de atenção:**
- HIST-01: verificar que `transport.py` não importa nada de `app/` (apenas stdlib + pyserial).
- HIST-04: verificar que não há importação circular entre `app_events.py` e `protocol.py`.
- HIST-07: usar lazy import para `event_bus` dentro dos métodos de `VehicleState` (evitar instanciação do Bus antes do `QApplication`).

---

### Onda 2 — Camada ECU e Adaptadores de Bus

Dependem da Onda 1. HIST-02 e HIST-05/06/09 podem ser desenvolvidas em paralelo entre si (desde que HIST-04 esteja pronta).

| História | O que faz | Estimativa | Depende de |
|---|---|---|---|
| **HIST-02** | Criar EcuSession (threads internas, handshake, request/response, eventos) | 8–12h | HIST-01 + HIST-04 |
| **HIST-05** | Refatorar SignalProcessor para ECU_MESS_FRAME + acumulação D01/D02 | 3–4h | HIST-04 |
| **HIST-06** | Refatorar LogWriter para ECU_MESS_FRAME + acumulação D01/D02 | 2–3h | HIST-04 |
| **HIST-09** | Refatorar AlarmProcessor (QTimer) + LambdaLoopStateProcessor (Bus) | 4–5h | HIST-04 + HIST-07 |

**Pré-requisitos para esta onda:** Onda 1 completa.

**Pontos de atenção:**
- HIST-02 é a mais complexa do projeto inteiro. Envolve threading, sincronização, handshake e protocolo. Deve ser desenvolvida com atenção especial.
- HIST-05 e HIST-06 podem ser desenvolvidas em paralelo com HIST-02 (só precisam de HIST-04).
- HIST-09 pode começar em paralelo com HIST-02 (precisa de HIST-04 e HIST-07).

---

### Onda 3 — Mock e Adaptação de UI

Dependem da Onda 2 (principalmente HIST-02 e HIST-07).

| História | O que faz | Estimativa | Depende de |
|---|---|---|---|
| **HIST-03** | Criar MockEcuTransport (replay CSV + respostas de handshake) | 4–5h | HIST-01 + HIST-02 |
| **HIST-08** | Adaptar VeCalibrationScreen + VeWriteController ao Bus e Session | 3–4h | HIST-07 + HIST-02 |

**Pré-requisitos para esta onda:** Onda 2 completa (HIST-01, HIST-02, HIST-04, HIST-07).

---

### Onda 4 — Wiring Final

Depende de todas as histórias anteriores.

| História | O que faz | Estimativa | Depende de |
|---|---|---|---|
| **HIST-10** | Reescrever main.py, remover conexões diretas, instanciar EcuSession | 2–3h | HIST-01–09 todos |

---

### Onda 5 — Cleanup

Depende de Onda 4 completa.

| História | O que faz | Estimativa | Depende de |
|---|---|---|---|
| **HIST-11** | Remover arquivos e construções obsoletas, verificar com grep | 2–3h | HIST-10 |

---

## Resumo de Ondas

```
ONDA 1 (paralelo):    HIST-01  HIST-04  HIST-07
                         ↓        ↓        ↓
ONDA 2 (paralelo):    HIST-02  HIST-05  HIST-06  HIST-09
                         ↓
ONDA 3 (paralelo):    HIST-03  HIST-08
                         ↓
ONDA 4 (sequencial):  HIST-10
                         ↓
ONDA 5 (sequencial):  HIST-11
```

---

## Caminho Crítico

O caminho crítico é a sequência mais longa e bloqueante:

```
HIST-01 (2–3h)
  → HIST-02 (8–12h)   ← HIST-04 (1–2h, paralelo)
    → HIST-03 (4–5h)
      → HIST-10 (2–3h)
        → HIST-11 (2–3h)
```

**Total no caminho crítico: ~19–25h de implementação efetiva**

Com paralelização nas ondas 1 e 2, o tempo de calendário pode ser reduzido significativamente.

---

## Pontos de Decisão do Usuário (DECISION_NEEDED)

Estes pontos foram identificados nos documentos de revisão e impactam histórias específicas. Requerem uma decisão antes de prosseguir.

### [DECISION-1] Thread model da EcuSession (HIST-02)

**Impacta:** HIST-02

**Contexto (DECISION_NEEDED-1.1):** A Session deve usar `threading.Thread` Python puras ou `QThread`?

**Decisão tomada neste plano:** `threading.Thread` Python puras. A publicação no EventBus é thread-safe via `pyqtSignal`. Essa decisão está incorporada na spec de HIST-02.

**Se o usuário preferir QThread:** a spec de HIST-02 precisará ser revisada para incluir cuidados com thread affinity de QObject.

---

### [DECISION-2] Métodos nomeados na Session (HIST-02)

**Impacta:** HIST-02, HIST-08, HIST-10

**Contexto (DECISION_NEEDED-1.2):** Quais comandos terão métodos nomeados na Session vs. API genérica `send_command()`?

**Decisão tomada neste plano:** Apenas `open_loop()` e `close_loop()` como métodos nomeados. Demais comandos (VE rows, etc.) passam por `send_command()`.

**Se o usuário quiser mais métodos nomeados:** adicionar `fetch_ve(row)`, `write_ve_row(row, values)`, etc. em HIST-02.

---

### [DECISION-3] ECU_COMMAND_REQUESTED — manter ou remover (HIST-10, HIST-11)

**Impacta:** HIST-10, HIST-11

**Contexto (DECISION_NEEDED-2.1):** Com a Session tendo métodos nomeados, o evento `ECU_COMMAND_REQUESTED` ainda é necessário?

**Decisão tomada neste plano:** Remover do fluxo ativo. `LambdaToggle` chamará `get_ecu_session().open_loop()/close_loop()` diretamente. Se outro componente precisar enviar comandos no futuro, pode ser readicionado.

---

### [DECISION-4] Unificação de EventType e AppEventType (HIST-07, HIST-11)

**Impacta:** HIST-07, HIST-08, HIST-11

**Contexto (DECISION_NEEDED-2.2 / análise CONFLICT de Seção 2.5):** `app/state/event.py` tem `EventType` (MAP_BREAKPOINTS, RPM_BREAKPOINTS, FUEL_MAP). `AppEventType` em `app_events.py` tem eventos diferentes. Devemos unificar?

**Decisão tomada neste plano:** NÃO unificar neste ciclo de refactor. `VehicleStateChangedEvent.change_type` continua usando `EventType` de `app/state/event.py`. Após HIST-11 remover o arquivo, os valores de `EventType` são inlined ou recriados em `app_events.py`. Esta decisão pode ser revisada antes de HIST-11.

**Needs decision before HIST-11:** O que fazer com `EventType` após remoção de `app/state/event.py`?

---

### [DECISION-5] fetch_ignition — comando inexistente

**Impacta:** HIST-02 (métodos nomeados)

**Contexto (MISSING-1.2):** `fetch_ignition` é mencionado nos requisitos originais mas não existe nenhum `EcuCommand` equivalente.

**Decisão tomada neste plano:** NÃO implementar `fetch_ignition` neste ciclo. Adicionar ao `EcuCommand` e `EcuResponse` enums quando o protocolo for definido.

---

## Riscos e Mitigações

| Risco | Impacto | História afetada | Mitigação |
|---|---|---|---|
| RISK-1: índices de Signal enum com frames separados | Alto | HIST-05 | Usar Opção A: SignalProcessor recombina D01+D02 antes de parsear — nenhuma mudança em `signal.py` |
| RISK-2: dependência circular VehicleState→event_bus | Médio | HIST-07 | Lazy import dentro dos métodos; instanciação de `vehicle_state` no módulo não importa event_bus no nível de módulo |
| RISK-3: EcuConnectionMock incompatível | Médio | HIST-03 | HIST-03 cria MockEcuTransport completo que simula o protocolo |
| RISK-4: LambdaLoopStateProcessor desconectado | Médio | HIST-09 | HIST-09 migra explicitamente para Bus |
| RISK-5: QMediaPlayer thread affinity | Baixo | HIST-09 | Eliminado — AlarmProcessor passa para main thread com QTimer |
| RISK-6: VeWriteController bypass do Bus | Baixo | HIST-08 | HIST-08 substitui por chamada ao método de Session |

---

## Arquivos Criados/Modificados por História

| Arquivo | HIST-01 | HIST-02 | HIST-03 | HIST-04 | HIST-05 | HIST-06 | HIST-07 | HIST-08 | HIST-09 | HIST-10 | HIST-11 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `app/ecu_connection/transport.py` | CRIAR | — | — | — | — | — | — | — | — | — | — |
| `app/ecu_connection/session.py` | — | CRIAR | — | — | — | — | — | — | — | — | — |
| `app/ecu_connection/mock_transport.py` | — | — | CRIAR | — | — | — | — | — | — | — | — |
| `app/ecu_connection/__init__.py` | — | MOD | — | — | — | — | — | — | — | MOD | MOD |
| `app/ecu_connection/thread.py` | — | — | — | — | — | — | — | — | — | — | REMOVER |
| `app/ecu_connection/serial.py` | — | — | — | — | — | — | — | — | — | — | REMOVER |
| `app/ecu_connection/mock_log.py` | — | — | DEP | — | — | — | — | — | — | — | REMOVER |
| `app/ecu_connection/ecu_connection.py` | — | — | — | — | — | — | — | — | — | — | AVALIAR |
| `app/event/app_events.py` | — | — | — | MOD | — | — | — | — | — | — | MOD |
| `app/event/bus.py` | — | — | — | MOD | — | — | — | — | — | — | MOD |
| `app/masterinjection/signal_processor.py` | — | — | — | — | MOD | — | — | — | — | — | MOD |
| `app/log_writer/log_writer.py` | — | — | — | — | — | MOD | — | — | — | — | MOD |
| `app/state/state.py` | — | — | — | — | — | — | MOD | — | — | — | MOD |
| `app/state/event.py` | — | — | — | — | — | — | — | — | — | — | REMOVER |
| `app/state/register.py` | — | — | — | — | — | — | — | — | — | — | REMOVER |
| `app/state/processors/lambda_loop_state.py` | — | — | — | — | — | — | — | — | MOD | — | — |
| `app/state/processors/base.py` | — | — | — | — | — | — | — | — | — | — | REMOVER |
| `app/alarm/processor.py` | — | — | — | — | — | — | — | — | MOD | — | — |
| `app/ui/ve_calibration/screen.py` | — | — | — | — | — | — | — | MOD | — | — | — |
| `app/ui/ve_calibration/ve_write_controller.py` | — | — | — | — | — | — | — | MOD | — | — | — |
| `app/event/lambda_toggle.py` | — | — | — | — | — | — | — | — | — | MOD | — |
| `main.py` | — | — | — | — | — | — | — | — | — | MOD | — |

---

## Estimativa Total

| Onda | Histórias | Estimativa (paralelo) | Estimativa (sequencial) |
|---|---|---|---|
| Onda 1 | HIST-01, HIST-04, HIST-07 | 3–4h | 6–9h |
| Onda 2 | HIST-02, HIST-05, HIST-06, HIST-09 | 8–12h | 17–24h |
| Onda 3 | HIST-03, HIST-08 | 4–5h | 7–9h |
| Onda 4 | HIST-10 | 2–3h | 2–3h |
| Onda 5 | HIST-11 | 2–3h | 2–3h |
| **Total** | 11 histórias | **19–27h** | **34–48h** |
