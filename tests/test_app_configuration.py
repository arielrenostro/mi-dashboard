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
