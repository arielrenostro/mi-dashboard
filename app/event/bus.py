from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal

from app.event.app_events import AppEvent, AppEventType

logger = logging.getLogger(__name__)

_SIGNAL_ATTR: dict[AppEventType, str] = {
    AppEventType.SCREEN_REQUESTED:              "screen_requested",
    AppEventType.ECU_COMMAND_REQUESTED:         "ecu_command_requested",
    AppEventType.ALARM_FIRED:                   "alarm_fired",
    AppEventType.VEHICLE_STATE_CHANGED:         "vehicle_state_changed",
    AppEventType.EVENT_MARK_REQUESTED:          "event_mark_requested",
    AppEventType.SIGNALS_RECEIVED:              "signals_received",
    AppEventType.ECU_MESS_FRAME:                "ecu_mess_frame",
    AppEventType.ECU_COMMAND_SENT:              "ecu_command_sent",
    AppEventType.ECU_COMMAND_RESPONSE:          "ecu_command_response",
    AppEventType.ECU_CONNECTION_STATUS_CHANGED: "ecu_connection_status_changed",
}


class _EventBusQObject(QObject):
    screen_requested              = pyqtSignal(object)
    ecu_command_requested         = pyqtSignal(object)
    alarm_fired                   = pyqtSignal(object)
    vehicle_state_changed         = pyqtSignal(object)
    event_mark_requested          = pyqtSignal(object)
    signals_received              = pyqtSignal(object)
    ecu_mess_frame                = pyqtSignal(object)
    ecu_command_sent              = pyqtSignal(object)
    ecu_command_response          = pyqtSignal(object)
    ecu_connection_status_changed = pyqtSignal(object)


class EventBus:
    """
    Global event broker — one pyqtSignal per event type.

    Thread safety: pyqtSignal.emit() is thread-safe; Qt delivers cross-thread
    emissions via QueuedConnection automatically.

    Bootstrap: _EventBusQObject is created lazily on first use so that this
    module can be imported before QApplication() is created without issues.
    """

    def __init__(self):
        self._qt: _EventBusQObject | None = None

    def _ensure_qt(self) -> None:
        if self._qt is None:
            self._qt = _EventBusQObject()

    def _signal(self, event_type: AppEventType):
        self._ensure_qt()
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
