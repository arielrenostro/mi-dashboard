import enum


class EcuCommand(enum.Enum):
    ECU_INFO = ("#D50", "Get ECU Info")
    STREAMING_STOP = ("#D01", "Start Streaming")
    STREAMING_START = ("#D01", "Start Streaming")
    WRITE_ON_MEMORY = ("#D04", "Write on Memory")
    LAMBDA_LOOP_CLOSE = ("#D05", "Close Lambda Loop")
    LAMBDA_LOOP_OPEN = ("#D06", "Open Lambda Loop")

    READ_RPM_BREAKPOINTS = ("#I20", "Ler Breakpoints RPM")
    READ_MAP_BREAKPOINTS = ("#I21", "Ler Breakpoints MAP")

    VE_ROW_1  = ("#F01", "VE Linha 1")
    VE_ROW_2  = ("#F02", "VE Linha 2")
    VE_ROW_3  = ("#F03", "VE Linha 3")
    VE_ROW_4  = ("#F04", "VE Linha 4")
    VE_ROW_5  = ("#F05", "VE Linha 5")
    VE_ROW_6  = ("#F06", "VE Linha 6")
    VE_ROW_7  = ("#F07", "VE Linha 7")
    VE_ROW_8  = ("#F08", "VE Linha 8")
    VE_ROW_9  = ("#F09", "VE Linha 9")
    VE_ROW_10 = ("#F10", "VE Linha 10")
    VE_ROW_11 = ("#F11", "VE Linha 11")
    VE_ROW_12 = ("#F12", "VE Linha 12")
    VE_ROW_13 = ("#F13", "VE Linha 13")
    VE_ROW_14 = ("#F14", "VE Linha 14")
    VE_ROW_15 = ("#F15", "VE Linha 15")
    VE_ROW_16 = ("#F16", "VE Linha 16")

    @property
    def description(self) -> str:
        return self.value[1]

    @property
    def cmd(self) -> str:
        return self.value[0]

    @classmethod
    def ve_row(cls, row: int) -> 'EcuCommand':
        """Return the EcuCommand for a VE row (row 0-15 → VE_ROW_1–VE_ROW_16)."""
        return cls[f'VE_ROW_{row + 1}']


class EcuResponse(enum.Enum):
    ECU_INFO = "#D50"
    MESS_DATA_1 = "#D01"
    MESS_DATA_2 = "#D02"
    MESS_DATA_3 = "#D03"
    RPM_BREAKPOINTS = "#I20"
    MAP_BREAKPOINTS = "#I21"
