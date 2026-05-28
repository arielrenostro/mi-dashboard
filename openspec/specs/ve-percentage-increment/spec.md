### Requirement: Abrir diálogo de percentual com tecla G
Na `VeCalibrationScreen`, pressionar `G` SHALL abrir um diálogo modal (`QInputDialog`) solicitando um valor percentual. O diálogo SHALL aceitar valores decimais no intervalo [-100.0, 100.0]. O diálogo SHALL ser cancelável com `Esc` sem nenhuma modificação no mapa.

#### Scenario: Abrir diálogo ao pressionar G
- **WHEN** o usuário pressiona `G` na `VeCalibrationScreen`
- **THEN** um `QInputDialog` é exibido pedindo um percentual

#### Scenario: Cancelar diálogo com Esc
- **WHEN** o diálogo está aberto e o usuário pressiona `Esc`
- **THEN** o diálogo fecha sem modificar nenhuma célula do mapa VE

#### Scenario: G sem dados de RPM/MAP disponíveis
- **WHEN** o usuário pressiona `G` e `vehicle_state` não possui dados de RPM ou MAP
- **THEN** nenhum diálogo é aberto e nenhuma modificação é feita

### Requirement: Aplicar percentual às células sob o cursor
Ao confirmar o diálogo, o sistema SHALL aplicar o percentual informado às células do mapa VE que estiverem sob o cursor lógico (células com peso de interpolação bilinear > 0). Cada célula SHALL ter seu valor multiplicado por `(1 + pct / 100)`, arredondado e clampado ao intervalo [0, 19999]. O ajuste SHALL ser enviado ao ECU pelo fluxo normal via `VeWriteController`.

#### Scenario: Aplicar percentual positivo
- **WHEN** o usuário confirma um percentual positivo (ex: 5.0)
- **THEN** cada célula ativa sob o cursor tem seu valor raw multiplicado por 1.05 e salvo via `set_cell`
- **THEN** `VeWriteController.on_adjustment_made()` é chamado para disparar o debounce de envio

#### Scenario: Aplicar percentual negativo
- **WHEN** o usuário confirma um percentual negativo (ex: -3.0)
- **THEN** cada célula ativa sob o cursor tem seu valor raw multiplicado por 0.97 e salvo via `set_cell`

#### Scenario: Aplicar percentual zero
- **WHEN** o usuário confirma o valor 0.0
- **THEN** nenhuma célula é modificada efetivamente (fator = 1.0), mas `on_adjustment_made()` ainda é chamado

### Requirement: Novo método adjust_ve_percent em VeMapState
`VeMapState` SHALL expor o método `adjust_ve_percent(rpm: float, map_val: float, percent: float)` que calcula os pesos de interpolação para a posição dada e aplica o percentual individualmente em cada célula com peso.

#### Scenario: Cálculo do novo valor raw
- **WHEN** `adjust_ve_percent` é chamado com `percent=10.0` para uma célula com valor raw 1000
- **THEN** o novo valor raw é `round(1000 * 1.10) = 1100`, salvo via `set_cell`

### Requirement: Footer hint atualizado
O footer da `VeCalibrationScreen` SHALL incluir a dica `G % VE` junto às demais dicas de teclado.

#### Scenario: Exibição da dica no footer
- **WHEN** a `VeCalibrationScreen` é exibida
- **THEN** o texto do footer contém `G % VE`
