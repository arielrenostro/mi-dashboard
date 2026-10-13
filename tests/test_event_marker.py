"""Spec: openspec/specs/datalog (Manual event mark, Event column)."""
from unittest.mock import Mock, call

import pytest
from PyQt6.QtCore import Qt

from app.event.marker import EventMarker
from app.log_writer.log_writer import LogWriter
from app.masterinjection.signal_processor import SignalProcessor
from app.ui.window import AppWindow
from tests.helpers import SAMPLE_FRAME, key_press
from tests.test_datalog import read_rows, wait_for_rows


@pytest.fixture
def marker(qapp):
    m = EventMarker("does-not-exist.wav")
    m._player = Mock()
    m.triggered = []
    m.event_triggered.connect(lambda: m.triggered.append(1))
    return m


# -------------------------------------------------------------- the marker alone

@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter])
def test_return_and_enter_play_the_sound_from_the_start_and_emit(marker, key):
    """Requirement: Manual event mark (sound restarted, mark requested)."""
    marker.handle_key(int(key))  # the window announces keys as plain ints

    assert marker._player.mock_calls == [call.stop(), call.play()]
    assert marker.triggered == [1]


@pytest.mark.parametrize("key", [Qt.Key.Key_A, Qt.Key.Key_Space, Qt.Key.Key_Escape, Qt.Key.Key_Up, Qt.Key.Key_R])
def test_other_keys_do_nothing(marker, key):
    marker.handle_key(int(key))

    marker._player.play.assert_not_called()
    assert marker.triggered == []


def test_every_press_restarts_the_sound(marker):
    marker.handle_key(int(Qt.Key.Key_Return))
    marker.handle_key(int(Qt.Key.Key_Return))

    assert marker._player.mock_calls == [call.stop(), call.play()] * 2


# ----------------------------------------------------- key -> marker -> log file

@pytest.fixture
def chain(qapp, tmp_path, request):
    """The real wiring: window key signal -> marker -> log writer."""
    path = str(tmp_path / "log_stream_test.csv")
    writer = LogWriter(path)

    def cleanup():  # registered before anything else can fail, so a broken setup never leaks the thread
        writer.thread.quit()
        writer.thread.wait()
        writer.worker.log_file.close()

    request.addfinalizer(cleanup)
    window = AppWindow(SignalProcessor())
    request.addfinalizer(window.close)
    marker = EventMarker("does-not-exist.wav")
    marker._player = Mock()
    window.key_event.connect(marker.handle_key)
    marker.event_triggered.connect(writer.set_event_pending)
    return window, writer, path, marker


def events(path, count):
    return [row[1] for row in wait_for_rows(path, count + 1)[1:]]


def test_enter_on_the_dashboard_marks_the_next_row_only(chain):
    """Scenario: Mark during a run."""
    window, writer, path, marker = chain
    window.show_screen("dashboard")
    writer.write(SAMPLE_FRAME)

    window.keyPressEvent(key_press(Qt.Key.Key_Return))
    writer.write(SAMPLE_FRAME)
    writer.write(SAMPLE_FRAME)

    assert events(path, 3) == ["", "MARK", ""]
    marker._player.play.assert_called_once()


def test_enter_on_the_ve_screen_marks_too(chain):
    window, writer, path, _ = chain
    window.show_screen("ve_calibration")

    window.keyPressEvent(key_press(Qt.Key.Key_Return))
    writer.write(SAMPLE_FRAME)

    assert events(path, 1) == ["MARK"]


def test_holding_enter_marks_once(chain):
    """Scenario: Held key."""
    window, writer, path, marker = chain
    window.show_screen("dashboard")

    window.keyPressEvent(key_press(Qt.Key.Key_Return))
    for _ in range(4):
        window.keyPressEvent(key_press(Qt.Key.Key_Return, auto_repeat=True))
    writer.write(SAMPLE_FRAME)
    writer.write(SAMPLE_FRAME)

    assert events(path, 2) == ["MARK", ""]
    marker._player.play.assert_called_once()


def test_two_presses_before_a_frame_produce_one_mark(chain):
    """Scenario: Two presses before a frame."""
    window, writer, path, _ = chain
    window.show_screen("dashboard")

    window.keyPressEvent(key_press(Qt.Key.Key_Return))
    window.keyPressEvent(key_press(Qt.Key.Key_Return))
    writer.write(SAMPLE_FRAME)
    writer.write(SAMPLE_FRAME)

    assert events(path, 2) == ["MARK", ""]


def test_enter_on_home_opens_the_screen_and_does_not_mark(chain):
    """Scenario: Home screen."""
    window, writer, path, marker = chain

    window.keyPressEvent(key_press(Qt.Key.Key_Return))  # opens the Dashboard
    writer.write(SAMPLE_FRAME)

    assert window._current_screen_name == "dashboard"
    assert events(path, 1) == [""]
    marker._player.play.assert_not_called()
