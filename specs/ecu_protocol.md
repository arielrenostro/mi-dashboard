# Spec: ECU Serial Protocol

Describes the Bluetooth serial communication protocol between the dashboard and the Master Injection ECU.

Implementation: `app/ecu_connection/ecu_connection.py`, `app/master/ecu.py`.

---

## Transport

| Parameter | Value |
|---|---|
| Interface | Bluetooth serial (Windows COM port) |
| Default port | `COM1` (configured in `main.py`) |
| Baud rate | 115200 |
| Timeout | 1 s (read and write) |
| Encoding | UTF-8 |
| Line terminator | `\n` |

---

## Frame format

The ECU streams two frame types per cycle. Each frame is a semicolon-delimited line:

```
#D01;<val1>;<val2>;...;<valN>
#D02;<val1>;<val2>;...;<valN>
```

`EcuConnection` waits for exactly one `#D01` and one `#D02` per cycle, joins them, and emits:

```
#D01;<...>;#D02;<...>
```

Signal indices in `signals.md` refer to absolute positions in this joined string.

---

## Commands

Defined in `EcuCommand` enum (`app/master/ecu.py`).

| Enum name | Command string | Description |
|---|---|---|
| `ECU_INFO` | `#D50` | Request ECU info (handshake) |
| `STREAMING_START` | `#D01` | Start data streaming |
| `STREAMING_STOP` | `#D01` | Stop data streaming (same command) |
| `WRITE_ON_MEMORY` | `#D04` | Write to ECU memory |
| `LAMBDA_LOOP_CLOSE` | `#D05` | Close the lambda feedback loop |
| `LAMBDA_LOOP_OPEN` | `#D06` | Open the lambda feedback loop |

Commands are sent as `"{cmd}\n"` encoded in UTF-8.

---

## Responses

Defined in `EcuResponse` enum.

| Enum name | Response prefix |
|---|---|
| `ECU_INFO` | `#D50` |
| `MESS_DATA_1` | `#D01` |
| `MESS_DATA_2` | `#D02` |
| `MESS_DATA_3` | `#D03` |

---

## Connection and handshake sequence

```
1. Open serial port
2. Send ECU_INFO (#D50) → wait for response starting with "#D50"
   - Retry every 3 attempts if no valid response
3. Send STREAMING_START (#D01) → wait for response starting with "#D01", "#D02", or "#D03"
   - Retry every 3 attempts if no valid response
4. Enter read loop
```

---

## Read loop

```
while running:
    line = readline()

    if line is empty:
        count_zero += 1
        if count_zero == 3:
            reconnect()        ← close port, restart from step 1
        continue

    count_zero = 0

    if line starts with "#D01": store as d01
    if line starts with "#D02": store as d02

    if d01 and d02 are both buffered:
        emit joined frame: "{d01};{d02}"
        clear d01 and d02
        drain command queue                ← send any pending commands
```

**Intent:** commands are drained after a complete frame, not mid-frame, to avoid interleaving with streaming data.

---

## Sending commands

`send_command(cmd: EcuCommand)` is thread-safe. It enqueues the command; the command is sent during the next `_drain_command_queue()` call in the read loop (i.e., after the next complete `#D01 + #D02` pair).

Multiple commands in the queue are sent in FIFO order.

---

## Mock mode

When `MOCK_FILE` is set in `main.py`, `EcuConnectionMock` is used instead of `EcuConnection`.

Implementation: `app/ecu_connection/ecu_connection_mock.py`.

| Behavior | Description |
|---|---|
| Source | Replays rows from a previously recorded CSV log file |
| Timing | Emits frames paced by the `Timestamp` column in the CSV when available |
| Commands | `send_command()` is a no-op |
| Emitted format | Same joined `#D01;...;#D02;...` string as real connection |

**Intent:** mock mode is for development and testing without hardware. The emitted format is identical to real mode so all downstream components are unaffected.
