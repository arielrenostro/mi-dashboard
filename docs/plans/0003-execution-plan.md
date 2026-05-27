# 0003 — Plano de Execução Paralelizável

## Visão Geral

Este documento organiza as 12 histórias de refatoração do dashboard de telemetria em fases de execução paralelizáveis. O objetivo é minimizar o tempo total de implementação permitindo que histórias independentes corram em paralelo.

A refatoração cobre cinco grandes áreas:
- **Camada de comunicação** (Transport/Session/EcuSession)
- **Sinais** (frame/frame_index no enum Signal)
- **EventBus** (4 novos tipos de evento)
- **Processadores de dados** (SignalProcessor, LogWriter, AlarmProcessor, VehicleState)
- **UI e wiring** (VeCalibration, AppWindow, main.py)

---

## Diagrama de Fases

```
FASE 1 (paralelo total — sem dependências)
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  H01 (0004)     │  │  H02 (0005)     │  │  H03 (0006)     │
│  Novos Eventos  │  │  frame/frame_   │  │  EcuTransport   │
│  no EventBus    │  │  index em Signal│  │  ABC            │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                     │
         └──────────┬─────────┘                     │
                    │                               │
FASE 2 (paralelo parcial — dependem de H03)         │
                    │             ┌─────────────────┘
                    │        ┌────┴────────┐  ┌─────────────────┐
                    │        │  H04 (0007) │  │  H05 (0008)     │
                    │        │  Serial     │  │  Mock           │
                    │        │  Transport  │  │  Transport      │
                    │        └──────┬──────┘  └──────┬──────────┘
                    │               │                │
FASE 3 (sequencial — depende de H01+H04+H05)        │
                    │               └────────┬───────┘
                    └────────────────────────┤
                                             ▼
                                    ┌─────────────────┐
                                    │  H06 (0009)     │
                                    │  EcuSession     │
                                    └────────┬────────┘
                                             │
FASE 4 (paralelo — dependem de H06+H01+H02) │
          ┌──────────────┬──────────────┬───┴──────────────┐
          ▼              ▼              ▼                   ▼
 ┌──────────────┐ ┌────────────┐ ┌──────────────┐ ┌──────────────┐
 │  H07 (0010)  │ │  H08(0011) │ │  H09 (0012)  │ │  H10 (0013)  │
 │  Signal-     │ │  LogWriter │ │  Alarm-      │ │  Vehicle-    │
 │  Processor   │ │  D01+D02   │ │  Processor   │ │  State       │
 │  buffers     │ │  buffer    │ │  QTimer      │ │  desacoplado │
 └──────┬───────┘ └────┬───────┘ └──────┬───────┘ └──────┬───────┘
        │              │                │                 │
        └──────────────┴────────────────┴─────────────────┘
                                    │
FASE 5 (paralelo parcial — dependem de H10+H06)
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
           ┌────────────────┐             ┌──────────────────┐
           │  H11 (0014)    │             │  H12 (0015)      │
           │  VeCalibration │             │  AppWindow +     │
           │  UI → bus      │             │  main.py final + │
           │                │             │  remoção legados │
           └────────────────┘             └──────────────────┘
```

---

## Tabela de Histórias

| ID Arquivo | Hist | Título                                      | Fase | Depende de           | Paralelo com       |
|------------|------|---------------------------------------------|------|----------------------|--------------------|
| 0004       | H01  | Novos Eventos no EventBus                   | 1    | —                    | H02, H03           |
| 0005       | H02  | Campos frame e frame_index em Signal        | 1    | —                    | H01, H03           |
| 0006       | H03  | EcuTransport ABC                            | 1    | —                    | H01, H02           |
| 0007       | H04  | SerialTransport                             | 2    | H03                  | H05                |
| 0008       | H05  | MockTransport                               | 2    | H03                  | H04                |
| 0009       | H06  | EcuSession                                  | 3    | H01, H03, H04, H05  | —                  |
| 0010       | H07  | SignalProcessor com buffers por frame       | 4    | H01, H02, H06        | H08, H09, H10      |
| 0011       | H08  | LogWriter com buffer D01+D02               | 4    | H01, H06             | H07, H09, H10      |
| 0012       | H09  | AlarmProcessor: QThread → QObject+QTimer   | 4    | H06 (para testar)    | H07, H08, H10      |
| 0013       | H10  | VehicleState desacoplado                   | 4    | H01 (VEHICLE_STATE_CHANGED existe)| H07, H08, H09|
| 0014       | H11  | VeCalibrationScreen + VeWriteController    | 5    | H10, H06, H01        | H12 (parcial)      |
| 0015       | H12  | AppWindow + main.py + remoção obsoletos    | 5    | H07–H11              | H11 (parcial)      |

---

## Detalhe das Fases

### Fase 1 — Fundações Independentes

**Duração estimada:** curta (histórias simples, sem dependências)  
**Histórias:** H01, H02, H03  
**Podem rodar em paralelo:** sim, as três simultaneamente

| História | O que faz | Arquivos modificados |
|----------|-----------|----------------------|
| H01 | Adiciona 4 novos tipos de evento no bus | `app/event/app_events.py`, `app/event/bus.py` |
| H02 | Adiciona `frame` e `frame_index` em cada Signal | `app/masterinjection/signal.py` |
| H03 | Cria ABC `EcuTransport` | `app/ecu_connection/transport.py` (novo) |

**Critério de sucesso da Fase 1:**
- `from app.event.app_events import EcuMessFrameEvent` funciona.
- `Signal.RPM.value["frame"]` retorna `"D01"`.
- `from app.ecu_connection.transport import EcuTransport` funciona.
- O app existente inicia sem erros (nenhuma quebra).

---

### Fase 2 — Implementações de Transport

**Duração estimada:** média  
**Histórias:** H04, H05  
**Dependência:** H03 (EcuTransport ABC)  
**Podem rodar em paralelo:** sim, H04 e H05 simultaneamente

| História | O que faz | Arquivos modificados |
|----------|-----------|----------------------|
| H04 | Cria `SerialTransport(EcuTransport)` | `app/ecu_connection/serial_transport.py` (novo) |
| H05 | Cria `MockTransport(EcuTransport)` com simulação de protocolo | `app/ecu_connection/mock_transport.py` (novo) |

**Critério de sucesso da Fase 2:**
- `SerialTransport` instancia sem erros.
- `MockTransport` responde ao handshake simulado com os prefixos corretos.
- App existente ainda funciona (nenhum arquivo antigo removido).

---

### Fase 3 — EcuSession (sequencial)

**Duração estimada:** alta (componente mais complexo)  
**Histórias:** H06  
**Dependência:** H01, H03, H04, H05  
**Não paralelizável:** depende de tudo da Fase 1 e 2

| História | O que faz | Arquivos modificados |
|----------|-----------|----------------------|
| H06 | Cria `EcuSession` com handshake, Reader thread, fila de comandos | `app/ecu_connection/session.py` (novo), `app/ecu_connection/__init__.py` |

**Critério de sucesso da Fase 3:**
- `EcuSession` com `MockTransport` inicia, faz handshake, publica `EcuMessFrameEvent` no bus.
- `vehicle_state.get_rpm_breakpoints()` retorna valores populados pelo handshake.
- `EcuCommandRequestedEvent` publicado no bus chega à `EcuSession` e é enviado ao transporte.

---

### Fase 4 — Migração dos Processadores (paralelo)

**Duração estimada:** média-alta  
**Histórias:** H07, H08, H09, H10  
**Dependência:** H06 (para funcionamento completo), H01, H02  
**Podem rodar em paralelo:** sim, as quatro simultaneamente (tocam arquivos distintos)

| História | O que faz | Arquivos modificados |
|----------|-----------|----------------------|
| H07 | Reescreve SignalProcessor para ECU_MESS_FRAME + buffers por frame | `signal_processor.py`, `main.py` (linha) |
| H08 | Reescreve LogWriter para ECU_MESS_FRAME + buffer D01+D02 | `log_writer.py`, `main.py` (linha) |
| H09 | Migra AlarmProcessor de QThread para QObject+QTimer | `alarm/processor.py`, `main.py` (linha) |
| H10 | Remove emitter do VehicleState; publica via bus; set_alarm com duration_s | `state/state.py`, `alarm/processor.py` |

**Atenção:** H09 e H10 tocam em `app/alarm/processor.py`. Se rodarem em paralelo, coordenar para não haver conflito de merge:
- H10 adiciona parâmetro `duration_s` à assinatura de `set_alarm()`.
- H09 usa `vehicle_state.set_alarm()` mas não muda sua assinatura.
- Recomendação: aplicar H10 primeiro se rodando em paralelo para evitar merge conflict.

**Critério de sucesso da Fase 4:**
- Sinais chegam ao `DashboardScreen` via `SIGNALS_RECEIVED`.
- Alarmes disparam e áudio toca/para corretamente.
- CSV é gerado com dados de D01+D02.
- `vehicle_state` publica `VEHICLE_STATE_CHANGED` via bus (sem `emitter`).

---

### Fase 5 — Fechamento e UI (paralelo parcial)

**Duração estimada:** média  
**Histórias:** H11, H12  
**Dependência:** toda a Fase 4 concluída  
**Podem rodar em paralelo:** H11 e H12 tocam arquivos diferentes, mas H12 depende que H11 não use mais `get_ecu_connection()` para não reintroduzi-lo em `main.py`.

| História | O que faz | Arquivos modificados |
|----------|-----------|----------------------|
| H11 | Migra VeCalibrationScreen e VeWriteController para bus | `ve_calibration/screen.py`, `ve_write_controller.py` |
| H12 | Reescreve main.py, remove signal_processor de AppWindow, deleta arquivos obsoletos | `main.py`, `window.py`, `__init__.py`, (deleta 3 arquivos) |

**Critério de sucesso da Fase 5 (= critério de sucesso do projeto inteiro):**
- App inicia com modo mock: sinais exibidos, VE table populada, alarmes funcionam, CSV gerado.
- Teclas O/P na tela VE enviam comandos via bus.
- `main.py` não importa nenhum arquivo de `serial.py`, `mock_log.py` ou `thread.py`.
- Os três arquivos obsoletos foram removidos do repositório.
- Nenhuma referência a `get_ecu_connection_thread()` ou `EcuConnectionThread` existe no codebase.

---

## Ordem de Execução Sugerida

### Execução com 1 agente (sequencial)

```
H01 → H02 → H03 → H04 → H05 → H06 → H10 → H09 → H07 → H08 → H11 → H12
```

(H10 antes de H09 para evitar conflito na assinatura de `set_alarm()`.)

### Execução com 3 agentes (máxima paralelização)

```
Fase 1:  [Agente 1: H01] [Agente 2: H02] [Agente 3: H03]
            ↓                                   ↓
Fase 2:                           [Agente 2: H04] [Agente 3: H05]
                                        ↓
Fase 3:                           [Agente 1: H06]
                                        ↓
Fase 4:  [A1: H07] [A2: H08] [A3: H10 → H09]
                        ↓
Fase 5:  [Agente 1: H11] [Agente 2: H12]
```

---

## Caminho Crítico

A sequência mais longa de dependências (caminho crítico) é:

```
H03 → H04 → H06 → H07 → H12
```

Ou equivalentemente:

```
H01 → H06 → H07 → H12
```

Isso significa que, independente de quantos agentes paralelos forem usados, o tempo mínimo total é a soma das durações dessas histórias em série.

O gargalo principal é **H06 (EcuSession)** — é o componente mais complexo e único na Fase 3.

---

## Riscos e Mitigações

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| R3: Fronteira D01/D02 em signal.py não confirmada | H07 pode não processar sinais D02 corretamente | Mapear todos os sinais como `frame: "D01"` inicialmente (equivalente funcional) |
| R5: MockTransport sem dados de VE/breakpoints | H06 bloqueia no handshake | Usar valores hardcoded no MockTransport para handshake |
| R7: Deadlock em blocking mode da EcuSession | H06 trava na inicialização | Handshake ocorre antes da Reader thread iniciar — seguro por design |
| Conflito de merge H09+H10 | `set_alarm()` modificado por ambas | Aplicar H10 antes de H09, ou coordenar a assinatura antes de paralelizar |
| `signal_processor` em AppWindow | H12 pode quebrar se H07 não limpar todas as referências | Verificar `grep signal_processor app/ui/window.py` antes de H12 |
