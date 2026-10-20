"""Spec: openspec/specs/settings-screen (change gyro-inclination)."""
import json
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

from app.config import AppConfig
from app.gyro.protocol import GyroReading
from app.gyro.state import GyroSnapshot, GyroStatus
from app.ui.settings.screen import HINT, SettingsScreen
from tests.helpers import key_press

PORT, CONNECT, ZERO, TILT, RPM_MIN, RPM_MAX, SETTLE, MIN_TIME = range(8)

READING = GyroReading(t_ms=1, pitch=1.37, roll=-0.62, ax_g=0, ay_g=0, az_g=1, temp_c=31.4)


class FakeGyro:
    """The inclinometer as the screen sees it."""

    def __init__(self):
        self.status = GyroStatus.DISABLED
        self.reading = None
        self.message = ""
        self.open = False
        self.user_closed = False
        self.calls = []

    def snapshot(self):
        pitch = self.reading.pitch if self.status is GyroStatus.USABLE and self.reading else None
        return GyroSnapshot(self.status, pitch, self.reading, self.message)

    def is_open(self):
        return self.open

    def is_user_closed(self):
        return self.user_closed

    def set_port(self, port):
        self.calls.append(("set_port", port))

    def connect(self):
        self.calls.append(("connect",))
        self.user_closed = False

    def disconnect(self):
        self.calls.append(("disconnect",))
        self.user_closed = True

    def zero(self):
        self.calls.append(("zero",))
        return self.open


class Env:
    def __init__(self, screen, gyro, settings, path, ports):
        self.screen, self.gyro, self.settings, self.path, self.ports = screen, gyro, settings, path, ports
        self.changed = []
        screen.setting_changed.connect(lambda section, key: self.changed.append((section, key)))

    def press(self, key, auto_repeat=False):
        self.screen.keyPressEvent(key_press(key, auto_repeat))

    def select(self, index):
        while self.screen.selected_index != index:
            self.press(Qt.Key.Key_Down)

    def value(self, index):
        return self.screen.row_texts()[index][1]

    def label(self, index):
        return self.screen.row_texts()[index][0]

    def saved(self):
        return json.loads(self.path.read_text(encoding="utf-8"))


@pytest.fixture
def env(qapp, tmp_path):
    path = tmp_path / "settings.json"
    settings = AppConfig({}, str(path))
    gyro = FakeGyro()
    ports = ["COM3", "COM7"]
    screen = SettingsScreen(close_fn=Mock(), gyro=gyro, settings=settings, list_ports=lambda: list(ports))
    screen.on_activated()
    yield Env(screen, gyro, settings, path, ports)
    screen.on_deactivated()


# ── Layout ───────────────────────────────────────────────────────────────────────────────────────────────

def test_initial_content(env):
    """Scenario: Initial content."""
    texts = [label.text() for label in env.screen.findChildren(QLabel)]

    assert "Configurações" in texts and "Giroscópio" in texts and "Ajuste de Ignição" in texts
    assert HINT in texts and HINT == "↑↓ Navegar | ←→ Alterar | Enter Executar | Esc Voltar"
    assert [label for label, _ in env.screen.row_texts()] == [
        "Porta", "Conectar", "Zerar inclinação", "Inclinação máxima", "RPM mínimo",
        "RPM máximo", "Estabilização", "Tempo mínimo do cenário"]
    assert env.screen.selected_index == PORT and env.screen.status_text == ""


# ── Navigation ───────────────────────────────────────────────────────────────────────────────────────────

def test_move_down(env):
    """Scenario: Move down."""
    env.press(Qt.Key.Key_Down)

    assert env.screen.selected_index == CONNECT


def test_wrap_at_the_end(env):
    """Scenario: Wrap at the end."""
    env.select(MIN_TIME)
    env.press(Qt.Key.Key_Down)

    assert env.screen.selected_index == PORT


def test_wrap_at_the_start(env):
    """Scenario: Wrap at the start."""
    env.press(Qt.Key.Key_Up)

    assert env.screen.selected_index == MIN_TIME


def test_escape_goes_back(env):
    """Scenario: Back to Home."""
    env.press(Qt.Key.Key_Escape)

    env.screen.close_fn.assert_called_once()


def test_held_keys_are_ignored(env):
    """Scenario: Held key."""
    env.select(TILT)

    env.press(Qt.Key.Key_Right, auto_repeat=True)
    env.press(Qt.Key.Key_Down, auto_repeat=True)

    assert env.value(TILT) == "3.0°" and env.screen.selected_index == TILT


# ── Port row ─────────────────────────────────────────────────────────────────────────────────────────────

def test_ports_are_offered_and_the_chosen_one_is_saved(env):
    """Scenario: Ports offered."""
    env.press(Qt.Key.Key_Right)
    assert env.value(PORT) == "COM3"
    env.press(Qt.Key.Key_Right)

    assert env.value(PORT) == "COM7"
    assert env.settings.gyro.port == "COM7"
    assert env.saved()["gyro"]["port"] == "COM7"
    assert env.gyro.calls == [("set_port", "COM3"), ("set_port", "COM7")]
    assert ("gyro", "port") in env.changed


def test_choosing_none_saves_an_empty_port_and_closes_the_connection(env):
    """Scenario: Choose none."""
    env.settings.gyro.port = "COM7"
    env.press(Qt.Key.Key_Left)
    env.press(Qt.Key.Key_Left)

    assert env.value(PORT) == "Nenhuma"
    assert env.saved()["gyro"]["port"] == ""
    assert env.gyro.calls[-1] == ("set_port", "")


def test_a_configured_port_that_is_not_available_is_still_listed(env):
    """Scenario: Configured port not available."""
    env.ports[:] = ["COM3"]
    env.settings.gyro.port = "COM9"
    env.screen.on_activated()

    assert env.value(PORT) == "COM9 (indisponível)"
    assert [value for value, _ in env.screen._port_choices()] == ["", "COM3", "COM9"]
    env.press(Qt.Key.Key_Left)
    assert env.value(PORT) == "COM3"
    env.press(Qt.Key.Key_Left)
    assert env.value(PORT) == "Nenhuma"


def test_the_end_of_the_port_list_does_not_wrap(env):
    """Scenario: End of the list."""
    for _ in range(5):
        env.press(Qt.Key.Key_Right)
    assert env.value(PORT) == "COM7"
    env.press(Qt.Key.Key_Left)
    env.press(Qt.Key.Key_Left)
    env.press(Qt.Key.Key_Left)

    assert env.value(PORT) == "Nenhuma"


def test_the_port_list_is_refreshed_on_every_press_and_on_activation(env):
    env.ports.append("COM9")

    for _ in range(3):
        env.press(Qt.Key.Key_Right)
    assert env.value(PORT) == "COM9"

    env.ports[:] = []
    env.settings.gyro.port = ""
    env.screen.on_activated()
    env.press(Qt.Key.Key_Right)
    assert env.value(PORT) == "Nenhuma"


def test_a_port_provider_that_fails_gives_an_empty_list(env):
    def failing():
        raise OSError("no ports")
    env.screen._list_ports = failing

    env.press(Qt.Key.Key_Right)

    assert env.value(PORT) == "Nenhuma"


# ── Connect row ──────────────────────────────────────────────────────────────────────────────────────────

def test_connect_opens_the_port(env):
    """Scenario: Connect."""
    env.settings.gyro.port = "COM7"
    env.select(CONNECT)

    env.press(Qt.Key.Key_Return)

    assert env.gyro.calls == [("connect",)]


def test_disconnect_closes_the_port_and_the_row_reads_connect(env):
    """Scenario: Disconnect."""
    env.settings.gyro.port = "COM7"
    env.gyro.open = True
    env.select(CONNECT)
    assert env.label(CONNECT) == "Desconectar"

    env.press(Qt.Key.Key_Return)

    assert env.gyro.calls == [("disconnect",)]
    assert env.label(CONNECT) == "Conectar"


def test_connect_without_a_port_says_so(env):
    """Scenario: No port chosen."""
    env.select(CONNECT)

    env.press(Qt.Key.Key_Return)

    assert env.screen.status_text == "Escolha uma porta" and env.gyro.calls == []


# ── Zero row ─────────────────────────────────────────────────────────────────────────────────

def test_zero_is_sent(env):
    """Scenario: Zero sent."""
    env.gyro.open = True
    env.select(ZERO)

    env.press(Qt.Key.Key_Return)

    assert env.gyro.calls == [("zero",)] and env.screen.status_text == "Comando enviado"


def test_zero_without_a_device(env):
    """Scenario: Zero without a device."""
    env.select(ZERO)

    env.press(Qt.Key.Key_Return)

    assert env.screen.status_text == "Giroscópio desconectado"


def test_there_is_no_row_to_recalibrate_the_device(env):
    """Scenario: Zero row. The inclinometer has no gyroscope to calibrate, so the screen has no such row."""
    labels = [label for label, _ in env.screen.row_texts()]

    assert not any("alibr" in label for label in labels)
    assert not hasattr(env.screen, "_send_recalibration")


def test_left_and_right_do_nothing_on_action_rows(env):
    env.select(ZERO)

    env.press(Qt.Key.Key_Right)
    env.press(Qt.Key.Key_Left)

    assert env.gyro.calls == [] and env.changed == []


# ── Readout ──────────────────────────────────────────────────────────────────────────────────────────────

def test_readout_when_usable(env):
    """Scenario: Usable."""
    env.gyro.status, env.gyro.reading = GyroStatus.USABLE, READING

    assert env.screen.readout_lines()[:4] == ["Conectado, zerado", "Pitch +1.4°", "Roll -0.6°", "Temp 31.4 °C"]


def test_readings_are_shown_before_the_zero(env):
    """Scenario: Readings before the zero."""
    env.gyro.status, env.gyro.reading = GyroStatus.NOT_ZEROED, READING

    assert env.screen.readout_lines()[:2] == ["Conectado, sem zero", "Pitch +1.4°"]


def test_readout_without_a_device(env):
    """Scenario: No device."""
    assert env.screen.readout_lines()[:4] == ["Desligado", "Pitch --", "Roll --", "Temp --"]


@pytest.mark.parametrize("status, text", [
    (GyroStatus.DISABLED, "Desligado"), (GyroStatus.DISCONNECTED, "Desconectado"),
    (GyroStatus.NO_SIGNAL, "Sem sinal"),
    (GyroStatus.NOT_ZEROED, "Conectado, sem zero"), (GyroStatus.USABLE, "Conectado, zerado"),
])
def test_state_texts(env, status, text):
    env.gyro.status = status

    assert env.screen.readout_lines()[0] == text


@pytest.mark.parametrize("status", [GyroStatus.DISCONNECTED, GyroStatus.NO_SIGNAL])
def test_stale_readings_are_not_shown(env, status):
    env.gyro.status, env.gyro.reading = status, READING

    assert env.screen.readout_lines()[1:4] == ["Pitch --", "Roll --", "Temp --"]


def test_device_message_line(env):
    """Scenario: Device message."""
    env.gyro.message = "COMANDO_DESCONHECIDO"

    assert env.screen.readout_lines()[4] == "Mensagem: COMANDO_DESCONHECIDO"


def test_command_reply_message_line(env):
    """Scenario: Command reply as message."""
    env.gyro.message = "Z: OK"

    assert env.screen.readout_lines()[4] == "Mensagem: Z: OK"


def test_the_readout_is_drawn_and_refreshed_by_the_timer(env):
    env.gyro.status, env.gyro.reading = GyroStatus.USABLE, READING

    env.screen._timer.timeout.emit()

    texts = [label.text() for label in env.screen.findChildren(QLabel)]
    assert "Pitch +1.4°" in texts and "Conectado, zerado" in texts
    assert env.screen._timer.isActive()


def test_the_timer_stops_when_the_screen_is_hidden(env):
    env.screen.on_deactivated()

    assert not env.screen._timer.isActive()


# ── Numeric rows ─────────────────────────────────────────────────────────────────────────────────────────

def test_the_tilt_limit_goes_up_by_half_a_degree_and_is_saved(env):
    """Scenario: Increase the tilt limit."""
    env.select(TILT)

    env.press(Qt.Key.Key_Right)

    assert env.value(TILT) == "3.5°"
    assert env.saved()["ignition_tuning"]["max_tilt_deg"] == 3.5
    assert env.settings.ignition_tuning.max_tilt_deg == 3.5
    assert env.changed == [("ignition_tuning", "max_tilt_deg")]


def test_the_tilt_limit_has_a_lower_bound(env):
    """Scenario: Lower bound."""
    env.settings.ignition_tuning.max_tilt_deg = 0.5
    env.select(TILT)

    env.press(Qt.Key.Key_Left)

    assert env.value(TILT) == "0.5°" and env.changed == []


def test_the_tilt_limit_has_an_upper_bound(env):
    env.settings.ignition_tuning.max_tilt_deg = 20
    env.select(TILT)

    env.press(Qt.Key.Key_Right)

    assert env.settings.ignition_tuning.max_tilt_deg == 20


def test_the_rpm_band_cannot_cross(env):
    """Scenario: Band cannot cross."""
    env.settings.ignition_tuning.rpm_min = 3100
    env.settings.ignition_tuning.rpm_max = 3100
    env.select(RPM_MIN)

    env.press(Qt.Key.Key_Right)
    assert env.settings.ignition_tuning.rpm_min == 3100
    env.select(RPM_MAX)
    env.press(Qt.Key.Key_Left)
    assert env.settings.ignition_tuning.rpm_max == 3100


def test_the_rpm_band_moves_by_100(env):
    env.select(RPM_MIN)
    env.press(Qt.Key.Key_Left)
    env.select(RPM_MAX)
    env.press(Qt.Key.Key_Right)

    assert env.value(RPM_MIN) == "2800 rpm" and env.value(RPM_MAX) == "3200 rpm"
    assert env.saved()["ignition_tuning"]["rpm_min"] == 2800


def test_the_maximum_rpm_has_an_upper_bound(env):
    """Scenario: Maximum RPM bound."""
    env.settings.ignition_tuning.rpm_max = 9000
    env.select(RPM_MAX)

    env.press(Qt.Key.Key_Right)

    assert env.settings.ignition_tuning.rpm_max == 9000


def test_the_minimum_rpm_has_a_lower_bound(env):
    env.settings.ignition_tuning.rpm_min = 500
    env.select(RPM_MIN)

    env.press(Qt.Key.Key_Left)

    assert env.settings.ignition_tuning.rpm_min == 500


def test_settle_time_and_minimum_scenario_time_steps(env):
    env.select(SETTLE)
    env.press(Qt.Key.Key_Right)
    env.select(MIN_TIME)
    env.press(Qt.Key.Key_Left)

    assert (env.value(SETTLE), env.value(MIN_TIME)) == ("6 s", "15 s")
    assert env.saved()["ignition_tuning"]["settle_seconds"] == 6


def test_settle_time_cannot_go_below_zero(env):
    env.settings.ignition_tuning.settle_seconds = 0
    env.select(SETTLE)

    env.press(Qt.Key.Key_Left)

    assert env.settings.ignition_tuning.settle_seconds == 0


def test_enter_does_nothing_on_a_numeric_row(env):
    """Scenario: Enter does nothing."""
    env.select(RPM_MIN)

    env.press(Qt.Key.Key_Return)

    assert env.value(RPM_MIN) == "2900 rpm" and env.changed == [] and not env.path.exists()


def test_a_value_outside_the_range_is_clamped_by_the_first_press(env):
    """Scenario: Value outside the range."""
    env.settings.ignition_tuning.settle_seconds = 100
    env.select(SETTLE)
    assert env.value(SETTLE) == "100 s"

    env.press(Qt.Key.Key_Left)

    assert env.value(SETTLE) == "60 s" and env.saved()["ignition_tuning"]["settle_seconds"] == 60


# ── Saving ───────────────────────────────────────────────────────────────────────────────────────────────

def test_a_change_is_saved_and_reported(env):
    """Scenario: Saved."""
    env.select(SETTLE)

    env.press(Qt.Key.Key_Right)

    assert env.settings.ignition_tuning.settle_seconds == 6
    assert env.saved()["ignition_tuning"]["settle_seconds"] == 6
    assert env.screen.status_text == "Salvo"


def test_a_save_failure_still_applies_the_value(env):
    """Scenario: Save failure."""
    env.path.write_text("{ not json", encoding="utf-8")
    env.select(SETTLE)

    env.press(Qt.Key.Key_Right)

    assert env.settings.ignition_tuning.settle_seconds == 6
    assert env.screen.status_text == "Não foi possível gravar a configuração"
    assert env.path.read_text(encoding="utf-8") == "{ not json"
    assert env.changed == [("ignition_tuning", "settle_seconds")]


def test_the_failure_message_stays_until_another_status_replaces_it(env):
    env.path.write_text("{ not json", encoding="utf-8")
    env.select(SETTLE)
    env.press(Qt.Key.Key_Right)
    env.select(ZERO)
    assert env.screen.status_text == "Não foi possível gravar a configuração"

    env.press(Qt.Key.Key_Return)

    assert env.screen.status_text == "Giroscópio desconectado"
