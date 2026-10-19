"""Spec: openspec/specs/signal-model (Frame parsing, Calculated signals)."""
import pytest

from app.masterinjection.signal import Signal
from app.masterinjection.signal_processor import SignalProcessor
from tests.helpers import SAMPLE_FRAME, frame_with


@pytest.fixture
def processor():
    p = SignalProcessor()
    p.published = []
    p.emitter.connect(p.published.append)
    return p


def test_valid_frame_publishes_one_set_with_every_signal(processor):
    """Scenario: Valid frame."""
    processor.process_line(SAMPLE_FRAME)

    assert len(processor.published) == 1
    assert set(processor.published[0]) == set(Signal)


def test_injection_pulse_and_knock_are_read_from_their_frame_positions(processor):
    """Requirement: Direct signal catalog (INJ_PULSE at position 7, KNOCK at position 11)."""
    processor.process_line(frame_with({7: 107, 11: 42}))
    data = processor.published[0]

    assert data[Signal.INJ_PULSE].value == pytest.approx(1.07)
    assert data[Signal.INJ_PULSE].value_str == "1.07"
    assert data[Signal.KNOCK].value == 42
    assert data[Signal.KNOCK].raw == "42"


def test_parsed_signal_carries_raw_value_and_display(processor):
    """Requirement: Frame parsing (raw text, converted value and display string)."""
    processor.process_line(SAMPLE_FRAME)
    data = processor.published[0]

    assert data[Signal.CLT].raw == "360"
    assert data[Signal.CLT].value == 87
    assert data[Signal.CLT].value_str == "87"
    assert data[Signal.LAMBDA].value == pytest.approx(1.119)
    assert data[Signal.LAMBDA].value_str == "1.12"
    assert data[Signal.LAMBDA_LOOP].value_str == "Open"


def test_calculated_signals_are_derived_from_parsed_values(processor):
    """Requirement: Calculated signals (computed from the same frame)."""
    processor.process_line(SAMPLE_FRAME)
    data = processor.published[0]

    assert data[Signal.POWER].value > 0
    assert data[Signal.TORQUE].value == pytest.approx(data[Signal.POWER].value * 716.2 / data[Signal.RPM].value)


def test_short_frame_omits_signals_beyond_its_length(processor):
    """Scenario: Short frame."""
    short = ";".join(SAMPLE_FRAME.split(";")[:11])  # positions 0..10
    processor.process_line(short)
    data = processor.published[0]

    assert Signal.RPM in data and Signal.IGN in data
    assert Signal.CLT not in data and Signal.GEAR not in data


def test_calculated_signal_is_minus_one_when_a_dependency_is_missing(processor):
    """Scenario: Failed computation."""
    short = ";".join(SAMPLE_FRAME.split(";")[:11])  # IAT (position 20) missing
    processor.process_line(short)

    assert processor.published[0][Signal.POWER].value == -1
    assert processor.published[0][Signal.POWER].raw == -1


def test_unconvertible_field_is_omitted_and_others_survive(processor):
    """Requirement: Frame parsing (a failed conversion omits only that signal)."""
    processor.process_line(frame_with({1: "abc"}))
    data = processor.published[0]

    assert Signal.RPM not in data
    assert Signal.MAP in data


@pytest.mark.parametrize("line", ["#D02;1;2;3", "#I21;20;30", "3415;20;10", "", "#D01"])
def test_foreign_or_empty_lines_publish_nothing(processor, line):
    """Scenario: Foreign line."""
    processor.process_line(line)

    assert processor.published == []
