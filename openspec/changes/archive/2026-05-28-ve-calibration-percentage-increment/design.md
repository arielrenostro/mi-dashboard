## Context

A tela `VeCalibrationScreen` já suporta ajuste de VE com ↑/↓ (±5 unidades raw distribuídas por pesos de interpolação bilinear). O cursor lógico é determinado pelos valores atuais de RPM e MAP via `ve_map_state.calculate_interpolation_weights()`. O `VeMapState.adjust_ve()` distribui um delta fixo pelos pesos — mas para ajuste percentual, cada célula tem um valor diferente, então o delta por célula precisa ser calculado individualmente.

## Goals / Non-Goals

**Goals:**
- Tecla `G` abre um `QInputDialog` solicitando um percentual (ex: `5` para +5%, `-3` para -3%).
- O valor de cada célula sob o cursor é multiplicado por `(1 + pct/100)` individualmente.
- `Esc` no diálogo cancela sem modificar nada.
- O ajuste passa pelo fluxo normal (`VeWriteController`), disparando o debounce de 1 s e envio ao ECU.
- Footer hint atualizado para incluir `G % VE`.

**Non-Goals:**
- Não há seleção manual de célula com teclado — o cursor é sempre o ponto de interpolação do RPM/MAP atual.
- Não há validação de limites além do clamp já existente em `set_cell` ([0, 19999]).
- Sem desfazer (undo) — comportamento consistente com os demais ajustes.

## Decisions

### 1. Usar `QInputDialog.getDouble` para entrada do percentual

**Alternativa**: `QInputDialog.getText` com parsing manual.

**Decisão**: `getDouble` — retorna `(float, ok)` diretamente, já valida que é número, suporta vírgula/ponto conforme locale, e dispensa parsing manual. Configurar `min=-100.0`, `max=100.0`, `decimals=1`.

### 2. Novo método `adjust_ve_percent` em `VeMapState`

**Alternativa**: Calcular o delta equivalente no `screen.py` e chamar `adjust_ve`.

**Decisão**: Método dedicado no `VeMapState` — a lógica de "aplicar percentual por célula com peso" é responsabilidade do estado do mapa, não da tela. Mantém coerência com `adjust_ve`.

Implementação:
```python
def adjust_ve_percent(self, rpm: float, map_val: float, percent: float):
    weights = self.calculate_interpolation_weights(rpm, map_val)
    for (row, col), _weight in weights.items():
        current = self.get_cell(row, col)
        self.set_cell(row, col, current * (1 + percent / 100))
```

O peso não escala o percentual — cada célula ativa recebe o ajuste completo. Isso é consistente com a expectativa do usuário de corrigir "exatamente X%".

### 3. Bloquear o timer de highlight durante o diálogo

O `_highlight_timer` atualiza a tela a cada 100 ms e chama `_adjust_ve` indiretamente via estado. O diálogo é modal (`exec()`), então o event loop do Qt continua rodando e o timer pode disparar durante a entrada. Isso não causa problema funcional — o timer só lê `vehicle_state`, não modifica nada — então não é necessário pausá-lo.

## Risks / Trade-offs

- [Risco] `rpm_data` ou `map_data` nulos ao pressionar `G` (ECU desconectado) → Mitigação: checar `None` antes de abrir o diálogo, igual a `_adjust_ve`.
- [Trade-off] Percentual aplicado às células com qualquer peso bilinear (até 4 células) — pode não ser o comportamento esperado se o usuário queria ajustar apenas "a célula mais próxima". Aceito por consistência com o comportamento atual de ↑/↓.
