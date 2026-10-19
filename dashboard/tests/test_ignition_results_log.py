"""Spec: openspec/specs/ignition-results-log (change ignition-multi-gear)."""
import csv
import logging
import os
from datetime import datetime

import pytest

from app.ui.ignition_tuning import results_log
from app.ui.ignition_tuning.analysis import IgnitionAnalysis
from app.ui.ignition_tuning.results_log import HEADER, IgnitionResultsLog
from tests.helpers import ignition_set

START = datetime(2026, 10, 15, 14, 3, 9)


class Env:
    """An analysis feeding a results log in a temporary directory, with a clock the test moves by hand."""

    def __init__(self, directory):
        self.directory = directory
        self.analysis = IgnitionAnalysis(rpm_min=2900, rpm_max=3100, gears=[4, 5], settle_seconds=0,
                                         min_scenario_seconds=10)
        self.t = 0.0
        self.offset = 0
        self.wall = START
        self.log = IgnitionResultsLog(self.analysis, directory=str(directory), wall_clock=lambda: self.wall,
                                      clock=lambda: self.t)
        self._sets = {}

    def sample(self, count=1, step=0.5, **fields):
        key = tuple(sorted(fields.items()))
        signals = self._sets.setdefault(key, ignition_set(**fields))
        for _ in range(count):
            self.analysis.process(signals, self.t, self.offset, True)
            self.log.tick()
            self.t += step

    def files(self):
        return sorted(p for p in os.listdir(self.directory) if p.startswith("ignition_results_"))

    def rows(self, name=None):
        path = os.path.join(self.directory, name or self.files()[0])
        with open(path, newline="") as f:
            return list(csv.reader(f, delimiter=";"))


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


def eligible_pair(env, gear=5, pulses=(110, 108), **fields):
    """Two eligible scenarios (offsets 0 and 1) of `gear`; the offset is left at 1."""
    for offset, pulse in enumerate(pulses):
        env.offset = offset
        env.sample(40, gear=gear, pulse=pulse, **fields)


# --------------------------------------------------------------------- one file per run

def test_the_file_is_named_after_the_first_sample(env):
    """Scenario: First sample."""
    env.sample()

    assert env.files() == ["ignition_results_20261015_140309.csv"]


def test_no_file_exists_before_a_sample(env):
    """Scenario: Nothing before a sample."""
    env.sample(rpm=3400, count=4)  # discarded sets
    env.log.flush()
    env.log.end_run()

    assert env.files() == []


def test_a_reset_closes_the_file_and_the_next_sample_opens_another(env):
    """Scenario: Reset starts a new file."""
    env.sample(4)
    env.log.end_run()
    env.analysis.reset()
    env.wall = datetime(2026, 10, 15, 14, 20, 0)

    env.sample(4)
    env.log.flush()

    assert env.files() == ["ignition_results_20261015_140309.csv", "ignition_results_20261015_142000.csv"]
    first, second = env.rows(env.files()[0]), env.rows(env.files()[1])
    assert len(first) == 2 and first[1][5] == "4"  # four samples of the first run, header excluded
    assert len(second) == 2 and second[1][5] == "4"
    env.t += 10
    env.sample()
    env.log.flush()
    assert env.rows(env.files()[0])[1][5] == "4"  # the first file is never touched again
    assert env.rows(env.files()[1])[1][5] == "5"


def test_a_reset_without_samples_creates_no_file(env):
    """Scenario: Reset without samples."""
    env.log.end_run()
    env.analysis.reset()
    env.log.tick()

    assert env.files() == []


# --------------------------------------------------------------------------- content

def test_the_header_has_the_specified_columns(env):
    """Scenario: Header."""
    env.sample()

    header = env.rows()[0]
    assert header == HEADER and len(header) == 18
    assert header[:4] == ["Gear", "Offset", "RPM min", "RPM max"] and header[-2:] == ["Best", "Discarded"]


def test_an_active_row_holds_the_statistics_of_the_scenario(env):
    """Scenario: Active row."""
    eligible_pair(env)
    env.log.flush()

    rows = env.rows()
    assert rows[2] == "5;1;2900;3100;19.5;40;1.08;45.0;50.0;1.000;40.0;0;1;0.0;0.0;0.0;1;0".split(";")


def test_lines_end_with_a_line_feed_and_fields_are_separated_by_semicolons(env):
    env.sample()

    with open(os.path.join(env.directory, env.files()[0]), newline="") as f:
        text = f.read()
    assert "\r" not in text and text.splitlines()[0] == ";".join(HEADER)


def test_differences_are_written_for_a_scenario_that_is_not_the_best(env):
    eligible_pair(env, pulses=(110, 108), map=45)
    env.log.flush()

    assert env.rows()[1][13:17] == ["1.9", "0.0", "0.0", "0"]


def test_a_scenario_that_is_not_eligible_has_empty_differences(env):
    """Scenario: Not eligible row."""
    env.sample(10, gear=5)  # 4.5 s of 10 required
    env.log.flush()

    row = env.rows()[1]
    assert row[12:17] == ["0", "", "", "", "0"]


def test_both_gears_are_in_one_file_ordered_by_gear(env):
    """Scenario: Both gears in one file."""
    env.sample(2, gear=5)
    env.sample(2, gear=4)
    env.log.flush()

    assert [row[:2] for row in env.rows()[1:]] == [["4", "0"], ["5", "0"]]


def discard_the_first_scenario(env):
    """Gear 5 with three eligible scenarios; the worst (offset 0) is discarded; the offset ends at +2."""
    eligible_pair(env, pulses=(112, 110, 108))
    assert env.analysis.discard_worst(5, env.offset)
    env.log.flush()


def test_a_discarded_scenario_is_flagged_and_not_compared(env):
    """Scenario: Discarded row."""
    discard_the_first_scenario(env)

    discarded = [row for row in env.rows()[1:] if row[17] == "1"]
    assert [(row[0], row[1]) for row in discarded] == [("5", "0")]
    assert discarded[0][13:17] == ["", "", "", "0"]
    assert discarded[0][6] == "1.12"  # the statistics it had when it was discarded


def test_a_discard_is_recorded_by_the_next_write(env):
    """Scenario: Discard is recorded."""
    eligible_pair(env, pulses=(112, 110, 108))
    env.log.flush()
    assert [row[17] for row in env.rows()[1:]] == ["0", "0", "0"]

    env.analysis.discard_worst(5, env.offset)
    env.log.flush()

    assert [row[17] for row in env.rows()[1:]] == ["1", "0", "0"]


def test_a_discarded_and_an_active_scenario_of_the_same_key_are_both_written(env):
    """Scenario: Same key discarded and active."""
    discard_the_first_scenario(env)
    env.offset = 0
    env.sample(40, gear=5, pulse=115)
    env.log.flush()

    zero = [row for row in env.rows()[1:] if row[:2] == ["5", "0"]]
    assert [row[17] for row in zero] == ["0", "1"]  # active first
    assert [row[6] for row in zero] == ["1.15", "1.12"]


# ----------------------------------------------------------------- when it is written

def test_a_changing_run_is_rewritten_at_most_every_five_seconds(env):
    """Scenario: Periodic rewrite."""
    env.sample()
    path = os.path.join(env.directory, env.files()[0])
    writes = []
    original = results_log.os.replace
    results_log.os.replace = lambda *a: (writes.append(env.t), original(*a))[1]
    try:
        env.sample(24, step=0.5)  # 12 more seconds of samples
    finally:
        results_log.os.replace = original

    assert len(writes) == 2
    assert writes[1] - writes[0] >= 5.0
    assert int(env.rows()[1][5]) >= 20 and os.path.exists(path)


def test_leaving_the_screen_writes_the_pending_change_at_once(env):
    """Scenario: Leaving the screen."""
    env.sample()
    env.sample(2)  # one second later: inside the interval, not written
    assert env.rows()[1][5] == "1"

    env.log.flush()

    assert env.rows()[1][5] == "3"


def test_a_reset_writes_a_final_snapshot_before_the_analysis_is_cleared(env):
    """Scenario: Final snapshot on reset."""
    env.sample()
    env.sample(2)

    env.log.end_run()
    env.analysis.reset()

    assert env.rows()[1][5] == "3"


def test_nothing_is_rewritten_while_nothing_changes(env):
    """Scenario: Nothing changed."""
    env.sample(4)
    env.log.flush()
    path = os.path.join(env.directory, env.files()[0])
    first = os.stat(path).st_mtime_ns
    env.analysis.pause()
    env.t += 30

    env.sample(10)
    env.log.flush()

    assert os.stat(path).st_mtime_ns == first


def test_flushing_twice_writes_once(env):
    env.sample(2)
    env.log.flush()
    calls = []
    original = results_log.os.replace
    results_log.os.replace = lambda *a: (calls.append(a), original(*a))[1]
    try:
        env.log.flush()
    finally:
        results_log.os.replace = original

    assert calls == []


# ------------------------------------------------------------------------- failures

def test_an_unusable_directory_is_logged_and_the_analysis_goes_on(tmp_path, caplog):
    """Scenario: Unusable directory."""
    env = Env(tmp_path / "missing")

    with caplog.at_level(logging.WARNING, logger=results_log.__name__):
        env.sample(40)
        env.log.flush()

    assert env.analysis.scenarios(5)[0].samples == 40
    assert len([r for r in caplog.records if r.name == results_log.__name__]) == 1  # once per streak


def test_a_failed_write_is_retried_at_the_next_opportunity(tmp_path):
    """Scenario: Retry."""
    env = Env(tmp_path / "later")
    env.sample(4)
    (tmp_path / "later").mkdir()

    env.sample(4)  # still inside the interval of the failed attempt
    assert env.files() == []
    env.sample(12)  # past it: the retry already wrote a snapshot

    assert env.files() == ["ignition_results_20261015_140309.csv"]
    env.log.flush()
    assert env.rows()[1][5] == "20"


def test_a_failed_replace_keeps_the_previous_snapshot(env, monkeypatch):
    """Scenario: Failure keeps the previous snapshot."""
    env.sample()
    before = env.rows()
    env.sample(2)

    def refuse(*args):
        raise PermissionError("locked by another program")

    monkeypatch.setattr(results_log.os, "replace", refuse)
    env.log.flush()

    assert env.rows() == before
    assert os.listdir(env.directory) == env.files()  # no temporary file left behind
