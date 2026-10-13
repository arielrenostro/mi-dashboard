"""Spec: openspec/specs/ecu-connection (serial source) and ecu-protocol."""
from collections import deque

import pytest

from app.ecu_connection.ecu_connection import EcuConnectionStatus
from app.ecu_connection.serial import EcuConnectionSerial
from app.masterinjection.protocol import EcuCommand, EcuResponse
from app.state.state import vehicle_state
from tests.conftest import RecordingEmitter
from tests.helpers import MAP_AXIS, RPM_AXIS


class FakeSerial:
    """Scriptable replacement for the pyserial port.

    `responder(text)` is called for every line written and returns a list of reply lines; a reply of
    None stands for a read timeout (empty read). `lines` are replies already waiting to be read.
    """

    def __init__(self, lines=(), responder=None, fail_open_times=0):
        self.is_open = True
        self.written = []
        self.closed = 0
        self.open_calls = 0
        self.fail_open_times = fail_open_times
        self._replies = deque(lines)
        self._responder = responder
        self.read_error = None

    def open(self):
        self.open_calls += 1
        if self.open_calls <= self.fail_open_times:
            raise OSError("port unavailable")
        self.is_open = True

    def close(self):
        self.closed += 1
        self.is_open = False

    def write(self, data):
        text = data.decode("utf-8").rstrip("\n")
        assert data.endswith(b"\n")
        self.written.append(text)
        if self._responder:
            self._replies.extend(self._responder(text))

    def readline(self):
        if self.read_error:
            raise self.read_error
        if not self._replies:
            return b""
        reply = self._replies.popleft()
        return b"" if reply is None else (reply + "\n").encode("utf-8")


def ve_row(n):
    return [100 * n + col for col in range(16)]


def ecu_responder(text):
    """A well-behaved ECU."""
    if text == "#D50":
        return ["#D50;MI;1.0"]
    if text == "#I21":
        return ["#I21;" + ";".join(map(str, MAP_AXIS))]
    if text == "#I20":
        return ["#I20;" + ";".join(map(str, RPM_AXIS))]
    if text.startswith("#F"):
        return [f"#F{text[2:]};" + ";".join(map(str, ve_row(int(text[2:]))))]
    if text == "#D01":
        return ["#D01;1;2"]
    return []


@pytest.fixture
def make_connection():
    def factory(serial_port=None):
        conn = EcuConnectionSerial("COM1", 115200)
        conn.serial = serial_port or FakeSerial()
        conn.emitter = RecordingEmitter()
        conn.running = True
        return conn

    return factory


# -------------------------------------------------------------- frame assembly

def test_complete_cycle_emits_one_combined_line(make_connection):
    """Scenario: Complete cycle."""
    conn = make_connection(FakeSerial(lines=["#D01;1;2", "#D02;3;4"]))

    conn.run()
    conn.run()

    assert conn.emitter.lines == ["#D01;1;2;#D02;3;4"]
    assert conn.d01 is None and conn.d02 is None


def test_incomplete_cycle_emits_nothing(make_connection):
    """Scenario: Incomplete cycle."""
    conn = make_connection(FakeSerial(lines=["#D01;1;2"]))

    conn.run()

    assert conn.emitter.lines == []


def test_two_cycles_emit_two_lines(make_connection):
    conn = make_connection(FakeSerial(lines=["#D01;1", "#D02;2", "#D01;3", "#D02;4"]))

    for _ in range(4):
        conn.run()

    assert conn.emitter.lines == ["#D01;1;#D02;2", "#D01;3;#D02;4"]


def test_other_lines_are_emitted_unchanged(make_connection):
    """Requirement: Frame assembly (any other non-empty line)."""
    conn = make_connection(FakeSerial(lines=["#D03;9;9"]))

    conn.run()

    assert conn.emitter.lines == ["#D03;9;9"]


# ---------------------------------------------------------------- command queue

def test_command_is_written_after_the_next_complete_cycle(make_connection):
    """Scenario: Command during streaming."""
    port = FakeSerial(lines=["#D01;1", "#D02;2"])
    conn = make_connection(port)
    conn.send_command(EcuCommand.LAMBDA_LOOP_OPEN)

    conn.run()
    assert port.written == []  # mid-cycle: nothing is written

    conn.run()
    assert port.written == ["#D06"]


def test_commands_are_written_in_order(make_connection):
    """Scenario: Order."""
    port = FakeSerial(lines=["#D01;1", "#D02;2"])
    conn = make_connection(port)
    conn.send_command(EcuCommand.LAMBDA_LOOP_CLOSE)
    conn.send_command(EcuCommand.LAMBDA_LOOP_OPEN)

    conn.run()
    conn.run()

    assert port.written == ["#D05", "#D06"]


def test_command_arguments_are_joined_with_semicolons(make_connection):
    """Scenario: Command with arguments."""
    port = FakeSerial(lines=["#D01;1", "#D02;2"])
    conn = make_connection(port)
    conn.send_command(EcuCommand.VE_ROW_5, [10, 20, 30])

    conn.run()
    conn.run()

    assert port.written == ["#F05;10;20;30"]


def test_command_is_also_written_after_a_non_telemetry_line(make_connection):
    """Requirement: Command queue (after a non-telemetry line)."""
    port = FakeSerial(lines=["#D03;x"])
    conn = make_connection(port)
    conn.send_command(EcuCommand.LAMBDA_LOOP_OPEN)

    conn.run()

    assert port.written == ["#D06"]


# ------------------------------------------------------------ failure recovery

def test_three_empty_reads_close_the_port_and_restart(make_connection):
    """Scenario: Silent link."""
    port = FakeSerial()
    conn = make_connection(port)

    for _ in range(3):
        conn.run()
    assert port.closed == 0

    conn.run()

    assert port.closed == 1
    assert conn.get_connection_status() == EcuConnectionStatus.DISCONNECTED


def test_data_resets_the_empty_read_counter(make_connection):
    port = FakeSerial(lines=[None, None, "#D03;x", None, None])
    conn = make_connection(port)

    for _ in range(5):
        conn.run()

    assert port.closed == 0


def test_io_error_closes_the_port(make_connection):
    """Scenario: I/O error."""
    port = FakeSerial()
    port.read_error = OSError("link lost")
    conn = make_connection(port)

    conn.run()

    assert port.closed == 1
    assert conn.get_connection_status() == EcuConnectionStatus.DISCONNECTED


def test_closing_discards_a_half_received_cycle(make_connection):
    conn = make_connection(FakeSerial(lines=["#D01;1"]))
    conn.run()

    conn._close()

    assert conn.d01 is None and conn.d02 is None


# ------------------------------------------------------ connect and synchronize

def test_connect_performs_the_full_sequence_in_order(make_connection):
    """Scenario: Normal connect."""
    port = FakeSerial(responder=ecu_responder)
    conn = make_connection(port)

    conn.connect()

    expected = ["#D50", "#I21", "#I20"] + [f"#F{n:02d}" for n in range(1, 17)] + ["#D01"]
    assert port.written == expected
    assert conn.get_connection_status() == EcuConnectionStatus.CONNECTED


def test_connect_publishes_breakpoints_and_ve_rows_to_the_shared_state(make_connection):
    """Requirement: VE row publication (and breakpoints)."""
    conn = make_connection(FakeSerial(responder=ecu_responder))

    conn.connect()

    assert vehicle_state.get_map_breakpoints() == MAP_AXIS
    assert vehicle_state.get_rpm_breakpoints() == RPM_AXIS
    assert vehicle_state.get_ve_map() == [ve_row(n) for n in range(1, 17)]


def test_all_sixteen_ve_rows_are_requested(make_connection):
    """Scenario: Highest-MAP row loaded (change fetch-ve-row-16)."""
    port = FakeSerial(responder=ecu_responder)
    conn = make_connection(port)

    conn._fetch_ve_map()

    assert port.written == [f"#F{n:02d}" for n in range(1, 17)]
    assert vehicle_state.get_ve_map()[15] == ve_row(16)
    assert vehicle_state.get_ve_map()[0] == ve_row(1)


def test_status_goes_through_connecting_and_handshake(make_connection, monkeypatch):
    seen = []
    conn = make_connection(FakeSerial(responder=ecu_responder))
    original = conn._start_communication

    def spy():
        seen.append(conn.get_connection_status())
        original()

    monkeypatch.setattr(conn, "_start_communication", spy)
    conn.connect()

    assert seen == [EcuConnectionStatus.HANDSHAKE]


def test_unanswered_request_is_resent_every_third_read(make_connection):
    """Scenario: Silent ECU."""
    reads_before_answer = 4
    port = FakeSerial(responder=lambda t: [None] * reads_before_answer + ["#D50;ok"] if t == "#D50" else [])
    conn = make_connection(port)

    line = conn._send_and_retry(EcuCommand.ECU_INFO, [EcuResponse.ECU_INFO])

    assert line == "#D50;ok"
    assert port.written.count("#D50") == 2  # initial send + one resend after 3 reads


def test_connect_retries_until_the_port_opens(make_connection):
    """Scenario: Port cannot be opened."""
    port = FakeSerial(responder=ecu_responder, fail_open_times=2)
    port.is_open = False
    conn = make_connection(port)

    conn.connect()

    assert port.open_calls == 3
    assert conn.get_connection_status() == EcuConnectionStatus.CONNECTED


def test_send_command_is_safe_from_other_threads(make_connection):
    import threading

    conn = make_connection()
    threads = [threading.Thread(target=lambda: [conn.send_command(EcuCommand.LAMBDA_LOOP_OPEN) for _ in range(100)]) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert conn._command_queue.qsize() == 400


# --------------------------------------------------------------------- shutdown

def run_in_thread(target):
    import threading

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread


def test_stop_clears_the_running_flag_and_closes_the_port(make_connection):
    """Requirement: Shutdown (the port is closed and the connection stops)."""
    port = FakeSerial()
    conn = make_connection(port)

    conn.stop()

    assert conn.running is False
    assert port.closed == 1


def test_stop_ends_a_connect_loop_that_keeps_retrying(make_connection):
    """Scenario: Exit while the port is unavailable."""
    import time

    port = FakeSerial(fail_open_times=10**9)
    port.is_open = False
    conn = make_connection(port)
    thread = run_in_thread(conn.connect)
    try:
        time.sleep(0.05)
        assert thread.is_alive()

        conn.stop()
        thread.join(2.0)

        assert not thread.is_alive()
    finally:
        conn.running = False  # never leave a spinning loop behind for the other tests
        thread.join(2.0)


def test_stop_ends_a_request_waiting_for_an_ecu_answer(make_connection):
    """Scenario: Exit during the handshake."""
    import time

    conn = make_connection(FakeSerial())  # a silent ECU
    thread = run_in_thread(lambda: conn._send_and_retry(EcuCommand.ECU_INFO, [EcuResponse.ECU_INFO]))
    try:
        time.sleep(0.05)
        assert thread.is_alive()

        conn.stop()
        thread.join(2.0)

        assert not thread.is_alive()
    finally:
        conn.running = False
        thread.join(2.0)


def test_stop_is_harmless_when_the_port_is_already_closed(make_connection):
    conn = make_connection(FakeSerial())

    conn.stop()
    conn.stop()

    assert conn.running is False
