"""Spec: openspec/specs/alarms."""
import time
from unittest.mock import Mock

import pytest
from PyQt6.QtMultimedia import QMediaPlayer

import app.state.state as state_module
from app.alarm.processor import AlarmProcessor
from app.masterinjection.signal import Signal
from app.state.state import vehicle_state
from tests.helpers import parsed


@pytest.fixture
def alarm(qapp):
    processor = AlarmProcessor("does-not-exist.wav")
    processor.onsets = []
    processor.emitter.connect(processor.onsets.append)
    return processor


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(state_module.time, "time", lambda: now[0])
    return now


def evaluate(alarm, signal, value):
    alarm.process_signals({signal: parsed(signal, value)})


# ------------------------------------------------------------ limit evaluation

def test_value_above_upper_limit_is_out_of_range(alarm):
    """Scenario: Above upper limit."""
    evaluate(alarm, Signal.RPM, 6700)

    assert vehicle_state.is_alarm_firing(Signal.RPM)


def test_value_below_lower_limit_is_out_of_range(alarm):
    evaluate(alarm, Signal.FUEL_TRIM, -21.0)

    assert vehicle_state.is_alarm_firing(Signal.FUEL_TRIM)


@pytest.mark.parametrize("signal,value", [(Signal.RPM, 6600), (Signal.RPM, 0), (Signal.FUEL_TRIM, 20.0), (Signal.FUEL_TRIM, -20.0)])
def test_value_exactly_at_a_limit_is_in_range(alarm, signal, value):
    """Scenario: At the limit."""
    evaluate(alarm, signal, value)

    assert not vehicle_state.is_alarm_firing(signal)
    assert alarm.onsets == []


def test_disabled_alarm_never_fires(alarm):
    """Scenario: Disabled alarm."""
    evaluate(alarm, Signal.BOOST, 200)

    assert not vehicle_state.is_alarm_firing(Signal.BOOST)
    assert alarm.onsets == []


def test_each_signal_is_evaluated_independently(alarm):
    alarm.process_signals({
        Signal.RPM: parsed(Signal.RPM, 3000),
        Signal.CLT: parsed(Signal.CLT, 110),
    })

    assert vehicle_state.is_alarm_firing(Signal.CLT)
    assert not vehicle_state.is_alarm_firing(Signal.RPM)


# ---------------------------------------------------------------- firing window

def test_sustained_condition_keeps_the_alarm_firing(alarm, clock):
    """Scenario: Sustained condition."""
    for _ in range(40):
        evaluate(alarm, Signal.RPM, 6700)
        clock[0] += 0.1

    assert vehicle_state.is_alarm_firing(Signal.RPM)


def test_alarm_stops_two_seconds_after_the_last_violation(alarm, clock):
    """Scenario: Condition ends."""
    evaluate(alarm, Signal.RPM, 6700)
    clock[0] += 0.5
    evaluate(alarm, Signal.RPM, 3000)  # back in range, but the window is still open
    assert vehicle_state.is_alarm_firing(Signal.RPM)

    clock[0] += 1.5

    assert not vehicle_state.is_alarm_firing(Signal.RPM)


# --------------------------------------------------------------- onset notice

def test_first_violation_notifies_once(alarm, clock):
    """Scenario: First violation."""
    evaluate(alarm, Signal.RPM, 6700)

    assert alarm.onsets == [Signal.RPM]


def test_continued_violation_does_not_notify_again(alarm, clock):
    """Scenario: Continued violation."""
    for _ in range(5):
        evaluate(alarm, Signal.RPM, 6700)
        clock[0] += 0.1

    assert alarm.onsets == [Signal.RPM]


def test_violation_after_the_window_expired_notifies_again(alarm, clock):
    evaluate(alarm, Signal.RPM, 6700)
    clock[0] += 3.0
    evaluate(alarm, Signal.RPM, 6700)

    assert alarm.onsets == [Signal.RPM, Signal.RPM]


# ------------------------------------------------------------------ audio loop

def run_poller(alarm, monkeypatch, firing_script):
    """Run the polling loop once per scripted 'any alarm firing' value; return the play/stop events."""
    events = []
    alarm._play_requested.connect(lambda: events.append("play"))
    alarm._stop_requested.connect(lambda: events.append("stop"))
    script = iter(firing_script)
    monkeypatch.setattr(vehicle_state, "is_any_alarm_firing", lambda: next(script))
    ticks = []

    def fake_sleep(ms):
        ticks.append(ms)
        if len(ticks) == len(firing_script):
            alarm.running = False

    alarm.msleep = fake_sleep
    alarm.run()
    assert set(ticks) == {100}  # polls every 100 ms
    return events


def test_sound_starts_when_an_alarm_starts_firing(alarm, monkeypatch):
    """Scenario: Alarm starts."""
    assert run_poller(alarm, monkeypatch, [False, True]) == ["play"]


def test_sound_is_requested_only_once_while_firing(alarm, monkeypatch):
    assert run_poller(alarm, monkeypatch, [True, True, True]) == ["play"]


def test_sound_stops_when_the_last_alarm_expires(alarm, monkeypatch):
    """Scenario: Alarm ends."""
    assert run_poller(alarm, monkeypatch, [True, True, False]) == ["play", "stop"]


def test_sound_can_start_again_after_stopping(alarm, monkeypatch):
    assert run_poller(alarm, monkeypatch, [True, False, True]) == ["play", "stop", "play"]


def test_sound_restarts_at_end_of_media_while_firing(alarm, monkeypatch):
    """Scenario: Looping."""
    alarm.player = Mock()
    monkeypatch.setattr(vehicle_state, "is_any_alarm_firing", lambda: True)

    alarm._handle_status(QMediaPlayer.MediaStatus.EndOfMedia)

    alarm.player.play.assert_called_once()


def test_sound_does_not_restart_at_end_of_media_when_not_firing(alarm, monkeypatch):
    alarm.player = Mock()
    monkeypatch.setattr(vehicle_state, "is_any_alarm_firing", lambda: False)

    alarm._handle_status(QMediaPlayer.MediaStatus.EndOfMedia)

    alarm.player.play.assert_not_called()


def test_other_media_statuses_do_not_restart_the_sound(alarm, monkeypatch):
    alarm.player = Mock()
    monkeypatch.setattr(vehicle_state, "is_any_alarm_firing", lambda: True)

    alarm._handle_status(QMediaPlayer.MediaStatus.LoadedMedia)

    alarm.player.play.assert_not_called()


# --------------------------------------------------------------------- shutdown

@pytest.fixture
def running_alarm(qapp, request):
    """A real alarm thread that is always joined, even when the test fails."""
    processor = AlarmProcessor("does-not-exist.wav")
    processor.player = Mock()

    def cleanup():
        processor.running = False
        processor.wait(2000)

    request.addfinalizer(cleanup)
    processor.start()
    deadline = time.time() + 2
    while not processor.isRunning() and time.time() < deadline:
        time.sleep(0.005)
    return processor


def test_stop_finishes_the_alarm_thread_and_stops_the_sound(running_alarm):
    """Scenario: Exit while an alarm is sounding."""
    running_alarm.stop()

    assert not running_alarm.isRunning()
    running_alarm.player.stop.assert_called()


def test_stop_stops_the_polling_loop(running_alarm):
    """Scenario: Exit with no alarm."""
    running_alarm.stop()

    assert running_alarm.running is False


def test_stop_without_start_is_harmless(alarm):
    alarm.player = Mock()

    alarm.stop()

    assert not alarm.isRunning()


def test_the_alarm_wait_is_bounded_to_one_second(alarm):
    """Requirement: Bounded waiting (1 second for the alarm)."""
    alarm.player = Mock()
    alarm.isRunning = Mock(return_value=True)
    alarm.wait = Mock(return_value=False)
    alarm.terminate = Mock()

    alarm.stop()

    alarm.wait.assert_any_call(1000)
    alarm.terminate.assert_called_once()
