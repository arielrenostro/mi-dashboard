## 1. VeMapState — novo método de ajuste percentual

- [x] 1.1 Adicionar método `adjust_ve_percent(self, rpm: float, map_val: float, percent: float)` em `app/ui/ve_calibration/ve_map_state.py` que calcula os pesos de interpolação e aplica `current * (1 + percent / 100)` em cada célula ativa via `set_cell`

## 2. VeCalibrationScreen — tecla G e diálogo

- [x] 2.1 Adicionar handler `elif event.key() == Qt.Key.Key_G:` em `VeCalibrationScreen.keyPressEvent` em `app/ui/ve_calibration/screen.py` que checa se RPM e MAP estão disponíveis, abre `QInputDialog.getDouble` com range [-100.0, 100.0] e 1 decimal, e chama `ve_map_state.adjust_ve_percent` + `self._writer.on_adjustment_made()` se confirmado
- [x] 2.2 Atualizar o texto do footer em `_build_footer` para incluir `G % VE` junto às demais dicas
