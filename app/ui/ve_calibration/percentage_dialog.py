from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QDoubleValidator
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton


class PercentageDialog(QDialog):
    """Modal dialog that asks the user for a VE increment percentage."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Incrementar VE")
        self.setModal(True)
        self.setFixedSize(360, 160)
        self.setStyleSheet(
            "QDialog { background-color: #111111; border: 1px solid #444444; }"
            "QLabel { color: #FFFFFF; }"
            "QLineEdit {"
            "  background-color: #1A1A1A;"
            "  color: #FFFFFF;"
            "  border: 1px solid #555555;"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 18px;"
            "}"
            "QPushButton {"
            "  background-color: #222222;"
            "  color: #CCCCCC;"
            "  border: 1px solid #444444;"
            "  border-radius: 4px;"
            "  padding: 4px 12px;"
            "}"
            "QPushButton:hover { background-color: #333333; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        label_font = QFont("Arial", 13)
        label = QLabel("Incrementar VE nas células do cursor (%):")
        label.setFont(label_font)
        layout.addWidget(label)

        self._input = QLineEdit()
        self._input.setFont(QFont("Arial", 18))
        self._input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._input.setPlaceholderText("ex: 5 ou -3.5")
        validator = QDoubleValidator(-100.0, 100.0, 2, self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self._input.setValidator(validator)
        self._input.returnPressed.connect(self._on_confirm)
        layout.addWidget(self._input)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_cancel = QPushButton("Cancelar  [ESC]")
        btn_cancel.setFont(QFont("Arial", 11))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_ok = QPushButton("Confirmar  [Enter]")
        btn_ok.setFont(QFont("Arial", 11))
        btn_ok.setStyleSheet(
            "QPushButton { background-color: #1A3A1A; color: #00FF88; border: 1px solid #005522; }"
            "QPushButton:hover { background-color: #254025; }"
        )
        btn_ok.clicked.connect(self._on_confirm)
        btn_layout.addWidget(btn_ok)

        layout.addLayout(btn_layout)

        self._value: float = 0.0
        self._input.setFocus()

    def _on_confirm(self):
        text = self._input.text().replace(",", ".")
        try:
            self._value = float(text)
            self.accept()
        except ValueError:
            self._input.setStyleSheet(
                "QLineEdit { background-color: #3A1A1A; color: #FF6666; border: 1px solid #882222; }"
            )

    def value(self) -> float:
        return self._value
