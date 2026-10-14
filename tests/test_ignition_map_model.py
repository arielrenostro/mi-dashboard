"""Spec: openspec/specs/ignition-map-model."""
import pytest

from app.ui.ignition_tuning.ignition_map_state import IgnitionMapState
from tests.helpers import MAP_AXIS

# MAP_AXIS = 10, 20, ... 160: with the default limit of 70 kPa the affected rows are 0..6.
AFFECTED = list(range(7))


def base_row(row):
    return [20 + row + col for col in range(16)]


def make_state(load=True, axis=True, **kwargs):
    state = IgnitionMapState(**{"max_map_kpa": 70, "ceiling": 50, **kwargs})
    state.map_axis = list(MAP_AXIS) if axis else [0] * 16
    if load:
        for row in range(16):
            assert state.load_row(row, base_row(row))
    return state


# ---------------------------------------------------------------- addressing, loading

def test_first_row_received_is_the_lowest_map_row():
    """Scenario: Addressing."""
    state = make_state(load=False)

    state.load_row(0, base_row(0))

    assert state.original[0] == base_row(0)
    assert state.get_cell(0, 3) == base_row(0)[3]


def test_row_received_at_offset_zero_replaces_original_and_working():
    """Scenario: Row received at offset 0."""
    state = make_state()

    assert state.load_row(4, [9] * 16)

    assert state.original[4] == [9] * 16
    assert state.working[4] == [9] * 16


def test_row_received_while_an_offset_is_applied_is_ignored():
    """Scenario: Row received while an offset is applied."""
    state = make_state()
    state.adjust_offset(+2)

    assert not state.load_row(2, [9] * 16)

    assert state.original[2] == base_row(2)


def test_row_received_while_a_write_is_outstanding_is_ignored():
    """Scenario: Row received while a write is outstanding."""
    state = make_state()
    state.adjust_offset(+1)
    for row in state.get_pending_rows():
        state.mark_row_sent(row)
    state.adjust_offset(-1)  # back to 0, but the ECU still holds the +1 values

    assert not state.load_row(2, [9] * 16)

    assert state.original[2] == base_row(2)


def test_row_is_taken_again_once_the_original_was_written_back():
    state = make_state()
    state.adjust_offset(+1)
    for row in state.get_pending_rows():
        state.mark_row_sent(row)
    state.adjust_offset(-1)
    for row in state.get_pending_rows():
        state.mark_row_sent(row)

    assert state.load_row(2, [9] * 16)


@pytest.mark.parametrize("row,values", [(-1, [1] * 16), (16, [1] * 16), (3, [1] * 15)])
def test_invalid_rows_are_ignored(row, values):
    """Requirement: Loading an ignition row (out-of-range index, fewer than 16 values)."""
    state = make_state(load=False)

    assert not state.load_row(row, values)

    assert state.original == [[0] * 16 for _ in range(16)]


def test_map_is_not_loaded_until_all_sixteen_rows_arrive():
    """Scenario: Not loaded yet."""
    state = make_state(load=False)
    for row in range(15):
        state.load_row(row, base_row(row))

    assert not state.is_loaded()

    state.load_row(15, base_row(15))

    assert state.is_loaded()


def test_map_axis_with_the_wrong_size_is_ignored():
    """Requirement: Raw ignition units and addressing (the axis comes from the ECU, 16 values)."""
    state = make_state()

    state.load_breakpoints_map([1, 2, 3])

    assert state.map_axis == MAP_AXIS


# ----------------------------------------------------------------------- the offset

def test_raising_adds_one_degree_to_every_cell_of_the_affected_rows():
    """Scenario: Raise."""
    state = make_state()

    assert state.adjust_offset(+1)

    assert state.offset == 1
    for row in AFFECTED:
        assert state.working[row] == [v + 1 for v in base_row(row)]


def test_lowering_subtracts_one_degree():
    """Scenario: Lower."""
    state = make_state()

    state.adjust_offset(-1)

    for row in AFFECTED:
        assert state.working[row] == [v - 1 for v in base_row(row)]


def test_lowering_stops_at_zero_degrees():
    """Scenario: Lower (minimum of 0)."""
    state = make_state(load=False)
    for row in range(16):
        state.load_row(row, [0, 1, 2] + [30] * 13)

    state.adjust_offset(-1)

    assert state.working[0][:3] == [0, 0, 1]


def test_cells_clamped_at_zero_recover_their_original_value():
    """Scenario: Floor and recovery."""
    state = make_state(load=False)
    for row in range(16):
        state.load_row(row, [2] + [30] * 15)

    for _ in range(5):
        state.adjust_offset(-1)
    assert state.working[0][0] == 0

    for _ in range(4):
        state.adjust_offset(+1)

    assert state.offset == -1
    assert state.working[0][0] == 1  # not 0: the map is derived from the original


def test_offset_is_capped_by_the_ceiling():
    """Scenario: Ceiling."""
    state = make_state(load=False)
    for row in range(16):
        state.load_row(row, [49] + [10] * 15)

    for _ in range(3):
        state.adjust_offset(+1)

    assert state.working[0][0] == 50
    assert state.working[0][1] == 13


def test_ceiling_comes_from_the_constructor():
    state = make_state(ceiling=25)

    state.adjust_offset(+10)

    assert max(max(row) for row in state.working[:7]) == 25


def test_offset_zero_is_the_original_even_above_the_ceiling():
    """Scenario: Offset zero is the original."""
    state = make_state(load=False)
    for row in range(16):
        state.load_row(row, [55] + [10] * 15)

    assert state.working[0][0] == 55

    state.adjust_offset(+1)
    state.adjust_offset(-1)

    assert state.working[0][0] == 55
    assert state.get_pending_rows() == []


def test_offset_cannot_change_before_the_map_is_loaded():
    """Scenario: Map not loaded."""
    state = make_state(load=False)
    for row in range(15):
        state.load_row(row, base_row(row))

    assert not state.adjust_offset(+1)

    assert state.offset == 0
    assert state.working[0] == base_row(0)


# ------------------------------------------------------------- rows the offset covers

def test_limit_row_is_included_and_every_column_changes():
    """Scenario: Limit row included."""
    state = make_state()
    assert MAP_AXIS[6] == 70

    state.adjust_offset(+1)

    assert state.affected_rows() == AFFECTED
    assert all(new == old + 1 for new, old in zip(state.working[6], base_row(6)))


def test_rows_above_the_limit_keep_their_original_values():
    """Scenario: Rows above the limit."""
    state = make_state()

    for delta in (+1, +1, -1, -3):
        state.adjust_offset(delta)
        for row in range(7, 16):
            assert state.working[row] == base_row(row)


def test_limit_follows_the_configured_value():
    state = make_state(max_map_kpa=40)

    assert state.affected_rows() == [0, 1, 2, 3]


def test_offset_cannot_change_while_the_axis_is_not_loaded():
    """Scenario: Axis not loaded."""
    state = make_state(axis=False)

    assert not state.adjust_offset(+1)

    assert state.offset == 0


def test_axis_arriving_after_the_rows_enables_the_offset():
    state = make_state(axis=False)

    state.load_breakpoints_map(MAP_AXIS)

    assert state.adjust_offset(+1)
    assert state.affected_rows() == AFFECTED


# ---------------------------------------------------------------------- pending rows

def test_raising_makes_exactly_the_affected_rows_pending():
    """Scenario: Raise by one."""
    state = make_state()

    state.adjust_offset(+1)

    assert state.get_pending_rows() == AFFECTED


def test_nothing_is_pending_before_any_change():
    assert make_state().get_pending_rows() == []


def test_sent_rows_are_no_longer_pending():
    """Scenario: Sent rows."""
    state = make_state()
    state.adjust_offset(+1)

    for row in state.get_pending_rows():
        state.mark_row_sent(row)

    assert state.get_pending_rows() == []


def test_a_change_after_sending_makes_the_rows_pending_again():
    state = make_state()
    state.adjust_offset(+1)
    for row in state.get_pending_rows():
        state.mark_row_sent(row)

    state.adjust_offset(+1)

    assert state.get_pending_rows() == AFFECTED


def test_raising_and_lowering_before_sending_leaves_nothing_pending():
    """Scenario: Undone before sending."""
    state = make_state()

    state.adjust_offset(+1)
    state.adjust_offset(-1)

    assert state.get_pending_rows() == []


def test_row_raw_values_are_the_working_values():
    state = make_state()
    state.adjust_offset(+2)

    assert state.get_row_raw_values(0) == [v + 2 for v in base_row(0)]


def test_raw_values_are_a_copy():
    state = make_state()

    state.get_row_raw_values(0)[0] = 999

    assert state.working[0][0] == base_row(0)[0]


# ----------------------------------------------------------------------------- reset

def test_reset_restores_the_original_and_queues_all_sixteen_rows():
    """Scenario: Reset after edits."""
    state = make_state()
    for _ in range(3):
        state.adjust_offset(+1)
    for row in state.get_pending_rows():
        state.mark_row_sent(row)

    state.reset()

    assert state.offset == 0
    assert state.working == [base_row(row) for row in range(16)]
    assert state.get_pending_rows() == list(range(16))


def test_reset_rows_are_sent_once():
    state = make_state()
    state.adjust_offset(+1)
    state.reset()

    for row in state.get_pending_rows():
        state.mark_row_sent(row)

    assert state.get_pending_rows() == []


def test_reset_without_a_loaded_map_only_clears_the_offset():
    """Scenario: Reset without a loaded map."""
    state = make_state(load=False)

    state.reset()

    assert state.offset == 0
    assert state.get_pending_rows() == []
