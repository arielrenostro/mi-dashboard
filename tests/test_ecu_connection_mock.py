"""Spec: openspec/specs/ecu-connection (Mock replay, Connection status) and app-configuration (mock_skip_lines)."""
import pytest

import app.ecu_connection.mock_log as mock_module
from app.ecu_connection.ecu_connection import EcuConnectionStatus
from app.ecu_connection.mock_log import EcuConnectionMock
from app.masterinjection.protocol import EcuCommand
from app.state.state import vehicle_state
from tests.conftest import RecordingEmitter

MAP_BREAKPOINTS = [20, 30, 40, 50, 60, 70, 80, 90, 100, 120, 140, 160, 180, 200, 220, 240]
RPM_BREAKPOINTS = [400, 800, 1200, 1600, 2000, 2400, 2800, 3200, 3600, 4000, 4400, 4800, 5200, 5600, 6200, 6800]


@pytest.fixture
def sleeps(monkeypatch):
    """Replace time.sleep in the mock so replays are instant, and record the pauses."""
    calls = []
    monkeypatch.setattr(mock_module.time, "sleep", calls.append)
    return calls


def write_log(path, count, header="Timestamp,Event,Mess 1,RPM"):
    """A replay file: one header line followed by `count` data lines #D01;1 .. #D01;<count>."""
    path.write_text(header + "\n" + "".join(f"#D01;{i}\n" for i in range(1, count + 1)))
    return str(path)


def make_mock(path, skip=None, running=True):
    mock = EcuConnectionMock(path) if skip is None else EcuConnectionMock(path, skip_lines=skip)
    mock.emitter = RecordingEmitter()
    mock.running = running
    return mock


def emitted_numbers(mock):
    return [int(line.split(";")[1]) for line in mock.emitter.lines]


# ------------------------------------------------------------------ start-up data

def test_start_publishes_fixed_breakpoints(tmp_path, sleeps):
    """Requirement: Mock replay (fixed breakpoints)."""
    make_mock(write_log(tmp_path / "log.csv", 0)).run()

    assert vehicle_state.get_map_breakpoints() == MAP_BREAKPOINTS
    assert vehicle_state.get_rpm_breakpoints() == RPM_BREAKPOINTS


def test_start_publishes_the_fixed_ve_map(tmp_path, sleeps):
    """Requirement: Mock replay (fixed VE map)."""
    make_mock(write_log(tmp_path / "log.csv", 0)).run()
    ve_map = vehicle_state.get_ve_map()

    assert ve_map[0][:3] == [561, 588, 630]  # #F01, lowest MAP
    assert ve_map[15][:3] == [855, 898, 909]  # #F16, highest MAP
    assert all(len(row) == 16 for row in ve_map)


# ----------------------------------------------------------------------- replay

def test_header_is_skipped_and_every_data_line_is_emitted_in_order(tmp_path, sleeps):
    mock = make_mock(write_log(tmp_path / "log.csv", 5))

    mock.run()

    assert mock.emitter.lines == [f"#D01;{i}" for i in range(1, 6)]


def test_lines_are_emitted_trimmed(tmp_path, sleeps):
    path = tmp_path / "log.csv"
    path.write_bytes(b"Header\r\n#D01;1;2  \r\n#D01;3;4\t\r\n")
    mock = make_mock(str(path))

    mock.run()

    assert mock.emitter.lines == ["#D01;1;2", "#D01;3;4"]


def test_one_line_is_emitted_every_tenth_of_a_second(tmp_path, sleeps):
    """Scenario: Replay pace."""
    make_mock(write_log(tmp_path / "log.csv", 4)).run()

    assert sleeps == [0.1] * 4


def test_replay_stops_when_the_source_is_stopped(tmp_path, sleeps):
    mock = make_mock(write_log(tmp_path / "log.csv", 10))
    mock.emitter.emit = lambda line, original=mock.emitter.emit: (original(line), setattr(mock, "running", len(mock.emitter.lines) < 2))

    mock.run()

    assert len(mock.emitter.lines) == 2


# ------------------------------------------------------------------- skip lines

def test_nothing_is_skipped_by_default(tmp_path, sleeps):
    """Requirement: Supported settings (default 0)."""
    mock = make_mock(write_log(tmp_path / "log.csv", 6))

    mock.run()

    assert emitted_numbers(mock) == [1, 2, 3, 4, 5, 6]


@pytest.mark.parametrize("skip", [1, 3, 5])
def test_configured_skip_starts_at_the_following_data_line(tmp_path, sleeps, skip):
    """Scenario: Configured skip (skip N -> first emitted is data line N+1)."""
    mock = make_mock(write_log(tmp_path / "log.csv", 8), skip=skip)

    mock.run()

    assert emitted_numbers(mock) == list(range(skip + 1, 9))


def test_skip_applies_to_the_first_pass_only(tmp_path, sleeps):
    """Scenario: Restart after skip."""
    mock = make_mock(write_log(tmp_path / "log.csv", 6), skip=4)

    mock.run()
    first_pass = emitted_numbers(mock)
    mock.emitter.lines.clear()
    mock.run()

    assert first_pass == [5, 6]
    assert emitted_numbers(mock) == [1, 2, 3, 4, 5, 6]


def test_replay_restarts_from_the_first_data_line(tmp_path, sleeps):
    """Scenario: End of file."""
    mock = make_mock(write_log(tmp_path / "log.csv", 3))

    mock.run()
    mock.run()

    assert emitted_numbers(mock) == [1, 2, 3, 1, 2, 3]


def test_skip_larger_than_the_file_consumes_only_the_first_pass(tmp_path, sleeps):
    """Requirement: Mock replay (skip applies to the first pass only, even if it swallows the whole file)."""
    mock = make_mock(write_log(tmp_path / "log.csv", 3), skip=10)

    mock.run()
    assert mock.emitter.lines == []

    mock.run()
    assert emitted_numbers(mock) == [1, 2, 3]


# ----------------------------------------------------------- commands and status

def test_commands_do_not_affect_the_replay(tmp_path, sleeps):
    """Requirement: Mock replay (commands have no effect)."""
    mock = make_mock(write_log(tmp_path / "log.csv", 2))

    mock.send_command(EcuCommand.LAMBDA_LOOP_OPEN)
    mock.send_command(EcuCommand.VE_ROW_3, [1] * 16)
    assert mock.emitter.lines == []

    mock.run()
    assert emitted_numbers(mock) == [1, 2]


@pytest.mark.parametrize(
    "running,status", [(True, EcuConnectionStatus.CONNECTED), (False, EcuConnectionStatus.DISCONNECTED)]
)
def test_status_is_connected_only_while_running(tmp_path, running, status):
    """Requirement: Connection status (mock source)."""
    mock = make_mock(write_log(tmp_path / "log.csv", 0), running=running)

    assert mock.get_connection_status() == status
    assert mock.is_connected() is running
