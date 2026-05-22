import logging
import queue
from typing import List, Optional

import serial
from PyQt6.QtCore import pyqtSignal, QThread

from app.master.ecu import EcuCommand, EcuResponse

logger = logging.getLogger(__name__)


class EcuConnection(QThread):
    emitter = pyqtSignal(str)
    map_data_received = pyqtSignal(str)  # raw #I20/#I21/#F01-#F16 lines

    def __init__(self, port, baudrate):
        super().__init__()
        self.serial = serial.Serial(baudrate=baudrate, timeout=1, write_timeout=1)
        self.serial.port = port
        self.running = True
        self.d01 = None
        self.d02 = None
        self._command_queue: queue.Queue = queue.Queue()

    def send_command(self, cmd: EcuCommand, args: list = None) -> None:
        """Queue a command. args (optional list) are appended as ';'-separated values."""
        self._command_queue.put((cmd, args or []))

    def connect(self):
        while self.running:
            try:
                if not self.serial.is_open:
                    logger.info("Tentando conectar...")
                    self.serial.open()
                    logger.info("Conectado.")

                self._start_communication()
                self._start_streaming()
                return
            except Exception as e:
                logger.warning("Falha ao tentar conectar. Erro: %s", e)
                self._close()

    def run(self):
        count_zero = 0

        while self.running:
            if not self.serial.is_open:
                self.connect()

            if count_zero == 3:
                logger.warning("Muitos retornos vazios... Reconectando...")
                count_zero = 0
                self._close()
                continue

            try:
                line = self._readline()
                if len(line) == 0:
                    count_zero += 1
                    continue

                count_zero = 0

                if line.startswith("#D01"):
                    self.d01 = line
                elif line.startswith("#D02"):
                    self.d02 = line
                elif line.startswith(("#I", "#F", "#A")):
                    self.map_data_received.emit(line)

                if self.d01 and self.d02:
                    self.emitter.emit(f'{self.d01};{self.d02}'.strip())
                    self.d01 = None
                    self.d02 = None
                    self._drain_command_queue()

            except Exception as e:
                logger.warning("Conexão perdida. Reconectando... %s", e)
                try:
                    self._close()
                except:
                    pass

    def stop(self):
        self.running = False
        try:
            self._close()
        except:
            pass

    def _drain_command_queue(self):
        while not self._command_queue.empty():
            try:
                cmd, args = self._command_queue.get_nowait()
                if args:
                    cmd_str = f"{cmd.cmd};{';'.join(str(a) for a in args)}"
                    logger.info("Enviando comando: %s [%d valores]", cmd.description, len(args))
                else:
                    cmd_str = cmd.cmd
                    logger.info("Enviando comando: %s", cmd.description)
                self.serial.write(f'{cmd_str}\n'.encode("utf-8"))
            except queue.Empty:
                break

    def _start_streaming(self):
        logger.debug("Iniciando streaming...")
        line = self._send_and_retry(
            EcuCommand.STREAMING_START,
            [
                EcuResponse.MESS_DATA_1,
                EcuResponse.MESS_DATA_2,
                EcuResponse.MESS_DATA_3,
            ]
        )
        if line and len(line) > 0:
            logger.info("Streaming iniciado.")
        else:
            logger.warning("Streaming não iniciado.")

    def _start_communication(self):
        logger.debug("Iniciando comunicação...")
        line = self._send_and_retry(EcuCommand.ECU_INFO, [EcuResponse.ECU_INFO])
        if line and len(line) > 0:
            logger.info("Comunicação iniciada.")
        else:
            logger.warning("Comunicação não iniciada.")

    def _send_and_retry(self, cmd: EcuCommand, expected: List[EcuResponse]) -> Optional[str]:
        count = 0
        while self.running and self.serial.is_open:
            if count % 3 == 0:
                logger.debug("Enviando para ECU \"%s\"", cmd.description)
                self._send_command(cmd)
            count += 1
            line = self._readline()

            for exp in expected:
                if exp.value in line:
                    logger.debug("Dado encontrado: %s", line)
                    return line
            if len(line) > 0:
                logger.debug("Dado não esperado recebido: %s", line)
            else:
                logger.debug("Nenhum dado recebido")
        return None

    def _readline(self) -> str:
        return self.serial.readline().decode("utf-8").strip()

    def _send_command(self, command: EcuCommand) -> None:
        self.serial.write(f'{command.cmd}\n'.encode("utf-8"))

    def _close(self):
        try:
            self.serial.close()
        except:
            pass
        self.d01 = None
        self.d02 = None
