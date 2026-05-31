import logging
import threading
import time
from typing import Optional, Dict

from PyQt6.QtCore import QObject, pyqtSignal

from app.ecu_connection.responses import (
    MapBreakpointsResponse, RpmBreakpointsResponse, VeRowResponse,
    LambdaResponse, LambdaState,
)
from app.event.app_events import (
    AppEventType, EcuHandshakeCompletedEvent, EcuResponseReceivedEvent,
    EcuFrameReceivedEvent,
)
from app.event.bus import event_bus
from app.masterinjection.signal import ParsedSignal, Signal
from app.state.event import VehicleStateChangeEvent, EventType

logger = logging.getLogger(__name__)

ALARM_DURATION = 2
DECEL_MAP_THRESHOLD = 20


class _VehicleStateEmitter(QObject):
    signal = pyqtSignal(VehicleStateChangeEvent)


class VehicleState:

    def __init__(self):
        self._emitter: Optional[_VehicleStateEmitter] = None
        self._lock = threading.RLock()
        self._signals: Dict[Signal, ParsedSignal] = {}
        self._alarm_timestamps: dict = {}
        self._lambda_loop_closed: bool = False
        self._rpm_breakpoints: list[int] = [0 for _ in range(16)]
        self._map_breakpoints: list[int] = [0 for _ in range(16)]
        self._ve_map: list[list[int]] = [[0 for _ in range(16)] for _ in range(16)]

        event_bus.subscribe(AppEventType.ECU_HANDSHAKE_COMPLETED, self._on_handshake_completed)
        event_bus.subscribe(AppEventType.ECU_RESPONSE_RECEIVED,   self._on_ecu_response)
        event_bus.subscribe(AppEventType.ECU_FRAME_RECEIVED,      self._on_frame_received)
        event_bus.subscribe(AppEventType.SIGNALS_RECEIVED,        self._on_signals_received)

    # ──────────────────────────────────────────────────────────────────────────
    # ECU event handlers
    # ──────────────────────────────────────────────────────────────────────────

    def _on_handshake_completed(self, event: EcuHandshakeCompletedEvent) -> None:
        logger.info("Handshake completed — spawning setup thread")
        t = threading.Thread(target=self._run_setup, daemon=True)
        t.start()

    def _run_setup(self) -> None:
        from app.ecu_connection import get_ecu_protocol
        proto = get_ecu_protocol()
        try:
            logger.info("Setup: fetch_map_breakpoints")
            proto.fetch_map_breakpoints()

            logger.info("Setup: fetch_rpm_breakpoints")
            proto.fetch_rpm_breakpoints()

            for row in range(16):
                logger.info("Setup: fetch_ve_row(%d)", row)
                proto.fetch_ve_row(row)

            logger.info("Setup: start_streaming")
            proto.start_streaming()
            logger.info("Setup complete — streaming started")
        except Exception:
            logger.exception("Setup thread failed")

    def _on_ecu_response(self, event: EcuResponseReceivedEvent) -> None:
        response = event.response
        if isinstance(response, MapBreakpointsResponse):
            self.set_map_breakpoints(list(response.values))
        elif isinstance(response, RpmBreakpointsResponse):
            self.set_rpm_breakpoints(list(response.values))
        elif isinstance(response, VeRowResponse):
            self.set_ve_map(list(response.values), response.row_index)
        elif isinstance(response, LambdaResponse):
            self.set_lambda_loop_state(response.state == LambdaState.CLOSED)

    def _on_frame_received(self, event: EcuFrameReceivedEvent) -> None:
        pass  # snapshot is updated via SIGNALS_RECEIVED after SignalProcessor runs

    def _on_signals_received(self, event) -> None:
        self.update(event.data)

    # ──────────────────────────────────────────────────────────────────────────
    # Public ECU command methods (delegate to EcuProtocol on worker threads)
    # ──────────────────────────────────────────────────────────────────────────

    def open_lambda_loop(self) -> None:
        logger.info("Requesting lambda loop OPEN")
        threading.Thread(target=self._do_open_lambda_loop, daemon=True).start()

    def _do_open_lambda_loop(self) -> None:
        from app.ecu_connection import get_ecu_protocol
        try:
            get_ecu_protocol().open_lambda_loop()
        except Exception:
            logger.exception("open_lambda_loop failed")

    def close_lambda_loop(self) -> None:
        logger.info("Requesting lambda loop CLOSE")
        threading.Thread(target=self._do_close_lambda_loop, daemon=True).start()

    def _do_close_lambda_loop(self) -> None:
        from app.ecu_connection import get_ecu_protocol
        try:
            get_ecu_protocol().close_lambda_loop()
        except Exception:
            logger.exception("close_lambda_loop failed")

    def write_ve_row(self, row: int, values: list[int]) -> None:
        threading.Thread(target=self._do_write_ve_row, args=(row, values), daemon=True).start()

    def _do_write_ve_row(self, row: int, values: list[int]) -> None:
        from app.ecu_connection import get_ecu_protocol
        try:
            get_ecu_protocol().set_ve_row(row, values)
        except Exception:
            logger.exception("write_ve_row(%d) failed", row)

    # ──────────────────────────────────────────────────────────────────────────
    # State accessors / mutators
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def emitter(self):
        if self._emitter is None:
            self._emitter = _VehicleStateEmitter()
        return self._emitter.signal

    def update(self, parsed_data: dict) -> None:
        with self._lock:
            self._signals.update(parsed_data)
            # Update lambda loop state from streaming data (with decel filter)
            loop_data = parsed_data.get(Signal.LAMBDA_LOOP)
            if loop_data is not None:
                ecu_is_closed = loop_data.value == 1
                if ecu_is_closed:
                    self._lambda_loop_closed = True
                elif not self._is_decelerating(parsed_data):
                    self._lambda_loop_closed = False

    def _is_decelerating(self, parsed_data: Dict[Signal, ParsedSignal]) -> bool:
        pedal = parsed_data.get(Signal.PEDAL)
        map_ = parsed_data.get(Signal.MAP)
        if pedal is not None and map_ is not None:
            return pedal.value == 0.0 and map_.value <= DECEL_MAP_THRESHOLD
        return False

    def get(self, signal) -> Optional[ParsedSignal]:
        with self._lock:
            return self._signals.get(signal)

    def get_all(self) -> Dict[Signal, ParsedSignal]:
        with self._lock:
            return dict(self._signals)

    def is_alarm_firing(self, signal) -> bool:
        with self._lock:
            last = self._alarm_timestamps.get(signal)
            return last is not None and (time.time() - last) < ALARM_DURATION

    def is_any_alarm_firing(self) -> bool:
        with self._lock:
            now = time.time()
            return any((now - t) < ALARM_DURATION for t in self._alarm_timestamps.values())

    def set_alarm(self, signal, active: bool) -> None:
        with self._lock:
            if active:
                self._alarm_timestamps[signal] = time.time()

    def set_lambda_loop_state(self, is_closed: bool) -> None:
        with self._lock:
            self._lambda_loop_closed = is_closed

    def is_lambda_loop_closed(self) -> bool:
        with self._lock:
            return self._lambda_loop_closed

    def get_rpm_breakpoints(self) -> list[int]:
        with self._lock:
            return self._rpm_breakpoints

    def set_rpm_breakpoints(self, breakpoints: list[int]) -> None:
        with self._lock:
            self._rpm_breakpoints = breakpoints
            self.emitter.emit(VehicleStateChangeEvent(EventType.RPM_BREAKPOINTS, [breakpoints]))

    def get_map_breakpoints(self) -> list[int]:
        with self._lock:
            return self._map_breakpoints

    def set_map_breakpoints(self, breakpoints: list[int]) -> None:
        with self._lock:
            self._map_breakpoints = breakpoints
            self.emitter.emit(VehicleStateChangeEvent(EventType.MAP_BREAKPOINTS, [breakpoints]))

    def get_ve_map(self) -> list[list[int]]:
        with self._lock:
            return self._ve_map

    def set_ve_map(self, ve_line: list[int], ve_idx: int) -> None:
        if len(ve_line) != 16:
            return
        if not (0 <= ve_idx <= 15):
            return
        with self._lock:
            self._ve_map[ve_idx] = ve_line
            self.emitter.emit(VehicleStateChangeEvent(EventType.FUEL_MAP, [ve_idx, ve_line]))


vehicle_state = VehicleState()
