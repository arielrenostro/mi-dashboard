# Customized Monitoring Dashboard for Master Injection

Customized Monitoring Dashboard for Master Injection is a real-time serial telemetry dashboard designed for high-frequency automotive data streaming over Bluetooth (Windows COM port).

![Example Image](assets/img.png)

### Video

<!-- https://github.com/arielrenostro/mi-dashboard/raw/refs/heads/main/assets/video.webm -->
<video width="100%" controls>
  <source src="https://github.com/arielrenostro/mi-dashboard/raw/refs/heads/main/assets/video.mp4" type="video/mp4">
  Your browser does not support the video tag.
</video>

It provides:

* Live full-screen dashboard display
* Configurable internal signal definitions (hardcoded)
* Real-time plotting
* Audible limit alarms
* Automatic Bluetooth reconnection
* Filtered CSV logging with millisecond timestamps
* Thread-safe Qt architecture

Built for robustness in unstable Bluetooth environments and high-rate ECU streaming.

---

# Features

## Real-Time Dashboard

* Full-screen adaptive layout
* Large high-contrast numeric display
* Automatic color changes based on limits:

  * Red → Below minimum
  * Green → Within range
  * Red → Above maximum

## Internal Signal Configuration

Signals are defined internally in the `SIGNALS` list:

Each signal includes:

* Name
* CSV column index
* Minimum limit
* Maximum limit
* Conversion function
* Graph enabled/disabled
* Alarm enabled/disabled

Example:

```python
SIGNALS = [
    {
        "name": "MAP",
        "index": 2,
        "min": 20,
        "max": 110,
        "func": lambda x: x,
        "labelFunc": lambda x: f'{trunc(x)}  kPa',
        "graph": True,
        "alarm": True
    }
]
```

No runtime configuration is exposed to the user.

---

## Audible Alerts

* Triggered when value exceeds limits
* 2-second cooldown to prevent alarm spam
* Windows `winsound.Beep()` implementation
* Easily customizable

---

## Automatic Bluetooth Reconnection

If the serial connection drops:

* Port is closed
* Automatic reconnect attempts every 3 seconds
* `#D01\n` command is resent upon reconnection
* Dashboard continues operating

---

## CSV Logging

Logs only lines where the first column matches a defined prefix:

```python
LOG_PREFIX = "#D01"
```

Output format:

```
timestamp_ms,original_stream_line...
```

Example:

```
1709041234567,#D01,1500,98.4,12.3
```

Timestamp is always the first column (Unix time in milliseconds).

---

# Architecture

## Thread-Safe Design

Uses:

* `QThread` for serial communication
* `pyqtSignal` for safe UI updates
* Qt event loop for rendering

UI is never updated from background threads.

This prevents:

* Random UI freezes
* Race conditions
* Event loop corruption

---

## Components

* SerialWorker (QThread)
* Dashboard (Qt UI)
* Internal signal registry
* Buffered plotting (pyqtgraph)
* CSV logger

---

# Requirements

* Windows (for winsound)
* Python 3.9+
* Bluetooth serial device

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Configuration

Edit the following section inside the code:

```python
PORT = "COM5"
BAUDRATE = 115200
LOG_PREFIX = "#D01"
LOG_FILE = "log_stream.csv"
ALARM_COOLDOWN = 0.1
```

Add or modify signals in the `SIGNALS` list.

---

# How It Works

1. Application launches full screen
2. SerialWorker attempts connection
3. Sends:

   ```
   #D01\n
   ```
4. Streaming begins
5. Lines are:
   * Filtered
   * Logged
   * Parsed
   * Displayed
   * Graphed
   * Checked for alarms
