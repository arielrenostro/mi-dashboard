"""Spec: openspec/specs/gyro-connection (the optional inclinometer)."""
import pytest

from app.gyro.protocol import (
    CALIBRATION_POSITIONS, COMMANDS, GyroCalibrationReport, GyroCommandReply, GyroHeader, GyroMessage, GyroReading,
    parse_line)
from app.gyro.state import CalibrationProgress, GyroState, GyroStatus

REPORT = "#K;OFFSET;0.0100;-0.0200;-0.3450;SCALE;1.0000;1.0000;1.0350;"
SAVED = "#M;CALIBRACAO_SALVA;"
INVALID = "#M;CALIBRACAO_INVALIDA_REPITA_AS_POSICOES;"

DATA = "#D;12840;1.37;-0.62;-0.024;-0.011;1.000;31.4;"
HEADER = "#H;t_ms;pitch;roll;ax_g;ay_g;az_g;temp_c;"


def data(t_ms=12840, pitch=1.37, roll=-0.62):
    return f"#D;{t_ms};{pitch};{roll};-0.024;-0.011;1.000;31.4;"


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


# ── Line format ──────────────────────────────────────────────────────────────────────────────────────────

def test_data_line_is_a_reading():
    """Scenario: Data line."""
    reading = parse_line(DATA)

    assert reading == GyroReading(12840, 1.37, -0.62, -0.024, -0.011, 1.0, 31.4)


def test_carriage_return_is_ignored():
    """Scenario: Carriage return."""
    assert parse_line(DATA + "\r\n") == parse_line(DATA)


def test_data_line_with_six_values_is_ignored():
    """Scenario: Wrong number of values."""
    assert parse_line("#D;12840;1.37;-0.62;-0.024;-0.011;1.000;") is None


def test_data_line_with_eight_values_is_ignored():
    assert parse_line(DATA + "9;") is None


def test_data_line_of_the_old_ten_value_format_is_ignored():
    """Scenario: Wrong number of values (the gyroscope columns are gone)."""
    assert parse_line("#D;12840;1.37;-0.62;-0.024;-0.011;1.000;0.12;-0.05;0.03;31.4;") is None


def test_data_line_with_a_value_that_is_not_a_number_is_ignored():
    """Scenario: Not a number."""
    assert parse_line("#D;12840;abc;-0.62;-0.024;-0.011;1.000;31.4;") is None


def test_data_line_with_a_value_that_is_not_finite_is_ignored():
    """Scenario: Not finite."""
    assert parse_line("#D;12840;nan;-0.62;-0.024;-0.011;1.000;31.4;") is None
    assert parse_line("#D;12840;inf;-0.62;-0.024;-0.011;1.000;31.4;") is None


@pytest.mark.parametrize("line", ["hello;1;2;", "", ";", "D;1;2;", "#X;1;"])
def test_unknown_lines_are_ignored(line):
    """Scenario: Unknown prefix."""
    assert parse_line(line) is None


def test_header_is_not_a_reading():
    """Scenario: Header."""
    assert parse_line(HEADER) == GyroHeader()


def test_message_carries_its_text():
    assert parse_line("#M;COMANDO_DESCONHECIDO;") == GyroMessage("COMANDO_DESCONHECIDO")


@pytest.mark.parametrize("line, status", [("#Z;OK;", "OK"), ("#Z;OK;\r\n", "OK"), ("#Z;ERRO;", "ERRO")])
def test_command_reply_carries_the_command_and_its_status(line, status):
    """Scenario: Command reply."""
    assert parse_line(line) == GyroCommandReply("#Z", status)


@pytest.mark.parametrize("line", ["#Z;OK;EXTRA;", "#Z;", "#Z;;"])
def test_command_reply_with_the_wrong_shape_is_ignored(line):
    """Scenario: Command reply with the wrong shape."""
    assert parse_line(line) is None


@pytest.mark.parametrize("line", ["#C;OK;", "#C;CALIBRANDO;", "#R;OK;"])
def test_replies_of_the_retired_commands_are_ignored(line):
    """Scenario: Retired replies."""
    assert parse_line(line) is None


@pytest.mark.parametrize("command", CALIBRATION_POSITIONS + ("#KP", "#KR"))
def test_calibration_reply_carries_the_command_and_its_status(command):
    """Scenario: Calibration reply."""
    assert parse_line(f"{command};OK;") == GyroCommandReply(command, "OK")


@pytest.mark.parametrize("line", ["#KQU;OK;", "#KZX;OK;", "#KZU;OK;EXTRA;", "#KZU;", "#KZ;OK;", "#KZUU;OK;"])
def test_calibration_reply_with_an_unknown_command_or_shape_is_ignored(line):
    """Scenarios: Calibration reply with an unknown axis, Command reply with the wrong shape."""
    assert parse_line(line) is None


def test_calibration_report_carries_offsets_and_gains():
    """Scenario: Calibration report."""
    assert parse_line(REPORT) == GyroCalibrationReport((0.01, -0.02, -0.345), (1.0, 1.0, 1.035))


@pytest.mark.parametrize("line", [
    "#K;OFFSET;0.01;-0.02;-0.345;SCALE;1.0;1.0;",
    "#K;SCALE;1.0;1.0;1.035;OFFSET;0.01;-0.02;-0.345;",
    "#K;OFFSET;0.01;-0.02;nan;SCALE;1.0;1.0;1.035;",
    "#K;OFFSET;0.01;-0.02;abc;SCALE;1.0;1.0;1.035;",
    "#K;OFFSET;0.01;-0.02;-0.345;SCALE;1.0;1.0;1.035;9;",
    "#K;",
])
def test_calibration_report_with_the_wrong_shape_is_ignored(line):
    """Scenario: Calibration report with the wrong shape."""
    assert parse_line(line) is None


def test_the_app_commands_are_the_zero_and_the_calibration_ones():
    """Scenario: No other command."""
    assert COMMANDS == ("#Z", "#KZU", "#KZD", "#KXU", "#KXD", "#KYU", "#KYD", "#KP", "#KR")


# ── State: helpers ───────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def state(clock):
    """A state with a configured port whose link is open."""
    s = GyroState(clock)
    s.set_enabled(True)
    s.opened()
    return s


def stream(state, clock, seconds=0.5, start=1000, pitch=1.37):
    """Feed data lines at 100 Hz for `seconds`."""
    for i in range(int(seconds * 100)):
        state.feed(data(start + i * 10, pitch))
        clock.advance(0.01)


# ── Device messages ──────────────────────────────────────────────────────────────────────────────────────

def test_latest_message_is_kept(state):
    """Scenario: Latest message kept."""
    state.feed("#M;ENVIE_Z_COM_O_CARRO_EM_SOLO_PLANO_PARA_ZERAR;")

    assert state.snapshot().message == "ENVIE_Z_COM_O_CARRO_EM_SOLO_PLANO_PARA_ZERAR"


def test_unknown_message_only_updates_the_text(state, clock):
    """Scenario: Unknown message."""
    stream(state, clock)
    before = state.snapshot().status

    state.feed("#M;COMANDO_DESCONHECIDO;")

    assert state.snapshot().message == "COMANDO_DESCONHECIDO"
    assert state.snapshot().status is before


def test_old_state_texts_do_nothing(state, clock):
    """Scenario: Old state texts do nothing. A `#M` text never changes the zero flag."""
    zeroed(state, clock)

    state.feed("#M;ZERO_REMOVIDO;")
    stream(state, clock, start=3000)

    assert state.snapshot().status is GyroStatus.USABLE
    assert state.snapshot().message == "ZERO_REMOVIDO"


# ── Command replies ──────────────────────────────────────────────────────────────────────────────────────

def test_command_reply_is_the_latest_message(state):
    """Scenario: Zero acknowledged."""
    state.feed("#Z;OK;")

    assert state.snapshot().message == "Z: OK"


def test_unknown_status_only_updates_the_message(state, clock):
    """Scenario: Unknown status."""
    stream(state, clock)

    state.feed("#Z;ERRO;")
    stream(state, clock, start=2000)

    assert state.snapshot().message == "Z: ERRO"
    assert state.snapshot().status is GyroStatus.NOT_ZEROED


def test_reply_status_is_not_case_folded(state, clock):
    """Scenario: Not case folded."""
    stream(state, clock)

    state.feed("#Z;ok;")
    stream(state, clock, start=2000)

    assert state.snapshot().message == "Z: ok"
    assert state.snapshot().status is GyroStatus.NOT_ZEROED


def test_message_is_the_last_of_texts_and_replies(state):
    state.feed("#Z;OK;")
    state.feed("#M;COMANDO_DESCONHECIDO;")
    assert state.snapshot().message == "COMANDO_DESCONHECIDO"

    state.feed("#Z;OK;")
    assert state.snapshot().message == "Z: OK"


def test_retired_replies_change_nothing(state, clock):
    """Scenario: Retired replies. They are not even kept as the latest message."""
    zeroed(state, clock)

    for line in ("#R;OK;", "#C;CALIBRANDO;", "#C;OK;"):
        state.feed(line)
    stream(state, clock, start=3000)

    assert state.snapshot().status is GyroStatus.USABLE
    assert state.snapshot().message == "Z: OK"


# ── Zero flag ───────────────────────────────────────────────────────────────────────────────────────────

def test_a_new_link_is_not_zeroed(state, clock):
    """Scenario: Not zeroed at start."""
    stream(state, clock)

    assert state.snapshot().status is GyroStatus.NOT_ZEROED


def test_zero_defined_by_the_device(state, clock):
    """Scenario: Zeroed by the device."""
    stream(state, clock)
    state.feed("#Z;OK;")
    stream(state, clock, start=2000)

    assert state.snapshot().status is GyroStatus.USABLE


def test_command_without_an_answer_does_not_zero(state, clock):
    """Scenario: Command sent but not acknowledged. The state never sees the command, only the answers."""
    stream(state, clock)

    assert state.snapshot().status is GyroStatus.NOT_ZEROED


def zeroed(state, clock):
    stream(state, clock)
    state.feed("#Z;OK;")
    stream(state, clock, start=2000)
    assert state.snapshot().status is GyroStatus.USABLE


def test_header_means_the_device_restarted(state, clock):
    """Scenario: Device restarted."""
    zeroed(state, clock)

    state.feed(HEADER)
    stream(state, clock, start=0)

    assert state.snapshot().status is GyroStatus.NOT_ZEROED


def test_time_going_back_means_the_device_restarted(state, clock):
    """Scenario: Time went back."""
    zeroed(state, clock)
    state.feed(data(90000))
    state.feed(data(150))

    assert state.snapshot().status is GyroStatus.NOT_ZEROED


def test_time_moving_forward_keeps_the_zero(state, clock):
    zeroed(state, clock)
    state.feed(data(90000))
    state.feed(data(90010))

    assert state.snapshot().status is GyroStatus.USABLE


def test_reconnecting_loses_the_zero(state, clock):
    """Scenario: Reconnected."""
    zeroed(state, clock)

    state.closed()
    state.opened()
    stream(state, clock)

    assert state.snapshot().status is GyroStatus.NOT_ZEROED


# ── Calibration acknowledgements, progress and the zero ──────────────────────────────────────────────────

def test_calibration_reply_is_the_latest_message(state):
    """Scenario: Capture acknowledged as message."""
    state.feed("#KZU;OK;")

    assert state.snapshot().message == "KZU: OK"


@pytest.mark.parametrize("line, message", [("#KZU;ERRO;", "KZU: ERRO"), ("#KZU;ok;", "KZU: ok")])
def test_calibration_reply_that_is_not_ok_only_updates_the_message(state, line, message):
    """Scenarios: Unknown status, Not case folded (calibration)."""
    state.feed(line)

    snap = state.snapshot()
    assert snap.message == message and snap.calibration == CalibrationProgress()


def test_capture_replies_are_collected(state):
    """Scenario: Capture acknowledged."""
    state.feed("#KZU;OK;")
    state.feed("#KZD;OK;")

    progress = state.snapshot().calibration
    assert progress.acknowledged == {"#KZU", "#KZD"} and progress.outcome is None


def test_calibration_saved_sets_the_outcome_and_clears_the_captures(state):
    """Scenario: Calibration saved."""
    for command in CALIBRATION_POSITIONS:
        state.feed(f"{command};OK;")
    state.feed(SAVED)
    state.feed(REPORT)

    progress = state.snapshot().calibration
    assert progress.outcome == "saved" and progress.acknowledged == frozenset()
    assert progress.report == GyroCalibrationReport((0.01, -0.02, -0.345), (1.0, 1.0, 1.035))
    assert state.snapshot().message == "CALIBRACAO_SALVA"


def test_invalid_calibration_sets_the_outcome_and_keeps_the_report(state):
    """Scenario: Calibration invalid."""
    state.feed(REPORT)
    for command in CALIBRATION_POSITIONS:
        state.feed(f"{command};OK;")
    state.feed(INVALID)

    progress = state.snapshot().calibration
    assert progress.outcome == "invalid" and progress.acknowledged == frozenset()
    assert progress.report == GyroCalibrationReport((0.01, -0.02, -0.345), (1.0, 1.0, 1.035))


def test_a_new_capture_clears_the_outcome(state):
    """Scenario: New capture clears the outcome."""
    state.feed(SAVED)

    state.feed("#KXU;OK;")

    progress = state.snapshot().calibration
    assert progress.outcome is None and progress.acknowledged == {"#KXU"}


def test_report_requested_changes_only_the_report(state):
    """Scenario: Report requested."""
    state.feed("#KZU;OK;")
    state.feed("#KP;OK;")
    state.feed(REPORT)

    progress = state.snapshot().calibration
    assert progress.report is not None and progress.acknowledged == {"#KZU"} and progress.outcome is None


def test_restore_clears_the_captures_and_the_outcome(state):
    """Scenario: Restored."""
    state.feed("#KZU;OK;")
    state.feed(SAVED)
    state.feed("#KZU;OK;")

    state.feed("#KR;OK;")

    progress = state.snapshot().calibration
    assert progress.acknowledged == frozenset() and progress.outcome is None


def test_reconnecting_forgets_the_calibration_progress(state):
    """Scenario: Port reopened."""
    state.feed("#KZU;OK;")
    state.feed(SAVED)
    state.feed(REPORT)

    state.closed()
    state.opened()

    assert state.snapshot().calibration == CalibrationProgress()


def test_calibration_saved_clears_the_zero(state, clock):
    """Scenario: Calibration saved (Zero flag)."""
    state.feed("#Z;OK;")
    state.feed(data())

    state.feed(SAVED)
    state.feed(data(13000))

    assert state.status() is GyroStatus.NOT_ZEROED


def test_calibration_restored_clears_the_zero(state):
    """Scenario: Calibration restored."""
    state.feed("#Z;OK;")
    state.feed(data())

    state.feed("#KR;OK;")
    state.feed(data(13000))

    assert state.status() is GyroStatus.NOT_ZEROED


@pytest.mark.parametrize("line", [INVALID, "#KZU;OK;", "#KP;OK;", REPORT])
def test_calibration_lines_that_change_nothing_in_the_device_keep_the_zero(state, line):
    """Scenarios: Calibration invalid, Calibration capture (Zero flag)."""
    state.feed("#Z;OK;")
    state.feed(data())

    state.feed(line)
    state.feed(data(13000))

    assert state.status() is GyroStatus.USABLE


def test_calibration_text_is_also_the_latest_message(state):
    """Scenario: Calibration text is also a message."""
    state.feed(INVALID)

    assert state.snapshot().message == "CALIBRACAO_INVALIDA_REPITA_AS_POSICOES"


# ── Data stream presence ──────────────────────────────────────────────────────────────────────────────────────

def test_stream_that_stops_is_no_signal(state, clock):
    """Scenario: Stream stops."""
    zeroed(state, clock)

    clock.advance(1.5)

    assert state.snapshot().status is GyroStatus.NO_SIGNAL
    assert state.snapshot().pitch is None


def test_stream_that_resumes_is_usable_again(state, clock):
    """Scenario: Stream resumes."""
    zeroed(state, clock)
    clock.advance(1.5)

    state.feed(data(5000))

    assert state.snapshot().status is GyroStatus.USABLE


def test_one_second_of_silence_is_still_signal(state, clock):
    zeroed(state, clock)
    clock.now = clock.now - 0.01 + 1.0  # the last line is exactly 1.0 s old

    assert state.snapshot().status is GyroStatus.USABLE


def test_port_that_never_sends_is_no_signal_after_a_second(state, clock):
    assert state.snapshot().status is GyroStatus.NOT_ZEROED  # still inside the first second
    clock.advance(1.5)

    assert state.snapshot().status is GyroStatus.NO_SIGNAL


def test_a_short_pause_is_still_signal(state, clock):
    """Scenario: Short pause. The device pauses its stream for less than a second (zero, calibration capture)."""
    zeroed(state, clock)

    clock.advance(0.8)

    assert state.snapshot().status is GyroStatus.USABLE


# ── Usable pitch ─────────────────────────────────────────────────────────────────────────────────────────

def test_usable_pitch_is_the_latest_pitch(state, clock):
    """Scenario: Usable."""
    zeroed(state, clock)
    state.feed(data(9000, pitch=1.37))

    snap = state.snapshot()

    assert (snap.status, snap.pitch) == (GyroStatus.USABLE, 1.37)


def test_pitch_is_not_given_when_not_zeroed(state, clock):
    """Scenario: Not zeroed."""
    stream(state, clock)

    snap = state.snapshot()

    assert snap.status is GyroStatus.NOT_ZEROED and snap.pitch is None
    assert snap.reading is not None and snap.reading.pitch == 1.37  # the reading itself is still available


def test_no_signal_beats_not_zeroed(state, clock):
    """Scenario: Priority."""
    stream(state, clock)

    clock.advance(2)

    assert state.snapshot().status is GyroStatus.NO_SIGNAL


def test_roll_does_not_take_part(state, clock):
    """Scenario: Roll ignored."""
    zeroed(state, clock)
    state.feed(data(9000, pitch=0.5, roll=12))

    assert state.snapshot().status is GyroStatus.USABLE


def test_status_without_a_port_is_disabled(clock):
    """Scenario: No port configured."""
    s = GyroState(clock)

    assert s.snapshot().status is GyroStatus.DISABLED


def test_status_with_a_closed_port_is_disconnected(clock):
    s = GyroState(clock)
    s.set_enabled(True)

    assert s.snapshot().status is GyroStatus.DISCONNECTED


def test_disabling_forgets_the_link(state, clock):
    zeroed(state, clock)

    state.set_enabled(False)
    state.set_enabled(True)

    assert state.snapshot().status is GyroStatus.DISCONNECTED
    assert state.snapshot().reading is None


def test_zeroed_but_without_any_data_is_not_usable(state):
    state.feed("#Z;OK;")

    assert state.snapshot().status is GyroStatus.NO_SIGNAL


def test_ignored_lines_change_nothing(state, clock):
    zeroed(state, clock)
    before = state.snapshot()

    for line in ("garbage", "#D;1;2;", "#D;a;b;c;d;e;f;g;h;i;j;", ""):
        state.feed(line)

    assert state.snapshot() == before


# ── Connection (serial, retry, commands) ─────────────────────────────────────────────────────────────────

import threading
import time
from collections import deque
from types import SimpleNamespace

from app.gyro import GyroConnection, get_gyro, register_gyro
from app.gyro.ports import list_serial_ports


class FakePort:
    """Scriptable pyserial port: `readline()` gives the queued lines, then b"" (a read timeout)."""

    def __init__(self, lines=()):
        self.lines = deque(lines)
        self.written = []
        self.closed = False
        self.read_error = None

    def readline(self):
        if self.read_error:
            raise self.read_error
        return (self.lines.popleft() + "\n").encode() if self.lines else b""

    def write(self, data):
        self.written.append(data)

    def close(self):
        self.closed = True


class Ports:
    """Serial factory: only the ports in `available` open."""

    def __init__(self, *available):
        self.available = set(available)
        self.attempts = []
        self.opened = []

    def __call__(self, port):
        self.attempts.append(port)
        if port not in self.available:
            raise OSError(f"could not open {port}")
        fake = FakePort()
        self.opened.append((port, fake))
        return fake

    @property
    def last(self):
        return self.opened[-1][1]


@pytest.fixture
def ports():
    return Ports("COM7", "COM9")


def make(port, ports, clock):
    return GyroConnection(port, serial_factory=ports, clock=clock, idle_wait=0)


def test_no_port_configured_opens_nothing(ports, clock):
    """Scenario: No port configured."""
    gyro = make("", ports, clock)

    gyro.step()

    assert ports.attempts == []
    assert gyro.snapshot().status is GyroStatus.DISABLED


def test_configured_port_is_opened_at_once_at_115200_8n1(clock, monkeypatch):
    """Scenario: Port configured."""
    import app.gyro.connection as connection
    captured = {}
    monkeypatch.setattr(connection.serial, "Serial", lambda *args, **kwargs: captured.update(args=args, kwargs=kwargs) or FakePort())
    gyro = GyroConnection("COM7", clock=clock, idle_wait=0)

    gyro.step()

    assert captured["args"] == ("COM7", 115200)
    assert captured["kwargs"]["bytesize"] == 8 and captured["kwargs"]["parity"] == "N" and captured["kwargs"]["stopbits"] == 1
    assert gyro.is_open()


def test_absent_port_is_retried_every_two_seconds(ports, clock):
    """Scenario: Port absent at startup."""
    gyro = make("COM3", ports, clock)

    gyro.step()
    clock.advance(1.9)
    gyro.step()
    assert len(ports.attempts) == 1
    clock.advance(0.2)
    gyro.step()
    assert len(ports.attempts) == 2
    assert gyro.snapshot().status is GyroStatus.DISCONNECTED


def test_device_that_appears_later_is_opened_without_any_action(ports, clock):
    """Scenario: Device appears later."""
    gyro = make("COM3", ports, clock)
    gyro.step()

    ports.available.add("COM3")
    clock.advance(10)
    gyro.step()

    assert gyro.is_open()


def test_port_lost_while_reading_is_closed_and_retried(ports, clock):
    """Scenario: Port lost."""
    gyro = make("COM7", ports, clock)
    gyro.step()
    port = ports.last

    port.read_error = OSError("device disconnected")
    gyro.step()

    assert port.closed and gyro.snapshot().status is GyroStatus.DISCONNECTED
    clock.advance(2.1)
    gyro.step()
    assert len(ports.opened) == 2 and gyro.is_open()


def test_changing_the_port_closes_the_old_one_and_opens_the_new_one(ports, clock):
    """Scenario: Port changed."""
    gyro = make("COM7", ports, clock)
    gyro.step()
    old = ports.last

    gyro.set_port("COM9")
    gyro.step()

    assert old.closed
    assert [p for p, _ in ports.opened] == ["COM7", "COM9"]


def test_setting_no_port_closes_it_and_never_retries(ports, clock):
    """Scenario: Port set to none."""
    gyro = make("COM7", ports, clock)
    gyro.step()
    port = ports.last

    gyro.set_port("")
    gyro.step()
    clock.advance(10)
    gyro.step()

    assert port.closed
    assert gyro.snapshot().status is GyroStatus.DISABLED
    assert len(ports.attempts) == 1


def test_port_closed_by_the_user_stays_closed_until_connected_again(ports, clock):
    """Scenario: Closed by the user."""
    gyro = make("COM7", ports, clock)
    gyro.step()
    port = ports.last

    gyro.disconnect()
    gyro.step()
    clock.advance(10)
    gyro.step()
    assert port.closed and not gyro.is_open() and len(ports.attempts) == 1

    gyro.connect()
    gyro.step()
    assert gyro.is_open() and len(ports.attempts) == 2


def test_opening_failure_does_not_raise_and_is_not_an_ecu_error(ports, clock):
    """Scenario: ECU unaffected."""
    gyro = make("COM3", ports, clock)

    gyro.step()

    assert gyro.snapshot().status is GyroStatus.DISCONNECTED


def test_zero_command_is_written_with_a_line_break(ports, clock):
    """Scenario: Zero."""
    gyro = make("COM7", ports, clock)
    gyro.step()

    assert gyro.zero() is True
    gyro.step()

    assert ports.last.written == [b"#Z\n"]


def test_capture_command_is_written_with_a_line_break(ports, clock):
    """Scenario: Capture."""
    gyro = make("COM7", ports, clock)
    gyro.step()

    assert gyro.capture("#KZU") is True
    gyro.step()

    assert ports.last.written == [b"#KZU\n"]


def test_report_and_restore_commands_are_written(ports, clock):
    """Scenarios: Report, Restore."""
    gyro = make("COM7", ports, clock)
    gyro.step()

    assert gyro.request_calibration() is True
    assert gyro.restore_calibration() is True
    gyro.step()

    assert ports.last.written == [b"#KP\n", b"#KR\n"]


def test_capture_refuses_a_command_that_is_not_a_calibration_position(ports, clock):
    """Scenario: No other command."""
    gyro = make("COM7", ports, clock)
    gyro.step()

    for command in ("#Z", "#C", "#R", "#KP", "#KQU"):
        with pytest.raises(ValueError):
            gyro.capture(command)
    gyro.step()

    assert ports.last.written == []
    assert not hasattr(gyro, "recalibrate") and not hasattr(gyro, "remove_zero")


def test_calibration_commands_with_the_port_closed_are_dropped(ports, clock):
    """Scenario: Port closed (calibration commands)."""
    gyro = make("COM3", ports, clock)
    gyro.step()

    assert gyro.capture("#KZU") is False
    assert gyro.request_calibration() is False
    assert gyro.restore_calibration() is False
    ports.available.add("COM3")
    clock.advance(3)
    gyro.step()

    assert ports.last.written == []


def test_sending_a_calibration_command_changes_no_state(ports, clock):
    """Scenario: Sending changes nothing (calibration)."""
    gyro = make("COM7", ports, clock)
    gyro.step()
    ports.last.lines.extend(["#Z;OK;", data(100)])
    gyro.step()
    gyro.step()

    gyro.capture("#KZU")
    gyro.step()

    snap = gyro.snapshot()
    assert ports.last.written == [b"#KZU\n"]
    assert snap.status is GyroStatus.USABLE and snap.calibration == CalibrationProgress()


def test_sending_a_command_changes_no_state(ports, clock):
    """Scenario: Sending changes nothing."""
    gyro = make("COM7", ports, clock)
    gyro.step()
    ports.last.lines.append(data(100))
    gyro.step()

    gyro.zero()
    gyro.step()

    assert ports.last.written == [b"#Z\n"]
    assert gyro.snapshot().status is GyroStatus.NOT_ZEROED


def test_command_with_the_port_closed_is_dropped(ports, clock):
    """Scenario: Port closed."""
    gyro = make("COM3", ports, clock)
    gyro.step()

    assert gyro.zero() is False
    ports.available.add("COM3")
    clock.advance(3)
    gyro.step()

    assert ports.last.written == []


def test_command_still_queued_when_the_port_is_lost_is_never_written_later(ports, clock):
    gyro = make("COM7", ports, clock)
    gyro.step()
    gyro.zero()
    ports.last.read_error = OSError("gone")
    gyro.step()

    clock.advance(3)
    gyro.step()

    assert ports.last.written == []


def test_lines_read_from_the_port_reach_the_state(ports, clock):
    gyro = make("COM7", ports, clock)
    gyro.step()
    ports.last.lines.extend(["#Z;OK;", data(100)])

    gyro.step()
    gyro.step()

    snap = gyro.snapshot()
    assert snap.status is GyroStatus.USABLE and snap.pitch == 1.37 and snap.message == "Z: OK"


def test_a_state_change_is_announced_once(ports, clock):
    """Scenario: State change announced."""
    gyro = make("COM7", ports, clock)
    announced = []
    gyro.state_changed.connect(lambda: announced.append(gyro.snapshot().status))
    gyro.step()
    ports.last.lines.append(data(100))
    gyro.step()
    announced.clear()

    ports.last.lines.append("#Z;OK;")
    gyro.step()
    ports.last.lines.append(data(110))
    gyro.step()
    gyro.step()

    assert announced == [GyroStatus.USABLE]


def test_a_calibration_change_is_announced_once(ports, clock):
    """Scenario: Change announced."""
    gyro = make("COM7", ports, clock)
    announced = []
    gyro.state_changed.connect(lambda: announced.append(gyro.snapshot().calibration.report))
    gyro.step()
    ports.last.lines.append(data(0))
    gyro.step()
    announced.clear()

    ports.last.lines.append(REPORT)
    gyro.step()
    for i in range(5):
        ports.last.lines.append(data(10 + i))
        gyro.step()

    assert announced == [GyroCalibrationReport((0.01, -0.02, -0.345), (1.0, 1.0, 1.035))]


def test_data_lines_are_not_announced(ports, clock):
    """Scenario: Data lines are not announced."""
    gyro = make("COM7", ports, clock)
    announced = []
    gyro.state_changed.connect(lambda: announced.append(1))
    gyro.step()
    ports.last.lines.append(data(0))
    gyro.step()
    announced.clear()

    for i in range(100):
        ports.last.lines.append(data(10 + i))
        gyro.step()
        clock.advance(0.01)

    assert announced == []


def test_stop_joins_the_thread_and_closes_the_port():
    ports = Ports("COM7")
    gyro = GyroConnection("COM7", serial_factory=ports, idle_wait=0.01)

    gyro.start()
    deadline = time.monotonic() + 2
    while not gyro.is_open() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert gyro.is_open()

    gyro.stop(timeout=1.0)

    assert ports.last.closed
    assert gyro._thread is not None and not gyro._thread.is_alive()
    assert threading.active_count() >= 1


def test_stop_without_ever_starting_is_harmless():
    GyroConnection("").stop()


# ── Registry and port listing ────────────────────────────────────────────────────────────────────────────

def test_the_default_gyro_is_disabled_and_never_none():
    register_gyro(None)

    default = get_gyro()

    assert default is not None and default.snapshot().status is GyroStatus.DISABLED
    assert get_gyro() is default


def test_a_registered_gyro_is_the_one_returned():
    mine = GyroConnection("")
    register_gyro(mine)

    assert get_gyro() is mine
    register_gyro(None)


def test_ports_are_listed_by_name_in_ascending_order():
    """Scenario: Two ports."""
    provider = lambda: [SimpleNamespace(device="COM7"), SimpleNamespace(device="COM3")]

    assert list_serial_ports(provider) == ["COM3", "COM7"]


def test_port_numbers_are_ordered_as_numbers():
    provider = lambda: [SimpleNamespace(device="COM10"), SimpleNamespace(device="COM3")]

    assert list_serial_ports(provider) == ["COM3", "COM10"]
