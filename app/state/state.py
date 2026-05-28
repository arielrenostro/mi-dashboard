import threading
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from app.masterinjection.signal import ParsedSignal
from app.state.event import VehicleStateChangeEvent, EventType


class _VehicleStateEmitter(QObject):
    signal = pyqtSignal(VehicleStateChangeEvent)


class VehicleState:

    def __init__(self):
        self._emitter: Optional[_VehicleStateEmitter] = None
        self._lock = threading.RLock()
        self._signals: dict = {}
        self._alarming_signals: set = set()
        self._lambda_loop_closed: bool = False
        self._rpm_breakpoints: list[int] = [0 for _ in range(16)]
        self._map_breakpoints: list[int] = [0 for _ in range(16)]
        self._ve_map: list[list[int]] = [[0 for _ in range(16)] for _ in range(16)]

    @property
    def emitter(self):
        if self._emitter is None:
            self._emitter = _VehicleStateEmitter()
        return self._emitter.signal

    def update(self, parsed_data: dict) -> None:
        with self._lock:
            self._signals.update(parsed_data)

    def update_signals(self, event) -> None:
        self.update(event.data)

    def get(self, signal) -> Optional[ParsedSignal]:
        with self._lock:
            return self._signals.get(signal)

    def get_all(self) -> dict:
        with self._lock:
            return dict(self._signals)

    def is_alarm_firing(self, signal) -> bool:
        with self._lock:
            return signal in self._alarming_signals

    def is_any_alarm_firing(self) -> bool:
        with self._lock:
            return len(self._alarming_signals) > 0

    def set_alarm(self, signal, active: bool) -> None:
        with self._lock:
            if active:
                self._alarming_signals.add(signal)
            else:
                self._alarming_signals.discard(signal)

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
        if 0 > ve_idx > 15:
            return
        with self._lock:
            self._ve_map[ve_idx] = ve_line
            self.emitter.emit(VehicleStateChangeEvent(EventType.FUEL_MAP, [ve_idx, ve_line]))


vehicle_state = VehicleState()
