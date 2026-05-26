# Master Injection Dashboard

A real-time telemetry dashboard for the Master Injection ECU. Streams sensor data over Bluetooth (Windows COM port), displays live values and graphs, plays audible alarms on limit violations, and logs everything to CSV.

![Dashboard](assets/demo.png)

## Demo

![Demo video](assets/demo.mp4)

---

## Features

- **Full-screen live display** — large high-contrast numeric values with automatic color coding (green = in range, red = out of limits)
- **Real-time graphs** — multi-axis buffered plots with peak/min markers, updated every 100 ms
- **Audible alarms** — plays a `.wav` file while any signal stays outside its configured limits; 2-second cooldown prevents spam
- **VE map calibration** — live 16×16 VE map viewer with heatmap coloring, bilinear interpolation highlight of the current operating point, and keyboard-driven ±5 adjustments written to ECU with 1-second debounce
- **Lambda loop control** — open and close the lambda loop from the VE calibration screen with a keystroke; plays a configurable sound on each command
- **CSV logging** — appends every ECU frame with a millisecond Unix timestamp and an optional event label
- **Automatic reconnection** — detects dropped Bluetooth connections and reconnects without restarting the app
- **Mock mode** — replay a previously recorded CSV file instead of connecting to hardware
- **Manual event marking** — press **Enter** during a session to beep and stamp `MARK` on the next CSV row
- **Lambda loop toggle via hold** — hold **Space** for 2 seconds to toggle lambda loop from any screen

---

## Requirements

- Windows (COM port + `.wav` playback)
- Python 3.9+
- Bluetooth-paired ECU device

---

## Installation

```bash
pip install -r requirements.txt
```

Dependencies: `pyserial`, `pyqt6`, `pyqtgraph`.

---

## Running

```bash

# optional
export MI_DASHBOARD_CONFIG_FILE=config.json

python main.py
```

Press **Esc** or close the window to exit.

---

## Configuration

Settings are loaded from `config.json` in the project root or defined by env `MI_DASHBOARD_CONFIG_FILE`. If the file is absent, defaults apply.

```json
{
  "connection": {
    "port": "COM1",
    "baudrate": 115200,
    "mock": ""
  },
  "alarm": {
    "sound": "alarm.wav"
  },
  "dashboard": {
    "grid": [["RPM", "VSS", "MAP", "BOOST", "CLT", "IAT", "POWER"],
             ["LAMBDA", "LAMBDA_TARGET", "FUEL_TRIM", "BOOST_TARGET", "INJ_UTIL", "IGN", "TORQUE"]],
    "graph": [["RPM", "MAP"], ["LAMBDA", "LAMBDA_TARGET", "FUEL_TRIM"]],
    "graph_x_size": 150
  },
  "ve_calibration": {
    "ve_sound": "alarm.wav",
    "closed_sound": "alarm.wav",
    "open_sound": "alarm.wav"
  }
}
```

| Key | Description |
|-----|-------------|
| `connection.port` | Windows COM port (`"COM5"`, etc.) |
| `connection.baudrate` | Serial baud rate |
| `connection.mock` | Path to a recorded CSV for playback without hardware; `""` to use real serial |
| `alarm.sound` | `.wav` file played during limit alarms |
| `dashboard.grid` | 2-D list of signal names for the numeric display grid |
| `dashboard.graph` | List of row groups (each group shares one plot) |
| `dashboard.graph_x_size` | Number of samples kept in each graph buffer |
| `ve_calibration.*_sound` | `.wav` files for VE edit, loop-close, and loop-open events |

Signal definitions (name, ECU index, unit, limits, graph color, alarm thresholds) are in `app/masterinjection/signal.py`.

---

## Screens

The app uses a full-screen stacked layout. Navigation between screens is keyboard-only. **Esc** always returns to the Home screen (or closes the app if already on Home).

---

### Home Screen

The entry point of the application. Displays the app title, connection status, and a navigable menu.

**Layout:**
- Title: `Master Injection` centered at the top
- Connection status: port/baudrate (or mock file path) + a colored dot — green when connected, red when disconnected. Refreshed every 500 ms.
- Menu items: `Dashboard` and `Calibração de VE`
- Keyboard hint at the bottom

**Keyboard:**

| Key | Action |
|-----|--------|
| **↑ / ↓** | Move selection up/down |
| **Enter** | Open the selected screen |
| **Esc** | Exit the application |

---

### Dashboard Screen

Full-screen live telemetry display. Shows all active signals as numeric cards and plots them on real-time graphs.

**Layout:**
- **Signal grid** — rows and columns configured in `dashboard.grid` (`config.json`). Each cell is a `SignalCard` showing the signal name, current value, and unit. Color is green by default and turns red when the value is outside alarm limits.
- **Graphs** — one plot per group in `dashboard.graph`. Each plot can show multiple signals on independent Y-axes (right-side), with a shared X-axis. Every signal has its own color defined in `signal.py`. Peak and minimum markers with value labels float over each curve. Graphs refresh every 100 ms.

**Behavior:**
- Cards turn red when a limit is crossed. A visual flash (alternating black/yellow background) is triggered when an alarm fires.
- Graph buffers keep the last `graph_x_size` samples (default 150). Older data scrolls out of view.

**Keyboard:**

| Key | Action |
|-----|--------|
| **Esc** | Return to Home screen |

---

### VE Calibration Screen

Live VE (Volumetric Efficiency) map viewer and editor. Allows real-time adjustment of the ECU's 16×16 fuel map while the engine is running, with visual feedback of the current operating point.

**Layout:**

- **Top bar** — a row of `SignalCard` widgets showing live values for: RPM, MAP, VE, Lambda, Lambda Target, Fuel Trim, and Lambda Loop state. `LAMBDA_LOOP` is colored green (closed loop) or orange (open loop). Refreshed every 100 ms.
- **VE Map table (left panel)** — 16×16 grid. Rows are MAP (kPa) values (high at top, low at bottom); columns are RPM values. Cells are colored with a heatmap: dark blue (low VE) → green → yellow → red (high VE). The cells surrounding the current operating point are highlighted in orange, weighted by bilinear interpolation. Modified cells are shown in cyan text.
- **VE Graph (right panel)** — line chart with one curve per MAP row (blue = low MAP, orange = high MAP). Shows the shape of the entire VE map across RPM. Overlaid scatter points mark all 256 map nodes; the active interpolation region is highlighted. A lime dot marks the current VE reading from the ECU; a cyan dot marks the predicted `VE_LAMBDA` value (visible only in closed loop).
- **Footer** — keyboard hint bar.

**Behavior:**
- Operating point is computed every 100 ms from the latest RPM and MAP values using bilinear interpolation weights.
- VE adjustments are debounced 1 second before sending the `WRITE_ON_MEMORY` command to the ECU.
- A `.wav` sound plays on each VE adjustment, loop open, and loop close.
- Resetting the map reverts all cells to original values.

**Keyboard:**

| Key | Action |
|-----|--------|
| **↑** | Increase VE by +5 at the current operating point |
| **↓** | Decrease VE by −5 at the current operating point |
| **O** | Send `LAMBDA_LOOP_OPEN` command to ECU + play sound |
| **P** | Send `LAMBDA_LOOP_CLOSE` command to ECU + play sound |
| **R** | Reset all VE cells to original (pre-session) values |
| **Esc** | Return to Home screen |

---

## Keyboard shortcuts

| Key | Screen | Action | Status |
|-----|--------|--------|--------|
| **Esc** | Any | Return to Home screen (or exit from Home) | Active |
| **↑ / ↓** | Home | Navigate menu | Active |
| **Enter** | Home | Open selected screen | Active |
| **↑ / ↓** | VE Calibration | Adjust VE ±5 at current operating point | Active |
| **O** | VE Calibration | Open lambda loop | Active |
| **P** | VE Calibration | Close lambda loop | Active |
| **R** | VE Calibration | Reset all VE cells to original values | Active |
| **Enter** | Any | Beep + stamp `MARK` on the next CSV row | Active |
| **Space** (hold 2 s) | Any | Toggle lambda loop open ↔ closed | Active |

---

## CSV Format

Each row corresponds to one ECU frame:

```
Timestamp;Event;Mess 1;RPM;MAP;...
1709041234567;;#D01;5000;120;...
1709041234667;MARK;#D01;5100;121;...
```

| Column            | Content                                                        |
|-------------------|----------------------------------------------------------------|
| `Timestamp`       | Unix time in milliseconds                                      |
| `Event`           | `MARK` when Enter was pressed before this row; otherwise empty |
| Remaining columns | Raw ECU fields from the `#D01` and `#D02` frames              |

---

## ECU Protocol

The ECU streams two frame types per cycle over serial:

- `#D01;val1;val2;...` — primary sensor data  
- `#D02;val1;val2;...` — secondary sensor data

The app waits for one of each, joins them with `;`, and processes the combined frame as a single row. Only `#D01`-prefixed frames are logged to CSV.

---

## ECU Data Fields

The combined `#D01;...;#D02;...` frame contains 34 fields (index 0–33). Fields marked **dashboard** are actively displayed and graphed; others are logged to CSV only.

| Index | CSV column        | Sample  | Displayed value       | Notes                                           |
|-------|-------------------|---------|-----------------------|-------------------------------------------------|
| 0     | Mess 1            | `#D01`  | —                     | Frame type marker                               |
| 1     | RPM               | `1055`  | **1055 RPM**          | Direct value                                    |
| 2     | MAP               | `44`    | **44 kPa**            | Manifold absolute pressure                      |
| 3     | Boost             | `104`   | **104 kPa**           | Post-turbo MAP                                  |
| 4     | Load %            | `33`    | —                     | Engine load                                     |
| 5     | Idle              | `33`    | —                     | Idle correction                                 |
| 6     | Lambda 1          | `903`   | **0.90 λ**            | ÷ 1000                                          |
| 7     | Inj. Pulse        | `176`   | —                     | Injection pulse width (raw)                     |
| 8     | Inj. Utiliz.      | `3`     | **3 %**               | Injector duty cycle                             |
| 9     | VE Value          | `627`   | **62.7 %**            | ÷ 10                                            |
| 10    | Ign. Adv.         | `14`    | **14 °**              | Ignition advance                                |
| 11    | Knock             | `0`     | —                     | Knock count                                     |
| 12    | A/C Input         | `0001`  | —                     | Binary digital inputs (4 bits)                  |
| 13    | Start Input       | `1000`  | —                     | Binary digital inputs (4 bits)                  |
| 14    | Outputs 1         | `1101`  | —                     | Binary digital outputs (4 bits)                 |
| 15    | Outputs 2         | `00`    | —                     | Binary digital outputs (2 bits)                 |
| 16    | Lambda 2          | `0`     | —                     | Secondary lambda (0 = not connected)            |
| 17    | Mess 2            | `#D02`  | —                     | Frame type marker                               |
| 18    | Batt Volt.        | `138`   | —                     | ÷ 10 → V (13.8 V)                               |
| 19    | CLT               | `342`   | **69 °C**             | K − 273 (coolant temperature)                   |
| 20    | IAT               | `296`   | **23 °C**             | K − 273 (intake air temperature)                |
| 21    | Inj. DT           | `580`   | —                     | Injector dead time (raw)                        |
| 22    | Ign. Dwell        | `357`   | —                     | Ignition dwell time (raw)                       |
| 23    | KM/H              | `4`     | **4 km/h**            | Vehicle speed                                   |
| 24    | Lambda Loop       | `0`     | **Open**              | 0 = Open loop, 1 = Closed loop                  |
| 25    | Lambda Target     | `1000`  | **1.00 λ**            | ÷ 1000                                          |
| 26    | Lambda Corr       | `1001`  | **−0.1 %**            | (1000 − x) ÷ 10 (fuel trim correction)          |
| 27    | Strobo Angle      | `1170`  | —                     | Strobe timing angle (raw)                       |
| 28    | Turbo Target      | `150`   | **150 kPa**           | Boost target                                    |
| 29    | ACC %             | `0`     | **0.0 %**             | Throttle pedal position; (x ÷ 990) × 100, max 100 |
| 30    | ACP %             | `1013`  | —                     | Throttle position controller output (raw)       |
| 31    | dACC %            | `5000`  | —                     | Delta accelerator (raw)                         |
| 32    | *(reserved)*      | `0`     | —                     |                                                 |
| 33    | *(Gear)*          | `1`     | **1**                 | Current gear (header label `0` is a firmware artifact) |

---

## Pending features

- **ECU startup sync** — sending `RPM_BREAKPOINTS`, `MAP_BREAKPOINTS`, and all 16 VE rows on connect to pre-populate the live VE map on startup.

---

Two signals are **calculated** by the app and not present in the raw stream:

| Signal  | Formula                                                  | Unit   |
|---------|----------------------------------------------------------|--------|
| Power   | Derived from MAP, VE, RPM, IAT, λ via air-mass equation  | HP     |
| Torque  | Power × 716.2 ÷ RPM                                      | kgf·m  |
