## Context

See proposal.md for motivation and the specs for behaviour. Today:

- `IgnitionAnalysis` (`app/ui/ignition_tuning/analysis.py`) is Qt-free and clock-free: `process(signals, now, offset, map_loaded)` and `status(...)`. It already keeps "wait N seconds" state (`_settle_until`) and tracks the lambda loop on every set, which is the pattern the inclination condition follows. It copies the `ignition_tuning` settings in `__init__` (with constructor overrides for tests).
- `IgnitionResultsLog` writes `analysis.rpm_min` / `rpm_max` in every row of its CSV and only starts a new file after `end_run()`.
- `app/config.py` builds `AppConfig` objects once, at import, from `config.json` and never writes. Several screens read it in `__init__`.
- The ECU connection is `EcuConnectionSerial` inside an `EcuConnectionThread`, registered in `app/ecu_connection/__init__.py`. `AppWindow` wires screens to signals (`_register_screens`); shortcuts F1-F4 and the `_DATA_SCREENS` tuple live in `app/ui/window.py`.
- The inclinometer talks `#D;…;`, `#H;…;`, `#M;…;` lines at 100 Hz and answers `#Z`, `#R`, `#C` (see the specs for the exact protocol).

## Goals / Non-Goals

**Goals:**
- The inclinometer is optional, never blocks or disturbs the ECU connection, and when configured it is mandatory for the ignition analysis.
- The protocol and state logic is pure and unit-testable without a serial port, a clock or Qt.
- Settings edited on a keyboard-only screen are saved to `config.json` safely, and the rule "every setting has a row" is enforced by a test.

**Non-Goals:**
- Filtering, axis mapping or zero offsets in the app (the device does all of it).
- Logging the inclination to the datalog or to the ignition results CSV.
- Editing the settings in the backlog (paths, sounds, lists), which need text entry.
- Using the roll, the accelerations, the gyro rates or the temperature for anything but display.
- Compensating the pitch for the vehicle's own acceleration.
- `#R` (remove zero) from the app.

## Decisions

1. **`app/gyro/` is split in a pure core and a thin thread.**
   - `protocol.py`: `parse_line(line) -> Data | Header | Message | None` and the reading dataclass.
   - `state.py`: `GyroState`, a lock-protected object with an injected clock. `feed(line)` applies the rules of the spec (zero flag, calibrating, last message, `t_ms` going back), and `snapshot()` computes the derived state (`disabled`, `disconnected`, `calibrating`, `no signal`, `not zeroed`, `usable`) and the usable pitch from timestamps at query time, so staleness is right even if the thread is stuck. `opened()`, `closed()` and `set_enabled()` cover the port events.
   - `connection.py`: `GyroConnection(QObject)` owns one `threading.Thread`, a `serial_factory`, a command queue and a pyqtSignal `state_changed`. Its loop body is a `step()` method, so tests call `step()` with a `FakeSerial` and a fake clock instead of starting a thread.
   - *Alternative:* subclass `EcuConnection`/`EcuConnectionThread`. Rejected: that base class is built around `report_error` (overlay) and `send_command(EcuCommand)`, both of which the inclinometer must not use.

2. **Latest value by query, signal on change.** At 100 Hz, one Qt signal per line would flood the event loop for no gain: the screens refresh at 10 Hz and the analysis needs the latest pitch once per ECU set. So readers call `gyro.snapshot()`; the thread emits `state_changed` only when the derived state or the last message differs from what it announced before, checked after every line and on every read timeout (0.1 s), so `no signal` is noticed about 1.1 s after the last line.

3. **Zero tracked from the device's answer.** The flag follows `#M;Zero definido;`, not the sent command, and is cleared by every event that can lose the zero (port opened, `#H`, `t_ms` going back, `Zero removido`, `Calibrando...`, port closed). No auto-zero exists anywhere; the user decides when the car is level. After `Calibracao ok` the flag stays false because the protocol does not say whether a recalibration keeps the zero.

4. **Retry and user-closed connection.** `GyroConnection` has a desired state: port name, and a `user_closed` flag set by `disconnect()` and cleared by `connect()` or a port change. The loop reopens every 2 s only when a port is configured and `user_closed` is false. Open errors are logged at debug level only and never use the ECU's `report_error`. Reading uses a 0.1 s serial timeout so commands queued from the UI thread are written within 0.1 s, also while the device is silent.

5. **A registry like the ECU's, with a safe default.** `app/gyro/__init__.py` exposes `register_gyro()` / `get_gyro()`. `get_gyro()` returns a disabled instance when nothing was registered, so screens and `AppWindow` tests never see `None`. Screens still accept an injected `gyro=` argument (the style of `IgnitionTuningScreen(state=…, analysis=…)`), which is what the tests use.

6. **The analysis gets the inclination as an input, not a dependency.** `process()` and `status()` take an optional `tilt: Tilt(required, pitch)` (default: not required), with `pitch` already `None` when the inclinometer is not usable. The analysis tracks `tilt_ok` on every set (required and usable and `|pitch| <= max_tilt_deg`) like it tracks the lambda loop: a false-to-true transition sets `_settle_until`, and false clears `_prev`. When not required, `tilt_ok` is kept false so that a port configured later still settles on its first usable reading. `IgnitionTuningScreen` builds the `Tilt` from `gyro.snapshot()` (`required` = state is not `disabled`).
   - *Alternative:* push the pitch into the telemetry dict as a pseudo-`Signal`. Rejected: the catalog is the ECU's, signals arrive in frames and the pitch arrives on another clock.

7. **Settings applied through an explicit signal, not a global observer.** The Settings screen mutates the config object, saves it, and emits `setting_changed(section, key)`. `AppWindow._register_screens` connects that signal to `IgnitionTuningScreen.on_setting_changed`, the way it already connects the signal processor. The gyro port is applied by the Settings screen calling `gyro.set_port(...)` directly. This avoids a global subscription list that every test-created screen would leak into.
   - On a change of `rpm_min` / `rpm_max` the ignition screen first calls `IgnitionResultsLog.end_run()` (so the previous run is written with the band it was analysed with: the CSV rows read `analysis.rpm_min/rpm_max`) and only then `IgnitionAnalysis.reload_settings()`, which copies the five settings from the config and clears the scenarios when the band differs. `reload_settings()` neither unpauses nor touches the offset or the ECU.
   - *Alternative:* make the analysis read the config live. Rejected: the results CSV and the band label would change under existing scenarios, and the order "write the old run, then clear" would be impossible.

8. **Saving the configuration.** `AppConfig` keeps the path it was loaded from and gets `set_value(section, key, value) -> bool`: it validates that the key exists, `setattr`s the value on the section object (so the running app uses it even when saving fails), then calls the saver. The saver re-reads the file (`{}` if absent; abort and return `False` if it is unreadable or not a JSON object), sets `data[section][key]`, writes `json.dumps(data, indent=2, ensure_ascii=False) + "\n"` to `<file>.tmp` in the same directory and `os.replace`s it. `AppConfig` can be built with an explicit path, so tests use a temporary directory and never the developer's file. The module-level `config` still resolves the path from `MI_DASHBOARD_CONFIG_FILE` or `config.json`.
   - Existing lists such as `"gears": [4, 5]` become multi-line on the first save; this is accepted by the "always indented" rule.

9. **Settings screen model.** Rows are declared as data (kind `choice`, `action` or `number`, with step, bounds as callables so `rpm_min` is bounded by the current `rpm_max`, and a format function) plus a few read-only readout lines. One generic key handler serves all rows. The list of serial ports is injected (`list_ports=`) and the clock-free refresh timer runs at 200 ms only while the screen is active.
   - The rule "every setting has a row" is a test: it walks the public attributes of every section of `AppConfig`, and requires each `section.key` to be either a row key or in `SETTINGS_BACKLOG` (a constant next to the rows that mirrors the list in the `app-configuration` spec), and that the two sets do not overlap. Adding a setting without a row, or leaving a stale backlog entry, fails the suite.

10. **Recalibration speed guard** reads VSS from `vehicle_state`. A VSS never received does not block, because the guard is a convenience for the driver, not a safety interlock (the device only pauses its output for ~2 s).

11. **Rename.** Only text changes: the Home entry, the title of the options screen and the Portuguese labels in tests. The internal screen name `options`, the folder `app/ui/options/` and the capability `options-screen` stay.

12. **Shutdown.** `lifecycle.shutdown(window, ecu_thread, alarm, log_writer, gyro=None)` gets one more isolated step, `("inclinometer", gyro, "stop")`, placed right after the ECU source. `GyroConnection.stop(timeout=1.0)` sets the stop flag, closes the port and joins the thread with that bound (warning on timeout), like `EcuConnectionThread.stop`.

## Risks / Trade-offs

- [Arduino boards reset when the port is opened, so the first seconds after connecting carry no data or a boot header] → `#H` clears the zero flag, `no signal` covers the gap, and the user zeroes afterwards; nothing assumes data at open time.
- [The pitch may still contain the vehicle's longitudinal acceleration (the device filters but does not know the car's speed)] → the settle time after the pitch comes back within the limit and the manual limit absorb short disturbances; verify on the road (manual task) and tune `max_tilt_deg`. Compensating with VSS is left out on purpose.
- [A recalibration may or may not keep the zero (the protocol is silent)] → the app treats the zero as lost and asks for a new one; relaxing this later is a one-line spec change once the firmware behaviour is known.
- [Pressing G on a slope sets the wrong "flat"] → the box shows the pitch right after, `0.0°` is expected on level ground; the user can press G again. No automatic guard on purpose (the user asked for manual zeroing).
- [A configured but absent or broken inclinometer blocks all ignition analysis] → deliberate (the analysis is not trustworthy without it). The status `AGUARDANDO SENSOR` and the box name the reason; `Nenhuma` on the Settings screen turns the requirement off.
- [`config.json` rewritten by the app while the user edits it by hand] → the file is re-read right before each write and only one key changes; two writers in the same instant remain last-write-wins.
- [A power loss during a save] → temporary file plus `os.replace`; the old file stays intact.
- [A band change discards scenarios the user wanted] → the previous run is first written to the results CSV with its own band; the Settings screen is not used while driving, so this is a deliberate action.
- [Leaked temporary file after a failed replace] → the saver removes the temporary file on failure.

## Migration Plan

No data migration. On the first save the existing `config.json` is reformatted (2-space indentation, lists expanded); every key and its order are kept. Without `gyro.port` in the file, behaviour is identical to today. Rollback: remove `gyro.port` (or choose `Nenhuma`); the extra keys the app wrote are ignored by older versions.
