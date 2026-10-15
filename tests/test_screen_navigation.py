"""Spec: openspec/specs/screen-navigation (Home screen, connection status, screen lifecycle)."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QWidget

import app.ecu_connection as registry
import app.ui.home.screen as home_module
from app.ecu_connection.ecu_connection import EcuConnectionStatus
from app.ui.home.screen import HomeScreen
from tests.helpers import key_press


def make_config(mock="", port="COM3", baudrate=115200):
    return SimpleNamespace(connection=SimpleNamespace(mock=mock, port=port, baudrate=baudrate))


@pytest.fixture
def home(qapp, monkeypatch):
    monkeypatch.setattr(home_module, "config", make_config())
    screen = HomeScreen(close_fn=lambda: None)
    screen.close_fn = Mock()
    screen.requested = []
    screen.screen_requested.connect(screen.requested.append)
    return screen


def label_texts(screen):
    return [label.text() for label in screen.findChildren(QLabel)]


# ---------------------------------------------------------------- content

def test_home_shows_title_menu_and_hint(home):
    """Requirement: Home screen content."""
    texts = label_texts(home)

    assert "Master Injection" in texts
    assert (texts.index("Dashboard") < texts.index("Calibração de VE") < texts.index("Ajuste de Ignição")
            < texts.index("ECU") < texts.index("Configurações"))
    assert "Opções" not in texts
    assert "↑↓ Navegar | Enter Selecionar" in texts


def test_dashboard_is_selected_initially(home):
    """Scenario: Initial selection."""
    home.keyPressEvent(key_press(Qt.Key.Key_Return))

    assert home.requested == ["dashboard"]


# ------------------------------------------------------------- navigation

def test_down_moves_to_next_item(home):
    home.keyPressEvent(key_press(Qt.Key.Key_Down))
    home.keyPressEvent(key_press(Qt.Key.Key_Return))

    assert home.requested == ["ve_calibration"]


def test_down_from_last_item_wraps_to_first(home):
    """Scenario: Wrap down."""
    for _ in range(5):
        home.keyPressEvent(key_press(Qt.Key.Key_Down))
    home.keyPressEvent(key_press(Qt.Key.Key_Return))

    assert home.requested == ["dashboard"]


def test_up_from_first_item_wraps_to_last(home):
    """Scenario: Wrap up."""
    home.keyPressEvent(key_press(Qt.Key.Key_Up))
    home.keyPressEvent(key_press(Qt.Key.Key_Return))

    assert home.requested == ["settings"]


def test_ignition_tuning_entry_opens_the_ignition_tuning_screen(home):
    """Scenario: Ignition tuning entry."""
    home.keyPressEvent(key_press(Qt.Key.Key_Down))
    home.keyPressEvent(key_press(Qt.Key.Key_Down))
    home.keyPressEvent(key_press(Qt.Key.Key_Return))

    assert home.requested == ["ignition_tuning"]


def test_options_entry_opens_the_options_screen(home):
    """Scenario: Options entry (the entry reads ECU)."""
    for _ in range(3):
        home.keyPressEvent(key_press(Qt.Key.Key_Down))
    home.keyPressEvent(key_press(Qt.Key.Key_Return))

    assert home.requested == ["options"]


def test_settings_entry_opens_the_settings_screen(home):
    """Scenario: Settings entry."""
    for _ in range(4):
        home.keyPressEvent(key_press(Qt.Key.Key_Down))
    home.keyPressEvent(key_press(Qt.Key.Key_Return))

    assert home.requested == ["settings"]


def test_home_menu_content_and_order(home):
    """Scenario: Menu content."""
    assert [name for name, _ in home._menu_items] == [
        "Dashboard", "Calibração de VE", "Ajuste de Ignição", "ECU", "Configurações"]
    assert [target for _, target in home._menu_items] == [
        "dashboard", "ve_calibration", "ignition_tuning", "options", "settings"]


@pytest.mark.parametrize("enter", [Qt.Key.Key_Return, Qt.Key.Key_Enter])
def test_return_and_enter_both_open_the_selected_screen(home, enter):
    """Scenario: Open."""
    home.keyPressEvent(key_press(Qt.Key.Key_Down))
    home.keyPressEvent(key_press(enter))

    assert home.requested == ["ve_calibration"]


def test_auto_repeat_is_ignored(home):
    """Scenario: Held key."""
    home.keyPressEvent(key_press(Qt.Key.Key_Down))
    for _ in range(5):
        home.keyPressEvent(key_press(Qt.Key.Key_Down, auto_repeat=True))
    home.keyPressEvent(key_press(Qt.Key.Key_Return))

    assert home.requested == ["ve_calibration"]


def test_escape_on_home_closes_the_app(home):
    """Scenario: Exit from Home."""
    home.keyPressEvent(key_press(Qt.Key.Key_Escape))

    home.close_fn.assert_called_once()
    assert home.requested == []


def test_auto_repeat_escape_does_not_close_the_app(home):
    """Requirement: Exit with ESC on Home (auto-repeat is ignored)."""
    home.keyPressEvent(key_press(Qt.Key.Key_Escape, auto_repeat=True))

    home.close_fn.assert_not_called()


def test_escape_does_not_disturb_the_menu_selection(home):
    home.keyPressEvent(key_press(Qt.Key.Key_Down))
    home.keyPressEvent(key_press(Qt.Key.Key_Escape))
    home.keyPressEvent(key_press(Qt.Key.Key_Return))

    assert home.requested == ["ve_calibration"]


def test_selected_item_is_highlighted_and_others_are_gray(home):
    """Requirement: Menu navigation (selected item style)."""
    menu = [l for l in home.findChildren(QLabel) if l.text() in ("Dashboard", "Calibração de VE", "Ajuste de Ignição")]

    assert "white" in menu[0].styleSheet() and "#1E90FF" in menu[0].styleSheet()
    assert "gray" in menu[1].styleSheet() and "gray" in menu[2].styleSheet()

    home.keyPressEvent(key_press(Qt.Key.Key_Down))

    assert "gray" in menu[0].styleSheet()
    assert "white" in menu[1].styleSheet() and "#1E90FF" in menu[1].styleSheet()


# ------------------------------------------------- connection info and status

def test_serial_connection_info(qapp, monkeypatch):
    """Requirement: Connection information and status."""
    monkeypatch.setattr(home_module, "config", make_config(port="COM5", baudrate=9600))

    screen = HomeScreen(close_fn=lambda: None)

    assert "Port: COM5 | Baudrate: 9600 | " in label_texts(screen)


def test_short_mock_path_is_shown_in_full(qapp, monkeypatch):
    monkeypatch.setattr(home_module, "config", make_config(mock="replay.csv"))

    assert "Mock: replay.csv | " in label_texts(HomeScreen(close_fn=lambda: None))


def test_long_mock_path_is_shortened_to_its_last_40_characters(qapp, monkeypatch):
    path = "/very/long/directory/structure/that/goes/on/and/on/replay_file.csv"
    assert len(path) > 40
    monkeypatch.setattr(home_module, "config", make_config(mock=path))

    assert f"Mock: ...{path[-40:]} | " in label_texts(HomeScreen(close_fn=lambda: None))


class FakeConnection:
    def __init__(self, status):
        self.status = status

    def get_connection_status(self):
        return self.status


@pytest.mark.parametrize(
    "status,label",
    [
        (EcuConnectionStatus.CONNECTED, "Connected"),
        (EcuConnectionStatus.CONNECTING, "Connecting"),
        (EcuConnectionStatus.HANDSHAKE, "Handshake"),
        (EcuConnectionStatus.ERROR, "Error"),
        (EcuConnectionStatus.DISCONNECTED, "Disconnected"),
        (None, "Unknow"),
    ],
)
def test_status_label_follows_the_connection_status(home, monkeypatch, status, label):
    """Scenario: Serial link up (and the status table)."""
    monkeypatch.setattr(registry, "ecu_connection", FakeConnection(status), raising=False)

    home._status_timer.timeout.emit()

    assert label in label_texts(home)


def test_status_dot_color_matches_the_status(home, monkeypatch):
    monkeypatch.setattr(registry, "ecu_connection", FakeConnection(EcuConnectionStatus.CONNECTED), raising=False)
    home._status_timer.timeout.emit()
    dots = [w for w in home.findChildren(QWidget) if "border-radius: 6px" in w.styleSheet()]

    assert "#2ecc71" in dots[0].styleSheet()  # green

    monkeypatch.setattr(registry, "ecu_connection", FakeConnection(EcuConnectionStatus.DISCONNECTED), raising=False)
    home._status_timer.timeout.emit()

    assert "#e74c3c" in dots[0].styleSheet()  # red


def test_status_refresh_runs_every_500ms_only_while_active(home):
    """Scenario: Refresh stops when hidden."""
    assert not home._status_timer.isActive()

    home.on_activated()
    assert home._status_timer.isActive() and home._status_timer.interval() == 500

    home.on_deactivated()
    assert not home._status_timer.isActive()

