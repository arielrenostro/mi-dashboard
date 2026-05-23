from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from pyqtgraph.examples.ExampleApp import QFont

from app.masterinjection.signal import Signal


class SignalCard(QWidget):

    def __init__(self, signal: Signal):
        super(SignalCard, self).__init__()

        name = signal.value['name']
        unit = signal.value['unit']
        color = signal.value["color"]

        self.setStyleSheet("background-color:black;")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setContentsMargins(8, 4, 8, 4)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if unit != "":
            self.small_label = QLabel(f"{name} ({unit})")
        else:
            self.small_label = QLabel(f"{name}")
        self.small_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        small_font = QFont("Arial", 14)
        small_font.setBold(True)
        self.small_label.setFont(small_font)
        self.small_label.setStyleSheet("color: gray;")

        self.big_label = QLabel("--")
        self.big_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        big_font = QFont("Arial", 56)
        big_font.setBold(True)
        self.big_label.setFont(big_font)
        self.big_label.setStyleSheet("color: white;")

        layout.addWidget(self.small_label)
        layout.addWidget(self.big_label)

        self.set_text_color(color)

    def set_value(self, value: Any):
        self.big_label.setText(f"{value}")

    def set_text_color(self, color: str):
        self.big_label.setStyleSheet(f"color:{color};")
