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

HINT = "↑↓ Navegar | ←→ Alterar | Enter Executar | Esc Voltar"
NO_PORT = "Nenhuma"

STATUS_SAVED = "Salvo"
STATUS_NOT_SAVED = "Não foi possível gravar a configuração"
STATUS_CHOOSE_PORT = "Escolha uma porta"
STATUS_SENT = "Comando enviado"
STATUS_NOT_CONNECTED = "Giroscópio desconectado"

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


class SettingsScreen(Screen):
    """
    Settings edited from the keyboard, saved to config.json at once, and the controls of the inclinometer
    (port, connect, zero) with its live readout.
    """

    # (section, key) of a setting that was changed here, after it was applied and saved.
    setting_changed = pyqtSignal(str, str)

    def __init__(self, close_fn: Callable, gyro=None, settings: Optional[AppConfig] = None,
                 list_ports: Callable[[], list] = list_serial_ports):
        super().__init__(close_fn)
        self._gyro = get_gyro() if gyro is None else gyro
        self._settings = config if settings is None else settings
        self._list_ports = list_ports
        self._ports: list = []
        self._status = ""

        # The selectable rows, in order: the gyroscope ones, then one per numeric setting.
        self._rows: list = [_PORT, _CONNECT, _ZERO, *NUMBER_ROWS]
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
        for row in self._rows[:4]:
            column.addWidget(self._row_widget())
        for _ in range(5):
            label = QLabel()
            label.setFont(QFont("Arial", 16))
            label.setStyleSheet("color: #AAAAAA; padding-left: 16px;")
            self._readout_labels.append(label)
            column.addWidget(label)
        column.addWidget(self._heading("Ajuste de Ignição"))
        for row in self._rows[4:]:
            column.addWidget(self._row_widget())
        layout.addWidget(container, alignment=Qt.AlignmentFlag.AlignCenter)

        self._status_label = QLabel()
        self._status_label.setFont(QFont("Arial", 16))
        self._status_label.setStyleSheet("color: white;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

        hint = QLabel(HINT)
        hint.setFont(QFont("Arial", 14))
        hint.setStyleSheet("color: gray;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        layout.addStretch()

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

    def readout_lines(self) -> list:
        """The five lines under the gyroscope rows: state, pitch, roll, temperature, device message."""
        snapshot = self._gyro.snapshot()
        reading = None if snapshot.status in _NO_READING else snapshot.reading
        return [
            _STATE_TEXTS[snapshot.status],
            f"Pitch {reading.pitch:+.1f}°" if reading else "Pitch --",
            f"Roll {reading.roll:+.1f}°" if reading else "Roll --",
            f"Temp {reading.temp_c:.1f} °C" if reading else "Temp --",
            f"Mensagem: {snapshot.message}" if snapshot.message else "Mensagem:",
        ]

    def _label(self, row) -> str:
        if isinstance(row, NumberRow):
            return row.label
        return {
            _PORT: "Porta",
            _CONNECT: "Desconectar" if self._connected() else "Conectar",
            _ZERO: "Zerar inclinação",
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
        for index, (row, name, value) in enumerate(self._row_widgets):
            name.setText(self._label(self._rows[index]))
            value.setText(self._value(self._rows[index]))
            style = _SELECTED_STYLE if index == self._selected else _UNSELECTED_STYLE
            row.setStyleSheet(f"QWidget {{ {style} }}")
        for label, text in zip(self._readout_labels, self.readout_lines()):
            label.setText(text)
        self._status_label.setText(self._status)

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
        row = self._rows[self._selected]
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
        elif key == Qt.Key.Key_Escape:
            self.close_fn()
            return
        else:
            super().keyPressEvent(event)
            return
        self._refresh()
