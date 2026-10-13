"""Spec: openspec/specs/ve-map-model."""
import pytest

from app.ui.ve_calibration.ve_map_state import VeMapState
from tests.helpers import MAP_AXIS, RPM_AXIS


@pytest.fixture
def ve():
    model = VeMapState()
    model.load_breakpoints_rpm(RPM_AXIS)
    model.load_breakpoints_map(MAP_AXIS)
    return model


def load_all_rows(model, base=800):
    for row in range(16):
        model.load_row(row, [base + row * 16 + col for col in range(16)])


# ---------------------------------------------------------------- units & axes

def test_placeholder_values_before_ecu_data():
    """Scenario: Placeholder values."""
    model = VeMapState()

    assert all(cell == 1000 for row in model.ve_map for cell in row)
    assert all(cell == 1000 for row in model.original_ve_map for cell in row)


def test_axis_loaded_from_sixteen_values(ve):
    """Scenario: Axis loaded."""
    assert ve.rpm_axis == RPM_AXIS
    assert ve.map_axis == MAP_AXIS


def test_axis_with_wrong_size_is_ignored(ve):
    """Scenario: Wrong size."""
    ve.load_breakpoints_rpm([1, 2, 3])
    ve.load_breakpoints_map(list(range(15)))

    assert ve.rpm_axis == RPM_AXIS
    assert ve.map_axis == MAP_AXIS


def test_loading_a_row_replaces_working_and_original_values(ve):
    """Requirement: Loading a row from the ECU."""
    ve.set_cell(2, 3, 5000)
    ve.load_row(2, list(range(16)))

    assert ve.ve_map[2] == list(range(16))
    assert ve.original_ve_map[2] == list(range(16))
    assert (2, 3) not in ve.get_visually_modified()


def test_loading_invalid_rows_is_ignored(ve):
    ve.load_row(16, [1] * 16)
    ve.load_row(-1, [1] * 16)
    ve.load_row(0, [1] * 15)

    assert ve.ve_map[0] == [1000] * 16


# --------------------------------------------------------------- interpolation

def test_halfway_between_four_cells_weights_each_quarter(ve):
    """Scenario: Between four cells."""
    weights = ve.calculate_interpolation_weights(
        (RPM_AXIS[4] + RPM_AXIS[5]) / 2, (MAP_AXIS[6] + MAP_AXIS[7]) / 2
    )

    assert weights == pytest.approx({(6, 4): 0.25, (6, 5): 0.25, (7, 4): 0.25, (7, 5): 0.25})


def test_exactly_on_an_rpm_breakpoint_uses_two_cells(ve):
    """Scenario: Exactly on a breakpoint."""
    weights = ve.calculate_interpolation_weights(RPM_AXIS[4], (MAP_AXIS[6] + MAP_AXIS[7]) / 2)

    assert weights == pytest.approx({(6, 4): 0.5, (7, 4): 0.5})


def test_exactly_on_a_node_uses_one_cell(ve):
    weights = ve.calculate_interpolation_weights(RPM_AXIS[4], MAP_AXIS[6])

    assert weights == pytest.approx({(6, 4): 1.0})


def test_above_last_rpm_breakpoint_uses_last_column(ve):
    """Scenario: Above the last breakpoint."""
    weights = ve.calculate_interpolation_weights(9000, MAP_AXIS[6])

    assert set(weights) == {(6, 15)}


@pytest.mark.parametrize(
    "rpm,map_val,cell",
    [(0, 0, (0, 0)), (RPM_AXIS[0], MAP_AXIS[0], (0, 0)), (99999, 999, (15, 15)), (0, 999, (15, 0)), (99999, 0, (0, 15))],
)
def test_edge_clamping(ve, rpm, map_val, cell):
    """Requirement: Interpolation weights (values at or beyond the ends)."""
    assert ve.calculate_interpolation_weights(rpm, map_val) == pytest.approx({cell: 1.0})


def test_weights_sum_to_one(ve):
    weights = ve.calculate_interpolation_weights(1337, 47)

    assert sum(weights.values()) == pytest.approx(1.0, abs=0.002)


def test_weights_below_threshold_are_omitted(ve):
    # 0.0005 of the way between two RPM breakpoints -> the far column has weight < 0.001
    rpm = RPM_AXIS[4] + (RPM_AXIS[5] - RPM_AXIS[4]) * 0.0005
    weights = ve.calculate_interpolation_weights(rpm, MAP_AXIS[6])

    assert set(weights) == {(6, 4)}


def test_empty_axes_give_no_weights():
    """Requirement: Interpolation weights (empty axis -> empty result)."""
    model = VeMapState()
    model.rpm_axis = []

    assert model.calculate_interpolation_weights(1000, 50) == {}


# ------------------------------------------------------------------- adjusting

def test_adjust_on_a_node_changes_that_cell_by_the_delta(ve):
    """Scenario: Single cell."""
    load_all_rows(ve)
    before = ve.get_cell(6, 4)

    ve.adjust_ve(RPM_AXIS[4], MAP_AXIS[6], 5)

    assert ve.get_cell(6, 4) == before + 5


def test_adjust_splits_the_delta_by_weight(ve):
    """Scenario: Split between two cells."""
    load_all_rows(ve)
    a, b = ve.get_cell(6, 4), ve.get_cell(7, 4)

    ve.adjust_ve(RPM_AXIS[4], (MAP_AXIS[6] + MAP_AXIS[7]) / 2, 10)

    assert (ve.get_cell(6, 4), ve.get_cell(7, 4)) == (a + 5, b + 5)


def test_cell_values_are_clamped(ve):
    """Scenario: Upper clamp (and lower bound 0)."""
    ve.set_cell(0, 0, 25000)
    ve.set_cell(0, 1, -50)

    assert ve.get_cell(0, 0) == 19999
    assert ve.get_cell(0, 1) == 0


def test_cell_values_are_rounded_to_integers(ve):
    ve.set_cell(0, 0, 1000.4)

    assert ve.get_cell(0, 0) == 1000
    assert isinstance(ve.get_cell(0, 0), int)


# ------------------------------------------------------------ modification set

def test_edit_marks_pending_and_visually_modified(ve):
    load_all_rows(ve)
    ve.set_cell(3, 7, ve.get_cell(3, 7) + 5)

    assert ve.modified_cells == {(3, 7)}
    assert ve.get_visually_modified() == {(3, 7)}
    assert ve.get_pending_rows() == [3]


def test_edit_then_undo_is_no_longer_modified(ve):
    """Scenario: Edit then undo."""
    load_all_rows(ve)
    original = ve.get_cell(3, 7)
    ve.set_cell(3, 7, original + 5)
    ve.set_cell(3, 7, original)

    assert ve.modified_cells == set()
    assert ve.get_visually_modified() == set()


def test_pending_rows_are_sorted_and_distinct(ve):
    load_all_rows(ve)
    for row, col in [(9, 1), (2, 5), (9, 3)]:
        ve.set_cell(row, col, ve.get_cell(row, col) + 1)

    assert ve.get_pending_rows() == [2, 9]


def test_sent_row_is_not_pending_but_stays_visually_modified(ve):
    """Scenario: Sent row."""
    load_all_rows(ve)
    ve.set_cell(3, 7, ve.get_cell(3, 7) + 5)
    ve.mark_row_sent(3)

    assert ve.get_pending_rows() == []
    assert ve.get_visually_modified() == {(3, 7)}


def test_row_raw_values_are_returned_as_a_copy(ve):
    load_all_rows(ve)
    values = ve.get_row_raw_values(2)
    values[0] = -1

    assert ve.get_cell(2, 0) != -1


# ----------------------------------------------------------------------- reset

def test_reset_restores_originals_and_marks_every_row_pending(ve):
    """Scenario: Reset after edits."""
    load_all_rows(ve)
    ve.set_cell(3, 7, ve.get_cell(3, 7) + 50)
    ve.set_cell(12, 0, ve.get_cell(12, 0) - 50)

    ve.reset()

    assert ve.ve_map == ve.original_ve_map
    assert ve.get_visually_modified() == set()
    assert ve.get_pending_rows() == list(range(16))
