# Master Injection Dashboard

A real-time telemetry dashboard for the Master Injection ECU. Streams sensor data over Bluetooth (Windows COM port), displays live values and graphs, plays audible alarms on limit violations, logs everything to CSV, and helps tune the engine from the driver's seat: VE map calibration and on-road ignition tuning, with an optional inclinometer so the tuning only samples on level ground.

![Dashboard](docs/demo.png)

## Demo

![Demo video](docs/demo.mp4)

---

## How the pieces fit

```
                 Bluetooth (COM port)
+-----+  frames  +--------------------+  serial  +-----------------------+
| ECU | -------> |  Dashboard (PC)    | <------- | Inclinometer          |
|     | <------- |  dashboard/        |  (opt.)  | inclinometer/         |
+-----+ commands +--------------------+          +-----------------------+
                  screens, alarms, CSV log
```

- The **dashboard app** (`dashboard/`) reads the ECU, shows everything, writes VE and ignition maps back to the ECU RAM and logs to CSV.
- The **inclinometer** (`inclinometer/`) is an optional Arduino with an MPU-6500 that tells the ignition tuning when the car is on a slope.

## Features

- **Full-screen live display**: large high-contrast numeric values with automatic color coding (green = in range, red = out of limits)
- **Real-time graphs**: multi-axis buffered plots with peak/min markers
- **Audible and visual alarms**: a sound plays and the signal's card flashes while a signal with an enabled alarm stays outside its limits
- **VE map calibration**: live 16×16 VE map with heatmap, a cursor that follows the car's RPM and MAP, and keyboard-driven adjustments written to the ECU
- **Lambda loop control**: open and close the lambda loop from the VE calibration screen
- **Ignition tuning**: on-road search for the best spark advance at light load, comparing injection time, MAP and pedal at the same RPM and gear, one advance offset at a time
- **Inclinometer (optional)**: the ignition analysis only samples when the car is level
- **ECU screen**: change the engine phase (Negativa / Positiva) from the car, without saving it to the ECU memory
- **Settings screen**: edit the settings from the keyboard and manage the inclinometer
- **CSV logging**: one file per run, every ECU frame with a timestamp and an optional event label (mark events with **Enter**)
- **Keyboard-only navigation**: **F1** Dashboard, **F2** VE calibration, **F3** Ignition tuning, **F4** ECU, **F12** Settings, from any screen
- **Automatic reconnection**: detects dropped Bluetooth connections and reconnects without restarting the app
- **Mock mode**: replay a previously recorded CSV file instead of connecting to hardware

![VE calibration screen](docs/ve_calibration.png)

![Ignition tuning screen](docs/ignition_tuning.png)

*Ignition tuning screenshot with illustrative data (two gears, six offsets from 0° to +5°, best result at +4°, inclinometer zeroed at +0.6°), not a real tuning session.*

---

## Repository layout

```
dashboard/      the dashboard app: code, tests, sounds, config.json, requirements
inclinometer/   the optional inclinometer (Arduino firmware and documentation)
docs/           images and video used by the READMEs
openspec/       specifications (one folder per capability) and change history
CLAUDE.md       guidance for Claude Code in this repository
```

## Where to go next

- **[dashboard/README.md](dashboard/README.md)**: requirements, installation, running, tests, configuration, every screen and every keyboard shortcut.
- **[inclinometer/README.md](inclinometer/README.md)**: the inclinometer hardware, the serial protocol and how the zero and the calibration work.
- **[openspec/specs/](openspec/specs/)**: the behavior of the system, specified with [OpenSpec](https://github.com/Fission-AI/OpenSpec). Planned and in-flight work lives in [openspec/changes/](openspec/changes/).
