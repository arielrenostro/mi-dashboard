from __future__ import annotations

import enum
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from PyQt6.QtCore import QObject, pyqtSignal, Qt, QMetaObject, Q_ARG

from app.ecu.commands import EcuCommand, EcuTimeoutError, ResponseContract
from app.ecu.transport.base import EcuTransport


class EcuConnectionStatus(enum.Enum):
    CONNECTED    = 0
    DISCONNECTED = 1
    CONNECTING   = 2
    HANDSHAKE    = 3
    ERROR        = 4

logger = logging.getLogger(__name__)

_MESS_PREFIXES = ("#D01", "#D02", "#D03")
_HANDSHAKE_TIMEOUT = 5.0
_COMMAND_TIMEOUT = 5.0
_RECONNECT_EMPTY_THRESHOLD = 3
_MAX_HANDSHAKE_RETRIES = 10


@dataclass
class _PendingCommand:
    cmd_str: str
    expected_prefix: str
    event: threading.Event = field(default_factory=threading.Event)
    result_box: list = field(default_factory=list)


class _SessionQObject(QObject):
    """Qt object that lives on main thread — used for queued bus publications."""
    _publish_mess_frame = pyqtSignal(str, str)
    _publish_cmd_send   = pyqtSignal(str, object)
    _publish_cmd_resp   = pyqtSignal(str, str)


class EcuSession:

    def __init__(self, transport: EcuTransport):
        self._transport = transport
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._write_queue: queue.Queue[_PendingCommand] = queue.Queue()
        self._pending: Optional[_PendingCommand] = None
        self._pending_lock = threading.Lock()
        self._status = EcuConnectionStatus.DISCONNECTED
        self._qt = _SessionQObject()
        self._qt._publish_mess_frame.connect(self._on_publish_mess_frame, Qt.ConnectionType.QueuedConnection)
        self._qt._publish_cmd_send.connect(self._on_publish_cmd_send, Qt.ConnectionType.QueuedConnection)
        self._qt._publish_cmd_resp.connect(self._on_publish_cmd_resp, Qt.ConnectionType.QueuedConnection)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, name="EcuSessionIO", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        try:
            self._transport.close()
        except Exception:
            pass

    def is_connected(self) -> bool:
        return self._transport.is_open()

    def get_connection_status(self) -> EcuConnectionStatus:
        return self._status

    # ------------------------------------------------------------------ #
    # High-level command API
    # ------------------------------------------------------------------ #

    def send_command(self, cmd: EcuCommand, args: Any = None) -> str:
        """Enqueue a command and block until response received. Returns raw response line."""
        arg_list = args if isinstance(args, list) else (list(args) if args else [])
        if arg_list:
            cmd_str = f"{cmd.cmd};{';'.join(str(a) for a in arg_list)}"
        else:
            cmd_str = cmd.cmd

        expected_prefix = cmd.cmd  # response always starts with same code

        pending = _PendingCommand(cmd_str=cmd_str, expected_prefix=expected_prefix)
        self._write_queue.put(pending)
        self._qt._publish_cmd_send.emit(cmd.cmd, args)

        if not pending.event.wait(timeout=_COMMAND_TIMEOUT):
            raise EcuTimeoutError(f"Timeout aguardando resposta para {cmd.cmd}")
        return pending.result_box[0]

    def open_loop(self) -> None:
        self.send_command(EcuCommand.LAMBDA_LOOP_OPEN)

    def close_loop(self) -> None:
        self.send_command(EcuCommand.LAMBDA_LOOP_CLOSE)

    def fetch_breakpoints(self) -> tuple[list[int], list[int]]:
        """Returns (map_bp, rpm_bp)."""
        map_resp = self.send_command(EcuCommand.MAP_BREAKPOINTS)
        rpm_resp = self.send_command(EcuCommand.RPM_BREAKPOINTS)
        map_bp = [int(v) for v in map_resp.split(";")[1:]]
        rpm_bp = [int(v) for v in rpm_resp.split(";")[1:]]
        return map_bp, rpm_bp

    def fetch_ve_map(self) -> list[list[int]]:
        ve_map = [[0] * 16 for _ in range(16)]
        for i in range(1, 17):
            cmd = EcuCommand[f"VE_ROW_{i}"]
            resp = self.send_command(cmd)
            values = [int(v) for v in resp.split(";")[1:]]
            ve_map[i - 1] = values
        return ve_map

    def set_ve_row(self, row: int, values: list) -> None:
        """row is 0-based; sends VE_ROW_{row+1}."""
        cmd = EcuCommand[f"VE_ROW_{row + 1}"]
        self.send_command(cmd, values)

    # ------------------------------------------------------------------ #
    # I/O thread
    # ------------------------------------------------------------------ #

    def _run(self) -> None:
        while self._running:
            try:
                self._connect_and_run()
            except Exception:
                logger.exception("Erro na sessão ECU — reconectando em 1s")
                try:
                    self._transport.close()
                except Exception:
                    pass
                time.sleep(1.0)

    def _connect_and_run(self) -> None:
        self._status = EcuConnectionStatus.CONNECTING
        self._transport.open()
        logger.info("Transport aberto — iniciando handshake")

        self._status = EcuConnectionStatus.HANDSHAKE
        if not self._handshake():
            logger.warning("Handshake falhou — fechando transport")
            self._status = EcuConnectionStatus.ERROR
            self._transport.close()
            self._status = EcuConnectionStatus.DISCONNECTED
            return

        self._status = EcuConnectionStatus.CONNECTED
        logger.info("Handshake OK — iniciando read loop")
        self._read_loop()
        self._status = EcuConnectionStatus.DISCONNECTED

    def _handshake(self) -> bool:
        # Step 1: ECU_INFO
        if not self._send_and_wait_prefix(EcuCommand.ECU_INFO.cmd, EcuCommand.ECU_INFO.cmd):
            return False
        # Step 2: STREAMING_START
        if not self._send_and_wait_prefix(EcuCommand.STREAMING_START.cmd, ("#D01", "#D02", "#D03")):
            # Try to fetch breakpoints and VE map before streaming
            pass
        self._init_vehicle_data()
        return True

    def _init_vehicle_data(self) -> None:
        """Fetch breakpoints and VE map during handshake (non-blocking variant)."""
        try:
            map_resp = self._send_and_receive(EcuCommand.MAP_BREAKPOINTS.cmd, EcuCommand.MAP_BREAKPOINTS.cmd)
            rpm_resp = self._send_and_receive(EcuCommand.RPM_BREAKPOINTS.cmd, EcuCommand.RPM_BREAKPOINTS.cmd)
            if map_resp and rpm_resp:
                from app.state.state import vehicle_state
                vehicle_state.set_map_breakpoints([int(v) for v in map_resp.split(";")[1:]])
                vehicle_state.set_rpm_breakpoints([int(v) for v in rpm_resp.split(";")[1:]])
                logger.info("Breakpoints carregados")

            for i in range(1, 17):
                cmd = EcuCommand[f"VE_ROW_{i}"]
                resp = self._send_and_receive(cmd.cmd, cmd.cmd)
                if resp:
                    values = [int(v) for v in resp.split(";")[1:]]
                    vehicle_state.set_ve_map(values, i - 1)
            logger.info("VE map carregado")
        except Exception:
            logger.exception("Erro ao inicializar dados do veículo")

        # Now start streaming
        self._send_and_wait_prefix(EcuCommand.STREAMING_START.cmd, ("#D01", "#D02", "#D03"))

    def _send_and_wait_prefix(self, cmd_str: str, expected, retries: int = _MAX_HANDSHAKE_RETRIES) -> bool:
        if isinstance(expected, str):
            expected = (expected,)
        for attempt in range(retries):
            if not self._running:
                return False
            self._transport.write_line(cmd_str)
            logger.debug("Handshake enviado: %s (tentativa %d)", cmd_str, attempt + 1)
            deadline = time.monotonic() + _HANDSHAKE_TIMEOUT / retries
            while time.monotonic() < deadline and self._running:
                line = self._transport.read_line()
                if not line:
                    continue
                for prefix in expected:
                    if line.startswith(prefix):
                        logger.debug("Handshake resposta recebida: %s", line)
                        return True
        logger.warning("Handshake sem resposta após %d tentativas: %s", retries, cmd_str)
        return False

    def _send_and_receive(self, cmd_str: str, expected_prefix: str, retries: int = _MAX_HANDSHAKE_RETRIES) -> Optional[str]:
        for attempt in range(retries):
            if not self._running:
                return None
            self._transport.write_line(cmd_str)
            deadline = time.monotonic() + _HANDSHAKE_TIMEOUT / retries
            while time.monotonic() < deadline and self._running:
                line = self._transport.read_line()
                if line and line.startswith(expected_prefix):
                    return line
        return None

    def _read_loop(self) -> None:
        empty_count = 0
        while self._running:
            # Drain write queue first
            self._drain_write_queue()

            line = self._transport.read_line()

            if not line:
                empty_count += 1
                if empty_count >= _RECONNECT_EMPTY_THRESHOLD:
                    logger.warning("3 reads vazios consecutivos — reconectando")
                    self._transport.close()
                    empty_count = 0
                    return
                continue

            empty_count = 0

            # Check if this is a MESS_FRAME
            frame_type = None
            for prefix in _MESS_PREFIXES:
                if line.startswith(prefix):
                    frame_type = prefix[1:]  # "D01", "D02", "D03"
                    break

            if frame_type:
                self._qt._publish_mess_frame.emit(frame_type, line)
                continue

            # Try to match pending command response
            with self._pending_lock:
                pending = self._pending
                if pending and line.startswith(pending.expected_prefix):
                    pending.result_box.append(line)
                    pending.event.set()
                    self._pending = None
                    self._qt._publish_cmd_resp.emit(pending.expected_prefix, line)
                    continue

            logger.debug("Linha não classificada: %s", line)

    def _drain_write_queue(self) -> None:
        with self._pending_lock:
            if self._pending is not None:
                return  # Still waiting for a response
            try:
                cmd = self._write_queue.get_nowait()
            except queue.Empty:
                return
            self._pending = cmd
            try:
                self._transport.write_line(cmd.cmd_str)
                logger.debug("Enviado: %s", cmd.cmd_str)
            except Exception as e:
                logger.warning("Erro ao enviar comando: %s", e)
                cmd.result_box.append("")
                cmd.event.set()
                self._pending = None

    # ------------------------------------------------------------------ #
    # Queued-connection bus publications (execute on main thread)
    # ------------------------------------------------------------------ #

    def _on_publish_mess_frame(self, frame_type: str, line: str) -> None:
        from app.event.bus import event_bus
        from app.event.app_events import EcuMessFrameEvent
        event_bus.publish(EcuMessFrameEvent(frame_type=frame_type, line=line))

    def _on_publish_cmd_send(self, cmd: str, args: object) -> None:
        from app.event.bus import event_bus
        from app.event.app_events import EcuCommandSendEvent
        event_bus.publish(EcuCommandSendEvent(cmd=cmd, args=args))

    def _on_publish_cmd_resp(self, cmd: str, response_line: str) -> None:
        from app.event.bus import event_bus
        from app.event.app_events import EcuCommandResponseEvent
        event_bus.publish(EcuCommandResponseEvent(cmd=cmd, response_line=response_line))
