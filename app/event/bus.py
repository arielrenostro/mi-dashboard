from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal

from app.event.app_events import AppEvent, AppEventType

logger = logging.getLogger(__name__)

_SIGNAL_ATTR: dict[AppEventType, str] = {
    AppEventType.ECU_FRAME_RECEIVED:      "ecu_frame_received",
    AppEventType.ECU_HANDSHAKE_COMPLETED: "ecu_handshake_completed",
    AppEventType.ECU_RESPONSE_RECEIVED:   "ecu_response_received",
    AppEventType.ALARM_FIRED:             "alarm_fired",
    AppEventType.VEHICLE_STATE_CHANGED:   "vehicle_state_changed",
    AppEventType.EVENT_MARK_REQUESTED:    "event_mark_requested",
    AppEventType.SIGNALS_RECEIVED:        "signals_received",
}


class _EventBusQObject(QObject):
    ecu_frame_received      = pyqtSignal(object)
    ecu_handshake_completed = pyqtSignal(object)
    ecu_response_received   = pyqtSignal(object)
    alarm_fired             = pyqtSignal(object)
    vehicle_state_changed   = pyqtSignal(object)
    event_mark_requested    = pyqtSignal(object)
    signals_received        = pyqtSignal(object)


class EventBus:
    """
    Global event broker — one pyqtSignal per event type.

    Thread safety: pyqtSignal.emit() is thread-safe; Qt delivers cross-thread
    emissions via QueuedConnection automatically.

    Bootstrap: event_bus is instantiated at module import. Import this module
    after QApplication() is created in main() to ensure correct thread affinity.
    """

    def __init__(self):
        self._qt = _EventBusQObject()

    def _signal(self, event_type: AppEventType):
        return getattr(self._qt, _SIGNAL_ATTR[event_type])

    def publish(self, event: AppEvent) -> None:
        self._signal(event.type_).emit(event)

    def subscribe(self, event_type: AppEventType, callback: Callable[[AppEvent], None]) -> object:
        sig = self._signal(event_type)
        sig.connect(callback)
        return sig, callback

    def unsubscribe(self, token: object) -> None:
        sig, callback = token
        try:
            sig.disconnect(callback)
        except TypeError:
            pass


event_bus: EventBus = EventBus()
