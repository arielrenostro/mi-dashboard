import logging
from collections import deque
from typing import Dict

import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QVBoxLayout, QGridLayout
)
from pyqtgraph.Qt.QtCore import Slot

from app.event.app_events import AppEventType
from app.masterinjection.signal import Signal, ParsedSignal
from app.state.state import vehicle_state
from app.ui.base.screen import Screen
from app.ui.components.signal_card import SignalCard

logger = logging.getLogger(__name__)


class DashboardScreen(Screen):

    def __init__(self, close_fn, grid, graphs, graph_x_size):
        super().__init__(close_fn)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)
        self.setLayout(self.layout)

        self.grid = QGridLayout()
        self.grid.setSpacing(4)
        self.layout.addLayout(self.grid)

        self.labels: Dict[Signal, SignalCard] = {}
        self._create_grid(grid)

        self.curves = {}
        self.buffers = {}
        self.peak_markers = {}
        self.peak_labels = {}
        self.min_markers = {}
        self.min_labels = {}
        self._create_graphs(graphs, graph_x_size)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_graph)

    def on_activated(self):
        self.timer.start(100)
        self._subscribe(AppEventType.SIGNALS_RECEIVED, lambda e: self.on_signal_received(e.data))
        self._subscribe(AppEventType.ALARM_FIRED, lambda e: self.fire_field_alarm(e.signal))

    def on_deactivated(self):
        self.timer.stop()
        super().on_deactivated()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.close_fn()

    def _create_grid(self, grid):
        for row_idx in range(len(grid)):
            for col_idx in range(len(grid[row_idx])):
                signal = Signal[grid[row_idx][col_idx]]
                card = SignalCard(signal)

                self.grid.addWidget(card, row_idx, col_idx)
                self.labels[signal] = card

    def _create_graphs(self, graphs, graph_x_size):
        for row in graphs:
            plot_widget = pg.PlotWidget()
            self.layout.addWidget(plot_widget)

            plot_item = plot_widget.getPlotItem()
            base_view = plot_item.getViewBox()
            base_view.setMouseEnabled(x=False, y=True)
            plot_item.hideAxis("left")
            plot_item.hideAxis("bottom")

            for signal in row:
                signal = Signal[signal]
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
    def on_signal_received(self, parsed_data: Dict[Signal, ParsedSignal]):
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
                buff.append(data.value)

    def update_display(self, signal: Signal, data: ParsedSignal):
        value = data.value
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

        card = self.labels[signal]
        card.set_value(data.value_str)

        firing = vehicle_state.is_alarm_firing(signal)

        if not in_alarm and not firing:
            card.set_text_color(color)

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

        card = self.labels[signal]

        def _fn(i):
            def __fn():
                if not vehicle_state.is_alarm_firing(signal):
                    card.setStyleSheet("background-color:black;")
                    return
                QTimer.singleShot(200, _fn(i + 1))
                card.set_text_color("red")
                if i % 2 == 0:
                    card.setStyleSheet("background-color:black;")
                else:
                    card.setStyleSheet("background-color:yellow;")

            return __fn

        QTimer.singleShot(0, _fn(0))
