"""Spec: openspec/specs/app-lifecycle (Orderly shutdown, Failure isolation)."""
import logging

import pytest

from app.lifecycle import shutdown


class Component:
    """Records the moment its shutdown method is called."""

    def __init__(self, name, calls, method, fail=False):
        self.name, self.calls, self.fail = name, calls, fail
        setattr(self, method, self._call)

    def _call(self):
        self.calls.append(self.name)
        if self.fail:
            raise RuntimeError(f"{self.name} failed")


@pytest.fixture
def parts():
    calls = []
    return calls, {
        "window": Component("window", calls, "close"),
        "ecu_thread": Component("ecu", calls, "stop"),
        "alarm": Component("alarm", calls, "stop"),
        "log_writer": Component("datalog", calls, "close"),
    }


def test_components_are_stopped_in_the_specified_order(parts):
    """Scenario: Normal exit."""
    calls, components = parts

    shutdown(**components)

    assert calls == ["window", "ecu", "alarm", "datalog"]


def test_each_component_is_stopped_exactly_once(parts):
    calls, components = parts

    shutdown(**components)

    assert sorted(calls) == ["alarm", "datalog", "ecu", "window"]


def test_a_failing_component_is_logged_and_the_rest_still_stop(parts, caplog):
    """Scenario: Alarm fails to stop."""
    calls, components = parts
    components["alarm"].fail = True

    with caplog.at_level(logging.ERROR):
        shutdown(**components)

    assert calls == ["window", "ecu", "alarm", "datalog"]
    assert any("alarm" in record.getMessage().lower() for record in caplog.records)


@pytest.mark.parametrize("failing", ["window", "ecu_thread", "alarm", "log_writer"])
def test_a_failure_in_any_step_never_stops_the_later_ones(parts, failing):
    """Requirement: Failure isolation."""
    calls, components = parts
    components[failing].fail = True

    shutdown(**components)

    assert len(calls) == 4


def test_missing_components_are_tolerated(parts):
    calls, components = parts
    components["window"] = None
    components["alarm"] = None

    shutdown(**components)

    assert calls == ["ecu", "datalog"]


def test_the_datalog_is_closed_last_so_it_keeps_the_frames_that_arrived(parts):
    """Scenario: Last frames are kept."""
    calls, components = parts

    shutdown(**components)

    assert calls[-1] == "datalog"
    assert calls.index("ecu") < calls.index("datalog")


# ── Inclinometer connection (change gyro-inclination) ────────────────────────────────────────────────────

def test_the_inclinometer_is_stopped_right_after_the_ecu_source(parts):
    """Spec: Inclinometer connection stops on shutdown (order)."""
    calls, components = parts

    shutdown(**components, gyro=Component("gyro", calls, "stop"))

    assert calls == ["window", "ecu", "gyro", "alarm", "datalog"]


def test_the_inclinometer_port_is_closed_on_exit():
    """Scenario: Port closed."""
    from tests.test_gyro_connection import Ports
    from app.gyro.connection import GyroConnection

    ports = Ports("COM7")
    gyro = GyroConnection("COM7", serial_factory=ports, idle_wait=0.01)
    gyro.start()
    import time
    deadline = time.monotonic() + 2
    while not gyro.is_open() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert gyro.is_open()

    shutdown(None, None, None, None, gyro=gyro)

    assert ports.last.closed
    assert not gyro._thread.is_alive()


def test_shutdown_without_a_configured_inclinometer_completes(parts):
    """Scenario: Not configured."""
    from app.gyro.connection import GyroConnection

    calls, components = parts

    shutdown(**components, gyro=GyroConnection(""))

    assert calls == ["window", "ecu", "alarm", "datalog"]


def test_shutdown_without_an_inclinometer_at_all_completes(parts):
    calls, components = parts

    shutdown(**components, gyro=None)

    assert calls == ["window", "ecu", "alarm", "datalog"]


def test_a_failing_inclinometer_stop_is_logged_and_the_rest_still_stop(parts, caplog):
    """Scenario: Stop fails."""
    calls, components = parts

    with caplog.at_level(logging.ERROR):
        shutdown(**components, gyro=Component("gyro", calls, "stop", fail=True))

    assert calls == ["window", "ecu", "gyro", "alarm", "datalog"]
    assert any("inclinometer" in record.getMessage().lower() for record in caplog.records)


def test_an_inclinometer_thread_that_does_not_finish_in_time_only_warns(caplog):
    """Spec: waiting for it is bounded; on timeout the app logs a warning and continues."""
    from unittest.mock import Mock
    from app.gyro.connection import GyroConnection

    gyro = GyroConnection("")
    gyro._thread = Mock(is_alive=Mock(return_value=True), join=Mock())

    with caplog.at_level(logging.WARNING):
        shutdown(None, None, None, None, gyro=gyro)

    gyro._thread.join.assert_called_once_with(1.0)
    assert any("did not finish" in record.getMessage() for record in caplog.records)
