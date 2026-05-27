from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class AppEventType(Enum):
    SCREEN_REQUESTED              = auto()
    ECU_COMMAND_REQUESTED         = auto()
    ALARM_FIRED                   = auto()
    VEHICLE_STATE_CHANGED         = auto()
    EVENT_MARK_REQUESTED          = auto()
    SIGNALS_RECEIVED              = auto()
    ECU_MESS_FRAME                = auto()
    ECU_COMMAND_SENT              = auto()
    ECU_COMMAND_RESPONSE          = auto()
    ECU_CONNECTION_STATUS_CHANGED = auto()


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


@dataclass(frozen=True)
class EcuMessFrameEvent(AppEvent):
    """Publicado pela Reader thread da EcuSession para cada frame recebido."""
    type_: AppEventType = field(default=AppEventType.ECU_MESS_FRAME, init=False)
    frame_id: str = ""   # "D01", "D02", "D03"
    line: str = ""       # linha completa: "#D01;v1;v2;..."


@dataclass(frozen=True)
class EcuCommandSentEvent(AppEvent):
    """Publicado pela EcuSession ao enviar qualquer comando."""
    type_: AppEventType = field(default=AppEventType.ECU_COMMAND_SENT, init=False)
    command: Any = None
    args: Any = None


@dataclass(frozen=True)
class EcuCommandResponseEvent(AppEvent):
    """Publicado pela Reader thread para linhas que não são frames de medição."""
    type_: AppEventType = field(default=AppEventType.ECU_COMMAND_RESPONSE, init=False)
    line: str = ""


@dataclass(frozen=True)
class EcuConnectionStatusChangedEvent(AppEvent):
    """Publicado pela EcuSession quando o status de conexão muda."""
    type_: AppEventType = field(default=AppEventType.ECU_CONNECTION_STATUS_CHANGED, init=False)
    status: Any = None   # EcuConnectionStatus enum (definido em session.py)
