import time
from collections.abc import Callable
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.config import config
from app.gyro import get_gyro
from app.gyro.state import GyroSnapshot, GyroStatus
from app.masterinjection.signal import Signal
from app.state.event import EventType, VehicleStateChangeEvent
from app.state.state import vehicle_state
from app.ui.base.screen import Screen
from app.ui.components.signal_card import SignalCard
from app.ui.ignition_tuning.analysis import AnalysisStatus, IgnitionAnalysis, ScenarioStats, Tilt
from app.ui.ignition_tuning.ignition_map_state import IgnitionMapState, ignition_map_state
from app.ui.ignition_tuning.ignition_write_controller import IgnitionWriteController
from app.ui.ignition_tuning.results_log import IgnitionResultsLog

# Signals shown as cards in the top bar, in order
_TOP_BAR_SIGNALS = [
    Signal.RPM,
    Signal.MAP,
    Signal.PEDAL,
    Signal.GEAR,
    Signal.IGN,
    Signal.LAMBDA,
]

# Second line of the top bar, before the gear indicator and the RPM band
_SECOND_LINE_SIGNALS = [
    Signal.CLT,
    Signal.IAT,
]

_STATUS_COLORS = {
    AnalysisStatus.ANALYSING: "#2ECC71",
    AnalysisStatus.SETTLING: "#E7C53C",
    AnalysisStatus.OUT_OF_RANGE: "#FF8800",
    AnalysisStatus.WAITING_ECU: "#888888",
    AnalysisStatus.WAITING_SENSOR: "#FF8800",
    AnalysisStatus.TILTED: "#E74C3C",
    AnalysisStatus.PAUSED: "#1E90FF",
}

_BEST_BORDER = "#2ECC71"
_PLAIN_BORDER = "#151515"
_CURRENT_HEADER_BG = "#1E90FF"
_DIM_TEXT = "#777777"

_FOOTER_TEXT = ("↑ +1°   ↓ -1°   ←→ Marcha   Espaço Pausa   X Descarta pior   R Resetar   G Zerar inclinação   "
                "ESC Voltar")
_EMPTY_TEXT = "Sem amostras ainda: mantenha a faixa de RPM, a marcha e o lambda em malha fechada"


def format_offset(offset: int) -> str:
    """Top-bar form of the offset: `+2°`, `0°`, `-1°`."""
    return "0°" if offset == 0 else f"{offset:+d}°"


def format_column_offset(offset: int) -> str:
    """Column header form of the offset: `+1°`, `0° orig`, `-1°`."""
    return "0° orig" if offset == 0 else f"{offset:+d}°"


_TILT_GREEN = "#2ECC71"
_TILT_RED = "#E74C3C"
_TILT_ORANGE = "#FF8800"
_TILT_GRAY = "#777777"

_TILT_TEXTS = {
    GyroStatus.DISABLED: ("desligada", _TILT_GRAY),
    GyroStatus.DISCONNECTED: ("desconectada", _TILT_ORANGE),
    GyroStatus.CALIBRATING: ("calibrando…", _TILT_ORANGE),
    GyroStatus.NO_SIGNAL: ("sem sinal", _TILT_ORANGE),
    GyroStatus.NOT_ZEROED: ("sem zero (G)", _TILT_ORANGE),
}


def format_inclination(snapshot: GyroSnapshot, max_tilt_deg: float) -> tuple:
    """The inclination box: (`Inclinação: +1.4° ↓`, colour). Positive pitch is nose down, negative nose up."""
    if snapshot.status is not GyroStatus.USABLE:
        text, color = _TILT_TEXTS[snapshot.status]
        return f"Inclinação: {text}", color
    pitch = snapshot.pitch
    color = _TILT_GREEN if abs(pitch) <= max_tilt_deg else _TILT_RED
    if round(pitch, 1) == 0:
        return "Inclinação: 0.0°", color
    return f"Inclinação: {pitch:+.1f}° {'↓' if pitch > 0 else '↑'}", color


def format_gear_indicator(gears: list, shown: int, with_data: list) -> str:
    """Every configured gear, the shown one in brackets, followed by a dot when it holds scenarios: `4ª•  [5ª]`."""
    parts = []
    for gear in sorted(gears):
        text = f"{gear}ª{'•' if gear in with_data else ''}"
        parts.append(f"[{text}]" if gear == shown else text)
    return "  ".join(parts)


def format_time(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def format_diff(diff: Optional[float]) -> str:
    """`+2.2%`, `0.0%` or `--` when there is no percentage."""
    if diff is None:
        return "--"
    if round(diff, 1) == 0:
        return "0.0%"
    return f"{diff:+.1f}%"


def diff_color(diff: Optional[float]) -> str:
    """Green for the best value, warmer the larger the difference."""
    if diff is None:
        return _DIM_TEXT
    if round(diff, 1) == 0:
        return "#2ECC71"
    if diff < 2:
        return "#E7C53C"
    if diff < 5:
        return "#FF9A3C"
    return "#E74C3C"


class ScenarioColumn(QFrame):
    """One scenario (one ignition offset of the shown gear) of the tuning screen."""

    _ROWS = ("header", "time", "ign", "inj", "inj_diff", "map", "map_diff", "pedal", "pedal_diff",
             "lam", "knock")

    def __init__(self, offset: int):
        super().__init__()
        self.offset = offset
        self.is_best = False
        self.is_current = False
        self.labels: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)
        for name in self._ROWS:
            label = QLabel("--")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            big = name in ("header", "inj", "map", "pedal")
            font = QFont("Arial", 34 if name == "header" else 26 if big else 20)
            font.setBold(big)
            label.setFont(font)
            label.setStyleSheet("color: white;")
            self.labels[name] = label
            layout.addWidget(label)
        layout.addStretch()
        self._apply_frame_style()

    def update_from(self, stats: ScenarioStats, is_current: bool):
        self.is_best = stats.is_best
        self.is_current = is_current
        text = self.labels
        text["header"].setText(format_column_offset(stats.offset))
        text["time"].setText(format_time(stats.time_s))
        text["ign"].setText(f"IGN {stats.ign:.1f}")
        text["inj"].setText(f"{stats.inj_pulse:.2f} ms")
        text["map"].setText(f"{stats.map:.1f} kPa")
        text["pedal"].setText(f"{stats.pedal:.1f} %")
        text["lam"].setText(f"λ {stats.lambda_:.2f}")
        text["knock"].setText(f"Knock {stats.knock}")
        for key, signal in (("inj_diff", Signal.INJ_PULSE), ("map_diff", Signal.MAP), ("pedal_diff", Signal.PEDAL)):
            diff = stats.diff.get(signal)
            text[key].setText(format_diff(diff))
            text[key].setStyleSheet(f"color: {diff_color(diff)};")
        text["time"].setStyleSheet(f"color: {'white' if stats.eligible else _DIM_TEXT};")
        text["header"].setStyleSheet(
            f"color: white; background-color: {_CURRENT_HEADER_BG if is_current else 'transparent'};")
        self._apply_frame_style()

    def _apply_frame_style(self):
        # Same border width for every column, so the highlight never shifts the content.
        color = _BEST_BORDER if self.is_best else _PLAIN_BORDER
        self.setObjectName("scenarioColumn")
        self.setStyleSheet(
            f"#scenarioColumn {{ background-color: black; border: 6px solid {color}; }}")


class IgnitionTuningScreen(Screen):
    """
    Ignition tuning: a very small set of keys (Up, Down, Left, Right, Space, X, R, Esc) moves one global advance
    offset and compares, per offset and gear, what the engine needed to hold the same speed.
    """

    def __init__(self, close_fn: Callable, state: Optional[IgnitionMapState] = None,
                 analysis: Optional[IgnitionAnalysis] = None, clock: Callable[[], float] = time.monotonic,
                 results: Optional[IgnitionResultsLog] = None, gyro=None):
        super().__init__(close_fn)
        self._gyro = get_gyro() if gyro is None else gyro
        self._state = ignition_map_state if state is None else state
        self._analysis = IgnitionAnalysis() if analysis is None else analysis
        self._results = IgnitionResultsLog(self._analysis) if results is None else results
        self._shown_gear = max(self._analysis.gears)
        self._engaged_gear: Optional[int] = None
        self._clock = clock
        self._active = False
        self._columns: list[ScenarioColumn] = []

        self.setStyleSheet("background-color: black;")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_top_bar())
        root_layout.addWidget(self._separator())
        root_layout.addWidget(self._build_centre(), stretch=1)
        root_layout.addWidget(self._separator())
        root_layout.addWidget(self._build_footer())

        cfg = config.ignition_tuning
        self._players: dict[str, QMediaPlayer] = {}
        self._outputs: list[QAudioOutput] = []
        for name, path in (("ready", cfg.ready_sound), ("pause", cfg.pause_sound), ("resume", cfg.resume_sound),
                           ("discard", cfg.discard_sound)):
            self._players[name] = self._make_player(path)

        self._writer = IgnitionWriteController(cfg.write_sound, self._state, on_finished=self._on_write_finished)

        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh)

        vehicle_state.emitter.connect(self._on_vehicle_state_event)

    # ── Construction helpers ─────────────────────────────────────────────────

    def _make_player(self, path: str) -> QMediaPlayer:
        output = QAudioOutput()
        output.setVolume(1.0)
        player = QMediaPlayer()
        player.setAudioOutput(output)
        player.setSource(QUrl.fromLocalFile(path))
        self._outputs.append(output)
        return player

    @staticmethod
    def _separator() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #333333; border: none;")
        return line

    def _build_top_bar(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background-color: #000000;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(0)

        lines = QVBoxLayout()
        lines.setSpacing(0)

        first = QHBoxLayout()
        first.setSpacing(0)
        self._top_bar_cards: dict[Signal, SignalCard] = {}
        for signal in _TOP_BAR_SIGNALS:
            card = SignalCard(signal)
            self._equal_column(card)
            first.addWidget(card, stretch=1)
            self._top_bar_cards[signal] = card
        lines.addLayout(first)

        # The second line uses the same columns as the first one: CLT and IAT one column each, the inclination
        # box two, the gear indicator and the RPM band the last two.
        second = QHBoxLayout()
        second.setSpacing(0)
        self._second_line_cards: dict[Signal, SignalCard] = {}
        for signal in _SECOND_LINE_SIGNALS:
            card = SignalCard(signal)
            self._equal_column(card)
            second.addWidget(card, stretch=1)
            self._second_line_cards[signal] = card
        self.inclination_label = QLabel("")
        self.inclination_label.setFont(self._bold_font(22))
        self.inclination_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._equal_column(self.inclination_label)
        second.addWidget(self.inclination_label, stretch=2)
        gear_band_widget = QWidget()
        self._equal_column(gear_band_widget)
        gear_band = QHBoxLayout(gear_band_widget)
        gear_band.setContentsMargins(0, 0, 0, 0)
        gear_band.setSpacing(0)
        self.gear_label = self._info_label(22)
        self.band_label = self._info_label(22)
        gear_band.addStretch()
        gear_band.addWidget(self.gear_label)
        gear_band.addSpacing(30)
        gear_band.addWidget(self.band_label)
        gear_band.addStretch()
        second.addWidget(gear_band_widget, stretch=2)
        lines.addLayout(second)
        layout.addLayout(lines, stretch=1)
        layout.addSpacing(24)

        info = QVBoxLayout()
        info.setSpacing(0)
        self.offset_label = QLabel(format_offset(0))
        self.offset_label.setFont(self._bold_font(48))
        self.offset_label.setStyleSheet("color: white;")
        self.offset_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label = QLabel(AnalysisStatus.WAITING_ECU.value)
        self.status_label.setFont(self._bold_font(20))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.addWidget(self.offset_label)
        info.addWidget(self.status_label)
        layout.addLayout(info)
        return container

    @staticmethod
    def _equal_column(widget: QWidget):
        """Ignore the widget's own width so the stretch factors alone share the line: both lines then use the
        same six columns, whatever the text inside."""
        widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    @staticmethod
    def _bold_font(size: int) -> QFont:
        font = QFont("Arial", size)
        font.setBold(True)
        return font

    def _info_label(self, size: int) -> QLabel:
        label = QLabel("")
        label.setFont(self._bold_font(size))
        label.setStyleSheet("color: white;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _build_centre(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background-color: #000000;")
        self._columns_layout = QHBoxLayout(container)
        self._columns_layout.setContentsMargins(8, 8, 8, 8)
        self._columns_layout.setSpacing(8)

        self.empty_label = QLabel(_EMPTY_TEXT)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setFont(QFont("Arial", 20))
        self.empty_label.setStyleSheet(f"color: {_DIM_TEXT};")
        self._columns_layout.addWidget(self.empty_label)
        return container

    def _build_footer(self) -> QWidget:
        container = QWidget()
        container.setFixedHeight(40)
        container.setStyleSheet("background-color: #000000;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 0, 12, 0)

        self.hint_label = QLabel(_FOOTER_TEXT)
        self.hint_label.setFont(QFont("Arial", 12))
        self.hint_label.setStyleSheet("color: #888888;")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint_label)
        return container

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def on_activated(self):
        self._active = True
        self._writer.set_muted(False)
        self._refresh_timer.start(100)
        self._refresh()

    def on_deactivated(self):
        self._active = False
        self._refresh_timer.stop()
        self._writer.set_muted(True)  # a write still pending plays no sound while hidden
        self._results.flush()

    # ── Keys ─────────────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if event.isAutoRepeat():
            return
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close_fn()
        elif key == Qt.Key.Key_Up:
            self._change_offset(+1)
        elif key == Qt.Key.Key_Down:
            self._change_offset(-1)
        elif key == Qt.Key.Key_Left:
            self._shift_gear(-1)
        elif key == Qt.Key.Key_Right:
            self._shift_gear(+1)
        elif key == Qt.Key.Key_Space:
            self._toggle_pause()
        elif key == Qt.Key.Key_X:
            self._discard_worst()
        elif key == Qt.Key.Key_R:
            self._reset()
        elif key == Qt.Key.Key_G:
            self._gyro.zero()

    def _change_offset(self, delta: int):
        if not self._state.adjust_offset(delta):
            return
        self._analysis.offset_changed(self._clock())
        self._writer.on_adjustment_made()
        self._refresh()

    def _toggle_pause(self):
        if self._analysis.paused:
            self._analysis.resume(self._clock())
            self._play("resume")
        else:
            self._analysis.pause()
            self._play("pause")
        self._refresh()

    def _shift_gear(self, delta: int):
        gears = sorted(self._analysis.gears)
        index = gears.index(self._shown_gear) + delta
        if 0 <= index < len(gears):
            self._shown_gear = gears[index]
            self._refresh()

    def _discard_worst(self):
        if self._analysis.discard_worst(self._shown_gear, self._state.offset):
            self._play("discard")
            self._results.tick()
            self._refresh()

    def _reset(self):
        self._state.reset()
        self._results.end_run()  # the results of this run are final: the next sample starts a new file
        self._analysis.reset()
        self._analysis.offset_changed(self._clock())  # wait for the write that puts the original map back
        self._writer.on_adjustment_made()
        self._refresh()

    def _play(self, name: str):
        player = self._players[name]
        player.stop()
        player.play()

    # ── Data in ──────────────────────────────────────────────────────────────

    def on_signal_received(self, signals: dict):
        """Every parsed telemetry set. Only analysed while the screen is active."""
        if not self._active:
            return
        self._follow_engaged_gear(signals)
        ready = self._analysis.process(signals, self._clock(), self._state.offset, self._state.is_loaded(),
                                       self._tilt())
        self._results.tick()
        if ready:
            self._play("ready")

    def _tilt(self) -> Tilt:
        """The inclinometer for the analysis: required whenever a port is configured, pitch only while usable."""
        snapshot = self._gyro.snapshot()
        return Tilt(snapshot.status is not GyroStatus.DISABLED, snapshot.pitch)

    def on_setting_changed(self, section: str, key: str):
        """A setting was changed on the Settings screen. A new RPM band ends the results of the current run first."""
        if section != "ignition_tuning":
            return
        if self._analysis.band_differs_from_config():
            self._results.end_run()  # written with the band the scenarios were analysed with
        self._analysis.reload_settings()
        self._refresh()

    def flush_results(self):
        """Write the ignition results now if they changed (the window calls this when it closes)."""
        self._results.flush()

    def _follow_engaged_gear(self, signals: dict):
        """The shown gear follows the engaged gear each time it changes to a configured gear."""
        parsed = signals.get(Signal.GEAR)
        if parsed is None:
            return
        gear = int(parsed.value)
        if gear != self._engaged_gear:
            self._engaged_gear = gear
            if gear in self._analysis.gears:
                self._shown_gear = gear

    def _on_write_finished(self):
        self._analysis.write_finished(self._clock())

    def _on_vehicle_state_event(self, event: VehicleStateChangeEvent):
        if event.type_ == EventType.MAP_BREAKPOINTS:
            self._state.load_breakpoints_map(event.args[0])
        elif event.type_ == EventType.IGNITION_MAP:
            self._state.load_row(event.args[0], event.args[1])

    # ── View ─────────────────────────────────────────────────────────────────

    def _refresh(self):
        self._update_top_bar()
        self._update_columns()

    def _update_top_bar(self):
        for signal, card in (*self._top_bar_cards.items(), *self._second_line_cards.items()):
            data = vehicle_state.get(signal)
            card.set_value(data.value_str if data else "--")
        self.gear_label.setText(format_gear_indicator(
            self._analysis.gears, self._shown_gear, self._analysis.gears_with_data()))
        self.band_label.setText(f"Faixa {self._analysis.rpm_min}-{self._analysis.rpm_max}")
        self.offset_label.setText(format_offset(self._state.offset))
        status = self._analysis.status(vehicle_state.get_all(), self._clock(), self._state.is_loaded(), self._tilt())
        self.status_label.setText(status.value)
        self.status_label.setStyleSheet(f"color: {_STATUS_COLORS[status]};")
        text, color = format_inclination(self._gyro.snapshot(), self._analysis.max_tilt_deg)
        self.inclination_label.setText(text)
        self.inclination_label.setStyleSheet(f"color: {color}; border: 3px solid {color}; margin: 12px 0px; padding: 2px 8px;")

    def _update_columns(self):
        stats = self._analysis.scenarios(self._shown_gear)
        offsets = [s.offset for s in stats]
        if offsets != [c.offset for c in self._columns]:
            self._rebuild_columns(offsets)
        for column, scenario in zip(self._columns, stats):
            column.update_from(scenario, scenario.offset == self._state.offset)
        self.empty_label.setVisible(not stats)

    def _rebuild_columns(self, offsets: list):
        for column in self._columns:
            self._columns_layout.removeWidget(column)
            column.setParent(None)
            column.deleteLater()
        self._columns = [ScenarioColumn(offset) for offset in offsets]
        for column in self._columns:
            self._columns_layout.addWidget(column, stretch=1)
