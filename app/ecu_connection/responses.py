from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LambdaState(Enum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass(frozen=True)
class EcuResponse:
    pass


@dataclass(frozen=True)
class EcuInfoResponse(EcuResponse):
    raw_values: tuple = ()


@dataclass(frozen=True)
class MapBreakpointsResponse(EcuResponse):
    values: tuple = ()  # List[int] as tuple


@dataclass(frozen=True)
class RpmBreakpointsResponse(EcuResponse):
    values: tuple = ()


@dataclass(frozen=True)
class VeRowResponse(EcuResponse):
    row_index: int = 0
    values: tuple = ()  # List[int] as tuple


@dataclass(frozen=True)
class StreamingAckResponse(EcuResponse):
    pass


@dataclass(frozen=True)
class LambdaResponse(EcuResponse):
    state: LambdaState = LambdaState.OPEN


@dataclass(frozen=True)
class CommandAckResponse(EcuResponse):
    """Generic acknowledgment for commands with no structured payload."""
    prefix: str = ""
