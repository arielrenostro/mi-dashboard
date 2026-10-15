import json
import os
from typing import List


class AppConfigDashboard:

    def __init__(self, config_dict: dict):
        self.graph: List[List[str]] = config_dict.get('graph', [
            ['RPM', 'MAP'],
            ['LAMBDA', 'LAMBDA_TARGET', 'FUEL_TRIM']
        ])
        self.grid: List[List[str]] = config_dict.get('grid', [
            ["RPM", "VSS", "MAP", "BOOST", "CLT", "IAT", "POWER"],
            ["LAMBDA", "LAMBDA_TARGET", "FUEL_TRIM", "BOOST_TARGET", "INJ_UTIL", "IGN", "TORQUE"]
        ])
        self.graph_x_size: int = config_dict.get('graph_x_size', 150)


class AppConfigAlarm:

    def __init__(self, config_dict: dict):
        self.sound: str = config_dict.get('sound', 'alarm.wav')


class AppConfigDatalog:

    def __init__(self, config_dict: dict):
        self.path: str = config_dict.get('path', os.path.pathsep)
        self.mark_sound: str = config_dict.get('mark_sound', 'alarm.wav')


class AppConfigVeCalibration:

    def __init__(self, config_dict: dict):
        self.ve_sound: str = config_dict.get('ve_sound', 'alarm.wav')
        self.closed_sound: str = config_dict.get('closed_sound', 'alarm.wav')
        self.open_sound: str = config_dict.get('open_sound', 'alarm.wav')


class AppConfigIgnitionTuning:

    def __init__(self, config_dict: dict):
        self.rpm_min: int = config_dict.get('rpm_min', 2900)
        self.rpm_max: int = config_dict.get('rpm_max', 3100)
        self.gears: list[int] = self._gears(config_dict.get('gears'))
        self.max_map_kpa: int = config_dict.get('max_map_kpa', 70)
        self.max_ignition: int = config_dict.get('max_ignition', 50)
        self.settle_seconds: float = config_dict.get('settle_seconds', 5)
        self.min_scenario_seconds: float = config_dict.get('min_scenario_seconds', 20)
        self.write_sound: str = config_dict.get('write_sound', 'alarm.wav')
        self.ready_sound: str = config_dict.get('ready_sound', 'alarm.wav')
        self.pause_sound: str = config_dict.get('pause_sound', 'alarm.wav')
        self.resume_sound: str = config_dict.get('resume_sound', 'alarm.wav')
        self.discard_sound: str = config_dict.get('discard_sound', 'alarm.wav')

    @staticmethod
    def _gears(value) -> list[int]:
        """A non-empty list of integers; anything else takes the default [5]."""
        if isinstance(value, list) and value and all(isinstance(g, int) and not isinstance(g, bool) for g in value):
            return list(value)
        return [5]


class AppConfigConnection:

    def __init__(self, config_dict: dict):
        self.mock: str = config_dict.get('mock', '')
        self.mock_skip_lines: int = config_dict.get('mock_skip_lines', 0)
        self.port: str = config_dict.get('port', '')
        self.baudrate: int = config_dict.get('baudrate', 115200)


class AppConfig:

    def __init__(self, config_dict: dict):
        self.dashboard = AppConfigDashboard(config_dict.get('dashboard', {}))
        self.alarm = AppConfigAlarm(config_dict.get('alarm', {}))
        self.connection = AppConfigConnection(config_dict.get('connection', {}))
        self.ve_calibration = AppConfigVeCalibration(config_dict.get('ve_calibration', {}))
        self.datalog = AppConfigDatalog(config_dict.get('datalog', {}))
        self.ignition_tuning = AppConfigIgnitionTuning(config_dict.get('ignition_tuning', {}))


def _setup_config():
    config_path = os.getenv('MI_DASHBOARD_CONFIG_FILE', 'config.json')
    config_dict = dict()
    if os.path.isfile(config_path):
        with open(config_path, 'r') as f:
            config_dict = json.loads(f.read())
    return AppConfig(config_dict)


config: AppConfig = _setup_config()
