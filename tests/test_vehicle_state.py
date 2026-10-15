"""Spec: openspec/specs/vehicle-state."""
import threading

import pytest

import app.state.state as state_module
from app.masterinjection.signal import Signal
from app.state.event import EventType
from app.state.state import vehicle_state
from tests.helpers import parsed


def test_publishing_merges_by_signal():
    """Scenario: Merge."""
    vehicle_state.update({Signal.RPM: parsed(Signal.RPM, 1000), Signal.MAP: parsed(Signal.MAP, 50)})
    vehicle_state.update({Signal.RPM: parsed(Signal.RPM, 2000)})

    assert vehicle_state.get(Signal.RPM).value == 2000
    assert vehicle_state.get(Signal.MAP).value == 50


def test_signal_never_received_reads_as_nothing():
    """Scenario: Never received."""
    assert vehicle_state.get(Signal.RPM) is None


def test_get_all_returns_a_copy():
    """Requirement: Latest signal snapshot (copy of the whole snapshot)."""
    vehicle_state.update({Signal.RPM: parsed(Signal.RPM, 1000)})
    snapshot = vehicle_state.get_all()
    snapshot.clear()

    assert vehicle_state.get(Signal.RPM) is not None


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(state_module.time, "time", lambda: now[0])
    return now


def test_alarm_is_firing_inside_the_two_second_window(clock):
    """Scenario: Firing window."""
    vehicle_state.set_alarm(Signal.RPM, True)
    clock[0] += 1.5

    assert vehicle_state.is_alarm_firing(Signal.RPM)
    assert vehicle_state.is_any_alarm_firing()


def test_alarm_stops_firing_after_two_seconds(clock):
    """Scenario: Window elapsed."""
    vehicle_state.set_alarm(Signal.RPM, True)
    clock[0] += 2.0

    assert not vehicle_state.is_alarm_firing(Signal.RPM)
    assert not vehicle_state.is_any_alarm_firing()


def test_reporting_not_out_of_range_does_not_clear_an_alarm(clock):
    """Requirement: Alarm timestamps (inactive report keeps the timestamp)."""
    vehicle_state.set_alarm(Signal.RPM, True)
    vehicle_state.set_alarm(Signal.RPM, False)

    assert vehicle_state.is_alarm_firing(Signal.RPM)


def test_never_alarmed_signal_is_not_firing():
    assert not vehicle_state.is_alarm_firing(Signal.MAP)
    assert not vehicle_state.is_any_alarm_firing()


def test_breakpoints_and_ve_map_start_at_zero():
    """Requirement: Axis breakpoints and VE map."""
    assert vehicle_state.get_rpm_breakpoints() == [0] * 16
    assert vehicle_state.get_map_breakpoints() == [0] * 16
    assert vehicle_state.get_ve_map() == [[0] * 16 for _ in range(16)]


@pytest.fixture
def events():
    received = []
    vehicle_state.emitter.connect(received.append)
    yield received
    vehicle_state.emitter.disconnect(received.append)


def test_setting_map_breakpoints_emits_event(events):
    """Scenario: Breakpoints loaded."""
    values = list(range(10, 170, 10))
    vehicle_state.set_map_breakpoints(values)

    assert vehicle_state.get_map_breakpoints() == values
    assert [(e.type_, e.args) for e in events] == [(EventType.MAP_BREAKPOINTS, [values])]


def test_setting_rpm_breakpoints_emits_event(events):
    values = list(range(500, 6500, 400))[:16]
    vehicle_state.set_rpm_breakpoints(values)

    assert [(e.type_, e.args) for e in events] == [(EventType.RPM_BREAKPOINTS, [values])]


def test_setting_a_ve_row_emits_event(events):
    """Scenario: Row loaded."""
    row = list(range(100, 116))
    vehicle_state.set_ve_map(row, 3)

    assert vehicle_state.get_ve_map()[3] == row
    assert [(e.type_, e.args) for e in events] == [(EventType.FUEL_MAP, [3, row])]


def test_ve_row_with_wrong_length_is_ignored(events):
    """Scenario: Wrong row length."""
    vehicle_state.set_ve_map([1] * 15, 3)

    assert vehicle_state.get_ve_map()[3] == [0] * 16
    assert events == []


def test_ignition_map_starts_at_zero():
    """Requirement: Axis breakpoints and VE map (the ignition map is 16x16 of zeros)."""
    assert vehicle_state.get_ignition_map() == [[0] * 16 for _ in range(16)]


def test_setting_an_ignition_row_emits_event(events):
    """Scenario: Ignition row loaded."""
    row = list(range(10, 26))
    vehicle_state.set_ignition_row(row, 4)

    assert vehicle_state.get_ignition_map()[4] == row
    assert [(e.type_, e.args) for e in events] == [(EventType.IGNITION_MAP, [4, row])]


def test_ignition_row_with_wrong_length_is_ignored(events):
    """Scenario: Wrong ignition row length."""
    vehicle_state.set_ignition_row([1] * 15, 4)

    assert vehicle_state.get_ignition_map()[4] == [0] * 16
    assert events == []


@pytest.mark.parametrize("index", [-1, 16])
def test_ignition_row_with_out_of_range_index_is_ignored(events, index):
    """Requirement: Axis breakpoints and VE map (a row is stored at the given index only)."""
    vehicle_state.set_ignition_row([1] * 16, index)

    assert vehicle_state.get_ignition_map() == [[0] * 16 for _ in range(16)]
    assert events == []


def test_concurrent_updates_are_consistent():
    """Requirement: Thread safety (no lost or partial updates)."""
    errors = []

    def writer(value):
        try:
            for _ in range(500):
                vehicle_state.update({Signal.RPM: parsed(Signal.RPM, value), Signal.MAP: parsed(Signal.MAP, value)})
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    def reader():
        try:
            for _ in range(500):
                snapshot = vehicle_state.get_all()
                if snapshot:
                    assert snapshot[Signal.RPM].value == snapshot[Signal.MAP].value
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(v,)) for v in (1, 2)] + [threading.Thread(target=reader)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []


# ------------------------------------------------------------ parameter block X02

def test_parameter_block_never_received_reads_as_nothing():
    """Scenario: Never received (parameter block)."""
    assert vehicle_state.get_x02() is None


def test_setting_the_parameter_block_emits_event(events):
    """Scenario: Parameter block loaded."""
    block = list(range(100, 116))
    vehicle_state.set_x02(block)

    assert vehicle_state.get_x02() == block
    assert [(e.type_, e.args) for e in events] == [(EventType.PARAMETER_BLOCK, [block])]


def test_parameter_block_with_wrong_length_is_ignored(events):
    """Scenario: Wrong length (parameter block)."""
    vehicle_state.set_x02([1] * 16)
    events.clear()

    vehicle_state.set_x02([2] * 15)

    assert vehicle_state.get_x02() == [1] * 16
    assert events == []


def test_a_newer_parameter_block_replaces_the_older_one():
    """Scenario: Replacement."""
    vehicle_state.set_x02([1] * 16)
    vehicle_state.set_x02([2] * 16)

    assert vehicle_state.get_x02() == [2] * 16


def test_parameter_block_reader_gets_a_copy():
    """Scenario: Copy returned."""
    vehicle_state.set_x02([1] * 16)

    vehicle_state.get_x02()[11] = 99

    assert vehicle_state.get_x02() == [1] * 16
