import csv
import math
import sys
import time
from collections import deque

import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QGridLayout
)

from serial_reader_mock import SerialReaderMock

PORT = "COM5"
BAUDRATE = 115200
LOG_PREFIX = "#D01"
LOG_FILE = "log_stream.csv"

ALARM_COOLDOWN = 2

SIGNALS = [
    {
        "name": "MAP",
        "index": 2,
        "min": 20,
        "max": 160,
        "func": lambda x: x,
        "labelFunc": lambda x: f'{math.trunc(x)}  kPa',
        "graph": True,
        "alarm": True
    },
    {
        "name": "RPM",
        "index": 1,
        "min": 700,
        "max": 7000,
        "func": lambda x: math.trunc(x),
        "labelFunc": lambda x: f'{x}',
        "graph": False,
        "alarm": False
    },
    {
        "name": "Lambda",
        "index": 6,
        "min": 0,
        "max": 2000,
        "func": lambda x: round(x / 1000, 2),
        "labelFunc": lambda x: f'{x}',
        "graph": False,
        "alarm": False
    },
    {
        "name": "Trim",
        "index": 26,
        "min": -10,
        "max": 10,
        "func": lambda x: round((1000 - x) / 10, 2),
        "labelFunc": lambda x: f'{x} %',
        "graph": False,
        "alarm": False
    },
    {
        "name": "Lambda Target",
        "index": 25,
        "min": 0.6,
        "max": 1.2,
        "func": lambda x: round(x / 1000, 2),
        "labelFunc": lambda x: f'{x}',
        "graph": False,
        "alarm": False
    },
    {
        "name": "Ign",
        "index": 10,
        "min": 0,
        "max": 30,
        "func": lambda x: math.trunc(x),
        "labelFunc": lambda x: f'{x} º',
        "graph": False,
        "alarm": False
    },
]


class Dashboard(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Logger PRO")
        self.showFullScreen()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.grid = QGridLayout()
        self.layout.addLayout(self.grid)

        self.labels = {}
        self.last_alarm_time = {}

        self.row = 0

        for signal in SIGNALS:
            self.create_label(signal["name"])

        # Gráfico
        self.graph = pg.PlotWidget()
        self.layout.addWidget(self.graph)

        self.curves = {}
        self.buffers = {}

        for signal in SIGNALS:
            if signal["graph"]:
                self.curves[signal["name"]] = self.graph.plot()
                self.buffers[signal["name"]] = deque(maxlen=300)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_graph)
        self.timer.start(100)

        # Log
        self.log_file = open(LOG_FILE, "a", newline="")
        self.csv_writer = csv.writer(self.log_file)

    def create_label(self, name):
        label = QLabel(f"{name} --")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        font = QFont("Arial", 56)
        font.setBold(True)
        label.setFont(font)

        label.setStyleSheet("background-color:black; color:white;")

        self.grid.addWidget(label, self.row // 2, self.row % 2)
        self.labels[name] = label
        self.last_alarm_time[name] = 0

        self.row += 1

    def process_line(self, line):
        if not line.startswith(LOG_PREFIX):
            return

        parts = line.split(";")
        if len(parts) < 2:
            return

        # LOG
        timestamp = int(time.time() * 1000)
        self.csv_writer.writerow([timestamp] + parts)
        self.log_file.flush()

        for signal in SIGNALS:

            idx = signal["index"]
            if idx >= len(parts):
                continue

            try:
                raw = float(parts[idx])
                value = signal["func"](raw)
                valueStr = signal["labelFunc"](value)

                self.update_display(signal, value, valueStr)

            except:
                pass

    def update_display(self, signal, value, valueStr):

        name = signal["name"]
        label = self.labels[name]

        label.setText(f"{name} {valueStr}")

        # Cor por faixa
        if value < signal["min"]:
            color = "red"
            self.trigger_alarm(signal)
        elif value > signal["max"]:
            color = "red"
            self.trigger_alarm(signal)
        else:
            color = "lime"

        label.setStyleSheet(
            f"background-color:black; color:{color};"
        )

        if signal["graph"]:
            self.buffers[name].append(value)

    def trigger_alarm(self, signal):
        pass
        # if not signal["alarm"]:
        #     return
        #
        # name = signal["name"]
        # now = time.time()
        #
        # if now - self.last_alarm_time[name] < ALARM_COOLDOWN:
        #     return
        #
        # self.last_alarm_time[name] = now
        #
        # # beep crítico
        # winsound.Beep(2000, 300)

    def update_graph(self):
        for name, curve in self.curves.items():
            curve.setData(list(self.buffers[name]))


# ==========================================
# MAIN
# ==========================================

def main():
    app = QApplication(sys.argv)

    dashboard = Dashboard()

    serial_thread = SerialReaderMock(PORT, BAUDRATE)
    serial_thread.emitter.connect(dashboard.process_line)
    serial_thread.start()

    app.exec()

    serial_thread.stop()


if __name__ == "__main__":
    main()
