"""Spec: openspec/specs/ignition-analysis (changes ignition-tuning-screen and ignition-multi-gear)."""
import pytest

from app.masterinjection.signal import Signal
from app.masterinjection.signal_processor import SignalProcessor
from app.ui.ignition_tuning.analysis import AnalysisStatus, IgnitionAnalysis
from tests.helpers import SAMPLE_FRAME, frame_with

DEFAULT = dict(rpm=3000, gear=5, loop=2, pulse=108, map=45, pedal=495, knock=40, lam=1000, ign=40)


@pytest.fixture(scope="module")
def processor():
    return SignalProcessor()


def make_set(processor, **fields):
    """A parsed telemetry set built through the real frame parser. Fields are raw frame values."""
    f = {**DEFAULT, **fields}
    frame = frame_with({1: f["rpm"], 2: f["map"], 6: f["lam"], 7: f["pulse"], 10: f["ign"], 11: f["knock"],
                        24: f["loop"], 29: f["pedal"], 33: f["gear"]}, SAMPLE_FRAME)
    received = []
    processor.emitter.connect(received.append)
    try:
        processor.process_line(frame)
    finally:
        processor.emitter.disconnect(received.append)
    data = received[0]
    for name in f.get("drop", ()):
        data.pop(name)
    return data


class Rig:
    """Drives an IgnitionAnalysis with a fake clock and keeps the offset like the screen does."""

    def __init__(self, processor, step=0.5, **kwargs):
        settings = dict(rpm_min=2900, rpm_max=3100, gears=[5], settle_seconds=5, min_scenario_seconds=20)
        settings.update(kwargs)
        self.a = IgnitionAnalysis(**settings)
        self.processor = processor
        self.step = step
        self.t = 0.0
        self.offset = 0
        self.loaded = True
        self.ready = 0

    def feed(self, seconds, drop=(), **fields):
        n = round(seconds / self.step)
        for _ in range(n):
            self.one(drop=drop, **fields)

    def one(self, drop=(), **fields):
        signals = make_set(self.processor, drop=drop, **fields)
        if self.a.process(signals, self.t, self.offset, self.loaded):
            self.ready += 1
        self.t += self.step

    def status(self, **fields):
        return self.a.status(make_set(self.processor, **fields), self.t, self.loaded)

    def settled(self):
        """Arm the lambda-loop settling and wait it out, so that the next set is a sample."""
        self.feed(5.0)
        return self

    def change_offset(self, delta):
        self.offset += delta
        self.a.offset_changed(self.t)

    def write(self):
        self.a.write_finished(self.t)

    def go_to(self, offset, **fields):
        """Change the offset, run the write and wait for settling, like the driver pressing Up/Down."""
        self.change_offset(offset - self.offset)
        self.write()
        self.feed(5.0, **fields)

    def stats(self, gear=5):
        return {s.offset: s for s in self.a.scenarios(gear)}


@pytest.fixture
def rig(processor):
    return Rig(processor).settled()


# -------------------------------------------------------------- valid sample conditions

def test_a_set_inside_the_band_is_a_sample(rig):
    """Scenario: Inside the band."""
    rig.feed(2.0)

    assert rig.stats()[0].samples == 4


def test_a_set_with_rpm_outside_the_band_is_discarded(rig):
    """Scenario: RPM outside the band."""
    rig.feed(2.0, rpm=3200)

    assert rig.stats() == {}


@pytest.mark.parametrize("rpm", [2900, 3100])
def test_band_edges_are_inclusive(rig, rpm):
    """Scenario: Band edges."""
    rig.feed(1.0, rpm=rpm)

    assert rig.stats()[0].samples == 2


@pytest.mark.parametrize("rpm", [2899, 3101])
def test_just_outside_the_band_is_discarded(rig, rpm):
    rig.feed(1.0, rpm=rpm)

    assert rig.stats() == {}


def test_a_set_in_the_wrong_gear_is_discarded(rig):
    """Scenario: Wrong gear."""
    rig.feed(2.0, gear=4)

    assert rig.stats() == {}


def test_the_gear_comes_from_the_settings(processor):
    rig = Rig(processor, gears=[4]).settled()

    rig.feed(1.0, gear=4)

    assert rig.stats(4)[0].samples == 2


def test_a_set_with_the_lambda_loop_open_is_discarded(rig):
    """Scenario: Open lambda loop."""
    rig.feed(2.0, loop=0)

    assert rig.stats() == {}


@pytest.mark.parametrize("loop", [1, 2])
def test_both_closed_loop_values_are_accepted(processor, loop):
    rig = Rig(processor).settled()

    rig.feed(1.0, loop=loop)

    assert rig.stats()[0].samples == 2


def test_a_set_missing_a_required_signal_is_discarded(rig):
    """Scenario: Missing signal."""
    rig.feed(2.0, drop=[Signal.PEDAL])

    assert rig.stats() == {}


def test_nothing_is_counted_while_the_ignition_map_is_not_loaded(rig):
    """Requirement: Valid sample conditions (the ignition map is loaded)."""
    rig.loaded = False

    rig.feed(2.0)

    assert rig.stats() == {}


# ----------------------------------------------------------------------------- settling

def test_sets_are_discarded_while_waiting_for_the_write(rig):
    """Scenario: Waiting for the write."""
    rig.change_offset(+1)

    rig.feed(10.0)

    assert rig.stats() == {}


def test_sets_become_samples_five_seconds_after_the_write(rig):
    """Scenario: Settled after the write."""
    rig.change_offset(+1)
    rig.write()
    start = rig.t

    rig.feed(5.0)
    assert rig.stats() == {}

    rig.feed(1.0)
    assert rig.stats()[1].samples == 2
    assert rig.t - start == 6.0


def test_changing_the_offset_again_restarts_the_wait(rig):
    """Scenario: Offset changed again."""
    rig.change_offset(+1)
    rig.write()
    rig.feed(3.0)
    rig.change_offset(+1)

    rig.feed(5.0)
    assert rig.stats() == {}

    rig.write()
    rig.feed(4.5)
    assert rig.stats() == {}

    rig.feed(1.5)  # the sets 4.5 s, 5.0 s and 5.5 s after the new write: the last two count
    assert rig.stats()[2].samples == 2


def test_a_write_with_nothing_to_send_still_releases_the_analysis(rig):
    """Design D5: an undone edit sends nothing but the analysis must not wait forever."""
    rig.change_offset(+1)
    rig.change_offset(-1)
    rig.write()

    rig.feed(6.0)

    assert rig.stats()[0].samples > 0


def test_resuming_discards_sets_for_five_seconds(rig):
    """Scenario: Resume."""
    rig.a.pause()
    rig.feed(3.0)
    rig.a.resume(rig.t)

    rig.feed(5.0)
    assert rig.stats() == {}

    rig.feed(1.0)
    assert rig.stats()[0].samples == 2


def test_the_loop_closing_again_discards_sets_for_five_seconds(rig):
    """Scenario: Lambda loop closes again."""
    rig.feed(2.0)
    rig.feed(2.0, loop=0)

    rig.feed(5.0)
    assert rig.stats()[0].samples == 4  # nothing added since the loop closed

    rig.feed(1.0)
    assert rig.stats()[0].samples == 6


def test_a_loop_excursion_outside_the_band_still_triggers_the_settle_time(rig):
    """Scenario: Loop opened outside the band."""
    rig.feed(2.0, rpm=3600, loop=0)
    rig.feed(2.0, rpm=3600, loop=2)  # closes again, still outside the band

    rig.feed(2.0)  # back in the band: 2 s after the loop closed, the 5 s have not passed
    assert rig.stats() == {}

    rig.feed(1.0)  # 4 s after the loop closed
    assert rig.stats() == {}

    rig.feed(1.0)  # 5 s after the loop closed
    assert rig.stats()[0].samples > 0


# -------------------------------------------------------------------- scenarios by gear and offset

def test_the_first_sample_at_a_new_offset_creates_its_scenario(rig):
    """Scenario: New offset."""
    rig.feed(2.0)
    rig.go_to(+1)

    rig.feed(1.0)

    assert [s.offset for s in rig.a.scenarios(5)] == [0, 1]


def test_returning_to_an_offset_adds_to_its_scenario(rig):
    """Scenario: Return to an offset."""
    rig.feed(2.0)
    first_visit = rig.stats()[0].samples
    rig.go_to(+1)
    rig.feed(2.0)
    rig.go_to(0)
    rig.feed(2.0)

    stats = rig.stats()
    assert sorted(stats) == [0, 1]
    assert stats[0].samples > first_visit


def test_scenarios_are_ordered_by_offset_not_by_time(rig):
    rig.go_to(+1)
    rig.feed(1.0)
    rig.go_to(-1)
    rig.feed(1.0)
    rig.go_to(0)
    rig.feed(1.0)

    assert [s.offset for s in rig.a.scenarios(5)] == [-1, 0, 1]


def test_reset_discards_every_scenario_and_resumes(rig):
    """Scenario: Reset."""
    rig.feed(2.0)
    rig.a.pause()

    rig.a.reset()

    assert rig.a.scenarios(5) == []
    assert rig.a.paused is False


# ---------------------------------------------------------------------------- analysed time

def test_continuous_samples_add_up_to_the_elapsed_time(processor):
    """Scenario: Continuous samples."""
    rig = Rig(processor, step=0.1).settled()

    rig.feed(10.0)

    assert rig.stats()[0].time_s == pytest.approx(10.0, abs=0.3)  # within a few sample intervals


def test_the_first_sample_of_a_run_adds_no_time(rig):
    rig.feed(0.5)

    assert rig.stats()[0].time_s == 0.0


def test_a_gap_between_samples_is_not_counted(rig):
    """Scenario: Gap."""
    rig.feed(2.0)
    before = rig.stats()[0].time_s
    rig.t += 30.0

    rig.feed(2.0)

    assert rig.stats()[0].time_s == pytest.approx(before + 1.5)  # 4 sets, 3 intervals of 0.5 s


def test_an_interval_across_a_discarded_set_is_not_counted(rig):
    """Scenario: Discarded set in between."""
    rig.feed(1.0)
    before = rig.stats()[0].time_s
    rig.one(rpm=3600)  # discarded

    rig.feed(1.0)

    assert rig.stats()[0].time_s == pytest.approx(before + 0.5)  # only the interval inside the second run


def test_a_pause_adds_no_time(rig):
    rig.feed(2.0)
    before = rig.stats()[0].time_s
    rig.a.pause()
    rig.feed(10.0)
    rig.a.resume(rig.t)

    assert rig.stats()[0].time_s == before


# ------------------------------------------------------------------------- statistics

def test_means_are_taken_over_the_samples(rig):
    """Scenario: Means."""
    for pulse in (100, 110, 120):
        rig.one(pulse=pulse, map=40 + (pulse - 100) // 10, pedal=300, lam=1000, ign=38)

    s = rig.stats()[0]
    assert s.inj_pulse == pytest.approx(1.10)
    assert s.map == pytest.approx(41.0)
    assert s.pedal == pytest.approx(300 / 990 * 100)
    assert s.lambda_ == pytest.approx(1.0)
    assert s.ign == pytest.approx(38.0)
    assert s.samples == 3


def test_knock_counts_the_increase_of_the_counter(rig):
    """Scenario: Knock counted."""
    for knock in (40, 40, 42, 43):
        rig.one(knock=knock)

    assert rig.stats()[0].knock == 3


def test_knock_increases_while_sets_are_discarded_are_not_counted(rig):
    """Scenario: Knock while discarded."""
    rig.one(knock=43)
    rig.one(knock=50, gear=4)  # discarded

    rig.one(knock=50)

    assert rig.stats()[0].knock == 0


def test_a_counter_restart_adds_nothing(rig):
    """Scenario: Counter restart."""
    rig.one(knock=43)
    rig.one(knock=2)
    rig.one(knock=3)

    assert rig.stats()[0].knock == 1  # only the 2 -> 3 step


def test_knock_is_kept_per_scenario(rig):
    rig.one(knock=40)
    rig.one(knock=41)
    rig.go_to(+1, knock=41)
    rig.one(knock=41)
    rig.one(knock=45)

    stats = rig.stats()
    assert (stats[0].knock, stats[1].knock) == (1, 4)


# ---------------------------------------------------------------------------- eligibility

def test_a_short_scenario_has_no_percentages_and_cannot_be_best(rig):
    """Scenario: Short scenario."""
    rig.feed(21.0, pulse=110)
    rig.go_to(+1, pulse=100)
    rig.feed(12.0, pulse=100)  # not enough time

    stats = rig.stats()
    assert stats[0].eligible and not stats[1].eligible
    assert stats[1].diff == {}
    assert not stats[1].is_best


# --------------------------------------------------------------- percentages and best

def two_scenarios(rig, first, second):
    """Two eligible scenarios (offsets 0 and +1) with the given raw frame fields."""
    rig.feed(21.0, **first)
    rig.go_to(+1, **second)
    rig.feed(21.0, **second)
    return rig.stats()


def test_difference_is_relative_to_the_lowest_mean(rig):
    """Scenario: Difference."""
    stats = two_scenarios(rig, dict(map=46), dict(map=47))

    assert stats[0].diff[Signal.MAP] == pytest.approx(0.0)
    assert stats[1].diff[Signal.MAP] == pytest.approx(2.1739, abs=1e-3)


def test_each_sensor_has_its_own_best(rig):
    """Scenario: Each sensor has its own best."""
    stats = two_scenarios(rig, dict(map=46, pedal=500, pulse=110), dict(map=47, pedal=400, pulse=110))

    assert stats[0].diff[Signal.MAP] == pytest.approx(0.0)
    assert stats[1].diff[Signal.PEDAL] == pytest.approx(0.0)
    assert stats[0].diff[Signal.PEDAL] == pytest.approx(25.0)
    assert stats[1].diff[Signal.MAP] > 0


def test_the_lowest_injection_time_is_the_best_scenario(rig):
    """Scenario: Lowest injection time wins."""
    stats = two_scenarios(rig, dict(pulse=110), dict(pulse=108))

    assert (stats[0].is_best, stats[1].is_best) == (False, True)


def test_map_and_pedal_do_not_influence_the_best_scenario(rig):
    """Requirement: Best scenario (MAP and PEDAL SHALL NOT influence the choice)."""
    stats = two_scenarios(rig, dict(pulse=110, map=40, pedal=300), dict(pulse=108, map=60, pedal=700))

    assert stats[1].is_best and not stats[0].is_best


def test_there_is_no_best_with_a_single_eligible_scenario(rig):
    """Scenario: Single eligible scenario."""
    rig.feed(21.0)

    assert [s.is_best for s in rig.a.scenarios(5)] == [False]


def test_a_tie_goes_to_the_lower_offset(rig):
    """Scenario: Tie."""
    stats = two_scenarios(rig, dict(pulse=108), dict(pulse=108))

    assert (stats[0].is_best, stats[1].is_best) == (True, False)


def test_only_one_scenario_is_best(rig):
    rig.feed(21.0, pulse=110)
    rig.go_to(+1, pulse=108)
    rig.feed(21.0, pulse=108)
    rig.go_to(+2, pulse=109)
    rig.feed(21.0, pulse=109)

    assert [s.is_best for s in rig.a.scenarios(5)] == [False, True, False]


def test_a_zero_best_value_gives_no_percentage(rig):
    stats = two_scenarios(rig, dict(pedal=0), dict(pedal=100))

    assert stats[0].diff[Signal.PEDAL] is None
    assert stats[1].diff[Signal.PEDAL] is None


# ------------------------------------------------------------------------ discard worst

def three_scenarios(rig, pulses=(112, 110, 108)):
    """Eligible scenarios at offsets 0, +1, +2 (the rig ends at +2, the current offset)."""
    rig.feed(21.0, pulse=pulses[0])
    for offset, pulse in enumerate(pulses[1:], start=1):
        rig.go_to(offset, pulse=pulse)
        rig.feed(21.0, pulse=pulse)


def test_the_worst_scenario_is_discarded(rig):
    """Scenario: Worst discarded."""
    three_scenarios(rig)

    assert rig.a.discard_worst(5, rig.offset) is True

    assert sorted(rig.stats()) == [1, 2]


def test_discarding_changes_neither_the_other_scenarios_nor_their_best(rig):
    three_scenarios(rig)
    before = {o: (s.samples, s.time_s, s.inj_pulse) for o, s in rig.stats().items() if o != 0}

    rig.a.discard_worst(5, rig.offset)

    assert {o: (s.samples, s.time_s, s.inj_pulse) for o, s in rig.stats().items()} == before
    assert [s.is_best for s in rig.a.scenarios(5)] == [False, True]


def test_nothing_is_discarded_when_the_worst_is_the_current_one(rig):
    """Scenario: Worst is the current one."""
    three_scenarios(rig, pulses=(108, 110, 112))  # +2 is the worst and the current offset

    assert rig.a.discard_worst(5, rig.offset) is False

    assert sorted(rig.stats()) == [0, 1, 2]


def test_no_other_scenario_takes_the_place_of_a_current_worst(rig):
    three_scenarios(rig, pulses=(108, 110, 112))

    rig.a.discard_worst(5, rig.offset)
    rig.a.discard_worst(5, rig.offset)

    assert sorted(rig.stats()) == [0, 1, 2]


def test_nothing_is_discarded_with_fewer_than_two_eligible_scenarios(rig):
    """Scenario: Fewer than two eligible."""
    rig.feed(21.0)

    assert rig.a.discard_worst(5, rig.offset) is False

    assert sorted(rig.stats()) == [0]


def test_nothing_is_discarded_without_scenarios(rig):
    assert rig.a.discard_worst(5, 0) is False


def test_scenarios_that_are_not_eligible_are_never_the_worst(rig):
    """Scenario: Not eligible scenarios are never the worst."""
    rig.feed(21.0, pulse=108)
    rig.go_to(+1, pulse=110)
    rig.feed(21.0, pulse=110)
    rig.go_to(+2, pulse=130)
    rig.feed(5.0, pulse=130)  # worst by far, but not enough time
    rig.offset = +3  # the driver moved on

    assert rig.a.discard_worst(5, rig.offset) is True

    assert sorted(rig.stats()) == [0, 2]  # +1 (the worst eligible) was discarded, +2 is untouched


def test_a_tie_discards_the_lower_offset(rig):
    """Scenario: Tie."""
    rig.feed(21.0, pulse=112)
    rig.go_to(+1, pulse=112)
    rig.feed(21.0, pulse=112)
    rig.go_to(+2, pulse=108)
    rig.feed(21.0, pulse=108)

    rig.a.discard_worst(5, rig.offset)

    assert sorted(rig.stats()) == [1, 2]


def test_returning_to_a_discarded_offset_starts_a_new_scenario(rig):
    """Scenario: Returning to a discarded offset."""
    three_scenarios(rig)
    rig.a.discard_worst(5, rig.offset)
    assert 0 not in rig.stats()

    rig.go_to(0, pulse=112)
    rig.feed(3.0, pulse=112)

    s = rig.stats()[0]
    assert s.samples == 6 and s.time_s == pytest.approx(2.5)
    assert not s.eligible


def test_repeated_discards_stop_at_one_eligible_scenario(rig):
    """Scenario: Repeated."""
    three_scenarios(rig)

    assert [rig.a.discard_worst(5, rig.offset) for _ in range(3)] == [True, True, False]

    assert sorted(rig.stats()) == [2]  # one eligible scenario is left: nothing to compare, nothing to discard


def test_repeated_discards_stop_at_the_current_worst(rig):
    rig.feed(21.0, pulse=112)
    rig.go_to(+1, pulse=109)
    rig.feed(21.0, pulse=109)
    rig.go_to(+2, pulse=111)  # the current offset ends up the worst once +0 is gone
    rig.feed(21.0, pulse=111)

    results = [rig.a.discard_worst(5, rig.offset) for _ in range(3)]

    assert results == [True, False, False]
    assert sorted(rig.stats()) == [1, 2]


# ---------------------------------------------------------------------------------- pause

def test_nothing_is_counted_while_paused(rig):
    """Scenario: Paused."""
    rig.feed(2.0)
    before = rig.stats()[0].samples
    rig.a.pause()

    rig.feed(10.0)

    assert rig.stats()[0].samples == before


def test_the_offset_can_change_while_paused_without_creating_a_scenario(rig):
    """Scenario: Offset change while paused."""
    rig.a.pause()

    rig.go_to(+1)

    assert rig.stats() == {}


def test_pausing_and_resuming_do_not_change_scenarios(rig):
    rig.feed(2.0)
    before = rig.stats()[0]

    rig.a.pause()
    rig.a.resume(rig.t)

    after = rig.stats()[0]
    assert (after.samples, after.time_s, after.knock) == (before.samples, before.time_s, before.knock)


# ------------------------------------------------------------------ ready notification

def test_one_notification_when_the_threshold_is_reached(processor):
    """Scenario: Threshold reached."""
    rig = Rig(processor, step=1.0).settled()  # whole seconds: no rounding doubts

    rig.feed(20.0)  # 20 samples, 19 s
    assert rig.ready == 0

    rig.feed(1.0)
    assert rig.ready == 1
    assert rig.stats()[0].time_s == 20.0


def test_no_further_notification_beyond_the_threshold(processor):
    """Scenario: Beyond the threshold."""
    rig = Rig(processor, step=1.0).settled()

    rig.feed(40.0)

    assert rig.ready == 1


def test_returning_to_an_eligible_scenario_does_not_notify_again(processor):
    rig = Rig(processor, step=1.0).settled()
    rig.feed(21.0)
    rig.go_to(+1)
    rig.go_to(0)

    rig.feed(5.0)

    assert rig.ready == 1


# ------------------------------------------------------------------------------- status

def test_status_analysing(rig):
    """Scenario: Analysing."""
    rig.feed(1.0)

    assert rig.status() == AnalysisStatus.ANALYSING


def test_status_out_of_range(rig):
    """Scenario: Out of range."""
    assert rig.status(rpm=3400) == AnalysisStatus.OUT_OF_RANGE
    assert rig.status(gear=3) == AnalysisStatus.OUT_OF_RANGE
    assert rig.status(loop=0) == AnalysisStatus.OUT_OF_RANGE


def test_status_paused_has_priority(rig):
    """Scenario: Paused has priority."""
    rig.a.pause()

    assert rig.status(rpm=3400) == AnalysisStatus.PAUSED


def test_status_waits_for_the_ecu_when_the_map_is_not_loaded(rig):
    """Scenario: Map not loaded."""
    rig.loaded = False

    assert rig.status() == AnalysisStatus.WAITING_ECU


def test_status_settling_after_a_write_has_priority_over_out_of_range(rig):
    rig.change_offset(+1)

    assert rig.status(rpm=3400) == AnalysisStatus.SETTLING

    rig.write()
    assert rig.status() == AnalysisStatus.SETTLING

    rig.t += 5.0
    assert rig.status() == AnalysisStatus.ANALYSING


def test_status_settling_after_the_loop_closes_again(rig):
    """Scenario: Settling after the loop closes."""
    rig.one(loop=0)
    rig.one(loop=1)

    assert rig.status() == AnalysisStatus.SETTLING

    rig.t += 5.0
    assert rig.status() == AnalysisStatus.ANALYSING


def test_defaults_come_from_the_configuration(processor):
    from app.config import config

    a = IgnitionAnalysis()

    assert (a.rpm_min, a.rpm_max, a.gears) == (
        config.ignition_tuning.rpm_min, config.ignition_tuning.rpm_max, config.ignition_tuning.gears)
    assert (a.settle_seconds, a.min_scenario_seconds) == (5, 20)


# ----------------------------------------------------------------- several gears (ignition-multi-gear)

def two_gear_rig(processor, **kwargs):
    return Rig(processor, gears=[4, 5], **kwargs).settled()


def visit(rig, gear, pulses, **fields):
    """Eligible scenarios of `gear` at offsets 0, +1, ... with one mean injection time (raw) each."""
    for offset, pulse in enumerate(pulses):
        rig.go_to(offset, gear=gear, pulse=pulse, **fields)
        rig.feed(21.0, gear=gear, pulse=pulse, **fields)


def test_a_second_configured_gear_is_analysed(processor):
    """Scenario: Second configured gear."""
    rig = two_gear_rig(processor)

    rig.feed(1.0, gear=4)

    assert rig.stats(4)[0].samples == 2


def test_a_gear_that_is_not_configured_is_discarded(processor):
    """Scenario: Gear not configured."""
    rig = two_gear_rig(processor)

    rig.feed(2.0, gear=3)

    assert rig.a.gears_with_data() == []
    assert rig.stats(3) == {}


def test_the_same_offset_in_two_gears_makes_two_scenarios(processor):
    """Scenario: Same offset in two gears."""
    rig = two_gear_rig(processor)
    rig.feed(2.0, gear=5, pulse=100)
    rig.feed(1.0, gear=4, pulse=120)

    assert rig.stats(5)[0].samples == 4 and rig.stats(5)[0].inj_pulse == pytest.approx(1.00)
    assert rig.stats(4)[0].samples == 2 and rig.stats(4)[0].inj_pulse == pytest.approx(1.20)


def test_changing_gear_does_not_start_settling(processor):
    """Scenario: Gear change without settling."""
    rig = two_gear_rig(processor)
    rig.feed(2.0, gear=5)

    rig.one(gear=4)

    assert rig.stats(4)[0].samples == 1
    assert rig.status(gear=4) == AnalysisStatus.ANALYSING


def test_a_gear_change_ends_the_continuous_run(processor):
    """Scenario: Gear change ends the run."""
    rig = two_gear_rig(processor, step=0.1)

    rig.one(gear=5, knock=40)
    rig.one(gear=4, knock=45)
    rig.one(gear=5, knock=50)

    for gear in (4, 5):
        assert rig.stats(gear)[0].time_s == 0.0
        assert rig.stats(gear)[0].knock == 0


def test_the_gears_holding_data_are_listed(processor):
    """Scenario: Gears holding data."""
    rig = two_gear_rig(processor)
    rig.feed(1.0, gear=5)

    assert rig.a.gears_with_data() == [5]

    rig.feed(1.0, gear=4)

    assert rig.a.gears_with_data() == [4, 5]


def test_reset_clears_the_scenarios_of_every_gear(processor):
    """Scenario: Reset (every gear)."""
    rig = two_gear_rig(processor)
    rig.feed(1.0, gear=5)
    rig.feed(1.0, gear=4)

    rig.a.reset()

    assert rig.a.gears_with_data() == []
    assert rig.stats(4) == {} and rig.stats(5) == {}


def test_percentages_are_relative_inside_each_gear(processor):
    """Scenario: Gears are independent."""
    rig = two_gear_rig(processor)
    rig.feed(21.0, gear=5, map=46)
    rig.go_to(1, gear=5, map=47)
    rig.feed(21.0, gear=5, map=47)
    rig.feed(21.0, gear=4, map=60)
    rig.go_to(0, gear=4, map=61)
    rig.feed(21.0, gear=4, map=61)

    assert rig.stats(5)[1].diff[Signal.MAP] == pytest.approx(2.174, abs=0.01)
    assert rig.stats(4)[0].diff[Signal.MAP] == pytest.approx(1.667, abs=0.01)
    assert rig.stats(4)[1].diff[Signal.MAP] == pytest.approx(0.0)


def test_each_gear_has_its_own_best_scenario(processor):
    """Scenario: One best per gear."""
    rig = two_gear_rig(processor)
    visit(rig, 5, (110, 108))
    visit(rig, 4, (120, 125))

    assert [s.is_best for s in rig.a.scenarios(5)] == [False, True]
    assert [s.is_best for s in rig.a.scenarios(4)] == [True, False]


def test_the_ready_notification_is_raised_in_each_gear(processor):
    """Scenario: Threshold reached in the other gear."""
    rig = two_gear_rig(processor, step=1.0)
    rig.feed(21.0, gear=5)
    assert rig.ready == 1

    rig.feed(21.0, gear=4)

    assert rig.ready == 2


def test_discarding_acts_on_the_given_gear_only(processor):
    """Scenario: Other gear untouched."""
    rig = two_gear_rig(processor)
    visit(rig, 5, (112, 110))
    visit(rig, 4, (130, 128, 126))
    before = [(s.offset, s.samples, s.time_s) for s in rig.a.scenarios(5)]

    assert rig.a.discard_worst(4, rig.offset) is True

    assert [s.offset for s in rig.a.scenarios(4)] == [1, 2]
    assert [(s.offset, s.samples, s.time_s) for s in rig.a.scenarios(5)] == before


def test_a_discarded_scenario_is_retained_with_its_statistics(rig):
    """Scenario: Discarded scenario retained."""
    three_scenarios(rig)

    rig.a.discard_worst(5, rig.offset)

    assert sorted(rig.stats()) == [1, 2]
    [gone] = rig.a.discarded()
    assert (gone.gear, gone.offset, gone.discarded) == (5, 0, True)
    assert gone.inj_pulse == pytest.approx(1.12) and gone.time_s > 20


def test_the_same_gear_and_offset_can_be_retained_twice(rig):
    """Scenario: Same key twice."""
    three_scenarios(rig)
    rig.a.discard_worst(5, rig.offset)
    rig.go_to(0, pulse=115)
    rig.feed(21.0, pulse=115)
    rig.go_to(2)

    assert rig.a.discard_worst(5, rig.offset) is True

    assert [(s.gear, s.offset) for s in rig.a.discarded()] == [(5, 0), (5, 0)]
    assert [round(s.inj_pulse, 2) for s in rig.a.discarded()] == [1.12, 1.15]


def test_a_discarded_scenario_takes_no_part_in_the_comparison(rig):
    """Scenario: Discarded not compared."""
    rig.feed(21.0, pulse=112, map=40)  # worst injection time, lowest MAP
    rig.go_to(1, pulse=110, map=46)
    rig.feed(21.0, pulse=110, map=46)
    rig.go_to(2, pulse=108, map=47)
    rig.feed(21.0, pulse=108, map=47)

    rig.a.discard_worst(5, rig.offset)

    stats = rig.stats()
    assert sorted(stats) == [1, 2]
    assert stats[1].diff[Signal.MAP] == pytest.approx(0.0)
    assert stats[2].diff[Signal.MAP] == pytest.approx(2.174, abs=0.01)
    assert [o for o, s in stats.items() if s.is_best] == [2]


def test_reset_clears_the_discarded_scenarios(rig):
    """Scenario: Cleared by reset."""
    three_scenarios(rig)
    rig.a.discard_worst(5, rig.offset)

    rig.a.reset()

    assert rig.a.discarded() == []


def test_the_revision_changes_with_samples_discards_and_resets(rig):
    revision = rig.a.revision

    rig.feed(1.0, rpm=3400)  # discarded sets
    assert rig.a.revision == revision

    rig.feed(1.0)
    assert rig.a.revision > revision
    revision = rig.a.revision

    rig.a.pause()
    rig.a.resume(rig.t)
    assert rig.a.revision == revision

    rig.a.reset()
    assert rig.a.revision > revision

    three_scenarios(rig)
    revision = rig.a.revision
    rig.a.discard_worst(5, rig.offset)
    assert rig.a.revision > revision
