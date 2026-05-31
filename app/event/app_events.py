from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List


class AppEventType(Enum):
    ECU_FRAME_RECEIVED      = auto()
    ECU_HANDSHAKE_COMPLETED = auto()
    ECU_RESPONSE_RECEIVED   = auto()
    ALARM_FIRED             = auto()
    VEHICLE_STATE_CHANGED   = auto()
    EVENT_MARK_REQUESTED    = auto()
    SIGNALS_RECEIVED        = auto()


class EcuFrameType(Enum):
    D01 = "#D01"
    D02 = "#D02"
    D03 = "#D03"


@dataclass(frozen=True)
class AppEvent:
    type_: AppEventType


@dataclass(frozen=True)
class EcuFrameReceivedEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.ECU_FRAME_RECEIVED, init=False)
    frame_type: EcuFrameType = EcuFrameType.D01
    values: tuple = field(default_factory=tuple)  # List[str] as tuple for frozen


@dataclass(frozen=True)
class EcuHandshakeCompletedEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.ECU_HANDSHAKE_COMPLETED, init=False)


@dataclass(frozen=True)
class EcuResponseReceivedEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.ECU_RESPONSE_RECEIVED, init=False)
    response: Any = None


@dataclass(frozen=True)
class AlarmFiredEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.ALARM_FIRED, init=False)
    signal: Any = None
    until: float = 0.0


@dataclass(frozen=True)
class VehicleStateChangedEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.VEHICLE_STATE_CHANGED, init=False)
    change_type: Any = None
    args: tuple = field(default_factory=tuple)


@dataclass(frozen=True)
class EventMarkRequestedEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.EVENT_MARK_REQUESTED, init=False)


@dataclass(frozen=True)
class SignalsReceivedEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.SIGNALS_RECEIVED, init=False)
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.monotonic)
