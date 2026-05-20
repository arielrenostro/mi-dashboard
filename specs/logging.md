# Spec: CSV Logging

Describes the format, columns, and behavior of the CSV data log.

Implementation: `app/log_writer/log_writer.py`.

---

## File

| Property | Value |
|---|---|
| Format | CSV, semicolon-delimited |
| Line terminator | `\n` |
| Encoding | System default (Python `open()`) |
| Open mode | Append (`"a"`) — safe to restart without losing data |
| Header | Written once when the file does not yet exist |
| Flush | After every row |

The output path is configured via `LOG_FILE` in `main.py`.

---

## Columns

| # | Column name | Source | Description |
|---|---|---|---|
| 0 | `Timestamp` | `LogWriter` | Unix timestamp in milliseconds (`int(time.time() * 1000)`) |
| 1 | `Event` | `LogWriter` | `"MARK"` if an event was pending, empty otherwise |
| 2 | `Mess 1` | ECU frame | Raw `#D01` prefix token |
| 3 | `RPM` | ECU frame | Index 1 — raw value |
| 4 | `MAP` | ECU frame | Index 2 — raw value |
| 5 | `Boost` | ECU frame | Index 3 — raw value |
| 6 | `Load %` | ECU frame | Index 4 — raw value |
| 7 | `Idle` | ECU frame | Index 5 — raw value |
| 8 | `Lambda 1` | ECU frame | Index 6 — raw value |
| 9 | `Inj. Pulse` | ECU frame | Index 7 — raw value |
| 10 | `Inj. Utiliz.` | ECU frame | Index 8 — raw value |
| 11 | `VE Value` | ECU frame | Index 9 — raw value |
| 12 | `Ign. Adv.` | ECU frame | Index 10 — raw value |
| 13 | `Knock` | ECU frame | Index 11 — raw value |
| 14 | `A/C Input` | ECU frame | Index 12 — raw value |
| 15 | `Start Input` | ECU frame | Index 13 — raw value |
| 16 | `Outputs 1` | ECU frame | Index 14 — raw value |
| 17 | `Outputs 2` | ECU frame | Index 15 — raw value |
| 18 | `Lambda 2` | ECU frame | Index 16 — raw value |
| 19 | `Mess 2` | ECU frame | `#D02` prefix token (joined frame separator) |
| 20 | `Batt Volt.` | ECU frame | Index 20 — raw value |
| 21 | `CLT` | ECU frame | Index 21 — raw value (Kelvin) |
| 22 | `IAT` | ECU frame | Index 22 — raw value (Kelvin) |
| 23 | `Inj. DT` | ECU frame | Index 23 — raw value |
| 24 | `Ign. Dwell` | ECU frame | Index 24 — raw value |
| 25 | `KM/H` | ECU frame | Index 25 — raw value |
| 26 | `Lambda Loop` | ECU frame | Index 26 — raw value (0=open, 1=closed) |
| 27 | `Lambda Target` | ECU frame | Index 27 — raw value (lambda × 1000) |
| 28 | `Lambda Corr` | ECU frame | Index 28 — raw value |
| 29 | `Strobo Angle` | ECU frame | Index 29 — raw value |
| 30 | `Turbo Target` | ECU frame | Index 30 — raw value |
| 31 | `ACC %` | ECU frame | Index 31 — raw value |
| 32 | `ACP %` | ECU frame | Index 32 — raw value |
| 33 | `dACC %` | ECU frame | Index 33 — raw value |
| 34 | `0` | ECU frame | Index 34 — unused |
| 35 | `0` | ECU frame | Index 35 — unused |

**Note:** columns 2 onwards are the raw tokens from the joined `#D01;...;#D02;...` frame split on `;`. The log stores raw values; display-time conversion (as defined in `signals.md`) is applied by `SignalProcessor` and is not stored.

---

## Event marking

The `Event` column (column 1) is normally empty.

When the user presses `Enter`/`Return`:
1. `EventMarker` emits `event_triggered`.
2. `LogWriter.set_event_pending()` sets an internal flag.
3. The next call to `LogWriter.write()` writes `"MARK"` in the `Event` column and clears the flag.

**Intent:** the mark is attached to the **next** frame that arrives after the key press, not to a synthetic row. This keeps the log time-aligned with ECU data.

---

## Threading

`LogWriter` owns a `Worker` object moved to a dedicated `QThread`. All disk writes happen on that thread via a `pyqtSignal(list)` queue. The main thread (or ECU thread) calls `LogWriter.write()` which emits the queued signal — it never writes to disk directly.

---

## Mock / replay

The `EcuConnectionMock` reads the `Timestamp` column from the CSV to pace frame replay at the original recorded rate. No other columns are parsed by the mock.
