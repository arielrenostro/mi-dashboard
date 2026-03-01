from collections import deque

import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout
)

from app.dashboard.grid import GRID, GRAPH, SIGNALS_VIEW
from app.master.log import LOG_PREFIX
from app.master.signals import SIGNALS


class Dashboard(QWidget):

    def __init__(self, alarm_worker):
        super().__init__()

        self.setWindowTitle("Master Injection Dashboard")
        self.showFullScreen()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.grid = QGridLayout()
        self.layout.addLayout(self.grid)

        self.labels = {}
        self.create_grid()

        self.curves = {}
        self.buffers = {}

        for row in GRAPH:
            graph = pg.PlotWidget()
            self.layout.addWidget(graph)

            plot_item = graph.getPlotItem()
            base_view = plot_item.getViewBox()
            base_view.setBackgroundColor(None)
            base_view.setMouseEnabled(y=False)
            base_view.setZValue(-100)

            for signal_id in row:
                view_cfg = SIGNALS_VIEW[signal_id]

                axis = pg.AxisItem("left")
                plot_item.layout.addItem(
                    axis,
                    2,
                    plot_item.layout.columnCount()
                )

                view_box = pg.ViewBox(enableMenu=False)
                view_box.setBackgroundColor(None)
                view_box.setMouseEnabled(y=False)
                view_box.setZValue(-100)
                graph.scene().addItem(view_box)

                axis.linkToView(view_box)
                # view_box.setXLink(base_view)

                view_box.setYRange(view_cfg["min"], view_cfg["max"])

                curve = pg.PlotCurveItem(pen=view_cfg["color"])
                view_box.addItem(curve)

                self.curves[signal_id] = curve
                self.buffers[signal_id] = deque(maxlen=300)

        # for row in GRAPH:
        #     graph = pg.PlotWidget()
        #     self.layout.addWidget(graph)
        #
        #     for signal_id in row:
        #         view = SIGNALS_VIEW[signal_id]
        #         plot = graph.plot()
        #         self.curves[signal_id] = plot
        #         self.buffers[signal_id] = deque(maxlen=300)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_graph)
        self.timer.start(100)

        self.alarm_worker = alarm_worker

    def create_grid(self):
        for row_idx in range(len(GRID)):
            for col_idx in range(len(GRID[row_idx])):
                signal_id = GRID[row_idx][col_idx]
                signal = SIGNALS[signal_id]
                name = signal['name']

                label = QLabel(f"{name} --")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)

                font = QFont("Arial", 56)
                font.setBold(True)
                label.setFont(font)

                label.setStyleSheet("background-color:black; color:white;")

                self.grid.addWidget(label, row_idx, col_idx)
                self.labels[signal_id] = label

    def process_line(self, line):
        if not line.startswith(LOG_PREFIX):
            return

        parts = line.split(";")
        if len(parts) < 2:
            return

        parsed_data = {}
        for signal_id, signal in SIGNALS.items():
            idx = signal["index"]
            if idx >= len(parts):
                continue

            raw = parts[idx]
            value = signal["converter"](raw)
            value_str = signal["label_value"](value)

            parsed_data[signal_id] = {
                "signal": signal,
                "view": SIGNALS_VIEW.get(signal_id),
                "raw": raw,
                "value": value,
                "value_str": value_str,
            }

        self.alarm_worker.notify_data_received()

        for row in GRID:
            for signal_id in row:
                data = parsed_data[signal_id]
                try:
                    self.update_display(signal_id, data)
                except:
                    pass

        for row in GRAPH:
            for signal_id in row:
                data = parsed_data[signal_id]
                self.buffers[signal_id].append(data["value"])

    def update_display(self, signal_id, data):
        value = data["value"]
        view = data["view"]

        in_alarm = False
        color = view["color"]
        min_ = view["min"] if isinstance(view["min"], (int, float)) else view["min"](value)
        max_ = view["max"] if isinstance(view["max"], (int, float)) else view["max"](value)

        if value < min_:
            color = "red"
            in_alarm = view["alarm"]
        elif value > max_:
            color = "red"
            in_alarm = view["alarm"]

        label = self.labels[signal_id]
        label.setText(f"{data["signal"]["name"]} {data["value_str"]}")
        label.setStyleSheet(
            f"background-color:black; color:{color};"
        )

        self.alarm_worker.set_alarm_state(in_alarm)

    def update_graph(self):
        for signal_id, curve in self.curves.items():
            curve.setData(list(self.buffers[signal_id]))
