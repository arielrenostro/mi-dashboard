"""Spec: openspec/specs/app-configuration."""
import json

import pytest

from app.config import _setup_config


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MI_DASHBOARD_CONFIG_FILE", raising=False)
    return tmp_path


def write_json(path, data):
    path.write_text(json.dumps(data))
    return path


def test_defaults_apply_when_no_file_exists(workdir):
    """Scenario: File absent."""
    cfg = _setup_config()

    assert cfg.connection.mock == ""
    assert cfg.connection.port == ""
    assert cfg.connection.baudrate == 115200
    assert cfg.alarm.sound == "alarm.wav"
    assert cfg.dashboard.graph_x_size == 150
    assert cfg.dashboard.graph == [["RPM", "MAP"], ["LAMBDA", "LAMBDA_TARGET", "FUEL_TRIM"]]
    assert cfg.dashboard.grid == [
        ["RPM", "VSS", "MAP", "BOOST", "CLT", "IAT", "POWER"],
        ["LAMBDA", "LAMBDA_TARGET", "FUEL_TRIM", "BOOST_TARGET", "INJ_UTIL", "IGN", "TORQUE"],
    ]
    assert (cfg.ve_calibration.ve_sound, cfg.ve_calibration.closed_sound, cfg.ve_calibration.open_sound) == ("alarm.wav",) * 3


def test_config_json_in_the_working_directory_is_read(workdir):
    """Scenario: Default file name."""
    write_json(workdir / "config.json", {"connection": {"port": "COM5", "baudrate": 9600}})

    cfg = _setup_config()

    assert (cfg.connection.port, cfg.connection.baudrate) == ("COM5", 9600)


def test_environment_variable_overrides_the_default_file(workdir, monkeypatch):
    """Scenario: Environment override."""
    write_json(workdir / "config.json", {"connection": {"port": "COM1"}})
    other = write_json(workdir / "other.json", {"connection": {"port": "COM9"}})
    monkeypatch.setenv("MI_DASHBOARD_CONFIG_FILE", str(other))

    assert _setup_config().connection.port == "COM9"


def test_environment_variable_pointing_to_a_missing_file_uses_defaults(workdir, monkeypatch):
    write_json(workdir / "config.json", {"connection": {"port": "COM1"}})
    monkeypatch.setenv("MI_DASHBOARD_CONFIG_FILE", str(workdir / "missing.json"))

    assert _setup_config().connection.port == ""


def test_missing_keys_take_their_default_independently(workdir):
    """Scenario: Partial section."""
    write_json(workdir / "config.json", {"connection": {"port": "COM5"}})

    cfg = _setup_config()

    assert cfg.connection.port == "COM5"
    assert cfg.connection.baudrate == 115200
    assert cfg.connection.mock == ""


def test_mock_selected_by_configuration(workdir):
    """Scenario: Mock selected by configuration."""
    write_json(workdir / "config.json", {"connection": {"mock": "replay.csv"}})

    assert _setup_config().connection.mock == "replay.csv"


def test_all_documented_settings_are_loaded(workdir):
    """Requirement: Supported settings."""
    write_json(workdir / "config.json", {
        "connection": {"port": "COM7", "baudrate": 57600, "mock": "m.csv"},
        "alarm": {"sound": "a.wav"},
        "datalog": {"path": "logs"},
        "dashboard": {"grid": [["RPM"]], "graph": [["MAP"]], "graph_x_size": 40},
        "ve_calibration": {"ve_sound": "v.wav", "closed_sound": "c.wav", "open_sound": "o.wav"},
    })

    cfg = _setup_config()

    assert (cfg.connection.port, cfg.connection.baudrate, cfg.connection.mock) == ("COM7", 57600, "m.csv")
    assert cfg.alarm.sound == "a.wav"
    assert cfg.datalog.path == "logs"
    assert (cfg.dashboard.grid, cfg.dashboard.graph, cfg.dashboard.graph_x_size) == ([["RPM"]], [["MAP"]], 40)
    assert (cfg.ve_calibration.ve_sound, cfg.ve_calibration.closed_sound, cfg.ve_calibration.open_sound) == ("v.wav", "c.wav", "o.wav")


def test_alarm_limits_in_the_file_are_ignored(workdir):
    """Requirement: Fixed signal definitions / Scenario: Attempt to override limits."""
    from app.masterinjection.signal import Signal

    write_json(workdir / "config.json", {"alarm": {"sound": "a.wav", "limits": {"RPM": 1}}, "signals": {"RPM": {"max": 1}}})

    _setup_config()

    assert Signal.RPM.value["alarm"]["max"] == 6600


def test_mock_skip_lines_defaults_to_zero(workdir):
    """Requirement: Supported settings (connection.mock_skip_lines default)."""
    assert _setup_config().connection.mock_skip_lines == 0


def test_mock_skip_lines_is_loaded_from_the_file(workdir):
    """Scenario: Skip configured."""
    write_json(workdir / "config.json", {"connection": {"mock": "replay.csv", "mock_skip_lines": 500}})

    cfg = _setup_config()

    assert (cfg.connection.mock, cfg.connection.mock_skip_lines) == ("replay.csv", 500)


def test_mark_sound_defaults_to_alarm_wav(workdir):
    """Requirement: Supported settings (datalog.mark_sound default)."""
    assert _setup_config().datalog.mark_sound == "alarm.wav"


def test_mark_sound_is_loaded_from_the_file(workdir):
    """Scenario: Mark sound configured."""
    write_json(workdir / "config.json", {"datalog": {"path": "logs", "mark_sound": "mark.wav"}})

    cfg = _setup_config()

    assert (cfg.datalog.path, cfg.datalog.mark_sound) == ("logs", "mark.wav")


# ---------------------------------------------------------------- ignition tuning

def test_ignition_tuning_defaults_apply_without_the_section(workdir):
    """Scenario: Ignition tuning defaults."""
    cfg = _setup_config().ignition_tuning

    assert (cfg.rpm_min, cfg.rpm_max, cfg.gears) == (2900, 3100, [5])
    assert (cfg.max_map_kpa, cfg.max_ignition) == (70, 50)
    assert (cfg.settle_seconds, cfg.min_scenario_seconds) == (5, 20)
    assert (cfg.write_sound, cfg.ready_sound, cfg.pause_sound, cfg.resume_sound, cfg.discard_sound) == ("alarm.wav",) * 5


def test_ignition_tuning_band_is_loaded_from_the_file(workdir):
    """Scenario: Ignition tuning band configured."""
    write_json(workdir / "config.json", {"ignition_tuning": {"rpm_min": 3400, "rpm_max": 3600}})

    cfg = _setup_config().ignition_tuning

    assert (cfg.rpm_min, cfg.rpm_max) == (3400, 3600)


def test_ignition_tuning_missing_keys_take_their_default_independently(workdir):
    """Requirement: Per-key defaults (partial ignition_tuning section)."""
    write_json(workdir / "config.json", {"ignition_tuning": {"gears": [4], "ready_sound": "ready.wav"}})

    cfg = _setup_config().ignition_tuning

    assert (cfg.gears, cfg.ready_sound) == ([4], "ready.wav")
    assert (cfg.rpm_min, cfg.rpm_max, cfg.write_sound) == (2900, 3100, "alarm.wav")


def test_every_ignition_tuning_setting_is_loaded(workdir):
    """Requirement: Supported settings (all ignition_tuning keys)."""
    write_json(workdir / "config.json", {"ignition_tuning": {
        "rpm_min": 1, "rpm_max": 2, "gears": [3, 4], "max_map_kpa": 4, "max_ignition": 5,
        "settle_seconds": 6, "min_scenario_seconds": 7,
        "write_sound": "w.wav", "ready_sound": "r.wav", "pause_sound": "p.wav", "resume_sound": "u.wav",
        "discard_sound": "d.wav",
    }})

    cfg = _setup_config().ignition_tuning

    assert (cfg.rpm_min, cfg.rpm_max, cfg.gears, cfg.max_map_kpa, cfg.max_ignition) == (1, 2, [3, 4], 4, 5)
    assert (cfg.settle_seconds, cfg.min_scenario_seconds) == (6, 7)
    assert (cfg.write_sound, cfg.ready_sound, cfg.pause_sound, cfg.resume_sound, cfg.discard_sound) == (
        "w.wav", "r.wav", "p.wav", "u.wav", "d.wav")


def test_ignition_tuning_gears_are_loaded_from_the_file(workdir):
    """Scenario: Ignition tuning gears configured."""
    write_json(workdir / "config.json", {"ignition_tuning": {"gears": [4, 5]}})

    assert _setup_config().ignition_tuning.gears == [4, 5]


def test_the_previous_gear_key_is_not_read(workdir):
    """Scenario: Previous gear key not read."""
    write_json(workdir / "config.json", {"ignition_tuning": {"gear": 4}})

    assert _setup_config().ignition_tuning.gears == [5]


@pytest.mark.parametrize("value", [[], 5, "4,5", [4, "5"], [True], None])
def test_invalid_gears_fall_back_to_the_default(workdir, value):
    """Requirement: Supported settings (gears must be a non-empty list of integers)."""
    write_json(workdir / "config.json", {"ignition_tuning": {"gears": value}})

    assert _setup_config().ignition_tuning.gears == [5]
