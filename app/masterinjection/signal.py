import enum
from typing import Any

from app.event.app_events import EcuFrameType


class Signal(enum.Enum):
    # ── D01 signals (frame indices are relative to D01 frame, 1-based) ──────
    RPM = {
        "name": "RPM",
        "frame": EcuFrameType.D01,
        "index": 1,
        "converter": lambda x: int(x),
        "for_label": lambda x: f'{x}',
        "unit": "RPM",
        "min": 0,
        "max": 7000,
        "color": "red",
        "alarm": {
            "enabled": True,
            "min": 0,
            "max": 6600,
        },
    }

    MAP = {
        "name": "MAP",
        "frame": EcuFrameType.D01,
        "index": 2,
        "converter": lambda x: int(x),
        "for_label": lambda x: f'{x}',
        "unit": "kPa",
        "min": 20,
        "max": 250,
        "color": "fuchsia",
        "alarm": {
            "enabled": True,
            "min": 0,
            "max": 165,
        },
    }

    BOOST = {
        "name": "Boost",
        "frame": EcuFrameType.D01,
        "index": 3,
        "converter": lambda x: int(x),
        "for_label": lambda x: f'{x}',
        "unit": "kPa",
        "min": 20,
        "max": 250,
        "color": "blue",
        "alarm": {
            "enabled": False,
            "min": 0,
            "max": 165,
        },
    }

    LAMBDA = {
        "name": "λ",
        "frame": EcuFrameType.D01,
        "index": 6,
        "converter": lambda x: float(x) / 1000,
        "for_label": lambda x: f'{x:.2f}',
        "unit": "λ",
        "min": 0.5,
        "max": 1.5,
        "color": "lime",
        "alarm": {
            "enabled": False,
            "min": 0.70,
            "max": 9999.0,
        },
    }

    INJ_UTIL = {
        "name": "Inj. Duty",
        "frame": EcuFrameType.D01,
        "index": 8,
        "converter": lambda x: int(x),
        "for_label": lambda x: f'{x}',
        "unit": "%",
        "min": 0,
        "max": 100,
        "color": "lime",
        "alarm": {
            "enabled": True,
            "min": -999,
            "max": 90,
        },
    }

    VE = {
        "name": "VE",
        "frame": EcuFrameType.D01,
        "index": 9,
        "converter": lambda x: float(x) / 10,
        "for_label": lambda x: f'{x:.1f}',
        "unit": "%",
        "min": 0,
        "max": 1200,
        "color": "lime",
        "alarm": {
            "enabled": False,
            "min": None,
            "max": None,
        },
    }

    IGN = {
        "name": "Ign",
        "frame": EcuFrameType.D01,
        "index": 10,
        "converter": lambda x: int(x),
        "for_label": lambda x: f'{x}',
        "unit": "º",
        "min": -45,
        "max": 45,
        "color": "lime",
        "alarm": {
            "enabled": False,
            "min": 0,
            "max": 40,
        },
    }

    # ── D02 signals (frame indices are relative to D02 frame, 1-based) ──────
    # D02 relative index = original joined-string index - 17
    # (D01 has 16 values at joined positions 1-16; #D02 marker is at position 17)

    CLT = {
        "name": "CLT",
        "frame": EcuFrameType.D02,
        "index": 2,   # joined index was 19; 19 - 17 = 2
        "converter": lambda x: int(x) - 273,
        "for_label": lambda x: f'{x}',
        "unit": "ºC",
        "min": -20,
        "max": 120,
        "color": "orange",
        "alarm": {
            "enabled": True,
            "min": 0,
            "max": 95,
        },
    }

    IAT = {
        "name": "IAT",
        "frame": EcuFrameType.D02,
        "index": 3,   # joined index was 20; 20 - 17 = 3
        "converter": lambda x: int(x) - 273,
        "for_label": lambda x: f'{x}',
        "unit": "ºC",
        "min": -20,
        "max": 120,
        "color": "DodgerBlue",
        "alarm": {
            "enabled": False,
            "min": 0,
            "max": 80,
        },
    }

    VSS = {
        "name": "Speed",
        "frame": EcuFrameType.D02,
        "index": 6,   # joined index was 23; 23 - 17 = 6
        "converter": lambda x: int(x),
        "for_label": lambda x: f'{x}',
        "unit": "km/h",
        "min": 0,
        "max": 200,
        "color": "blue",
        "alarm": {
            "enabled": True,
            "min": 0,
            "max": 150,
        },
    }

    LAMBDA_LOOP = {
        "name": "λ Loop",
        "frame": EcuFrameType.D02,
        "index": 7,   # joined index was 24; 24 - 17 = 7
        "converter": lambda x: int(x),
        "for_label": lambda x: 'Closed' if x == 1 else 'Open',
        "unit": "",
        "min": 0,
        "max": 2,
        "color": "orange",
        "alarm": {
            "enabled": False,
            "min": None,
            "max": None,
        },
    }

    LAMBDA_TARGET = {
        "name": "λ Target",
        "frame": EcuFrameType.D02,
        "index": 8,   # joined index was 25; 25 - 17 = 8
        "converter": lambda x: float(x) / 1000,
        "for_label": lambda x: f'{x:.2f}',
        "unit": "λ",
        "min": 0.5,
        "max": 1.5,
        "color": "blue",
        "alarm": {
            "enabled": False,
            "min": 0.70,
            "max": 1.30,
        },
    }

    FUEL_TRIM = {
        "name": "Fuel Trim",
        "frame": EcuFrameType.D02,
        "index": 9,   # joined index was 26; 26 - 17 = 9
        "converter": lambda x: (float(x) - 1000) / 10,
        "for_label": lambda x: f'{x:.1f}',
        "unit": "%",
        "min": -20,
        "max": 20,
        "color": "gray",
        "alarm": {
            "enabled": True,
            "min": -20,
            "max": 20,
        },
    }

    BOOST_TARGET = {
        "name": "Boost Target",
        "frame": EcuFrameType.D02,
        "index": 11,  # joined index was 28; 28 - 17 = 11
        "converter": lambda x: int(x),
        "for_label": lambda x: f'{x}',
        "unit": "kPa",
        "min": 20,
        "max": 250,
        "color": "MediumSeaGreen",
        "alarm": {
            "enabled": False,
            "min": None,
            "max": None,
        },
    }

    PEDAL = {
        "name": "Pedal",
        "frame": EcuFrameType.D02,
        "index": 12,  # joined index was 29; 29 - 17 = 12
        "converter": lambda x: min(100.00, (float(x) / 990.0) * 100.0),
        "for_label": lambda x: f'{x:.1f}',
        "unit": "%",
        "min": 0,
        "max": 100,
        "color": "MediumSeaGreen",
        "alarm": {
            "enabled": False,
            "min": None,
            "max": None,
        },
    }

    GEAR = {
        "name": "Gear",
        "frame": EcuFrameType.D02,
        "index": 16,  # joined index was 33; 33 - 17 = 16
        "converter": lambda x: int(x),
        "for_label": lambda x: f'{x}',
        "unit": "",
        "min": 0,
        "max": 6,
        "color": "lime",
        "alarm": {
            "enabled": False,
            "min": None,
            "max": None,
        },
    }

    # ── Calculated signals (depend on D01 + D02 signals above) ──────────────

    VE_LAMBDA = {
        "name": "VE λ",
        "frame": None,
        "calculated": True,
        "value": lambda x: (
            int(x[Signal.LAMBDA].raw) + int(x[Signal.FUEL_TRIM].raw) - int(x[Signal.LAMBDA_TARGET].raw)
        ) * int(x[Signal.VE].raw) / 10000,
        "for_label": lambda x: f'{x:.2f}',
        "unit": "",
        "min": 0,
        "max": 200,
        "color": "cyan",
        "alarm": {
            "enabled": False,
            "min": None,
            "max": None,
        },
    }

    POWER = {
        "name": "Power",
        "frame": None,
        "calculated": True,
        "value": lambda x:
        (((x[Signal.MAP].value * x[Signal.VE].value * 10 * 0.001587 * x[Signal.RPM].value)
          / (287 * (x[Signal.IAT].value + 273) * 2 * 60)
          / (9 * x[Signal.LAMBDA].value)) * 3600 * 2.20462) / 0.8,
        "for_label": lambda x: f'{x:.1f}',
        "unit": "HP",
        "min": 0,
        "max": 270,
        "color": "lime",
        "alarm": {
            "enabled": False,
            "min": None,
            "max": None,
        },
    }

    TORQUE = {
        "name": "Torque",
        "frame": None,
        "calculated": True,
        "value": lambda x: (x[Signal.POWER].value * 716.2) / max(x[Signal.RPM].value, 1),
        "for_label": lambda x: f'{x:.1f}',
        "unit": "Kgf.m",
        "min": 0,
        "max": 30,
        "color": "blue",
        "alarm": {
            "enabled": False,
            "min": None,
            "max": None,
        },
    }


class ParsedSignal:

    def __init__(self, signal: Signal, raw: str | int, value: Any):
        self.signal = signal
        self.raw = raw
        self.value = value
        self.value_str = signal.value["for_label"](value)
