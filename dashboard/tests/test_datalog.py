"""Spec: openspec/specs/datalog."""
import csv
import time

import pytest

from app.log_writer.log_writer import LogWriter, Worker
from tests.helpers import SAMPLE_FRAME

HEADER = [
    "Timestamp", "Event", "Mess 1", "RPM", "MAP", "Boost", "Load %", "Idle", "Lambda 1", "Inj. Pulse",
    "Inj. Utiliz.", "VE Value", "Ign. Adv.", "Knock", "A/C Input", "Start Input", "Outputs 1", "Outputs 2",
    "Lambda 2", "Mess 2", "Batt Volt.", "CLT", "IAT", "Inj. DT", "Ign. Dwell", "KM/H", "Lambda Loop",
    "Lambda Target", "Lambda Corr", "Strobo Angle", "Turbo Target", "ACC %", "ACP %", "dACC %", "0", "0",
]


def read_rows(path):
    with open(path, newline="") as f:
        return list(csv.reader(f, delimiter=";"))


def wait_for_rows(path, count, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = read_rows(path)
        if len(rows) >= count:
            return rows
        time.sleep(0.01)
    return read_rows(path)


@pytest.fixture
def log_path(tmp_path):
    return str(tmp_path / "log_stream_20260526_140309.csv")


@pytest.fixture
def writer(qapp, log_path):
    lw = LogWriter(log_path)
    yield lw
    lw.thread.quit()
    lw.thread.wait()
    lw.worker.log_file.close()


# ---------------------------------------------------------------------- header

def test_header_has_36_columns_in_the_specified_order(log_path):
    """Requirement: Header columns / Scenario: Column count."""
    Worker(log_path).log_file.close()

    header = read_rows(log_path)[0]

    assert header == HEADER
    assert len(header) == 36


def test_header_is_written_only_when_the_file_is_new(log_path):
    """Requirement: One file per run (header when the file did not exist)."""
    first = Worker(log_path)
    first.log_file.close()
    second = Worker(log_path)
    second.log_file.close()

    assert len(read_rows(log_path)) == 1


def test_file_is_semicolon_delimited_with_unix_line_endings(log_path):
    Worker(log_path).log_file.close()

    raw = open(log_path, "rb").read()

    assert b"Timestamp;Event;Mess 1;" in raw
    assert b"\r" not in raw


def test_row_is_flushed_to_disk_immediately(log_path):
    """Requirement: One row per telemetry frame (flushed as soon as written)."""
    worker = Worker(log_path)
    worker.process_task([1, "", "#D01", "5"])

    assert read_rows(log_path)[-1] == ["1", "", "#D01", "5"]  # file still open, nothing closed
    worker.log_file.close()


# ------------------------------------------------------------------------ rows

def test_frame_is_logged_with_timestamp_event_and_raw_fields(writer, log_path):
    """Scenario: Frame logged."""
    before = int(time.time() * 1000)
    writer.write(SAMPLE_FRAME)
    rows = wait_for_rows(log_path, 2)
    after = int(time.time() * 1000)

    row = rows[1]
    assert before <= int(row[0]) <= after
    assert row[1] == ""
    assert row[2:] == SAMPLE_FRAME.split(";")
    assert len(row) == 2 + 34


@pytest.mark.parametrize("line", ["#I21;20;30", "#D02;1;2", "#D03;1", "", "#D01"])
def test_other_lines_are_not_logged(writer, log_path, line):
    """Scenario: Other lines."""
    writer.write(line)
    writer.write(SAMPLE_FRAME)  # sentinel that proves the queue was processed
    rows = wait_for_rows(log_path, 2)

    assert len(rows) == 2
    assert rows[1][2] == "#D01" and len(rows[1]) == 36


def test_one_row_per_frame_in_arrival_order(writer, log_path):
    for rpm in (1000, 2000, 3000):
        writer.write(SAMPLE_FRAME.replace("3415", str(rpm), 1))
    rows = wait_for_rows(log_path, 4)

    assert [r[3] for r in rows[1:]] == ["1000", "2000", "3000"]


# ---------------------------------------------------------------------- events

def test_requested_mark_applies_to_the_next_row_only(writer, log_path):
    """Scenario: Mark requested."""
    writer.write(SAMPLE_FRAME)
    writer.set_event_pending()
    writer.write(SAMPLE_FRAME)
    writer.write(SAMPLE_FRAME)
    rows = wait_for_rows(log_path, 4)

    assert [r[1] for r in rows[1:]] == ["", "MARK", ""]


def test_several_requests_before_a_frame_produce_one_mark(writer, log_path):
    writer.set_event_pending()
    writer.set_event_pending()
    writer.write(SAMPLE_FRAME)
    writer.write(SAMPLE_FRAME)
    rows = wait_for_rows(log_path, 3)

    assert [r[1] for r in rows[1:]] == ["MARK", ""]


def test_event_column_is_empty_without_a_request(writer, log_path):
    writer.write(SAMPLE_FRAME)
    rows = wait_for_rows(log_path, 2)

    assert rows[1][1] == ""


# --------------------------------------------------------------------- shutdown

@pytest.fixture
def closable_writer(qapp, log_path, request):
    lw = LogWriter(log_path)

    def cleanup():  # safety net for a failing test; a no-op once close() worked
        lw.thread.quit()
        lw.thread.wait()
        if not lw.worker.log_file.closed:
            lw.worker.log_file.close()

    request.addfinalizer(cleanup)
    return lw


def test_close_writes_every_row_that_was_already_received(closable_writer, log_path):
    """Scenario: Rows pending at exit (no waiting: close() itself guarantees the rows are written)."""
    for _ in range(300):
        closable_writer.write(SAMPLE_FRAME)

    closable_writer.close()

    assert len(read_rows(log_path)) == 1 + 300


def test_close_closes_the_file_and_finishes_the_writer_thread(closable_writer):
    """Requirement: Clean shutdown of the log."""
    closable_writer.write(SAMPLE_FRAME)

    closable_writer.close()

    assert closable_writer.worker.log_file.closed
    assert closable_writer.thread.isFinished()


def test_close_keeps_the_event_marks(closable_writer, log_path):
    closable_writer.set_event_pending()
    closable_writer.write(SAMPLE_FRAME)
    closable_writer.write(SAMPLE_FRAME)

    closable_writer.close()

    assert [row[1] for row in read_rows(log_path)[1:]] == ["MARK", ""]


def test_closing_twice_is_harmless(closable_writer, log_path):
    """Scenario: Closed twice."""
    closable_writer.write(SAMPLE_FRAME)
    closable_writer.close()

    closable_writer.close()

    assert len(read_rows(log_path)) == 2


def test_frames_arriving_after_close_are_ignored(closable_writer, log_path):
    closable_writer.close()

    closable_writer.write(SAMPLE_FRAME)

    assert len(read_rows(log_path)) == 1  # only the header


def test_close_without_any_rows_leaves_just_the_header(closable_writer, log_path):
    closable_writer.close()

    assert read_rows(log_path) == [HEADER]


def test_the_datalog_wait_is_bounded_to_three_seconds(closable_writer, monkeypatch):
    """Requirement: Bounded waiting (3 seconds for the datalog)."""
    from unittest.mock import Mock

    fake_thread = Mock()  # the real thread stays referenced by monkeypatch until the fixture can join it
    fake_thread.isRunning.return_value = True
    fake_thread.wait.return_value = False
    monkeypatch.setattr(closable_writer, "thread", fake_thread)

    closable_writer.close()

    fake_thread.wait.assert_any_call(3000)
    fake_thread.terminate.assert_called_once()
