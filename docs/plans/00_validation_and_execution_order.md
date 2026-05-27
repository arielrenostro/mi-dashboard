# Plano 00 — Validação e Ordem Global de Execução

Este documento consolida os resultados da validação cruzada dos 4 planos de refatoração.
Deve ser lido antes de qualquer implementação.

---

## Ordem Global de Execução (recomendada)

```
FASE 1 — Plano 04 (parcial): correção de bugs críticos
  → Corrigir bug set_alarm + emit fora do lock
  → NÃO remover VEHICLE_STATE_CHANGED ainda

FASE 2 — Plano 01: ECU transport/session
  → Criar app/ecu_protocol/ e transportes
  → EcuSession com framing individual
  → Manter main.py funcional durante transição

FASE 3 — Plano 02: pipeline de eventos
  → Só viável após Plano 01 ter EcuSession emitindo frames individuais
  → Inclui correção de sinais cross-frame

FASE 4 — Plano 03 + restante Plano 04: UI e limpeza de eventos
  → Remover SCREEN_REQUESTED, VEHICLE_STATE_CHANGED
  → Mover emitter.connect para on_activated/on_deactivated
  → Fazer em um único PR para evitar estado inconsistente
```

---

## Contradições Encontradas e Resoluções

### Contradição A — Atribuição duplicada: remover VEHICLE_STATE_CHANGED

**Problema:** Plano 03 e Plano 04 ambos reivindicam remover `VEHICLE_STATE_CHANGED` do bus.

**Resolução:** Atribuído ao **Plano 04**. O Plano 03 faz referência ao Plano 04 para essa remoção.

---

### Contradição B — Atribuição duplicada: mover `vehicle_state.emitter.connect`

**Problema:** Plano 03 e Plano 04 ambos descrevem mover `vehicle_state.emitter.connect(...)` de `VeCalibrationScreen.__init__` para `on_activated`/`on_deactivated`.

**Resolução:** Atribuído ao **Plano 04** (passo 4). O Plano 03 referencia o Plano 04 para essa mudança específica.

---

### Contradição C — `EcuCommandRequestedEvent.command` com novo tipo

**Problema:** O Plano 01 transforma `EcuCommand` de Enum para dataclass. O campo `command: Any` em `EcuCommandRequestedEvent` precisa ser atualizado para aceitar a nova `EcuCommand` dataclass. Nenhum plano menciona isso.

**Resolução:** Adicionar ao **Plano 01** (Fase 5 — migrar consumidores): atualizar a type hint de `EcuCommandRequestedEvent.command` para `EcuCommand` (dataclass). A interface prática não muda pois o campo era `Any`.

---

### Contradição D — Quem popula `vehicle_state` após o handshake refatorado

**Problema:** O Plano 01 move `_fetch_breakpoints`/`_fetch_ve_map` para `EcuSession`, mas não define claramente se `EcuSession` continua chamando `vehicle_state.*` diretamente ou emite `CommandResponseEvent` para que outro componente faça isso.

**Resolução (explicitada no Plano 01):** `EcuSession` continua chamando `vehicle_state.set_*` diretamente durante o handshake — isso é comportamento de sessão, não de transporte. O `CommandResponseEvent` é para respostas recebidas durante o streaming, não durante o handshake bloqueante.

---

## Omissões Encontradas e Planos de Ação

### Omissão A — `LambdaLoopStateProcessor` e `LambdaToggle` podem estar desativados em `main.py`

**Ação:** Antes de iniciar qualquer refatoração, verificar se os blocos estão comentados:
```bash
grep -n "LambdaToggle\|LambdaLoopState\|lambda_toggle\|lambda_loop" main.py
```
Se comentados, a refatoração dos imports pode ser feita mas o wiring não precisa ser restaurado — documentar como dívida técnica separada.

---

### Omissão B — `MESS_DATA_3` (#D03) não processado

**Ação:** No Plano 02, `EcuSession` emite `MessFrameEvent` para #D03, mas nenhum subscriber o processa. Isso é intencional (ECU envia D03 mas dados não foram mapeados ainda). `SignalProcessor._signals_by_frame` simplesmente não terá entradas para "#D03" → retorna sem processar. `LogWriter` ignora D03. Comportamento aceito — documentar explicitamente no código como "D03 recebido mas não processado".

---

### Omissão C — `LogWriter` CSV: mapeamento de colunas para frames individuais

**Problema:** O CSV tem colunas hardcoded que misturam campos de D01 e D02. Após o `LogWriter` acumular frames separados, precisa saber como montar a linha.

**Ação (adicionar ao Plano 02):** O `LogWriter._flush()` deve concatenar `list(pending_d01) + list(pending_d02)` na mesma ordem que o código atual faz. O formato do CSV não muda — apenas o mecanismo de acumulação. O `Worker.__init__` e o header do CSV permanecem iguais.

---

### Omissão D — `HomeScreen` tem `close_fn=lambda: self.close()` para fechar a aplicação

**Problema:** Ao remover `close_fn`, a saída da aplicação fica sem tratamento.

**Ação (adicionar ao Plano 03):** Adicionar um terceiro sinal `quit_app = pyqtSignal()` em `Screen`. `HomeScreen` emite `quit_app` quando o usuário confirma sair. `AppWindow` conecta `home_screen.quit_app.connect(self.close)`.

---

### Omissão E — `EcuConnectionStatus` deve ser exposto por `EcuSession`

**Problema:** `HomeScreen` chama `get_ecu_connection().get_connection_status()` via timer. Após o Plano 01, `get_ecu_connection()` retorna `EcuSession`. `EcuSession` deve expor `get_status() -> EcuConnectionStatus` com o mesmo enum.

**Ação:** Confirmado que o Plano 01 já prevê isso (`EcuSession.get_status()` e mantém `EcuConnectionStatus` em `ecu_connection.py`). `get_ecu_connection()` no `__init__.py` deve manter o nome para retrocompatibilidade com `HomeScreen`. Não é omissão crítica — verificar na implementação.

---

### Omissão F — `AlarmProcessor._alarm_until` duplica cooldown com `VehicleState._alarm_last_fired`

**Problema:** Após o Plano 04, `VehicleState` passa a ter `_alarm_last_fired`. O `AlarmProcessor` ainda mantém `_alarm_until: Dict[Signal, float]` para controle do cooldown de publicação do `AlarmFiredEvent`. São dois propósitos distintos:
- `AlarmProcessor._alarm_until`: controla **quando re-publicar** `AlarmFiredEvent` (throttle do evento de alarme)
- `VehicleState._alarm_last_fired`: registra **quando o alarme foi visto pela última vez** (para consulta de estado)

**Resolução:** Manter ambos — são responsabilidades diferentes. Documentar no código para evitar confusão futura.

---

### Omissão G — `SignalProcessor.emitter` legado

**Ação:** Após migração completa, verificar se `self.emitter.emit(parsed_data)` em `SignalProcessor` ainda tem consumidores:
```bash
grep -rn "signal_processor.emitter\|SignalProcessor.*emitter" app/ main.py
```
Se sem consumidores, remover `emitter = Signal(dict)` e a chamada. Adicionar como passo de limpeza final no Plano 02.

---

## Riscos Arquiteturais e Mitigações

### Risco B — Sinais calculados (POWER, TORQUE) com processamento parcial por frame

**Problema:** Se `SignalProcessor` processa D01 imediatamente sem aguardar D02, e sinais calculados dependem de sinais de ambos os frames, os valores serão incorretos na primeira iteração.

**Mitigação (adicionar ao Plano 02):** Sinais calculados usam `combined = {**vehicle_state.get_all(), **parsed_data}`. Na primeira frame, `vehicle_state.get_all()` retorna o estado atual (incluindo dados de D02 do ciclo anterior se disponíveis). O comportamento é aceitável: na primeira iteração haverá valores com dados desatualizados, mas em regime permanente (frame 2+) o comportamento é correto pois os dados do ciclo anterior estarão no `vehicle_state`.

---

### Risco C — Thread safety do acumulador interno do `LogWriter`

**Problema:** `_pending_d01` e `_pending_d02` são lidos/escritos nos callbacks do bus. O bus usa `pyqtSignal` com `QueuedConnection` para entrega na main thread — portanto, todos os callbacks do bus são executados na main thread sequencialmente. Não há concorrência real entre `_on_mess_frame` calls.

**Mitigação:** Não é necessário lock. Documentar que os callbacks do bus sempre executam na main thread.

---

### Risco D — `VeCalibrationScreen` e reconexão enquanto inativa

**Problema:** Se ECU reconecta enquanto `VeCalibrationScreen` está inativa, os breakpoints são atualizados no `vehicle_state` mas a tela não os captura. Ao ativar a tela depois, `_load_initial_state` carregará os dados corretos. O problema só ocorreria se `vehicle_state` fosse limpo no reconect — o que não acontece (apenas breakpoints e VE map são re-fetchados e sobrescritos).

**Mitigação:** O `_load_initial_state` no `on_activated` resolve o caso de borda. Comportamento aceito.

---

### Risco E — `EcuSession` acoplado a `vehicle_state` durante handshake

**Análise:** Dado o escopo e tamanho do projeto, `EcuSession` chamando `vehicle_state.*` diretamente durante handshake é aceitável. A alternativa (emitir `CommandResponseEvent` e ter um listener populando `vehicle_state`) adiciona complexidade sem benefício prático neste contexto.

**Decisão:** Manter acoplamento direto em `EcuSession._fetch_*`.

---

## Checklist de Verificação Pré-Implementação

Antes de começar cada fase, executar:

```bash
# Fase 1 (Plano 04 parcial)
grep -rn "set_alarm\|is_alarm_firing\|is_any_alarm_firing" app/

# Fase 2 (Plano 01)
grep -rn "LambdaToggle\|LambdaLoopState" main.py  # verificar se ativo
grep -rn "from app.masterinjection.protocol import" app/  # listar todos os imports

# Fase 3 (Plano 02)
grep -rn "emitter.connect.*process_line\|log_writer.write" main.py  # wirings a remover
grep -rn "SignalProcessor.*emitter\|signal_processor\.emitter" app/ main.py

# Fase 4 (Plano 03 + Plano 04 restante)
grep -rn "SCREEN_REQUESTED\|ScreenRequestedEvent" app/
grep -rn "VEHICLE_STATE_CHANGED\|VehicleStateChangedEvent" app/
grep -rn "close_fn" app/ui/
```
