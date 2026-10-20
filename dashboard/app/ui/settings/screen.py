import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional, Union

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.config import AppConfig, config
from app.gyro import get_gyro
from app.gyro.ports import list_serial_ports
from app.gyro.state import GyroStatus
from app.ui.base.screen import Screen
from app.ui.settings import calibration as wizard_texts
from app.ui.settings.calibration import CalibrationWizard, CloseReason, Phase

HINT = "↑↓ Navegar | ←→ Alterar | Enter Executar | Esc Voltar"
NO_PORT = "Nenhuma"

STATUS_SAVED = "Salvo"
STATUS_NOT_SAVED = "Não foi possível gravar a configuração"
STATUS_CHOOSE_PORT = "Escolha uma porta"
STATUS_SENT = "Comando enviado"
STATUS_NOT_CONNECTED = "Giroscópio desconectado"
STATUS_CONFIRM_RESTORE = "Enter de novo para restaurar"
STATUS_CALIBRATION_CANCELLED = "Calibração cancelada"

_STATE_TEXTS = {
    GyroStatus.DISABLED: "Desligado",
    GyroStatus.DISCONNECTED: "Desconectado",
    GyroStatus.NO_SIGNAL: "Sem sinal",
    GyroStatus.NOT_ZEROED: "Conectado, sem zero",
    GyroStatus.USABLE: "Conectado, zerado",
}
_NO_READING = (GyroStatus.DISABLED, GyroStatus.DISCONNECTED, GyroStatus.NO_SIGNAL)

_SELECTED_STYLE = (
    "color: white; border: 2px solid #1E90FF; background-color: rgba(30, 144, 255, 0.2); padding: 4px 10px;"
)
_UNSELECTED_STYLE = "color: gray; border: 2px solid transparent; background-color: transparent; padding: 4px 10px;"

Bound = Union[float, Callable[[AppConfig], float]]


@dataclass(frozen=True)
class NumberRow:
    """A numeric setting edited with ← and →: one step per press, clamped to the range."""
    section: str
    key: str
    label: str
    step: float
    minimum: Bound
    maximum: Bound
    unit: str
    decimals: int = 0

    @property
    def setting(self) -> str:
        return f"{self.section}.{self.key}"

    def bounds(self, settings: AppConfig) -> tuple:
        low = self.minimum(settings) if callable(self.minimum) else self.minimum
        high = self.maximum(settings) if callable(self.maximum) else self.maximum
        return low, high

    def text(self, value) -> str:
        return f"{value:.{self.decimals}f}{self.unit}" if self.decimals else f"{value:g}{self.unit}"


NUMBER_ROWS = (
    NumberRow("ignition_tuning", "max_tilt_deg", "Inclinação máxima", 0.5, 0.5, 20, "°", decimals=1),
    NumberRow("ignition_tuning", "rpm_min", "RPM mínimo", 100, 500, lambda c: c.ignition_tuning.rpm_max, " rpm"),
    NumberRow("ignition_tuning", "rpm_max", "RPM máximo", 100, lambda c: c.ignition_tuning.rpm_min, 9000, " rpm"),
    NumberRow("ignition_tuning", "settle_seconds", "Estabilização", 1, 0, 60, " s"),
    NumberRow("ignition_tuning", "min_scenario_seconds", "Tempo mínimo do cenário", 5, 5, 600, " s"),
)

# Settings that have a row on this screen.
SETTINGS_ON_SCREEN = frozenset({"gyro.port", *(row.setting for row in NUMBER_ROWS)})

# Settings that exist but are not on this screen yet (they need text entry). The list may only shrink: a new
# setting ships together with its row (spec app-configuration, "Every setting is on the Settings screen").
SETTINGS_BACKLOG = frozenset({
    "connection.port", "connection.baudrate", "connection.mock", "connection.mock_skip_lines",
    "alarm.sound",
    "datalog.path", "datalog.mark_sound",
    "dashboard.grid", "dashboard.graph", "dashboard.graph_x_size",
    "ve_calibration.ve_sound", "ve_calibration.closed_sound", "ve_calibration.open_sound",
    "ignition_tuning.gears", "ignition_tuning.max_map_kpa", "ignition_tuning.max_ignition",
    "ignition_tuning.write_sound", "ignition_tuning.ready_sound", "ignition_tuning.pause_sound",
    "ignition_tuning.resume_sound", "ignition_tuning.discard_sound",
})

_PORT, _CONNECT, _ZERO = "port", "connect", "zero"
_CALIBRATE, _VIEW_CALIBRATION, _RESTORE_CALIBRATION = "calibrate", "view_calibration", "restore_calibration"
_GYRO_ROWS = (_PORT, _CONNECT, _ZERO, _CALIBRATE, _VIEW_CALIBRATION, _RESTORE_CALIBRATION)
_READOUT_LINES = 6


class SettingsScreen(Screen):
    """
    Settings edited from the keyboard, saved to config.json at once, and the controls of the inclinometer
    (port, connect, zero, accelerometer calibration) with its live readout.
    """

    # (section, key) of a setting that was changed here, after it was applied and saved.
    setting_changed = pyqtSignal(str, str)

    def __init__(self, close_fn: Callable, gyro=None, settings: Optional[AppConfig] = None,
                 list_ports: Callable[[], list] = list_serial_ports, clock: Callable[[], float] = time.monotonic):
        super().__init__(close_fn)
        self._gyro = get_gyro() if gyro is None else gyro
        self._settings = config if settings is None else settings
        self._list_ports = list_ports
        self._clock = clock
        self._ports: list = []
        self._status = ""
        self._wizard: Optional[CalibrationWizard] = None
        self._restore_armed = False

        # The selectable rows, in order: the gyroscope ones, then one per numeric setting.
        self._rows: list = [*_GYRO_ROWS, *NUMBER_ROWS]
        self._selected = 0

        self.setStyleSheet("background-color:black;")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._build()

        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh)
        self._ports = self._read_ports()
        self._refresh()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addStretch()

        title = QLabel("Configurações")
        title_font = QFont("Arial", 40)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        container = QWidget()
        column = QVBoxLayout(container)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)

        self._row_widgets: list = []
        self._readout_labels: list = []
        column.addWidget(self._heading("Giroscópio"))
        for _ in _GYRO_ROWS:
            column.addWidget(self._row_widget())
        for _ in range(_READOUT_LINES):
            label = QLabel()
            label.setFont(QFont("Arial", 16))
            label.setStyleSheet("color: #AAAAAA; padding-left: 16px;")
            self._readout_labels.append(label)
            column.addWidget(label)
        column.addWidget(self._heading("Ajuste de Ignição"))
        for _ in NUMBER_ROWS:
            column.addWidget(self._row_widget())
        self._rows_container = container
        layout.addWidget(container, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._build_wizard_panel(), alignment=Qt.AlignmentFlag.AlignCenter)

        self._status_label = QLabel()
        self._status_label.setFont(QFont("Arial", 16))
        self._status_label.setStyleSheet("color: white;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

        self._hint_label = QLabel(HINT)
        self._hint_label.setFont(QFont("Arial", 14))
        self._hint_label.setStyleSheet("color: gray;")
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._hint_label)
        layout.addStretch()

    def _build_wizard_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(640)
        column = QVBoxLayout(panel)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)
        column.addWidget(self._heading(wizard_texts.TITLE))
        self._wizard_labels: list = []
        for size, color in ((20, "white"), (24, "white"), (20, "#1E90FF"), (16, "#AAAAAA")):
            label = QLabel()
            label.setFont(QFont("Arial", size))
            label.setStyleSheet(f"color: {color}; padding-left: 16px;")
            self._wizard_labels.append(label)
            column.addWidget(label)
        panel.setVisible(False)
        self._wizard_panel = panel
        return panel

    @staticmethod
    def _heading(text: str) -> QLabel:
        label = QLabel(text)
        font = QFont("Arial", 18)
        font.setBold(True)
        label.setFont(font)
        label.setStyleSheet("color: #1E90FF; padding-top: 8px;")
        return label

    def _row_widget(self) -> QWidget:
        row = QWidget()
        row.setMinimumWidth(640)
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        name, value = QLabel(), QLabel()
        for label in (name, value):
            label.setFont(QFont("Arial", 20))
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(name)
        layout.addStretch()
        layout.addWidget(value)
        self._row_widgets.append((row, name, value))
        return row

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def on_activated(self):
        self._ports = self._read_ports()
        self._timer.start(200)
        self._refresh()

    def on_deactivated(self):
        self._timer.stop()
        self._restore_armed = False
        self._wizard = None  # leaving the screen abandons the wizard; the next one starts at step 1
        self._show_wizard(False)

    # ── Display (also read by the tests) ─────────────────────────────────────

    @property
    def status_text(self) -> str:
        return self._status

    @property
    def selected_index(self) -> int:
        return self._selected

    def row_texts(self) -> list:
        """(label, value) of every selectable row, in order."""
        return [(self._label(row), self._value(row)) for row in self._rows]

    @property
    def wizard_open(self) -> bool:
        return self._wizard is not None

    def wizard_lines(self) -> list:
        """The wizard panel: progress, instruction, status and (once saved) the calibration line; [] when closed."""
        wizard = self._wizard
        if wizard is None:
            return []
        saved = wizard.phase is Phase.SAVED
        return [wizard.progress_text, wizard.instruction_text, wizard.status_text,
                self._calibration_line() if saved else ""]

    def readout_lines(self) -> list:
        """The six lines under the gyroscope rows: state, pitch, roll, temperature, device message, calibration."""
        snapshot = self._gyro.snapshot()
        reading = None if snapshot.status in _NO_READING else snapshot.reading
        return [
            _STATE_TEXTS[snapshot.status],
            f"Pitch {reading.pitch:+.1f}°" if reading else "Pitch --",
            f"Roll {reading.roll:+.1f}°" if reading else "Roll --",
            f"Temp {reading.temp_c:.1f} °C" if reading else "Temp --",
            f"Mensagem: {snapshot.message}" if snapshot.message else "Mensagem:",
            self._calibration_line(snapshot),
        ]

    def _calibration_line(self, snapshot=None) -> str:
        report = (snapshot or self._gyro.snapshot()).calibration.report
        if report is None:
            return "Calibração: --"
        offsets = " ".join(f"{value:+.3f}" for value in report.offset)
        gains = " ".join(f"{value:.3f}" for value in report.scale)
        return f"Calibração: offset {offsets} | ganho {gains}"

    def _label(self, row) -> str:
        if isinstance(row, NumberRow):
            return row.label
        return {
            _PORT: "Porta",
            _CONNECT: "Desconectar" if self._connected() else "Conectar",
            _ZERO: "Zerar inclinação",
            _CALIBRATE: "Calibrar acelerômetro",
            _VIEW_CALIBRATION: "Ver calibração",
            _RESTORE_CALIBRATION: "Restaurar calibração",
        }[row]

    def _value(self, row) -> str:
        if isinstance(row, NumberRow):
            return row.text(getattr(getattr(self._settings, row.section), row.key))
        if row == _PORT:
            choices = self._port_choices()
            current = self._settings.gyro.port
            return next(text for value, text in choices if value == current)
        return ""

    def _refresh(self):
        if self._wizard is not None:
            self._wizard.update()
            if self._wizard.closed:
                self._close_wizard()
        self._show_wizard(self._wizard is not None)
        for index, (row, name, value) in enumerate(self._row_widgets):
            name.setText(self._label(self._rows[index]))
            value.setText(self._value(self._rows[index]))
            style = _SELECTED_STYLE if index == self._selected else _UNSELECTED_STYLE
            row.setStyleSheet(f"QWidget {{ {style} }}")
        for label, text in zip(self._readout_labels, self.readout_lines()):
            label.setText(text)
        for label, text in zip(self._wizard_labels, self.wizard_lines()):
            label.setText(text.replace(". ", ".\n"))  # one sentence per line: a wrapped label is clipped in the column
        self._status_label.setText(self._status)
        if self._wizard is not None:
            self.layout().activate()  # the panel changes height with its text; do not wait for the next event

    def _show_wizard(self, shown: bool):
        self._rows_container.setVisible(not shown)
        self._wizard_panel.setVisible(shown)
        self._hint_label.setText(wizard_texts.HINT if shown else HINT)

    def _set_status(self, text: str):
        self._status = text
        self._status_label.setText(text)

    # ── Gyroscope port ───────────────────────────────────────────────────────

    def _read_ports(self) -> list:
        try:
            return list(self._list_ports())
        except Exception:
            return []

    def _port_choices(self) -> list:
        """(value, text): none, the ports of the machine, and the configured one when it is not among them."""
        choices = [("", NO_PORT)] + [(port, port) for port in self._ports]
        current = self._settings.gyro.port
        if current and current not in self._ports:
            choices.append((current, f"{current} (indisponível)"))
        return choices

    def _connected(self) -> bool:
        return self._gyro.is_open() and not self._gyro.is_user_closed()

    def _change_port(self, direction: int):
        self._ports = self._read_ports()
        values = [value for value, _ in self._port_choices()]
        current = values.index(self._settings.gyro.port)
        target = current + direction
        if 0 <= target < len(values):
            self._apply("gyro", "port", values[target])
            self._gyro.set_port(values[target])

    # ── Actions ──────────────────────────────────────────────────────────────

    def _toggle_connection(self):
        if not self._settings.gyro.port:
            self._set_status(STATUS_CHOOSE_PORT)
        elif self._connected():
            self._gyro.disconnect()
            self._set_status("")
        else:
            self._gyro.connect()
            self._set_status("")

    def _send_zero(self):
        self._set_status(STATUS_SENT if self._gyro.zero() else STATUS_NOT_CONNECTED)

    # ── Accelerometer calibration ────────────────────────────────────────────

    def _open_wizard(self):
        if not self._gyro.is_open():
            self._set_status(STATUS_NOT_CONNECTED)
            return
        self._set_status("")
        self._wizard = CalibrationWizard(self._gyro, self._clock)

    def _close_wizard(self):
        reason = self._wizard.close_reason
        self._wizard = None
        self._set_status({
            CloseReason.CANCELLED: STATUS_CALIBRATION_CANCELLED,
            CloseReason.DISCONNECTED: STATUS_NOT_CONNECTED,
            CloseReason.DONE: "",
        }[reason])

    def _view_calibration(self):
        self._set_status(STATUS_SENT if self._gyro.request_calibration() else STATUS_NOT_CONNECTED)

    def _restore_calibration(self):
        """The first Enter only asks for confirmation; the next one on the same row sends the restore."""
        if not self._gyro.is_open():
            self._set_status(STATUS_NOT_CONNECTED)
        elif self._restore_armed:
            self._restore_armed = False
            self._set_status(STATUS_SENT if self._gyro.restore_calibration() else STATUS_NOT_CONNECTED)
        else:
            self._restore_armed = True
            self._set_status(STATUS_CONFIRM_RESTORE)

    # ── Numeric settings ─────────────────────────────────────────────────────

    def _change_number(self, row: NumberRow, direction: int):
        current = getattr(getattr(self._settings, row.section), row.key)
        low, high = row.bounds(self._settings)
        new = round(min(max(current + direction * row.step, low), high), 4)
        if isinstance(row.step, int) and new == int(new):
            new = int(new)
        if new != current:
            self._apply(row.section, row.key, new)

    def _apply(self, section: str, key: str, value):
        """Use the new value, save it, and tell whoever shows or uses the setting."""
        saved = self._settings.set_value(section, key, value)
        self._set_status(STATUS_SAVED if saved else STATUS_NOT_SAVED)
        self.setting_changed.emit(section, key)

    # ── Keyboard ─────────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if event.isAutoRepeat():
            return
        key = event.key()
        if self._wizard is not None:
            self._wizard_key(key, event)
            return
        row = self._rows[self._selected]
        self._disarm_restore(key, row)
        if key == Qt.Key.Key_Up:
            self._selected = (self._selected - 1) % len(self._rows)
        elif key == Qt.Key.Key_Down:
            self._selected = (self._selected + 1) % len(self._rows)
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            direction = -1 if key == Qt.Key.Key_Left else 1
            if row == _PORT:
                self._change_port(direction)
            elif isinstance(row, NumberRow):
                self._change_number(row, direction)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if row == _CONNECT:
                self._toggle_connection()
            elif row == _ZERO:
                self._send_zero()
            elif row == _CALIBRATE:
                self._open_wizard()
            elif row == _VIEW_CALIBRATION:
                self._view_calibration()
            elif row == _RESTORE_CALIBRATION:
                self._restore_calibration()
        elif key == Qt.Key.Key_Escape:
            self.close_fn()
            return
        else:
            super().keyPressEvent(event)
            return
        self._refresh()

    def _disarm_restore(self, key, row):
        """Any key but the second Enter on the restore row takes the confirmation back."""
        if not self._restore_armed:
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and row == _RESTORE_CALIBRATION:
            return
        self._restore_armed = False
        if self._status == STATUS_CONFIRM_RESTORE:
            self._set_status("")

    def _wizard_key(self, key, event: QKeyEvent):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._wizard.confirm()
        elif key == Qt.Key.Key_Escape:
            self._wizard.cancel()
        elif key not in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
            super().keyPressEvent(event)  # other keys (such as the screen shortcuts) go on to the window
            return
        self._refresh()
