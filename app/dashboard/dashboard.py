import logging
from collections import deque

import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout
)
from pyqtgraph.Qt.QtCore import Slot

from app.master.signal import Signal
from app.vehicle.state import vehicle_state

logger = logging.getLogger(__name__)


class Dashboard(QWidget):
    key_event = pyqtSignal(int)

    def __init__(self, grid, graphs, graph_x_size):
        super().__init__()

        self.setWindowTitle("Master Injection Dashboard")
        self.showFullScreen()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.grid = QGridLayout()
        self.layout.addLayout(self.grid)

        self.labels = {}
        self.create_grid(grid)

        self.curves = {}
        self.buffers = {}
        self.peak_markers = {}
        self.peak_labels = {}
        self.min_markers = {}
        self.min_labels = {}
        self.create_graphs(graphs, graph_x_size)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_graph)
        self.timer.start(100)

    def keyPressEvent(self, event):
        self.key_event.emit(event.key())
        super().keyPressEvent(event)

    def close(self):
        super().close()
        self.timer.stop()

    def create_grid(self, grid):
        for row_idx in range(len(grid)):
            for col_idx in range(len(grid[row_idx])):
                signal = grid[row_idx][col_idx]
                name = signal.value['name']
                unit = signal.value['unit']

                cell_widget = QWidget()
                cell_widget.setStyleSheet("background-color:black;")

                cell_layout = QVBoxLayout(cell_widget)
                cell_layout.setContentsMargins(8, 4, 8, 4)
                cell_layout.setSpacing(0)

                if unit != "":
                    small_label = QLabel(f"{name} ({unit})")
                else:
                    small_label = QLabel(f"{name}")
                small_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

                small_font = QFont("Arial", 14)
                small_font.setBold(True)
                small_label.setFont(small_font)

                small_label.setStyleSheet("color: gray;")

                big_label = QLabel("--")
                big_label.setAlignment(Qt.AlignmentFlag.AlignRight)

                big_font = QFont("Arial", 56)
                big_font.setBold(True)
                big_label.setFont(big_font)

                big_label.setStyleSheet("color: white;")

                cell_layout.addWidget(small_label)
                cell_layout.addWidget(big_label)

                self.grid.addWidget(cell_widget, row_idx, col_idx)
                self.labels[signal] = (cell_widget, big_label)

    def create_graphs(self, graphs, graph_x_size):
        for row in graphs:
            plot_widget = pg.PlotWidget()
            self.layout.addWidget(plot_widget)

            plot_item = plot_widget.getPlotItem()
            base_view = plot_item.getViewBox()
            base_view.setMouseEnabled(x=False, y=True)
            plot_item.hideAxis("left")
            plot_item.hideAxis("bottom")

            for signal in row:
                name = signal.value["name"]
                color = signal.value["color"]
                min_ = signal.value["min"]
                max_ = signal.value["max"]

                axis = pg.AxisItem("right")

                font = QFont("Arial", 8)
                axis.setStyle(tickFont=font)

                axis.setTextPen(pg.mkPen(color))
                axis.setLabel(name)

                col = plot_item.layout.columnCount()
                plot_item.layout.addItem(axis, 2, col)

                view_box = pg.ViewBox(enableMenu=False)
                view_box.setMouseEnabled(y=False)
                view_box.setBackgroundColor(None)

                plot_widget.scene().addItem(view_box)

                axis.linkToView(view_box)
                view_box.setXLink(base_view)
                view_box.setYRange(min_, max_)

                def make_update(vb):
                    def update():
                        vb.setGeometry(base_view.sceneBoundingRect())

                    return update

                update_fn = make_update(view_box)
                base_view.sigResized.connect(update_fn)
                update_fn()

                curve = pg.PlotCurveItem(
                    pen=pg.mkPen(color, width=2)
                )

                view_box.addItem(curve)

                curve.getViewBox().setXRange(
                    0,
                    graph_x_size + 1,
                    padding=0
                )

                for markers, labels in [
                    (self.peak_markers, self.peak_labels),
                    (self.min_markers, self.min_labels),
                ]:
                    peak_marker = pg.ScatterPlotItem(
                        size=10,
                        brush=pg.mkBrush(color),
                        pen=pg.mkPen("white", width=2)
                    )
                    peak_label = pg.TextItem(
                        "",
                        color=color,
                        anchor=(0.5, 1.5)
                    )
                    q_font = QFont("Arial", 14)
                    q_font.setBold(True)
                    peak_label.setFont(q_font)

                    view_box.addItem(peak_marker)
                    view_box.addItem(peak_label)

                    markers[signal] = peak_marker
                    labels[signal] = peak_label

                self.curves[signal] = curve
                self.buffers[signal] = deque(maxlen=graph_x_size)

    @Slot(dict)
    def process_signals(self, parsed_data):
        for signal in self.labels.keys():
            try:
                data = parsed_data.get(signal)
                if data:
                    self.update_display(signal, data)
            except Exception:
                logger.exception("Erro ao processar sinal %s no dashboard", signal)

        for signal, buff in self.buffers.items():
            data = parsed_data.get(signal)
            if data:
                buff.append(data["value"])

    def update_display(self, signal, data):
        value = data["value"]
        alarm = signal.value["alarm"]
        color = signal.value["color"]

        in_alarm = False
        min_ = alarm["min"] if alarm["min"] is None or isinstance(alarm["min"], (int, float)) else alarm["min"](value)
        max_ = alarm["max"] if alarm["max"] is None or isinstance(alarm["max"], (int, float)) else alarm["max"](value)

        if min_ is not None and value < min_:
            color = "red"
            in_alarm = alarm["enabled"]

        elif max_ is not None and value > max_:
            color = "red"
            in_alarm = alarm["enabled"]

        container, label = self.labels[signal]
        label.setText(data["value_str"])

        firing = vehicle_state.is_alarm_firing(signal)

        if not in_alarm and not firing:
            label.setStyleSheet(f"color:{color};")

    def update_graph(self):
        for signal, curve in self.curves.items():
            data = list(self.buffers[signal])
            curve.setData(data)

            for markers, labels, fn_value in [
                (self.peak_markers, self.peak_labels, max),
                (self.min_markers, self.min_labels, min),
            ]:
                if len(data) > 0:
                    value = fn_value(data)
                    value_index = data.index(value)

                    markers[signal].setData(
                        [value_index],
                        [value],
                    )

                    unit = signal.value['unit']
                    label_text = signal.value["for_label"](value)
                    if unit != "":
                        label_text = f"{label_text} {unit}"

                    labels[signal].setText(label_text)
                    labels[signal].setPos(value_index, value)

                    markers[signal].show()
                    labels[signal].show()

                else:
                    markers[signal].hide()
                    labels[signal].hide()

    @Slot(Signal)
    def fire_field_alarm(self, signal):
        if signal not in self.labels:
            return

        container, label = self.labels[signal]

        def _fn(i):
            def __fn():
                if not vehicle_state.is_alarm_firing(signal):
                    container.setStyleSheet("background-color:black;")
                    return
                QTimer.singleShot(200, _fn(i + 1))
                label.setStyleSheet("color:red;")
                if i % 2 == 0:
                    container.setStyleSheet("background-color:black;")
                else:
                    container.setStyleSheet("background-color:yellow;")

            return __fn

        QTimer.singleShot(0, _fn(0))
