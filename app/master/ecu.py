import enum


class EcuCommand(enum.Enum):
    ECU_INFO = ("#D50", "Get ECU Info")
    STREAMING = ("#D01", "Start Streaming")

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
