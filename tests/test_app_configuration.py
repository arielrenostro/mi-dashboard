"""Spec: openspec/specs/app-configuration."""
import json

import pytest

from app.config import AppConfig, _setup_config


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


# ── Inclinometer and tilt settings (spec: "Inclinometer and tilt settings") ─────────────────────────────────

def test_gyro_defaults_apply_without_the_section(workdir):
    """Scenario: Defaults without the section."""
    cfg = _setup_config()

    assert cfg.gyro.port == ""
    assert cfg.ignition_tuning.max_tilt_deg == 3


def test_gyro_port_is_loaded_from_the_file(workdir):
    """Scenario: Port configured."""
    write_json(workdir / "config.json", {"gyro": {"port": "COM7"}})

    assert _setup_config().gyro.port == "COM7"


def test_gyro_port_that_is_not_text_is_empty(workdir):
    write_json(workdir / "config.json", {"gyro": {"port": 7}})

    assert _setup_config().gyro.port == ""


def test_max_tilt_is_loaded_from_the_file(workdir):
    write_json(workdir / "config.json", {"ignition_tuning": {"max_tilt_deg": 2.5}})

    assert _setup_config().ignition_tuning.max_tilt_deg == 2.5


@pytest.mark.parametrize("value", ["abc", 0, -2, None, True, [3]])
def test_invalid_max_tilt_takes_the_default(workdir, value):
    """Scenario: Invalid limit."""
    write_json(workdir / "config.json", {"ignition_tuning": {"max_tilt_deg": value}})

    assert _setup_config().ignition_tuning.max_tilt_deg == 3


def test_there_is_no_gyro_baudrate_setting(workdir):
    """Spec: no baud rate setting for the inclinometer."""
    write_json(workdir / "config.json", {"gyro": {"port": "COM7", "baudrate": 9600}})

    assert not hasattr(_setup_config().gyro, "baudrate")


# ── Saving the configuration (spec: "Saving the configuration") ─────────────────────────────────────────────

@pytest.fixture
def saved(workdir):
    """A config loaded from config.json in a temporary directory; returns (config, path)."""
    def make(data=None, text=None):
        path = workdir / "config.json"
        if text is not None:  # not necessarily JSON: the app started with defaults and the file broke afterwards
            path.write_text(text, encoding="utf-8")
            return AppConfig({}, str(path)), path
        if data is not None:
            write_json(path, data)
        return _setup_config(), path
    return make


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_value_is_saved_in_place(saved):
    """Scenario: Value saved in place."""
    cfg, path = saved({"ignition_tuning": {"settle_seconds": 5, "rpm_min": 3000}, "alarm": {"sound": "x.wav"}})

    assert cfg.set_value("ignition_tuning", "settle_seconds", 6) is True

    assert read_json(path) == {"ignition_tuning": {"settle_seconds": 6, "rpm_min": 3000}, "alarm": {"sound": "x.wav"}}
    assert cfg.ignition_tuning.settle_seconds == 6


def test_file_is_always_written_indented_with_a_final_line_break(saved):
    """Scenario: Always indented."""
    cfg, path = saved(text='{"gyro":{"port":"COM1"},"ignition_tuning":{"gears":[4,5]}}')

    cfg.set_value("gyro", "port", "COM7")

    text = path.read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert '\n  "gyro": {\n    "port": "COM7"\n  },' in text
    assert read_json(path)["ignition_tuning"]["gears"] == [4, 5]


def test_unknown_keys_are_kept(saved):
    """Scenario: Unknown keys kept."""
    cfg, path = saved({"mystery": {"a": 1}, "gyro": {"port": "", "extra": True}})

    cfg.set_value("gyro", "port", "COM3")

    assert read_json(path) == {"mystery": {"a": 1}, "gyro": {"port": "COM3", "extra": True}}


def test_a_hand_edit_made_after_startup_is_kept(saved):
    """Scenario: Edited by hand meanwhile."""
    cfg, path = saved({"alarm": {"sound": "a.wav"}})
    write_json(path, {"alarm": {"sound": "b.wav"}, "datalog": {"path": "D:/logs"}})

    cfg.set_value("gyro", "port", "COM3")

    assert read_json(path) == {"alarm": {"sound": "b.wav"}, "datalog": {"path": "D:/logs"}, "gyro": {"port": "COM3"}}


def test_a_missing_section_is_created(saved):
    """Scenario: Section created."""
    cfg, path = saved({"alarm": {"sound": "a.wav"}})

    cfg.set_value("gyro", "port", "COM7")

    assert read_json(path)["gyro"] == {"port": "COM7"}


def test_a_missing_file_is_created_with_only_that_setting(saved):
    """Scenario: File created."""
    cfg, path = saved()
    assert not path.exists()

    assert cfg.set_value("gyro", "port", "COM7") is True

    assert read_json(path) == {"gyro": {"port": "COM7"}}


def test_defaults_are_not_copied_to_the_file(saved):
    """Scenario: Defaults not copied."""
    cfg, path = saved({"connection": {"port": "COM1"}})

    cfg.set_value("ignition_tuning", "rpm_min", 3000)

    assert read_json(path) == {"connection": {"port": "COM1"}, "ignition_tuning": {"rpm_min": 3000}}


def test_non_ascii_text_is_written_as_it_is(saved):
    """Scenario: Non-ASCII text."""
    cfg, path = saved({"datalog": {"path": "C:\\Área"}})

    cfg.set_value("gyro", "port", "COM3")

    text = path.read_text(encoding="utf-8")
    assert "Área" in text and "\\u00" not in text


def test_an_invalid_file_is_left_untouched_and_the_value_is_still_used(saved):
    """Scenario: Invalid file."""
    cfg, path = saved(text="{ this is not json")

    assert cfg.set_value("gyro", "port", "COM3") is False

    assert path.read_text(encoding="utf-8") == "{ this is not json"
    assert cfg.gyro.port == "COM3"


def test_a_file_that_is_not_an_object_is_left_untouched(saved):
    cfg, path = saved(text="[1, 2]")

    assert cfg.set_value("gyro", "port", "COM3") is False

    assert path.read_text(encoding="utf-8") == "[1, 2]"


def test_no_temporary_file_is_left_behind(saved, workdir):
    """Scenario: Atomic replace."""
    cfg, _ = saved({"gyro": {"port": ""}})
    cfg.set_value("gyro", "port", "COM3")
    failing, _ = saved(text="nope")
    failing.set_value("gyro", "port", "COM3")

    assert sorted(p.name for p in workdir.iterdir()) == ["config.json"]


def test_saves_to_the_file_named_by_the_environment_variable(workdir, monkeypatch):
    """Scenario: Environment override."""
    other = write_json(workdir / "other.json", {"alarm": {"sound": "a.wav"}})
    monkeypatch.setenv("MI_DASHBOARD_CONFIG_FILE", str(other))
    cfg = _setup_config()

    cfg.set_value("gyro", "port", "COM3")

    assert read_json(other)["gyro"] == {"port": "COM3"}
    assert not (workdir / "config.json").exists()


def test_config_without_a_path_cannot_save_but_still_changes_the_value():
    cfg = AppConfig({})

    assert cfg.set_value("gyro", "port", "COM3") is False
    assert cfg.gyro.port == "COM3"


def test_setting_an_unknown_key_is_an_error():
    cfg = AppConfig({})

    with pytest.raises(KeyError):
        cfg.set_value("gyro", "baudrate", 9600)
    with pytest.raises(KeyError):
        cfg.set_value("nowhere", "port", "COM3")


# ── Every setting is on the Settings screen (spec: "Every setting is on the Settings screen") ───────────────

def test_every_setting_has_a_settings_screen_row_or_is_in_the_backlog():
    """Scenario: Setting without a row. A new setting cannot be added without its row."""
    from app.ui.settings.screen import SETTINGS_BACKLOG, SETTINGS_ON_SCREEN

    settings = AppConfig({}).keys()

    assert settings - SETTINGS_ON_SCREEN - SETTINGS_BACKLOG == set(), "settings with no Settings screen row"


def test_the_backlog_only_holds_settings_that_still_exist_and_have_no_row():
    from app.ui.settings.screen import SETTINGS_BACKLOG, SETTINGS_ON_SCREEN

    settings = AppConfig({}).keys()

    assert SETTINGS_BACKLOG - settings == set(), "stale entries in the backlog"
    assert SETTINGS_BACKLOG & SETTINGS_ON_SCREEN == set(), "a setting is both on the screen and in the backlog"
    assert SETTINGS_ON_SCREEN - settings == set(), "a row for a setting that does not exist"


def test_the_new_settings_have_a_row():
    """Scenario: Setting with a row."""
    from app.ui.settings.screen import SETTINGS_ON_SCREEN

    assert {"gyro.port", "ignition_tuning.max_tilt_deg", "ignition_tuning.rpm_min", "ignition_tuning.rpm_max",
            "ignition_tuning.settle_seconds", "ignition_tuning.min_scenario_seconds"} <= SETTINGS_ON_SCREEN


def test_a_setting_added_without_a_row_would_be_caught():
    """The comparison really detects a new setting (the guard is not vacuous)."""
    from app.ui.settings.screen import SETTINGS_BACKLOG, SETTINGS_ON_SCREEN

    cfg = AppConfig({})
    cfg.gyro.baudrate = 115200  # what someone adding a setting without its row would do

    assert cfg.keys() - SETTINGS_ON_SCREEN - SETTINGS_BACKLOG == {"gyro.baudrate"}
