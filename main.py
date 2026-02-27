import sys
import serial
import threading
import time
import csv
import winsound
from collections import deque

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

import pyqtgraph as pg


# ==========================================
# CONFIGURAÇÃO INTERNA (HARDCODED)
# ==========================================

PORT = "COM5"
BAUDRATE = 115200
LOG_PREFIX = "DR"
LOG_FILE = "log_stream.csv"

ALARM_COOLDOWN = 2  # segundos entre alarmes

SIGNALS = [
    {
        "name": "MAP",
        "index": 2,
        "min": 20,
        "max": 110,
        "func": lambda x: x,
        "graph": True,
        "alarm": True
    },
    {
        "name": "RPM",
        "index": 1,
        "min": 700,
        "max": 7000,
        "func": lambda x: x,
        "graph": False,
        "alarm": False
    },
]


# ==========================================
# Serial com reconexão automática
# ==========================================

class SerialReader(threading.Thread):

    def __init__(self, port, baudrate, callback):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.callback = callback
        self.running = True
        self.serial = None

    def connect(self):
        while self.running:
            try:
                print("Tentando conectar...")
                self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
                self.serial.write(b"DR1\n")
                print("Conectado.")
                return
            except:
                print("Falha. Tentando novamente...")
                time.sleep(3)

    def run(self):
        self.connect()

        while self.running:
            try:
                line = self.serial.readline().decode("utf-8").strip()
                if line:
                    self.callback(line)
            except:
                print("Conexão perdida. Reconectando...")
                try:
                    self.serial.close()
                except:
                    pass
                self.connect()

    def stop(self):
        self.running = False
        try:
            self.serial.close()
        except:
            pass


# ==========================================
# GUI Principal
# ==========================================

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

        # Criar labels automaticamente a partir do SIGNALS
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
        self.timer.start(50)

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

    # ==========================================
    # Processamento de dados
    # ==========================================

    def process_line(self, line):

        parts = line.split(",")

        if len(parts) < 2:
            return

        # LOG
        if parts[0].startswith(LOG_PREFIX):
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

                self.update_display(signal, value)

            except:
                pass

    def update_display(self, signal, value):

        name = signal["name"]
        label = self.labels[name]

        label.setText(f"{name} {round(value,2)}")

        # Cor por faixa
        if value < signal["min"]:
            color = "blue"
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

    # ==========================================
    # Alarme sonoro
    # ==========================================

    def trigger_alarm(self, signal):

        if not signal["alarm"]:
            return

        name = signal["name"]
        now = time.time()

        if now - self.last_alarm_time[name] < ALARM_COOLDOWN:
            return

        self.last_alarm_time[name] = now

        # beep crítico
        winsound.Beep(2000, 300)

    # ==========================================
    # Atualização gráfico
    # ==========================================

    def update_graph(self):
        for name, curve in self.curves.items():
            curve.setData(list(self.buffers[name]))


# ==========================================
# MAIN
# ==========================================

def main():
    app = QApplication(sys.argv)

    dashboard = Dashboard()

    serial_thread = SerialReader(PORT, BAUDRATE, dashboard.process_line)
    serial_thread.start()

    app.exec()

    serial_thread.stop()


if __name__ == "__main__":
    main()
