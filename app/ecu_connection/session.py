import enum
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from app.ecu_connection.transport import EcuTransport
from app.masterinjection.protocol import EcuCommand

logger = logging.getLogger(__name__)


class EcuConnectionStatus(enum.Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING   = "CONNECTING"
    CONNECTED    = "CONNECTED"


@dataclass
class _PendingCommand:
    cmd: EcuCommand
    args: list | None
    blocking: bool
    event: threading.Event | None      # None para fire-and-forget
    response: list = field(default_factory=list)  # [str] — preenchido pelo Reader
    expected_prefix: str | None = None


class EcuSession:
    """Gerencia toda a comunicação com a ECU.

    Handshake síncrono → Reader thread → publicação de eventos no bus.
    """

    def __init__(self, transport: EcuTransport) -> None:
        self._transport = transport
        self._status = EcuConnectionStatus.DISCONNECTED
        self._command_queue: queue.Queue[_PendingCommand] = queue.Queue()
        self._reader_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pending_blocking: _PendingCommand | None = None
        self._blocking_lock = threading.Lock()

    def start(self) -> None:
        """Conecta, executa handshake e inicia a Reader thread."""
        logger.info("EcuSession: iniciando")
        self._stop_event.clear()
        self._publish_status(EcuConnectionStatus.CONNECTING)

        try:
            self._transport.connect()
            self._do_handshake()
        except Exception as e:
            logger.error("EcuSession: falha no handshake: %s", e)
            self._publish_status(EcuConnectionStatus.DISCONNECTED)
            return

        self._reader_thread = threading.Thread(target=self._reader_loop, name="EcuReaderThread", daemon=True)
        self._reader_thread.start()
        self._publish_status(EcuConnectionStatus.CONNECTED)
        logger.info("EcuSession: conectado e streaming iniciado")

    def stop(self) -> None:
        """Para a Reader thread e fecha o transporte."""
        logger.info("EcuSession: parando")
        self._stop_event.set()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=5.0)
            self._reader_thread = None
        try:
            self._transport.disconnect()
        except Exception as e:
            logger.warning("EcuSession: erro ao desconectar: %s", e)
        self._publish_status(EcuConnectionStatus.DISCONNECTED)

    def get_status(self) -> EcuConnectionStatus:
        return self._status

    def send_command(
        self,
        cmd: EcuCommand,
        args: list | None = None,
        blocking: bool = False,
    ) -> str | None:
        """Envia comando à ECU.

        blocking=False: enfileira e retorna None imediatamente.
        blocking=True: aguarda resposta com timeout de 3s (1 retry).
        """
        if blocking:
            return self._send_blocking(cmd, args)
        else:
            pending = _PendingCommand(cmd=cmd, args=args, blocking=False, event=None)
            self._command_queue.put(pending)
            return None

    # ── Métodos semânticos ────────────────────────────────────────────────────

    def open_loop(self) -> None:
        self.send_command(EcuCommand.LAMBDA_LOOP_OPEN)

    def close_loop(self) -> None:
        self.send_command(EcuCommand.LAMBDA_LOOP_CLOSE)

    def fetch_ve(self) -> None:
        for i in range(1, 17):
            cmd = EcuCommand[f"VE_ROW_{i}"]
            response = self._send_blocking(cmd, None)
            if response:
                self._parse_ve_response(cmd, response)

    def fetch_breakpoints(self) -> None:
        r = self._send_blocking(EcuCommand.RPM_BREAKPOINTS, None)
        if r:
            from app.state.state import vehicle_state
            vehicle_state.set_rpm_breakpoints(self._parse_breakpoints(r))

        r = self._send_blocking(EcuCommand.MAP_BREAKPOINTS, None)
        if r:
            from app.state.state import vehicle_state
            vehicle_state.set_map_breakpoints(self._parse_breakpoints(r))

    # ── Internos ─────────────────────────────────────────────────────────────

    def _send_blocking(self, cmd: EcuCommand, args: list | None) -> str | None:
        """Envia comando bloqueante via Event — requer Reader thread ativa."""
        for attempt in range(2):
            evt = threading.Event()
            expected = cmd.cmd  # ex: "#I20"
            pending = _PendingCommand(
                cmd=cmd,
                args=args,
                blocking=True,
                event=evt,
                expected_prefix=expected,
            )
            with self._blocking_lock:
                self._pending_blocking = pending

            self._write_command(cmd, args)

            if evt.wait(timeout=3.0):
                with self._blocking_lock:
                    self._pending_blocking = None
                return pending.response[0] if pending.response else None
            else:
                logger.warning(
                    "EcuSession: timeout aguardando resposta para %s (tentativa %d/2)",
                    cmd.description, attempt + 1
                )
                with self._blocking_lock:
                    self._pending_blocking = None

        return None

    def _send_blocking_direct(self, cmd: EcuCommand, args: list | None) -> str | None:
        """Envia comando e lê resposta direto do transporte (sem Event/Reader thread).

        Usado durante handshake (antes da Reader thread iniciar) e em reconexão
        (onde a própria Reader thread pode chamar readline diretamente).
        """
        expected = cmd.cmd
        for attempt in range(2):
            self._write_command(cmd, args)
            deadline = time.time() + 3.0
            while time.time() < deadline:
                try:
                    line = self._transport.readline()
                except Exception as e:
                    logger.warning("EcuSession: erro na leitura direta: %s", e)
                    break
                if line and line.startswith(expected):
                    return line
            logger.warning(
                "EcuSession: timeout direto aguardando resposta para %s (tentativa %d/2)",
                cmd.description, attempt + 1,
            )
        return None

    def _write_command(self, cmd: EcuCommand, args: list | None) -> None:
        """Escreve um comando diretamente no transporte."""
        if args:
            cmd_str = f"{cmd.cmd};{';'.join(str(a) for a in args)}"
        else:
            cmd_str = cmd.cmd
        try:
            self._transport.write(cmd_str)
            logger.debug("EcuSession: enviado: %s", cmd_str)
        except Exception as e:
            logger.warning("EcuSession: erro ao enviar comando: %s", e)

    def _do_handshake(self) -> None:
        """Sequência de handshake: D50 → breakpoints → VE map → D01.

        Usa _send_blocking_direct() para ler do transporte sem Reader thread.
        Pode ser chamado antes do Reader thread iniciar (start) ou de dentro
        dele (reconnect) — em ambos os casos é seguro fazer readline direto.
        """
        logger.info("EcuSession: iniciando handshake")

        r = self._send_blocking_direct(EcuCommand.ECU_INFO, None)
        if r:
            logger.info("EcuSession: ECU info: %s", r)
        else:
            logger.warning("EcuSession: sem resposta ao ECU_INFO, continuando")

        # Breakpoints
        r = self._send_blocking_direct(EcuCommand.RPM_BREAKPOINTS, None)
        if r:
            from app.state.state import vehicle_state
            vehicle_state.set_rpm_breakpoints(self._parse_breakpoints(r))

        r = self._send_blocking_direct(EcuCommand.MAP_BREAKPOINTS, None)
        if r:
            from app.state.state import vehicle_state
            vehicle_state.set_map_breakpoints(self._parse_breakpoints(r))

        # VE map
        for i in range(1, 17):
            cmd = EcuCommand[f"VE_ROW_{i}"]
            response = self._send_blocking_direct(cmd, None)
            if response:
                self._parse_ve_response(cmd, response)

        # Iniciar streaming
        r = self._send_blocking_direct(EcuCommand.STREAMING_START, None)
        if r:
            logger.info("EcuSession: streaming confirmado: %s", r)
        else:
            logger.warning("EcuSession: streaming sem confirmação, continuando")

        logger.info("EcuSession: handshake concluído")

    def _reader_loop(self) -> None:
        """Loop de leitura contínua — executa em thread dedicada."""
        zero_count = 0

        while not self._stop_event.is_set():
            try:
                line = self._transport.readline()
            except Exception as e:
                logger.warning("EcuSession: erro na leitura: %s", e)
                self._reconnect()
                continue

            if not line:
                zero_count += 1
                if zero_count >= 3:
                    logger.warning("EcuSession: muitas leituras vazias, reconectando")
                    self._reconnect()
                    zero_count = 0
                continue

            zero_count = 0

            # Classificar linha
            if line.startswith(("#D01", "#D02", "#D03")):
                self._publish_frame(line)
                self._drain_command_queue()
            else:
                # Verificar se é resposta para comando blocking pendente
                with self._blocking_lock:
                    pb = self._pending_blocking
                    if pb is not None and pb.expected_prefix and line.startswith(pb.expected_prefix):
                        pb.response.append(line)
                        pb.event.set()

                self._publish_response(line)

    def _reconnect(self) -> None:
        """Fecha, aguarda 1s, reabre transporte e refaz handshake."""
        if self._stop_event.is_set():
            return

        logger.info("EcuSession: reconectando")
        self._publish_status(EcuConnectionStatus.DISCONNECTED)

        try:
            self._transport.disconnect()
        except Exception:
            pass

        time.sleep(1.0)

        if self._stop_event.is_set():
            return

        try:
            self._transport.connect()
            self._do_handshake()
            self._publish_status(EcuConnectionStatus.CONNECTED)
            logger.info("EcuSession: reconectado")
        except Exception as e:
            logger.error("EcuSession: falha na reconexão: %s", e)

    def _drain_command_queue(self) -> None:
        """Drena a fila de comandos fire-and-forget após cada frame."""
        while not self._command_queue.empty():
            try:
                pending = self._command_queue.get_nowait()
                self._write_command(pending.cmd, pending.args)
            except queue.Empty:
                break

    def _parse_breakpoints(self, line: str) -> list[int]:
        """Parseia linha de breakpoints: '#I20;v1;v2;...;v16'"""
        parts = line.split(";")
        try:
            return [int(p) for p in parts[1:17]]
        except (ValueError, IndexError) as e:
            logger.warning("EcuSession: erro ao parsear breakpoints: %s", e)
            return []

    def _parse_ve_response(self, cmd: EcuCommand, line: str) -> None:
        """Parseia resposta VE e atualiza vehicle_state."""
        parts = line.split(";")
        try:
            values = [int(p) for p in parts[1:17]]
            # "#F01" → row_idx=0, "#F16" → row_idx=15
            row_str = cmd.cmd[2:4]   # "#F01" → "01"
            row_idx = int(row_str) - 1
            from app.state.state import vehicle_state
            vehicle_state.set_ve_map(values, row_idx)
            logger.debug("EcuSession: VE row %d carregada", row_idx)
        except Exception as e:
            logger.warning("EcuSession: erro ao parsear VE row: %s", e)

    def _publish_frame(self, line: str) -> None:
        """Publica EcuMessFrameEvent no bus."""
        from app.event.bus import event_bus
        from app.event.app_events import EcuMessFrameEvent
        # frame_id: "#D01" → "D01"
        frame_id = line[1:4]
        event_bus.publish(EcuMessFrameEvent(frame_id=frame_id, line=line))

    def _publish_response(self, line: str) -> None:
        """Publica EcuCommandResponseEvent no bus."""
        from app.event.bus import event_bus
        from app.event.app_events import EcuCommandResponseEvent
        event_bus.publish(EcuCommandResponseEvent(line=line))

    def _publish_status(self, status: EcuConnectionStatus) -> None:
        """Publica EcuConnectionStatusChangedEvent no bus."""
        self._status = status
        try:
            from app.event.bus import event_bus
            from app.event.app_events import EcuConnectionStatusChangedEvent
            event_bus.publish(EcuConnectionStatusChangedEvent(status=status))
        except Exception as e:
            logger.debug("EcuSession: erro ao publicar status: %s", e)
