import enum
import math


class Signals(enum.Enum):
    RPM = {
        "name": "RPM",
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
        "index": 2,
        "converter": lambda x: int(x),
        "for_label": lambda x: f'{x}',
        "unit": "kPa",
        "min": 20,
        "max": 200,
        "color": "fuchsia",
        "alarm": {
            "enabled": True,
            "min": 0,
            "max": 165,
        },
    }

    LAMBDA = {
        "name": "λ",
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
        "index": 26,
        "converter": lambda x: (1000 - float(x)) / 10,
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

    PEDAL = {
        "name": "Pedal",
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

    POWER = {
        "name": "Power",
        "calculated": True,
        "value": lambda x:
        (((x[Signals.MAP]['value'] * x[Signals.VE]['value'] * 10 * 0.001587 * x[Signals.RPM]['value'])
          / (287 * (x[Signals.IAT]['value'] + 273) * 2 * 60)
          / (9 * x[Signals.LAMBDA]['value'])) * 3600 * 2.20462) / 0.8,
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
        "value": lambda x: (x[Signals.POWER]['value'] * 716.2) / x[Signals.RPM]['value'],
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
