"""Spec: openspec/specs/inclinometer-firmware, requirement "Firmware matches the dashboard's protocol".

The firmware cannot run here, so these tests read its source as text and check it against the constants the dashboard
uses. They catch a divergence between the two projects (a renamed command, a reordered field, a leftover gyroscope
column or retired command) without hardware. The angle accuracy, the calibration and the real serial behavior are
verified manually on the device.
"""
import re
from pathlib import Path

import pytest

from app.gyro.protocol import COMMAND_ZERO, COMMANDS, DATA_FIELDS, STATUS_OK

# The only place that knows where the firmware lives (it moves with the PlatformIO project).
FIRMWARE_SOURCE = Path(__file__).resolve().parents[2] / "inclinometer" / "inclinometro_6500.ino"

# Texts and names of what the firmware no longer has: the old `#M` state texts, the gyroscope and its commands.
RETIRED = (
    "Zero definido", "Zero removido", "Calibrando", "Calibracao ok", "Comando desconhecido",
    '"#C"', '"#R"', "#C;", "#R;", "CALIBRANDO", "gx_dps", "gy_dps", "gz_dps", "MPU6500_WE", "getGyrValues",
)


@pytest.fixture(scope="module")
def source():
    return FIRMWARE_SOURCE.read_text(encoding="utf-8")


def code_of(text):
    """The source without `//` and `/* */` comments, so a comment cannot satisfy a check."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", text)


@pytest.mark.parametrize("command", COMMANDS)
def test_firmware_recognises_each_command_of_the_dashboard(source, command):
    """Scenario: Contract check (commands)."""
    assert f'"{command}"' in code_of(source)


@pytest.mark.parametrize("command", ['"#KP"', '"#KR"', '"XYZ"'])
def test_firmware_has_the_accelerometer_calibration_commands(source, command):
    """Scenario: Contract check (the `#K` calibration family, made with a serial terminal)."""
    assert command in code_of(source)


def test_firmware_sends_the_reply_the_dashboard_reacts_to(source):
    """Scenario: Contract check (replies)."""
    assert f'"{COMMAND_ZERO};{STATUS_OK};"' in code_of(source)


def test_firmware_header_lists_the_fields_in_the_dashboards_order(source):
    """Scenario: Contract check (header)."""
    header = "#H;" + ";".join(DATA_FIELDS) + ";"

    assert f'"{header}"' in code_of(source)


def test_firmware_data_line_has_the_tag_and_the_dashboards_values(source):
    """Scenario: Contract check (data line). One `Serial.print(<value>)` per field between `#D;` and the line break."""
    code = code_of(source)
    start = code.index('"#D;"')
    body = code[start: code.index("Serial.print('\\n')", start)]

    assert len(re.findall(r"Serial\.print\((?!F\(\"#D;\"\)|';')", body)) == len(DATA_FIELDS)
    assert body.count("';'") == len(DATA_FIELDS)


def test_firmware_message_texts_are_uppercase_with_underscores(source):
    """Scenario: Text characters."""
    texts = re.findall(r'msg\(F\("([^"]*)"\)\)', code_of(source))

    assert texts
    assert all(re.fullmatch(r"[A-Z0-9_]+", text) for text in texts), texts


def test_firmware_has_none_of_the_retired_texts_commands_and_gyroscope_fields(source):
    """Scenario: Contract check (nothing retired is left)."""
    code = code_of(source)

    assert [item for item in RETIRED if item in code] == []
