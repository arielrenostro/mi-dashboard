## Why

Na tela de calibração de VE, o ajuste de células é feito incrementando/decrementando o valor unitariamente com as teclas ↑/↓. Quando o usuário precisa aplicar uma correção percentual maior (ex: +5% ou -3%), precisa repetir muitos pressionamentos de tecla. Adicionar uma forma de inserir um percentual direto torna o fluxo de calibração mais rápido e preciso.

## What Changes

- Pressionar `G` na `VeCalibrationScreen` abre um diálogo modal pedindo um percentual (ex: `5` para +5%, `-3` para -3%).
- O diálogo aceita valores positivos ou negativos com casas decimais.
- Ao confirmar (Enter), o valor da célula sob o cursor é multiplicado pelo fator `(1 + percentual/100)` e atualizado na tabela e no VeMapState.
- Pressionar `Esc` cancela sem modificar nada.
- O ajuste passa pelo fluxo normal de escrita (`VeWriteController`), disparando debounce e envio ao ECU.

## Capabilities

### New Capabilities

- `ve-percentage-increment`: Diálogo de incremento percentual na tela VE — abre com `G`, aceita percentual, aplica à célula sob o cursor e fecha com Enter/Esc.

### Modified Capabilities

<!-- Nenhuma spec existente precisa ser alterada -->

## Impact

- `app/ui/ve_calibration/screen.py`: captura tecla `G`, abre diálogo, aplica ajuste.
- `app/ui/ve_calibration/ve_map_state.py`: pode precisar expor método para ajuste percentual.
- Sem novas dependências externas (usa `QInputDialog` do PyQt6).
