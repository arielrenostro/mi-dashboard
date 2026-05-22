from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from app.masterinjection.protocol import EcuResponse
from app.ui.ve_calibration.ve_map_state import ve_map_state
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QHeaderView,
    QFrame,
    QSizePolicy,
)
from pyqtgraph.Qt.QtCore import Slot

from app.masterinjection.signal import Signal
from app.ui.base.screen import Screen

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

    def __init__(self):
        super().__init__()

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
        self._highlight_timer.start(100)

    # ── Construction helpers ─────────────────────────────────────────────────

    def _separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #333333; border: none;")
        return line

    def _build_top_bar(self) -> QWidget:
        container = QWidget()
        container.setFixedHeight(80)
        container.setStyleSheet("background-color: #000000;")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(0)

        self._top_bar_labels: dict[Signal, tuple[QLabel, QLabel]] = {}

        name_font = QFont("Arial", 12)
        name_font.setBold(True)

        value_font = QFont("Arial", 40)
        value_font.setBold(True)

        for i, signal in enumerate(_TOP_BAR_SIGNALS):
            sig_val = signal.value
            name = sig_val["name"]
            unit = sig_val["unit"]
            header_text = f"{name} ({unit})" if unit else name

            cell = QWidget()
            cell.setStyleSheet(
                "background-color: #000000;"
                + ("border-left: 1px solid #333333;" if i > 0 else "")
            )
            cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(8, 2, 8, 2)
            cell_layout.setSpacing(0)

            name_label = QLabel(header_text)
            name_label.setFont(name_font)
            name_label.setStyleSheet("color: #888888;")
            name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            value_label = QLabel("--")
            value_label.setFont(value_font)
            value_label.setStyleSheet("color: #FFFFFF;")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            cell_layout.addWidget(name_label)
            cell_layout.addWidget(value_label)

            layout.addWidget(cell)
            self._top_bar_labels[signal] = (name_label, value_label)

        return container

    def _build_centre(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background-color: #000000;")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left panel — VE Map table (60%)
        left_panel = self._build_left_panel()
        layout.addWidget(left_panel, stretch=60)

        # Thin vertical separator
        v_line = QFrame()
        v_line.setFrameShape(QFrame.Shape.VLine)
        v_line.setFixedWidth(1)
        v_line.setStyleSheet("background-color: #333333; border: none;")
        layout.addWidget(v_line)

        # Right panel — graph placeholder (40%)
        right_panel = self._build_right_panel()
        layout.addWidget(right_panel, stretch=40)

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

        # Table: 16 rows × 17 columns (col 0 = MAP axis label, cols 1-16 = RPM values)
        table = QTableWidget(16, 17)
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
        for col in range(1, 17):
            table.setHorizontalHeaderItem(col, self._header_item("—"))

        # Row headers: MAP values (populated later)
        for row in range(16):
            table.setVerticalHeaderItem(row, self._header_item("—"))

        # Fill all cells with placeholder
        for row in range(16):
            # Col 0: MAP axis value — duplicate of the vertical header for layout clarity
            map_item = QTableWidgetItem("—")
            map_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            map_item.setFont(cell_font)
            map_item.setBackground(QColor("#111111"))
            map_item.setForeground(QColor("#888888"))
            table.setItem(row, 0, map_item)

            for col in range(1, 17):
                item = QTableWidgetItem("—")
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )
                item.setFont(cell_font)
                item.setBackground(QColor(_DEFAULT_CELL_BG))
                item.setForeground(QColor(_DEFAULT_TEXT_COLOR))
                table.setItem(row, col, item)

        # Adjust column 0 (MAP axis) to be slightly wider
        table.setColumnWidth(0, 52)

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
        plot_widget.setLabel("left", "MAP (kPa)", color="#888888")

        # ImageItem: rows=MAP axis (y), cols=RPM axis (x), value=VE
        # pyqtgraph ImageItem expects shape (cols, rows) = (16, 16) with x=cols, y=rows
        # Use a ColorMap from dark blue (low VE) → orange/yellow (high VE)
        try:
            colormap = pg.colormap.get("CET-L1")
        except Exception:
            colormap = pg.colormap.get("inferno")

        image_item = pg.ImageItem()
        image_item.setColorMap(colormap)
        plot_widget.addItem(image_item)

        # Scatter for active interpolation point
        scatter = pg.ScatterPlotItem(size=12, pen=pg.mkPen("white", width=2), brush=pg.mkBrush("red"))
        plot_widget.addItem(scatter)

        layout.addWidget(plot_widget, stretch=1)

        self.graph_placeholder = header  # keep reference for backward compat
        self._heatmap_image = image_item
        self._heatmap_scatter = scatter
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

    @Slot(dict)
    def process_signals(self, parsed_data: dict):
        """Update top-bar labels from the latest parsed_data snapshot."""
        for signal, (name_label, value_label) in self._top_bar_labels.items():
            data = parsed_data.get(signal)
            if data:
                value_label.setText(data["value_str"])

                # Colour LAMBDA_LOOP: green = Closed, orange = Open
                if signal is Signal.LAMBDA_LOOP:
                    if data["value"] == 1:
                        value_label.setStyleSheet("color: #00FF00;")  # green
                    else:
                        value_label.setStyleSheet("color: #FF8800;")  # orange

    @Slot(int)
    def handle_key(self, key: int):
        """Handle keyboard input for VE map editing.

        - Up arrow: +6 VE
        - Down arrow: -6 VE
        - R key: reset to original values

        Space key (lambda loop toggle) is handled globally and should NOT be intercepted here.
        """
        if key == Qt.Key.Key_Up:
            self._adjust_ve(+6.0)
        elif key == Qt.Key.Key_Down:
            self._adjust_ve(-6.0)
        elif key == Qt.Key.Key_R:
            ve_map_state.reset()
            self.ve_adjustment_made.emit()

    def _adjust_ve(self, delta: float):
        from app.state.state import vehicle_state
        from app.masterinjection.signal import Signal

        rpm_data = vehicle_state.get(Signal.RPM)
        map_data = vehicle_state.get(Signal.MAP)

        if rpm_data is None or map_data is None:
            return

        ve_map_state.adjust_ve(rpm_data["value"], map_data["value"], delta)
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
                col_idx + 1, self._header_item(str(rpm_val))
            )

        for row_idx, map_val in enumerate(map_axis):
            # Vertical row header
            self.ve_table.setVerticalHeaderItem(
                row_idx, self._header_item(str(map_val))
            )

            # Col 0: MAP axis label cell
            map_item = self.ve_table.item(row_idx, 0)
            if map_item is None:
                map_item = QTableWidgetItem()
                map_item.setBackground(QColor("#111111"))
                map_item.setForeground(QColor("#888888"))
                self.ve_table.setItem(row_idx, 0, map_item)
            map_item.setText(str(map_val))
            map_item.setFont(row_header_font)
            map_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            # VE value cells (cols 1-16); ve_map contains raw ECU ints → display as raw/10
            for col_idx, ve_raw in enumerate(ve_map[row_idx]):
                item = self.ve_table.item(row_idx, col_idx + 1)
                if item is None:
                    item = QTableWidgetItem()
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.ve_table.setItem(row_idx, col_idx + 1, item)
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
        for row in range(16):
            for col in range(1, 17):
                item = self.ve_table.item(row, col)
                if item is None:
                    continue
                weight = weights.get((row, col - 1), 0.0)
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
        for row in range(16):
            for col in range(1, 17):
                item = self.ve_table.item(row, col)
                if item is None:
                    continue
                if (row, col - 1) in modified:
                    item.setForeground(QColor(_MODIFIED_TEXT_COLOR))
                else:
                    item.setForeground(QColor(_DEFAULT_TEXT_COLOR))

    def update_heatmap(self, ve_map: list, rpm_axis: list, map_axis: list, weights: dict):
        """Update the heatmap image and scatter point.

        Args:
            ve_map: 16x16 list[list[float]], ve_map[row][col] where row=MAP idx, col=RPM idx
            rpm_axis: list of 16 RPM values (ascending)
            map_axis: list of 16 MAP values (ascending, kPa)
            weights: {(row, col): float} from interpolation, or empty dict
        """
        import numpy as np

        # ImageItem expects shape (n_cols, n_rows) = (16, 16)
        # Convert ve_map[row][col] (raw int) → VE% → array[col][row] for ImageItem
        arr = [[ve_map[row][col] / 10 for row in range(16)] for col in range(16)]
        self._heatmap_image.setImage(np.array(arr))

        # Set the image position/scale to match rpm/map axis ranges
        rpm_min, rpm_max = rpm_axis[0], rpm_axis[-1]
        map_min, map_max = map_axis[0], map_axis[-1]
        self._heatmap_image.setRect(
            rpm_min, map_min,
            rpm_max - rpm_min,
            map_max - map_min,
        )

        # Scatter: show weighted centroid of active cells
        if weights:
            cx = sum(rpm_axis[col] * w for (row, col), w in weights.items())
            cy = sum(map_axis[row] * w for (row, col), w in weights.items())
            self._heatmap_scatter.setData([cx], [cy])
        else:
            self._heatmap_scatter.setData([], [])

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

        rpm = rpm_data["value"]
        map_val = map_data["value"]

        weights = ve_map_state.calculate_interpolation_weights(rpm, map_val)
        self.highlight_interpolation(weights)
        self.mark_modified_cells(ve_map_state.get_visually_modified())
        self.update_heatmap(ve_map_state.ve_map, ve_map_state.rpm_axis, ve_map_state.map_axis, weights)
        self._refresh_ve_values()

    def _refresh_ve_values(self):
        for row in range(16):
            for col in range(16):
                item = self.ve_table.item(row, col + 1)
                if item is not None:
                    item.setText(f"{ve_map_state.ve_map[row][col] / 10:.1f}")

    # ── ECU map data reception ────────────────────────────────────────────────

    @Slot(str)
    def receive_map_data(self, line: str):
        """
        Parse and apply a raw ECU map data line (#I20, #I21, or #F01-#F16).
        Connected to EcuConnection.map_data_received.
        """
        parts = line.strip().split(';')
        if not parts:
            return
        cmd = parts[0]
        try:
            values = [int(v) for v in parts[1:] if v.strip()]
        except ValueError:
            return

        if cmd == EcuResponse.MAP_BREAKPOINTS.value and len(values) == 16:
            ve_map_state.load_breakpoints_rpm(values)
            self.refresh_axes()
        elif cmd == '#I21' and len(values) == 16:
            ve_map_state.load_breakpoints_map(values)
            self.refresh_axes()
        elif len(cmd) == 3 and cmd[0] == '#' and cmd[1] == 'F':
            try:
                row_num = int(cmd[2:]) - 1  # #F01 → 0, #F16 → 15
                if 0 <= row_num <= 15 and len(values) == 16:
                    ve_map_state.load_row(row_num, values)
                    self.update_row(row_num)
            except ValueError:
                pass

    def refresh_axes(self):
        """Update table column/row headers from the current ve_map_state axes."""
        for col_idx, rpm_val in enumerate(ve_map_state.rpm_axis):
            self.ve_table.setHorizontalHeaderItem(col_idx + 1, self._header_item(str(rpm_val)))

        row_header_font = QFont("Arial", 10)
        row_header_font.setBold(True)
        for row_idx, map_val in enumerate(ve_map_state.map_axis):
            self.ve_table.setVerticalHeaderItem(row_idx, self._header_item(str(map_val)))
            map_item = self.ve_table.item(row_idx, 0)
            if map_item is not None:
                map_item.setText(str(map_val))
                map_item.setFont(row_header_font)

    def update_row(self, row: int):
        """Refresh the display of a single VE table row from ve_map_state."""
        cell_font = QFont("Arial", 10)
        for col in range(16):
            item = self.ve_table.item(row, col + 1)
            if item is None:
                item = QTableWidgetItem()
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFont(cell_font)
                item.setBackground(QColor(_DEFAULT_CELL_BG))
                item.setForeground(QColor(_DEFAULT_TEXT_COLOR))
                self.ve_table.setItem(row, col + 1, item)
            item.setText(f"{ve_map_state.ve_map[row][col] / 10:.1f}")
