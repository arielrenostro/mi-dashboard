import enum

# Re-export from new location for backwards compatibility
from app.ecu.commands import EcuCommand, ResponseContract, EcuTimeoutError  # noqa: F401


class EcuResponse(enum.Enum):
    ECU_INFO = "#D50"
    MESS_DATA_1 = "#D01"
    MESS_DATA_2 = "#D02"
    MESS_DATA_3 = "#D03"

    RPM_BREAKPOINTS = "#I20"
    MAP_BREAKPOINTS = "#I21"

    VE_ROW_1  = "#F01"
    VE_ROW_2  = "#F02"
    VE_ROW_3  = "#F03"
    VE_ROW_4  = "#F04"
    VE_ROW_5  = "#F05"
    VE_ROW_6  = "#F06"
    VE_ROW_7  = "#F07"
    VE_ROW_8  = "#F08"
    VE_ROW_9  = "#F09"
    VE_ROW_10 = "#F10"
    VE_ROW_11 = "#F11"
    VE_ROW_12 = "#F12"
    VE_ROW_13 = "#F13"
    VE_ROW_14 = "#F14"
    VE_ROW_15 = "#F15"
    VE_ROW_16 = "#F16"
