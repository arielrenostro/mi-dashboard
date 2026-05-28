from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class AppEventType(Enum):
    SCREEN_REQUESTED      = auto()
    ECU_COMMAND_REQUESTED = auto()
    ALARM_FIRED           = auto()
    EVENT_MARK_REQUESTED  = auto()
    SIGNALS_RECEIVED      = auto()
    ECU_MESS_FRAME        = auto()
    ECU_COMMAND_SEND      = auto()
    ECU_COMMAND_RESPONSE  = auto()


@dataclass(frozen=True)
class AppEvent:
    type_: AppEventType


@dataclass(frozen=True)
class ScreenRequestedEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.SCREEN_REQUESTED, init=False)
    screen_name: str = ""


@dataclass(frozen=True)
class EcuCommandRequestedEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.ECU_COMMAND_REQUESTED, init=False)
    command: Any = None
    args: Any = None


@dataclass(frozen=True)
class AlarmFiredEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.ALARM_FIRED, init=False)
    signal: Any = None
    until: float = 0.0


@dataclass(frozen=True)
class EventMarkRequestedEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.EVENT_MARK_REQUESTED, init=False)


@dataclass(frozen=True)
class SignalsReceivedEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.SIGNALS_RECEIVED, init=False)
    data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EcuMessFrameEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.ECU_MESS_FRAME, init=False)
    frame_type: str = ""
    line: str = ""


@dataclass(frozen=True)
class EcuCommandSendEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.ECU_COMMAND_SEND, init=False)
    cmd: str = ""
    args: Any = None


@dataclass(frozen=True)
class EcuCommandResponseEvent(AppEvent):
    type_: AppEventType = field(default=AppEventType.ECU_COMMAND_RESPONSE, init=False)
    cmd: str = ""
    response_line: str = ""
