import threading
import time
from typing import Optional

ALARM_DURATION = 2


class VehicleState:
    def __init__(self):
        self._lock = threading.RLock()
        self._signals: dict = {}
        self._alarm_timestamps: dict = {}

    def update(self, parsed_data: dict) -> None:
        with self._lock:
            self._signals.update(parsed_data)

    def get(self, signal) -> Optional[dict]:
        with self._lock:
            return self._signals.get(signal)

    def get_all(self) -> dict:
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


vehicle_state = VehicleState()
