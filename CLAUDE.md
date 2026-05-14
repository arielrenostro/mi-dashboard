# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Real-time automotive ECU telemetry dashboard for the Master Injection ECU. It reads data over a Bluetooth serial COM port (Windows), parses semicolon-delimited frames, displays live signal values and graphs, plays audio alarms, and logs raw data to CSV.

## Running the app

```
.venv\Scripts\python main.py
```

No build step. No test suite. Dependencies:

```
pip install -r requirements.txt   # pyserial, pyqt6, pyqtgraph
```

## Configuration (all in `main.py`)

| Variable | Purpose |
|---|---|
| `PORT` | Windows COM port (e.g. `"COM5"`) |
| `BAUDRATE` | Serial baud rate |
| `LOG_FILE` | Output CSV path |
| `ALARM_SOUND` | Path to `.wav` alarm file |
| `MOCK_FILE` | If set (non-empty), uses `SerialReaderMock` instead of real serial |

To run without hardware, set `MOCK_FILE` to a previously recorded CSV log.

## Architecture

### Data flow

```
SerialReader / SerialReaderMock (QThread)
    │  emitter(str)  — raw semicolon-joined #D01;#D02 line
    ├──► SignalProcessor.process_line()
    │         │  emitter(dict)  — {Signal: {value, value_str, raw, signal}}
    │         ├──► Dashboard.process_signals()     (UI update)
    │         └──► AlarmProcessor.process_signals() (alarm check)
    └──► LogWriter.write()                          (CSV append)

AlarmProcessor.emitter(Signal) ──► Dashboard.fire_field_alarm()  (visual flash)
```

All cross-thread communication goes through `pyqtSignal` / `@Slot`. The UI is never touched from background threads.

### Modules

**`app/reader/`** — Serial ingestion  
- `SerialReader`: QThread that connects to the ECU, sends `#D50` (ECU info handshake) then `#D01` (start streaming). Buffers `#D01` and `#D02` lines and emits them joined as `"#D01...;#D02..."`. Reconnects automatically after 3 consecutive empty reads.  
- `SerialReaderMock`: Replays a CSV log file, timing emissions based on embedded timestamps when available.

**`app/master/`** — Domain models  
- `signal.py`: `Signal` enum — the single source of truth for every ECU signal. Each entry defines `index` (CSV column), `converter` (raw→value), `for_label` (value→display string), `unit`, `min`/`max` (graph range), `color`, and `alarm` config. Signals with `calculated: True` (e.g. `POWER`, `TORQUE`) derive their value from other already-parsed signals via a `value` lambda.  
- `signal_processor.py`: `SignalProcessor` — splits the joined line on `;`, iterates all `Signal` enum members, applies converters, builds the `parsed_data` dict, and emits it.  
- `ecu.py`: `EcuCommand` / `EcuResponse` enums for the serial protocol.  
- `log.py`: `LOG_PREFIX = "#D01"` — only lines starting with this are parsed/logged.

**`app/dashboard/`** — Qt UI  
- `dashboard.py`: Full-screen `QWidget` with a `QGridLayout` of signal cells (name + big value label) and `pyqtgraph` plots below. Graph data is buffered in `deque(maxlen=graph_x_size)` and refreshed every 100 ms via `QTimer`. Alarm state changes trigger a yellow-flash animation via nested `QTimer.singleShot` calls.  
- `grid.py`: `GRID` (2D list of Signals for the numeric grid) and `GRAPH` (list of rows, each row a list of Signals sharing one plot).

**`app/alarm/`** — Audio alarms  
- `processor.py`: `AlarmProcessor` (QThread) — polls alarm state every 100 ms, plays `alarm.wav` via `QMediaPlayer` while any alarm is active, emits a `Signal` to the dashboard when a new alarm fires.  
- `state.py`: Module-level `_state` dict mapping `Signal → last_triggered_timestamp`. `is_alarm_firing()` returns `True` within 2 seconds of the last trigger.

**`app/log_writer/`** — CSV logging  
- `log_writer.py`: `LogWriter` (QWidget) owns a `Worker` (QObject) moved to a dedicated `QThread`. Filters lines by `LOG_PREFIX`, prepends a millisecond Unix timestamp, and appends rows to the CSV via `csv.writer`.

## Adding or modifying signals

1. Add/edit an entry in the `Signal` enum in `app/master/signal.py`.
2. Add it to `GRID` and/or `GRAPH` in `app/dashboard/grid.py`.

For calculated signals (no direct CSV column), set `"calculated": True` and provide a `"value"` lambda that receives the already-parsed `parsed_data` dict. Order in the enum matters — calculated signals must come after all their dependencies.

## ECU serial protocol

The ECU streams two frame types per cycle:
- `#D01;val1;val2;...` — primary sensor data
- `#D02;val1;val2;...` — secondary sensor data

`SerialReader` waits for one of each, joins them with `;`, and emits the combined string. `SignalProcessor` accesses fields by absolute index across this combined string.
