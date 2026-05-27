import threading
import time
from typing import Optional

from app.masterinjection.signal import ParsedSignal
from app.state.event import VehicleStateChangeEvent, EventType


class VehicleState:

    def __init__(self):
        self._lock = threading.RLock()
        self._signals: dict = {}
        self._alarm_timestamps: dict = {}  # Signal → (fired_at: float, expires_at: float)
        self._lambda_loop_closed: bool = False
        self._rpm_breakpoints: list[int] = [0 for _ in range(16)]
        self._map_breakpoints: list[int] = [0 for _ in range(16)]
        self._ve_map: list[list[int]] = [[0 for _ in range(16)] for _ in range(16)]

    def update(self, parsed_data: dict) -> None:
        with self._lock:
            self._signals.update(parsed_data)

    def get(self, signal) -> Optional[ParsedSignal]:
        with self._lock:
            return self._signals.get(signal)

    def get_all(self) -> dict:
        with self._lock:
            return dict(self._signals)

    def is_alarm_firing(self, signal) -> bool:
        with self._lock:
            entry = self._alarm_timestamps.get(signal)
            if entry is None:
                return False
            _, expires_at = entry
            return time.time() < expires_at

    def is_any_alarm_firing(self) -> bool:
        with self._lock:
            now = time.time()
            return any(now < expires_at for _, expires_at in self._alarm_timestamps.values())

    def set_alarm(self, signal, active: bool, duration_s: float = 2.0) -> None:
        with self._lock:
            if active:
                now = time.time()
                expires_at = now + duration_s
                self._alarm_timestamps[signal] = (now, expires_at)
            else:
                self._alarm_timestamps.pop(signal, None)

    def set_lambda_loop_state(self, is_closed: bool) -> None:
        with self._lock:
            self._lambda_loop_closed = is_closed

    def is_lambda_loop_closed(self) -> bool:
        with self._lock:
            return self._lambda_loop_closed

    def get_rpm_breakpoints(self) -> list[int]:
        with self._lock:
            return list(self._rpm_breakpoints)

    def set_rpm_breakpoints(self, breakpoints: list[int]) -> None:
        with self._lock:
            self._rpm_breakpoints = breakpoints
        from app.event.bus import event_bus
        from app.event.app_events import VehicleStateChangedEvent
        event_bus.publish(VehicleStateChangedEvent(change_type=EventType.RPM_BREAKPOINTS, args=(breakpoints,)))

    def get_map_breakpoints(self) -> list[int]:
        with self._lock:
            return list(self._map_breakpoints)

    def set_map_breakpoints(self, breakpoints: list[int]) -> None:
        with self._lock:
            self._map_breakpoints = breakpoints
        from app.event.bus import event_bus
        from app.event.app_events import VehicleStateChangedEvent
        event_bus.publish(VehicleStateChangedEvent(change_type=EventType.MAP_BREAKPOINTS, args=(breakpoints,)))

    def get_ve_map(self) -> list[list[int]]:
        with self._lock:
            return [list(row) for row in self._ve_map]

    def set_ve_map(self, ve_line: list[int], ve_idx: int) -> None:
        if len(ve_line) != 16:
            return
        if not (0 <= ve_idx <= 15):
            return
        with self._lock:
            self._ve_map[ve_idx] = ve_line
        from app.event.bus import event_bus
        from app.event.app_events import VehicleStateChangedEvent
        event_bus.publish(VehicleStateChangedEvent(change_type=EventType.FUEL_MAP, args=(ve_idx, ve_line)))


vehicle_state = VehicleState()
