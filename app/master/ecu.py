import enum


class EcuCommand(enum.Enum):
    ECU_INFO = ("#D50", "Get ECU Info")
    STREAMING_STOP = ("#D01", "Start Streaming")
    STREAMING_START = ("#D01", "Start Streaming")
    WRITE_ON_MEMORY = ("#D04", "Write on Memory")
    LAMBDA_LOOP_CLOSE = ("#D05", "Close Lambda Loop")
    LAMBDA_LOOP_OPEN = ("#D06", "Open Lambda Loop")

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
