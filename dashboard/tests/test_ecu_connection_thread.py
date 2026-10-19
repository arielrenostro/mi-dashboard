"""Spec: openspec/specs/ecu-connection (Shutdown) and app-lifecycle (Bounded waiting)."""
import logging
import time
from unittest.mock import Mock

import pytest

from app.ecu_connection.ecu_connection import EcuConnection
from app.ecu_connection.mock_log import EcuConnectionMock
from app.ecu_connection.thread import EcuConnectionThread
from app.state.state import vehicle_state


class CountingConnection(EcuConnection):
    """A connection whose run() does a little work and returns, like the real sources."""

    def __init__(self):
        super().__init__()
        self.calls = 0

    def send_command(self, cmd, args=None):
        pass

    def run(self):
        self.calls += 1
        time.sleep(0.005)

    def is_connected(self):
        return self.running


def wait_until(condition, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.005)
    return False


@pytest.fixture
def make_thread(qapp, request):
    """Builds a connection thread and always shuts it down, even when a test fails."""

    def factory(connection):
        thread = EcuConnectionThread(connection)

        def cleanup():
            thread.running = False
            connection.running = False
            thread.wait(2000)

        request.addfinalizer(cleanup)
        return thread

    return factory


def test_stop_waits_until_the_thread_has_finished(make_thread):
    """Requirement: Shutdown (the connection thread finishes)."""
    connection = CountingConnection()
    thread = make_thread(connection)
    thread.start()
    assert wait_until(lambda: connection.calls > 0)

    thread.stop()

    assert not thread.isRunning()
    assert connection.running is False


def test_the_source_is_not_run_again_after_stop(make_thread):
    connection = CountingConnection()
    thread = make_thread(connection)
    thread.start()
    assert wait_until(lambda: connection.calls > 0)

    thread.stop()
    calls = connection.calls
    time.sleep(0.05)

    assert connection.calls == calls


def test_stop_before_start_is_harmless(make_thread):
    thread = make_thread(CountingConnection())

    thread.stop()

    assert not thread.isRunning()


def test_stop_twice_is_harmless(make_thread):
    connection = CountingConnection()
    thread = make_thread(connection)
    thread.start()
    assert wait_until(lambda: connection.calls > 0)

    thread.stop()
    thread.stop()

    assert not thread.isRunning()


def test_the_wait_is_bounded_and_a_stuck_thread_is_logged_and_terminated(make_thread, caplog):
    """Requirement: Bounded waiting / Scenario: Thread does not finish."""
    thread = make_thread(CountingConnection())
    thread.isRunning = Mock(return_value=True)
    thread.wait = Mock(return_value=False)  # never finishes in time
    thread.terminate = Mock()

    with caplog.at_level(logging.WARNING):
        thread.stop(timeout_ms=50)

    thread.wait.assert_any_call(50)
    thread.terminate.assert_called_once()
    assert any("did not finish" in record.getMessage() for record in caplog.records)


def test_default_wait_for_the_ecu_source_is_three_seconds(make_thread):
    thread = make_thread(CountingConnection())
    thread.isRunning = Mock(return_value=True)
    thread.wait = Mock(return_value=True)

    thread.stop()

    thread.wait.assert_called_once_with(3000)


def test_a_thread_that_finishes_in_time_is_not_terminated(make_thread):
    thread = make_thread(CountingConnection())
    thread.isRunning = Mock(return_value=True)
    thread.wait = Mock(return_value=True)
    thread.terminate = Mock()

    thread.stop()

    thread.terminate.assert_not_called()


def test_mock_source_stops_during_a_replay(make_thread, tmp_path):
    """Scenario: Exit during a mock replay."""
    path = tmp_path / "log.csv"
    path.write_text("Header\n" + "".join(f"#D01;{i}\n" for i in range(200)))
    mock = EcuConnectionMock(str(path))
    thread = make_thread(mock)
    thread.start()
    assert wait_until(lambda: vehicle_state.get_map_breakpoints()[0] == 20)  # the replay is under way

    started = time.time()
    thread.stop()

    assert not thread.isRunning()
    assert time.time() - started < 1.0


# ------------------------------------------------------------ error signal path

def test_the_thread_gives_the_connection_its_error_signal(make_thread):
    """Requirement: Connection error reporting (reports are delivered through the thread's signal)."""
    connection = CountingConnection()

    thread = make_thread(connection)
    received = []
    thread.error.connect(received.append)

    connection.error_emitter.emit("erro de teste")

    assert received == ["erro de teste"]


def test_a_reported_error_reaches_the_receivers_of_the_thread_signal(make_thread):
    connection = CountingConnection()
    thread = make_thread(connection)
    received = []
    thread.error.connect(received.append)

    connection.report_error("Falha ao conectar em COM3")
    connection.report_error("Falha ao conectar em COM3")  # identical: not reported again
    connection.report_error("Conexão perdida")

    assert received == ["Falha ao conectar em COM3", "Conexão perdida"]


def test_clearing_the_reported_error_allows_the_same_message_again(make_thread):
    connection = CountingConnection()
    thread = make_thread(connection)
    received = []
    thread.error.connect(received.append)

    connection.report_error("erro")
    connection.clear_reported_error()
    connection.report_error("erro")

    assert received == ["erro", "erro"]
