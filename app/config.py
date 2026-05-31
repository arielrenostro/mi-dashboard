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
        self.graph_x_seconds: int = config_dict.get('graph_x_seconds', 30)
        self.graph_x_size: int = self.graph_x_seconds * 60


class AppConfigAlarm:

    def __init__(self, config_dict: dict):
        self.sound: str = config_dict.get('sound', 'alarm.wav')


class AppConfigDatalog:

    def __init__(self, config_dict: dict):
        self.path: str = config_dict.get('path', os.path.pathsep)


class AppConfigVeCalibration:

    def __init__(self, config_dict: dict):
        self.ve_sound: str = config_dict.get('ve_sound', 'alarm.wav')
        self.closed_sound: str = config_dict.get('closed_sound', 'alarm.wav')
        self.open_sound: str = config_dict.get('open_sound', 'alarm.wav')


class AppConfigConnection:

    def __init__(self, config_dict: dict):
        self.mock: str = config_dict.get('mock', '')
        self.port: str = config_dict.get('port', '')
        self.baudrate: int = config_dict.get('baudrate', 115200)


class AppConfig:

    def __init__(self, config_dict: dict):
        self.dashboard = AppConfigDashboard(config_dict.get('dashboard', {}))
        self.alarm = AppConfigAlarm(config_dict.get('alarm', {}))
        self.connection = AppConfigConnection(config_dict.get('connection', {}))
        self.ve_calibration = AppConfigVeCalibration(config_dict.get('ve_calibration', {}))
        self.datalog = AppConfigDatalog(config_dict.get('datalog', {}))


def _setup_config():
    config_path = os.getenv('MI_DASHBOARD_CONFIG_FILE', 'config.json')
    config_dict = dict()
    if os.path.isfile(config_path):
        with open(config_path, 'r') as f:
            config_dict = json.loads(f.read())
    return AppConfig(config_dict)


config: AppConfig = _setup_config()
