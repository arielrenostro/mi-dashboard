import enum
import math


class Signals(enum.Enum):
    RPM = {
        "name": "RPM",
        "index": 1,
        "converter": lambda x: math.trunc(float(x)),
        "for_label": lambda x: f'{x}',
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
        "converter": lambda x: float(x),
        "for_label": lambda x: f'{math.trunc(x)}  kPa',
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
        "converter": lambda x: round(float(x) / 1000, 2),
        "for_label": lambda x: f'{x:.2f} λ',
        "min": 0.5,
        "max": 1.5,
        "color": "lime",
        "alarm": {
            "enabled": True,
            "min": 0.70,
            "max": 9999.0,
        },
    }

    INJ_UTIL= {
        "name": "Inj. Duty",
        "index": 8,
        "converter": lambda x: math.trunc(float(x)),
        "for_label": lambda x: f'{x} %',
        "min": 0,
        "max": 100,
        "color": "lime",
        "alarm": {
            "enabled": True,
            "min": -999,
            "max": 90,
        },
    }

    IGN = {
        "name": "Ign",
        "index": 10,
        "converter": lambda x: math.trunc(float(x)),
        "for_label": lambda x: f'{x} º',
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
        "converter": lambda x: math.trunc(float(x) - 273),
        "for_label": lambda x: f'{x} ºC',
        "min": -20,
        "max": 120,
        "color": "lime",
        "alarm": {
            "enabled": True,
            "min": 0,
            "max": 95,
        },
    }

    IAT = {
        "name": "IAT",
        "index": 20,
        "converter": lambda x: math.trunc(float(x) - 273),
        "for_label": lambda x: f'{x} ºC',
        "min": -20,
        "max": 120,
        "color": "lime",
        "alarm": {
            "enabled": False,
            "min": 0,
            "max": 80,
        },
    }

    VSS = {
        "name": "Speed",
        "index": 23,
        "converter": lambda x: math.trunc(float(x)),
        "for_label": lambda x: f'{x} km/h',
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
        "converter": lambda x: 'Closed' if x == 0 else 'Open',
        "for_label": lambda x: f'{x}',
        "min": None,
        "max": None,
        "color": "lime",
        "alarm": {
            "enabled": False,
            "min": None,
            "max": None,
        },
    }


    LAMBDA_TARGET = {
        "name": "λ Target",
        "index": 25,
        "converter": lambda x: round(float(x) / 1000, 2),
        "for_label": lambda x: f'{x:.2f} λ',
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
        "converter": lambda x: round((1000 - float(x)) / 10, 2),
        "for_label": lambda x: f'{x:.1f} %',
        "min": -20,
        "max": 20,
        "color": "gray",
        "alarm": {
            "enabled": True,
            "min": -20,
            "max": 20,
        },
    }

    GEAR = {
        "name": "Gear",
        "index": 33,
        "converter": lambda x: math.trunc(float(x)),
        "for_label": lambda x: f'{x}',
        "min": 0,
        "max": 6,
        "color": "lime",
        "alarm": {
            "enabled": False,
            "min": None,
            "max": None,
        },
    }

