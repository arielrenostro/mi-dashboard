from __future__ import annotations

import logging
import threading
from enum import Enum
from typing import Optional, List

from app.ecu_connection.responses import (
    EcuResponse, EcuInfoResponse, MapBreakpointsResponse, RpmBreakpointsResponse,
    VeRowResponse, StreamingAckResponse, LambdaResponse, LambdaState)
from app.ecu_connection.transport import EcuTransport

logger = logging.getLogger(__name__)


class EcuConnectionStatus(Enum):
    CONNECTED = 0
    DISCONNECTED = 1
    CONNECTING = 2
    HANDSHAKE = 3
    ERROR = 4


class EcuProtocol:
    """
    Knows the ECU protocol. Sits on top of EcuTransport.
    Named methods form the public API; _send_and_wait is the private primitive.
    Read loop and writes are parallel (full-duplex serial).
    """

    def __init__(self, transport: EcuTransport):
        self._transport = transport
        self._running = False
        self._write_lock = threading.Lock()
        self._pending: Optional[tuple] = None  # (prefix, threading.Event, result_list)
        self._status = EcuConnectionStatus.DISCONNECTED

    # ──────────────────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def is_connected(self) -> bool:
        return self._transport.is_open()

    def get_connection_status(self) -> EcuConnectionStatus:
        return self._status

    def run(self) -> None:
        """Main loop — called by EcuConnectionThread.run(). Handles reconnection."""
        while self._running:
            try:
                self._status = EcuConnectionStatus.CONNECTING
                self._transport.open()

                self._status = EcuConnectionStatus.HANDSHAKE
                ack = self._do_handshake()
                if ack is None:
                    logger.warning("Handshake failed, retrying...")
                    self._transport.close()
                    continue

                self._status = EcuConnectionStatus.CONNECTED
                self._publish_handshake_completed(ack)
                self._read_loop()

            except Exception as e:
                logger.warning("ECU connection error: %s — reconnecting", e)
                self._status = EcuConnectionStatus.ERROR
                try:
                    self._transport.close()
                except Exception:
                    pass

    # ──────────────────────────────────────────────────────────────────────────
    # Setup methods (called by VehicleState setup thread)
    # ──────────────────────────────────────────────────────────────────────────

    def fetch_ecu_info(self) -> EcuInfoResponse:
        raw = self._send_and_wait("#D50\n", "#D50")
        response = EcuInfoResponse(raw_values=tuple(raw.split(";")[1:]) if raw else ())
        self._publish_response(response)
        return response

    def fetch_map_breakpoints(self) -> MapBreakpointsResponse:
        raw = self._send_and_wait("#I21\n", "#I21")
        values = self._parse_int_list(raw)
        response = MapBreakpointsResponse(values=tuple(values))
        self._publish_response(response)
        return response

    def fetch_rpm_breakpoints(self) -> RpmBreakpointsResponse:
        raw = self._send_and_wait("#I20\n", "#I20")
        values = self._parse_int_list(raw)
        response = RpmBreakpointsResponse(values=tuple(values))
        self._publish_response(response)
        return response

    def fetch_ve(self) -> List[VeRowResponse]:
        return list([self.fetch_ve_row(row) for row in range(16)])

    def fetch_ve_row(self, row: int) -> VeRowResponse:
        if row < 0 or row > 15:
            raise ValueError(f'Invalid row index: {row}')
        prefix = f"#F{(row + 1):02d}"
        raw = self._send_and_wait(f"{prefix}\n", prefix)
        values = self._parse_int_list(raw)
        response = VeRowResponse(row_index=row, values=tuple(values))
        self._publish_response(response)
        return response

    def start_streaming(self) -> StreamingAckResponse:
        _ = self._send_and_wait("#D01\n", "#D01")
        response = StreamingAckResponse()
        self._publish_response(response)
        return response

    # ──────────────────────────────────────────────────────────────────────────
    # Streaming methods (called by VehicleState during operation)
    # ──────────────────────────────────────────────────────────────────────────

    def set_ve_row(self, row: int, data: list) -> VeRowResponse:
        prefix = f"#F{row:02d}"
        args = ";".join(str(v) for v in data)
        raw = self._send_and_wait(f"{prefix};{args}\n", prefix)
        values = self._parse_int_list(raw)
        response = VeRowResponse(row_index=row, values=tuple(values))
        self._publish_response(response)
        return response

    def open_lambda_loop(self) -> LambdaResponse:
        _ = self._send_and_wait("#D06\n", "#D06")
        response = LambdaResponse(state=LambdaState.OPEN)
        self._publish_response(response)
        return response

    def close_lambda_loop(self) -> LambdaResponse:
        _ = self._send_and_wait("#D05\n", "#D05")
        response = LambdaResponse(state=LambdaState.CLOSED)
        self._publish_response(response)
        return response

    # ──────────────────────────────────────────────────────────────────────────
    # Private
    # ──────────────────────────────────────────────────────────────────────────

    def _do_handshake(self) -> Optional[str]:
        """Synchronous handshake on the ECU thread (read loop not yet running)."""
        count = 0
        while self._running:
            if count % 3 == 0:
                try:
                    self._transport.write("#D50\n".encode("utf-8"))
                except Exception as e:
                    logger.warning("Handshake write error: %s", e)
                    return None
            count += 1
            line = self._transport.read_line()
            if line.startswith("#D50"):
                logger.info("Handshake completed: %s", line)
                return line
            if count > 30:
                return None
        return None

    def _read_loop(self) -> None:
        """Main read loop — runs on the ECU thread while _running is True."""
        empty_count = 0
        while self._running:
            try:
                line = self._transport.read_line()
            except Exception as e:
                logger.warning("Read error: %s", e)
                raise

            if not line:
                empty_count += 1
                if empty_count >= 3:
                    logger.warning("Three consecutive empty reads — reconnecting")
                    raise ConnectionError("Three consecutive empty reads")
                continue
            empty_count = 0

            self._route(line)

    def _route(self, line: str) -> None:
        from app.event.app_events import EcuFrameReceivedEvent, EcuFrameType

        # Pending response takes priority over frame events
        if self._pending is not None:
            prefix, ev, result = self._pending
            if line.startswith(prefix):
                result[0] = line
                self._pending = None
                ev.set()
                return

        # Frame events
        if line.startswith("#D01"):
            from app.event.bus import event_bus
            values = tuple(line.split(";")[1:])
            event_bus.publish(EcuFrameReceivedEvent(frame_type=EcuFrameType.D01, values=values))
        elif line.startswith("#D02"):
            from app.event.bus import event_bus
            values = tuple(line.split(";")[1:])
            event_bus.publish(EcuFrameReceivedEvent(frame_type=EcuFrameType.D02, values=values))
        elif line.startswith("#D03"):
            from app.event.bus import event_bus
            values = tuple(line.split(";")[1:])
            event_bus.publish(EcuFrameReceivedEvent(frame_type=EcuFrameType.D03, values=values))
        else:
            logger.debug("Unrouted ECU line: %s", line[:60])

    def _send_and_wait(self, wire: str, prefix: str, timeout: float = 5.0) -> Optional[str]:
        """
        Acquires write lock, sends command, blocks caller until response arrives
        in the read loop. Write and read are parallel (full-duplex).
        """
        ev = threading.Event()
        result = [None]

        with self._write_lock:
            self._pending = (prefix, ev, result)
            try:
                self._transport.write(wire.encode("utf-8"))
            except Exception as e:
                self._pending = None
                logger.error("Write error in send_and_wait: %s", e)
                return None

        ev.wait(timeout=timeout)

        if result[0] is None:
            logger.warning("send_and_wait timeout for prefix=%s", prefix)
        return result[0]

    def _publish_handshake_completed(self, raw: str) -> None:
        from app.event.app_events import EcuHandshakeCompletedEvent
        from app.event.bus import event_bus
        event_bus.publish(EcuHandshakeCompletedEvent())

    def _publish_response(self, response: EcuResponse) -> None:
        from app.event.app_events import EcuResponseReceivedEvent
        from app.event.bus import event_bus
        event_bus.publish(EcuResponseReceivedEvent(response=response))

    @staticmethod
    def _parse_int_list(raw: Optional[str]) -> list:
        if not raw:
            return []
        try:
            return [int(v) for v in raw.split(";")[1:]]
        except (ValueError, IndexError):
            logger.warning("Failed to parse int list from: %s", raw)
            return []
