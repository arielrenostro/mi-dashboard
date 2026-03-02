import time

import serial
from PyQt6.QtCore import pyqtSignal, QThread


class SerialReader(QThread):
    emitter = pyqtSignal(str)

    def __init__(self, port, baudrate):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True
        self.serial = None
        self.d01 = None
        self.d02 = None

    def connect(self):
        while self.running:
            try:
                print("Tentando conectar...")
                self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
                print("Conectado.")

                self.serial.write(b"#D50\n")
                print(f'Informações da ECU: {self.serial.readline()}')

                while '#D01' not in self.serial.readline():
                    print("Tentando iniciar streaming...")
                    self.serial.write(b"\n")
                    time.sleep(0.5)
                    self.serial.write(b"#D01\n")

                print("Streaming iniciado.")
            except:
                print("Falha. Tentando novamente...")
                time.sleep(3)

    def run(self):
        self.connect()

        while self.running:
            try:
                line = self.serial.readline().decode("utf-8").strip()
                if line.startswith("#D01"):
                    self.d01 = line
                elif line.startswith("#D02"):
                    self.d02 = line

                if self.d01 and self.d02:
                    self.emitter.emit(f'{self.d01};{self.d02}')
                    self.d01 = None
                    self.d02 = None
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
