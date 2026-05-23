from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QKeyEvent
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QAbstractScrollArea,
    QHeaderView,
    QFrame,
)
from pyqtgraph.Qt.QtCore import Slot

from app.masterinjection.signal import Signal
from app.state.event import VehicleStateChangeEvent, EventType
from app.state.state import vehicle_state
from app.ui.base.screen import Screen
from app.ui.components.signal_card import SignalCard
from app.ui.ve_calibration.ve_map_state import ve_map_state

# Signals shown in the top bar, in order
_TOP_BAR_SIGNALS = [
    Signal.RPM,
    Signal.MAP,
    Signal.VE,
    Signal.LAMBDA,
    Signal.LAMBDA_TARGET,
    Signal.FUEL_TRIM,
    Signal.LAMBDA_LOOP,
]

_DEFAULT_CELL_BG = "#1A1A1A"
_HIGHLIGHT_COLOR = QColor(0xFF, 0x66, 0x00)  # #FF6600
_MODIFIED_TEXT_COLOR = "#00CCFF"
_DEFAULT_TEXT_COLOR = "#FFFFFF"


def _interpolate_color(weight: float) -> str:
    """Return a hex color string blending _HIGHLIGHT_COLOR with _DEFAULT_CELL_BG by weight."""
    bg = QColor(_DEFAULT_CELL_BG)
    r = int(bg.red() + (_HIGHLIGHT_COLOR.red() - bg.red()) * weight)
    g = int(bg.green() + (_HIGHLIGHT_COLOR.green() - bg.green()) * weight)
    b = int(bg.blue() + (_HIGHLIGHT_COLOR.blue() - bg.blue()) * weight)
    return f"#{r:02X}{g:02X}{b:02X}"


class VeCalibrationScreen(Screen):
    """VE Calibration screen — 16x16 map viewer with live top-bar telemetry."""

    ve_adjustment_made = pyqtSignal()

    def __init__(self, close_fn: Callable):
        super().__init__(close_fn)

        self.setStyleSheet("background-color: black;")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Zone 1: Top bar ──────────────────────────────────────────────────
        top_bar = self._build_top_bar()
        root_layout.addWidget(top_bar)

        # Thin separator
        root_layout.addWidget(self._separator())

        # ── Zone 2: Centre (table + graph) ───────────────────────────────────
        centre = self._build_centre()
        root_layout.addWidget(centre, stretch=1)

        # Thin separator
        root_layout.addWidget(self._separator())

        # ── Zone 3: Footer ────────────────────────────────────────────────────
        footer = self._build_footer()
        root_layout.addWidget(footer)

        # ── Interpolation highlight timer ─────────────────────────────────────
        self._highlight_timer = QTimer()
        self._highlight_timer.timeout.connect(self._update_highlight)

        vehicle_state.emitter.connect(self._on_vehicle_state_event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.close_fn()
        elif event.key() == Qt.Key.Key_Up:
            self._adjust_ve(+6.0)
        elif event.key() == Qt.Key.Key_Down:
            self._adjust_ve(-6.0)
        elif event.key() == Qt.Key.Key_R:
            ve_map_state.reset()
            self.ve_adjustment_made.emit()

    # ── Construction helpers ─────────────────────────────────────────────────

    def _separator(self) -> QFrame:
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

        self._top_bar_labels: dict[Signal, SignalCard] = {}

        for i, signal in enumerate(_TOP_BAR_SIGNALS):
            card = SignalCard(signal)
            layout.addWidget(card)

            self._top_bar_labels[signal] = card

        return container

    def _build_centre(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background-color: #000000;")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left panel — VE Map table (natural size)
        left_panel = self._build_left_panel()
        layout.addWidget(left_panel, stretch=0)

        # Thin vertical separator
        v_line = QFrame()
        v_line.setFrameShape(QFrame.Shape.VLine)
        v_line.setFixedWidth(1)
        v_line.setStyleSheet("background-color: #333333; border: none;")
        layout.addWidget(v_line)

        # Right panel — graph fills remaining space
        right_panel = self._build_right_panel()
        layout.addWidget(right_panel, stretch=1)

        return container

    def _build_left_panel(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background-color: #000000;")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header_font = QFont("Arial", 14)
        header_font.setBold(True)

        header = QLabel("Mapa VE (16×16)")
        header.setFont(header_font)
        header.setStyleSheet("color: #FFFFFF;")
        header.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(header)

        # Table: 16 rows × 16 columns
        table = QTableWidget(16, 16)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setStyleSheet(
            "QTableWidget {"
            "  background-color: #1A1A1A;"
            "  color: #FFFFFF;"
            "  gridline-color: #333333;"
            "  border: 1px solid #333333;"
            "  font-family: Arial;"
            "  font-size: 10px;"
            "}"
            "QHeaderView::section {"
            "  background-color: #111111;"
            "  color: #888888;"
            "  border: 1px solid #333333;"
            "  font-family: Arial;"
            "  font-size: 10px;"
            "  padding: 2px;"
            "}"
            "QTableWidget QTableCornerButton::section {"
            "  background-color: #111111;"
            "  border: 1px solid #333333;"
            "}"
            "QScrollBar:horizontal, QScrollBar:vertical {"
            "  background: #111111;"
            "}"
        )

        cell_font = QFont("Arial", 10)

        # Horizontal header: hide the default numeric header and set column labels
        table.horizontalHeader().setDefaultSectionSize(46)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        table.horizontalHeader().setVisible(True)

        # Vertical header: MAP axis values (populated later via populate_ve_table)
        table.verticalHeader().setDefaultSectionSize(22)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        table.verticalHeader().setVisible(True)
        table.verticalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        # Column headers: col 0 is the MAP-axis label column; cols 1-16 are RPM values
        table.setHorizontalHeaderItem(0, self._header_item("MAP\\RPM"))
        for col in range(16):
            table.setHorizontalHeaderItem(col, self._header_item("—"))

        # Row headers: MAP values (populated later)
        for row in range(16):
            table.setVerticalHeaderItem(row, self._header_item("—"))

        # Fill all cells with placeholder
        for row in range(16):
            for col in range(1, 16):
                item = QTableWidgetItem("—")
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )
                item.setFont(cell_font)
                item.setBackground(QColor(_DEFAULT_CELL_BG))
                item.setForeground(QColor(_DEFAULT_TEXT_COLOR))
                table.setItem(row, col, item)

        table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        layout.addWidget(table, stretch=1)
        self.ve_table = table

        return container

    def _build_right_panel(self) -> QWidget:
        import pyqtgraph as pg

        container = QWidget()
        container.setStyleSheet("background-color: #000000;")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header_font = QFont("Arial", 14)
        header_font.setBold(True)
        header = QLabel("Gráfico VE")
        header.setFont(header_font)
        header.setStyleSheet("color: #FFFFFF;")
        header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(header)

        plot_widget = pg.PlotWidget()
        plot_widget.setBackground("#000000")
        plot_widget.setLabel("bottom", "RPM", color="#888888")
        plot_widget.setLabel("left", "VE (%)", color="#888888")
        plot_widget.showGrid(x=True, y=True, alpha=0.2)

        # One line per MAP row: blue (low MAP) → orange (high MAP)
        ve_lines = []
        for i in range(16):
            t = i / 15.0
            r = int(0 + t * 255)
            g = int(136 - t * 136)
            b = int(255 - t * 255)
            curve = pg.PlotCurveItem(pen=pg.mkPen(color=(r, g, b), width=1))
            plot_widget.addItem(curve)
            ve_lines.append(curve)

        # Scatter: interpolated VE from table (red)
        scatter_table = pg.ScatterPlotItem(size=12, pen=pg.mkPen("white", width=2), brush=pg.mkBrush("red"))
        plot_widget.addItem(scatter_table)

        # Scatter: actual VE signal from ECU (lime)
        scatter_signal = pg.ScatterPlotItem(size=12, pen=pg.mkPen("white", width=2), brush=pg.mkBrush("lime"))
        plot_widget.addItem(scatter_signal)

        layout.addWidget(plot_widget, stretch=1)

        self.graph_placeholder = header
        self._ve_lines = ve_lines
        self._heatmap_scatter = scatter_table
        self._ve_signal_scatter = scatter_signal
        self._heatmap_plot = plot_widget

        return container

    def _build_footer(self) -> QWidget:
        container = QWidget()
        container.setFixedHeight(40)
        container.setStyleSheet("background-color: #000000;")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 0, 12, 0)

        hint_font = QFont("Arial", 12)

        hint = QLabel(
            "↑ +6 VE   ↓ -6 VE   Espaço Loop Open/Closed   R Resetar   ESC Voltar"
        )
        hint.setFont(hint_font)
        hint.setStyleSheet("color: #888888;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(hint)
        return container

    @staticmethod
    def _header_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        return item

    # ── Public API ────────────────────────────────────────────────────────────

    def _update_top_bar(self):
        """Update top-bar labels from the latest parsed_data snapshot."""
        for signal, card in self._top_bar_labels.items():
            data = vehicle_state.get(signal)
            if data:
                card.set_value(data.value_str)

                # Colour LAMBDA_LOOP: green = Closed, orange = Open
                if signal is Signal.LAMBDA_LOOP:
                    if data.value == 1:
                        card.set_text_color("#00FF00")  # green
                    else:
                        card.set_text_color("#FF8800")  # green

    def _adjust_ve(self, delta: float):
        from app.state.state import vehicle_state
        from app.masterinjection.signal import Signal

        rpm_data = vehicle_state.get(Signal.RPM)
        map_data = vehicle_state.get(Signal.MAP)

        if rpm_data is None or map_data is None:
            return

        ve_map_state.adjust_ve(rpm_data.value, map_data.value, delta)
        self.ve_adjustment_made.emit()

    def populate_ve_table(
            self,
            rpm_axis: list,
            map_axis: list,
            ve_map: list,
    ):
        """Populate the 16×16 VE table.

        Args:
            rpm_axis: 16 RPM integers used as column headers (cols 1-16).
            map_axis: 16 MAP integers used as row headers (rows 0-15).
            ve_map:   16×16 float matrix — ve_map[row][col] where row=MAP index,
                      col=RPM index.
        """
        cell_font = QFont("Arial", 10)
        row_header_font = QFont("Arial", 10)
        row_header_font.setBold(True)

        # Column headers (RPM values)
        for col_idx, rpm_val in enumerate(rpm_axis):
            self.ve_table.setHorizontalHeaderItem(
                col_idx, self._header_item(str(rpm_val))
            )

        for row_idx, map_val in enumerate(map_axis):
            display_row = 15 - row_idx
            # Vertical row header
            self.ve_table.setVerticalHeaderItem(
                display_row, self._header_item(str(map_val))
            )

            # Col 0: MAP axis label cell
            map_item = self.ve_table.item(display_row, 0)
            if map_item is None:
                map_item = QTableWidgetItem()
                map_item.setBackground(QColor("#111111"))
                map_item.setForeground(QColor("#888888"))
                self.ve_table.setItem(display_row, 0, map_item)
            map_item.setText(str(map_val))
            map_item.setFont(row_header_font)
            map_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            # VE value cells (cols 1-16); ve_map contains raw ECU ints → display as raw/10
            for col_idx, ve_raw in enumerate(ve_map[row_idx]):
                item = self.ve_table.item(display_row, col_idx)
                if item is None:
                    item = QTableWidgetItem()
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.ve_table.setItem(display_row, col_idx, item)
                item.setText(f"{ve_raw / 10:.1f}")
                item.setFont(cell_font)
                item.setBackground(QColor(_DEFAULT_CELL_BG))
                item.setForeground(QColor(_DEFAULT_TEXT_COLOR))

    def highlight_interpolation(self, weights: dict):
        """Apply interpolation highlights to the VE table.

        Args:
            weights: ``{(row, col): float}`` mapping.  weight=1.0 → full
                     highlight (#FF6600), weight=0.0 → default background.
                     Cells absent from the dict revert to the default background.
        """
        for data_row in range(16):
            display_row = 15 - data_row
            for col in range(16):
                item = self.ve_table.item(display_row, col)
                if item is None:
                    continue
                weight = weights.get((data_row, col), 0.0)
                if weight > 0.0:
                    item.setBackground(QColor(_interpolate_color(weight)))
                else:
                    item.setBackground(QColor(_DEFAULT_CELL_BG))

    def mark_modified_cells(self, modified: set):
        """Visually mark cells that have been modified.

        Args:
            modified: set of ``(row, col)`` tuples (0-based, matching the
                      ve_map indices — col is the RPM index, not the table
                      column index which is offset by 1).
        """
        for data_row in range(16):
            display_row = 15 - data_row
            for col in range(1, 16):
                item = self.ve_table.item(display_row, col)
                if item is None:
                    continue
                if (data_row, col) in modified:
                    item.setForeground(QColor(_MODIFIED_TEXT_COLOR))
                else:
                    item.setForeground(QColor(_DEFAULT_TEXT_COLOR))

    def update_heatmap(self, ve_map: list, rpm_axis: list, map_axis: list, weights: dict):
        """Update VE line chart and scatter point.

        Args:
            ve_map: 16x16 list[list[int]], ve_map[row][col] where row=MAP idx, col=RPM idx (raw ECU ints)
            rpm_axis: list of 16 RPM values (ascending)
            map_axis: list of 16 MAP values (ascending, kPa)
            weights: {(row, col): float} from interpolation, or empty dict
        """
        rpm_arr = rpm_axis

        for row_idx, curve in enumerate(self._ve_lines):
            ve_row = [ve_map[row_idx][col] / 10 for col in range(16)]
            curve.setData(rpm_arr, ve_row)

        if weights:
            cx = sum(rpm_axis[col] * w for (row, col), w in weights.items())
            cy = sum(ve_map[row][col] / 10 * w for (row, col), w in weights.items())
            self._heatmap_scatter.setData([cx], [cy])
        else:
            self._heatmap_scatter.setData([], [])

        rpm_data = vehicle_state.get(Signal.RPM)
        ve_data = vehicle_state.get(Signal.VE)
        if rpm_data is not None and ve_data is not None:
            self._ve_signal_scatter.setData([rpm_data.value], [ve_data.value])
        else:
            self._ve_signal_scatter.setData([], [])

    # ── Timer-driven live updates ─────────────────────────────────────────────

    def on_activated(self):
        self._highlight_timer.start(100)

    def on_deactivated(self):
        self._highlight_timer.stop()

    def _update_highlight(self):
        from app.state.state import vehicle_state
        from app.masterinjection.signal import Signal

        rpm_data = vehicle_state.get(Signal.RPM)
        map_data = vehicle_state.get(Signal.MAP)

        if rpm_data is None or map_data is None:
            return

        weights = ve_map_state.calculate_interpolation_weights(rpm_data.value, map_data.value)
        self.highlight_interpolation(weights)
        self.mark_modified_cells(ve_map_state.get_visually_modified())
        self.update_heatmap(ve_map_state.ve_map, ve_map_state.rpm_axis, ve_map_state.map_axis, weights)
        self._refresh_ve_values()
        self._update_top_bar()

    def _refresh_ve_values(self):
        for data_row in range(16):
            display_row = 15 - data_row
            for col in range(16):
                item = self.ve_table.item(display_row, col)
                if item is not None:
                    item.setText(f"{ve_map_state.ve_map[data_row][col]}")

    def _on_vehicle_state_event(self, event: VehicleStateChangeEvent):
        if event.type_ == EventType.MAP_BREAKPOINTS:
            ve_map_state.load_breakpoints_map(event.args[0])
            self.refresh_axes()
        elif event.type_ == EventType.RPM_BREAKPOINTS:
            ve_map_state.load_breakpoints_rpm(event.args[0])
            self.refresh_axes()
        elif event.type_ == EventType.FUEL_MAP:
            ve_map_state.load_row(event.args[0], event.args[1])
            self.update_row(event.args[0])

    def refresh_axes(self):
        """Update table column/row headers from the current ve_map_state axes."""
        for col_idx, rpm_val in enumerate(ve_map_state.rpm_axis):
            self.ve_table.setHorizontalHeaderItem(col_idx, self._header_item(str(rpm_val)))

        row_header_font = QFont("Arial", 10)
        row_header_font.setBold(True)
        for row_idx, map_val in enumerate(ve_map_state.map_axis):
            display_row = 15 - row_idx
            self.ve_table.setVerticalHeaderItem(display_row, self._header_item(str(map_val)))
            map_item = self.ve_table.item(display_row, 0)
            if map_item is not None:
                map_item.setText(str(map_val))
                map_item.setFont(row_header_font)

    def update_row(self, data_row: int):
        """Refresh the display of a single VE table row from ve_map_state."""
        display_row = 15 - data_row
        cell_font = QFont("Arial", 10)
        for col in range(16):
            item = self.ve_table.item(display_row, col)
            if item is None:
                item = QTableWidgetItem()
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFont(cell_font)
                item.setBackground(QColor(_DEFAULT_CELL_BG))
                item.setForeground(QColor(_DEFAULT_TEXT_COLOR))
                self.ve_table.setItem(display_row, col, item)
            item.setText(f"{ve_map_state.ve_map[data_row][col]}")
