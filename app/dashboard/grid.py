SIGNALS_VIEW = {
    "map": {
        "color": "fuchsia",
        "alarm": True,
        "min": 0,
        "max": 165,
    },
    "rpm": {
        "color": "red",
        "alarm": False,
        "min": 0,
        "max": 6400,
    },
    "vss": {
        "color": "blue",
        "alarm": False,
        "min": 0,
        "max": 150,
    },
    "lambda": {
        "color": "lime",
        "alarm": False,
        "min": 0.75,
        "max": 1.1,
    },
    "fuel_trim": {
        "color": "gray",
        "alarm": False,
        "min": -4,
        "max": 4,
    },
    "lambda_target": {
        "color": "blue",
        "alarm": False,
        "min": 0,
        "max": 2,
    },
    "ign": {
        "color": "lime",
        "alarm": False,
        "min": 0,
        "max": 40,
    },
    "inj_util": {
        "color": "lime",
        "alarm": False,
        "min": 0,
        "max": 90,
    },
}

GRAPH = [
    ["lambda", "lambda_target", "fuel_trim"],
    ["rpm", "vss", "map"],
]

GRID = [
    ["rpm", "vss", "map", "ign"],
    ["lambda", "lambda_target", "fuel_trim", "inj_util"],
]
