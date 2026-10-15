import json
import logging
import os
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_MAX_TILT_DEG = 3


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
        self.max_tilt_deg: float = self._tilt(config_dict.get('max_tilt_deg'))

    @staticmethod
    def _gears(value) -> list[int]:
        """A non-empty list of integers; anything else takes the default [5]."""
        if isinstance(value, list) and value and all(isinstance(g, int) and not isinstance(g, bool) for g in value):
            return list(value)
        return [5]

    @staticmethod
    def _tilt(value) -> float:
        """A number greater than 0; anything else takes the default."""
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            return value
        return DEFAULT_MAX_TILT_DEG


class AppConfigGyro:

    def __init__(self, config_dict: dict):
        port = config_dict.get('port', '')
        self.port: str = port if isinstance(port, str) else ''


class AppConfigConnection:

    def __init__(self, config_dict: dict):
        self.mock: str = config_dict.get('mock', '')
        self.mock_skip_lines: int = config_dict.get('mock_skip_lines', 0)
        self.port: str = config_dict.get('port', '')
        self.baudrate: int = config_dict.get('baudrate', 115200)


class AppConfig:

    def __init__(self, config_dict: dict, path: Optional[str] = None):
        self.path = path  # the file the settings came from (and are saved to); None when there is none
        self.dashboard = AppConfigDashboard(config_dict.get('dashboard', {}))
        self.alarm = AppConfigAlarm(config_dict.get('alarm', {}))
        self.connection = AppConfigConnection(config_dict.get('connection', {}))
        self.ve_calibration = AppConfigVeCalibration(config_dict.get('ve_calibration', {}))
        self.datalog = AppConfigDatalog(config_dict.get('datalog', {}))
        self.ignition_tuning = AppConfigIgnitionTuning(config_dict.get('ignition_tuning', {}))
        self.gyro = AppConfigGyro(config_dict.get('gyro', {}))

    def sections(self) -> dict:
        """Every section object by its name in the file."""
        return {name: value for name, value in vars(self).items() if not name.startswith('_') and name != 'path'}

    def keys(self) -> set:
        """Every setting as `section.key`."""
        return {f"{name}.{key}" for name, section in self.sections().items() for key in vars(section)}

    def set_value(self, section: str, key: str, value: Any) -> bool:
        """
        Change a setting. The running app uses the new value whatever happens next; then it is saved to the
        file. Returns whether it was saved.
        """
        target = self.sections().get(section)
        if target is None or key not in vars(target):
            raise KeyError(f"{section}.{key}")
        setattr(target, key, value)
        return self._save(section, key, value)

    def _save(self, section: str, key: str, value: Any) -> bool:
        """
        Read the file again, change only this key, and write the whole content back indented through a
        temporary file. An unreadable file, or one that is not a JSON object, is left untouched.
        """
        if not self.path:
            return False
        temporary = f"{self.path}.tmp"
        try:
            data = {}
            if os.path.exists(self.path):
                with open(self.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("the configuration file is not a JSON object")
            content = data.setdefault(section, {})
            if not isinstance(content, dict):
                raise ValueError(f"'{section}' is not a JSON object")
            content[key] = value
            with open(temporary, 'w', encoding='utf-8') as f:
                f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            os.replace(temporary, self.path)
            return True
        except Exception:
            logger.warning("Could not save the configuration to %s", self.path, exc_info=True)
            try:
                os.remove(temporary)
            except OSError:
                pass
            return False


def _setup_config():
    config_path = os.getenv('MI_DASHBOARD_CONFIG_FILE', 'config.json')
    config_dict = dict()
    if os.path.isfile(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config_dict = json.loads(f.read())
    return AppConfig(config_dict, config_path)


config: AppConfig = _setup_config()
