from __future__ import annotations

import enum


class ResponseContract(enum.Enum):
    """Defines how the session matches an ECU response to a sent command."""
    ECHO_FULL     = "echo_full"      # SetData: response must echo cmd + args exactly
    ECHO_CMD_ONLY = "echo_cmd_only"  # SetState: response is just the cmd code, no args
    DATA_RESPONSE = "data_response"  # GetData: response is cmd code + payload data
    HANDSHAKE     = "handshake"      # Special: used during connection init; matched by prefix only


class EcuCommand(enum.Enum):
    # Handshake / streaming
    ECU_INFO        = ("#D50", "Get ECU Info",         ResponseContract.HANDSHAKE)
    STREAMING_STOP  = ("#D00", "Stop Streaming",        ResponseContract.ECHO_CMD_ONLY)
    STREAMING_START = ("#D01", "Start Streaming",       ResponseContract.HANDSHAKE)
    WRITE_ON_MEMORY = ("#D04", "Write on Memory",       ResponseContract.ECHO_CMD_ONLY)

    # Lambda loop
    LAMBDA_LOOP_CLOSE = ("#D05", "Close Lambda Loop",   ResponseContract.ECHO_CMD_ONLY)
    LAMBDA_LOOP_OPEN  = ("#D06", "Open Lambda Loop",    ResponseContract.ECHO_CMD_ONLY)

    # Breakpoints (GET)
    RPM_BREAKPOINTS = ("#I20", "RPM Breakpoints",       ResponseContract.DATA_RESPONSE)
    MAP_BREAKPOINTS = ("#I21", "MAP Breakpoints",       ResponseContract.DATA_RESPONSE)

    # VE rows (GET when sent bare, SET when sent with data)
    VE_ROW_1  = ("#F01", "VE 1 line",   ResponseContract.ECHO_FULL)
    VE_ROW_2  = ("#F02", "VE 2 line",   ResponseContract.ECHO_FULL)
    VE_ROW_3  = ("#F03", "VE 3 line",   ResponseContract.ECHO_FULL)
    VE_ROW_4  = ("#F04", "VE 4 line",   ResponseContract.ECHO_FULL)
    VE_ROW_5  = ("#F05", "VE 5 line",   ResponseContract.ECHO_FULL)
    VE_ROW_6  = ("#F06", "VE 6 line",   ResponseContract.ECHO_FULL)
    VE_ROW_7  = ("#F07", "VE 7 line",   ResponseContract.ECHO_FULL)
    VE_ROW_8  = ("#F08", "VE 8 line",   ResponseContract.ECHO_FULL)
    VE_ROW_9  = ("#F09", "VE 9 line",   ResponseContract.ECHO_FULL)
    VE_ROW_10 = ("#F10", "VE 10 line",  ResponseContract.ECHO_FULL)
    VE_ROW_11 = ("#F11", "VE 11 line",  ResponseContract.ECHO_FULL)
    VE_ROW_12 = ("#F12", "VE 12 line",  ResponseContract.ECHO_FULL)
    VE_ROW_13 = ("#F13", "VE 13 line",  ResponseContract.ECHO_FULL)
    VE_ROW_14 = ("#F14", "VE 14 line",  ResponseContract.ECHO_FULL)
    VE_ROW_15 = ("#F15", "VE 15 line",  ResponseContract.ECHO_FULL)
    VE_ROW_16 = ("#F16", "VE 16 line",  ResponseContract.ECHO_FULL)

    @property
    def cmd(self) -> str:
        return self.value[0]

    @property
    def description(self) -> str:
        return self.value[1]

    @property
    def response_contract(self) -> ResponseContract:
        return self.value[2]


class EcuTimeoutError(TimeoutError):
    pass
