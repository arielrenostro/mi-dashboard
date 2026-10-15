from enum import Enum


class EventType(Enum):
    MAP_BREAKPOINTS = 0
    RPM_BREAKPOINTS = 1
    FUEL_MAP = 3
    IGNITION_MAP = 4
    PARAMETER_BLOCK = 5


class VehicleStateChangeEvent:

    def __init__(self, type_, args):
        self.type_ = type_
        self.args = args
