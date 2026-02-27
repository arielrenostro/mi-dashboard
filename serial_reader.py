import threading
import time

import serial


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
