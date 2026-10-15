from typing import Callable, Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.config import config
from app.ecu_connection import get_ecu_connection
from app.state.event import EventType, VehicleStateChangeEvent
from app.state.state import vehicle_state
from app.ui.base.screen import Screen
from app.ui.options.phase_write_controller import PhaseWriteController

UNKNOWN_VALUE = "—"
HINT = "↑↓ Navegar | Enter Alterar | Esc Voltar"

_SELECTED_STYLE = (
    "color: white; border: 2px solid #1E90FF; background-color: rgba(30, 144, 255, 0.2); padding: 10px;"
)
_UNSELECTED_STYLE = "color: gray; border: 2px solid transparent; background-color: transparent; padding: 10px;"


class OptionsScreen(Screen):
    """List of ECU settings changed from the keyboard. For now: the engine phase."""

    def __init__(self, close_fn: Callable, controller: Optional[PhaseWriteController] = None):
        super().__init__(close_fn)

        # Confirmation sound of a phase write: the VE one, restarted each time and never muted, because the
        # write can happen after the screen was left.
        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(1.0)
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio_output)
        self._player.setSource(QUrl.fromLocalFile(config.ve_calibration.ve_sound))

        self._controller = controller or PhaseWriteController(
            send_command=lambda cmd, args=None: get_ecu_connection().send_command(cmd, args),
            get_block=vehicle_state.get_x02,
            set_block=vehicle_state.set_x02,
            on_written=self._play_write_sound,
        )
        self._controller.changed.connect(self._refresh)
        vehicle_state.emitter.connect(self._on_vehicle_state_event)

        self.setStyleSheet("background-color:black;")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(40)
        layout.addStretch()

        title = QLabel("Opções")
        title_font = QFont("Arial", 48)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Fields: (label, value text, action on Enter). Add new settings here.
        self._fields = [
            ("Fase", self._phase_text, self._controller.toggle),
        ]
        self._field_rows = []
        fields_container = QWidget()
        fields_layout = QVBoxLayout(fields_container)
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setSpacing(10)
        row_font = QFont("Arial", 24)
        for label_text, _, _ in self._fields:
            row = QWidget()
            row.setMinimumWidth(520)
            row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            name = QLabel(label_text)
            name.setFont(row_font)
            value = QLabel()
            value.setFont(row_font)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(name)
            row_layout.addStretch()
            row_layout.addWidget(value)
            self._field_rows.append((row, name, value))
            fields_layout.addWidget(row)
        layout.addWidget(fields_container, alignment=Qt.AlignmentFlag.AlignCenter)

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

        self._selected = 0
        self._refresh()

    def _play_write_sound(self):
        self._player.stop()
        self._player.play()

    # ------------------------------------------------------------- lifecycle

    def on_activated(self):
        self._controller.request_refresh()
        self._refresh()

    def on_deactivated(self):
        self._controller.clear_success_status()

    def on_ecu_line(self, line: str):
        """A line received from the ECU (forwarded by the window)."""
        self._controller.on_line_received(line)

    # --------------------------------------------------------------- display

    def _phase_text(self) -> str:
        phase = self._controller.displayed_phase()
        if phase is None:
            return UNKNOWN_VALUE
        return f"{phase.label} …" if self._controller.in_progress else phase.label

    def _on_vehicle_state_event(self, event: VehicleStateChangeEvent):
        if event.type_ == EventType.PARAMETER_BLOCK:
            self._refresh()

    def _refresh(self):
        for i, ((_, value_fn, _), (row, name, value)) in enumerate(zip(self._fields, self._field_rows)):
            value.setText(value_fn())
            style = _SELECTED_STYLE if i == self._selected else _UNSELECTED_STYLE
            row.setStyleSheet(f"QWidget {{ {style} }}")
        self._status_label.setText(self._controller.status)

    # -------------------------------------------------------------- keyboard

    def keyPressEvent(self, event: QKeyEvent):
        if event.isAutoRepeat():
            return

        key = event.key()
        if key == Qt.Key.Key_Up:
            self._selected = (self._selected - 1) % len(self._fields)
            self._refresh()
        elif key == Qt.Key.Key_Down:
            self._selected = (self._selected + 1) % len(self._fields)
            self._refresh()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._fields[self._selected][2]()
        elif key == Qt.Key.Key_Escape:
            self.close_fn()
        else:
            super().keyPressEvent(event)
