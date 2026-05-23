import enum


class EcuCommand(enum.Enum):
    ECU_INFO = ("#D50", "Get ECU Info")
    STREAMING_STOP = ("#D00", "Stop Streaming")
    STREAMING_START = ("#D01", "Start Streaming")
    WRITE_ON_MEMORY = ("#D04", "Write on Memory")
    LAMBDA_LOOP_CLOSE = ("#D05", "Close Lambda Loop")
    LAMBDA_LOOP_OPEN = ("#D06", "Open Lambda Loop")

    RPM_BREAKPOINTS = ("#I20", "RPM Breakpoints")
    MAP_BREAKPOINTS = ("#I21", "MAP Breakpoints")

    VE_ROW_1 = ("#F01", "VE 1 line")
    VE_ROW_2 = ("#F02", "VE 2 line")
    VE_ROW_3 = ("#F03", "VE 3 line")
    VE_ROW_4 = ("#F04", "VE 4 line")
    VE_ROW_5 = ("#F05", "VE 5 line")
    VE_ROW_6 = ("#F06", "VE 6 line")
    VE_ROW_7 = ("#F07", "VE 7 line")
    VE_ROW_8 = ("#F08", "VE 8 line")
    VE_ROW_9 = ("#F09", "VE 9 line")
    VE_ROW_10 = ("#F10", "VE 10 line")
    VE_ROW_11 = ("#F11", "VE 11 line")
    VE_ROW_12 = ("#F12", "VE 12 line")
    VE_ROW_13 = ("#F13", "VE 13 line")
    VE_ROW_14 = ("#F14", "VE 14 line")
    VE_ROW_15 = ("#F15", "VE 15 line")
    VE_ROW_16 = ("#F16", "VE 16 line")

    @property
    def description(self) -> str:
        return self.value[1]

    @property
    def cmd(self) -> str:
        return self.value[0]


class EcuResponse(enum.Enum):
    ECU_INFO = "#D50"
    MESS_DATA_1 = "#D01"
    MESS_DATA_2 = "#D02"
    MESS_DATA_3 = "#D03"

    RPM_BREAKPOINTS = "#I20"
    MAP_BREAKPOINTS = "#I21"

    VE_ROW_1 = "#F01"
    VE_ROW_2 = "#F02"
    VE_ROW_3 = "#F03"
    VE_ROW_4 = "#F04"
    VE_ROW_5 = "#F05"
    VE_ROW_6 = "#F06"
    VE_ROW_7 = "#F07"
    VE_ROW_8 = "#F08"
    VE_ROW_9 = "#F09"
    VE_ROW_10 = "#F10"
    VE_ROW_11 = "#F11"
    VE_ROW_12 = "#F12"
    VE_ROW_13 = "#F13"
    VE_ROW_14 = "#F14"
    VE_ROW_15 = "#F15"
    VE_ROW_16 = "#F16"
