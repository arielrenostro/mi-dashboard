import enum
from typing import Any


class Signal(enum.Enum):
    RPM = {
        "name": "RPM",
        "frame": "D01",
        "frame_index": 1,
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
        "frame": "D01",
        "frame_index": 2,
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
        "frame": "D01",
        "frame_index": 3,
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
        "frame": "D01",
        "frame_index": 6,
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
        "frame": "D01",
        "frame_index": 8,
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
        "frame": "D01",
        "frame_index": 9,
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
        "frame": "D01",
        "frame_index": 10,
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

    CLT = {
        "name": "CLT",
        "frame": "D01",
        "frame_index": 19,
        "index": 19,
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
        "frame": "D01",
        "frame_index": 20,
        "index": 20,
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
        "frame": "D01",
        "frame_index": 23,
        "index": 23,
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
        "frame": "D01",
        "frame_index": 24,
        "index": 24,
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
        "frame": "D01",
        "frame_index": 25,
        "index": 25,
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
        "frame": "D01",
        "frame_index": 26,
        "index": 26,
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
        "frame": "D01",
        "frame_index": 28,
        "index": 28,
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
        "frame": "D01",
        "frame_index": 29,
        "index": 29,
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
        "frame": "D01",
        "frame_index": 33,
        "index": 33,
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

    VE_LAMBDA = {
        "name": "VE λ",
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
