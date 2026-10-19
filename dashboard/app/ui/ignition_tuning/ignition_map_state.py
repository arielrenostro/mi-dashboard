from typing import Optional

from app.config import config
from app.state.state import vehicle_state


class IgnitionMapState:
    """
    The 16x16 ignition map used for on-road tuning.

    Values are raw ECU integers in whole degrees. The map is never edited cell by cell: it is the
    ECU-confirmed `original` plus one global advance `offset`, recomputed from the original every time:

        affected row:    working = max(0, min(ceiling, original + offset))
        unaffected row:  working = original

    Affected rows are the ones whose MAP axis value is at or below `max_map_kpa`. Because the working map
    is always derived from the original, cells clamped at 0 return to their original value when the offset
    comes back up.

    `last_written` is what the ECU is believed to hold; rows whose working values differ from it are pending.
    """

    def __init__(self, max_map_kpa: Optional[int] = None, ceiling: Optional[int] = None):
        self.max_map_kpa: int = config.ignition_tuning.max_map_kpa if max_map_kpa is None else max_map_kpa
        self.ceiling: int = config.ignition_tuning.max_ignition if ceiling is None else ceiling
        self.map_axis: list = list(vehicle_state.get_map_breakpoints())
        self.original: list = [[0] * 16 for _ in range(16)]
        self.working: list = [[0] * 16 for _ in range(16)]
        self.last_written: list = [[0] * 16 for _ in range(16)]
        self.offset: int = 0
        self._loaded_rows: set = set()
        self._forced_rows: set = set()  # rows that must be written even if equal to last_written (reset)

    # ── Loading from the ECU ─────────────────────────────────────────────────

    def load_breakpoints_map(self, values: list):
        """Set the MAP axis from the ECU (16 ints). The axis is never modified by the app."""
        if len(values) == 16:
            self.map_axis = [int(v) for v in values]
            self._recompute()

    def load_row(self, row: int, values: list) -> bool:
        """
        Load an ignition row received from the ECU. Returns whether it was taken.

        Ignored while the offset is not 0, or while the ECU is believed to hold other values than the
        original for this row (a write is pending or was not undone yet): what the ECU then reports is
        something this tool wrote, not the original map.
        """
        if not (0 <= row <= 15) or len(values) < 16:
            return False
        if self.offset != 0 or self._row_is_dirty(row):
            return False
        raw = [int(v) for v in values[:16]]
        self.original[row] = list(raw)
        self.working[row] = list(raw)
        self.last_written[row] = list(raw)
        self._loaded_rows.add(row)
        return True

    # ── State queries ────────────────────────────────────────────────────────

    def is_loaded(self) -> bool:
        """True once all 16 rows were received from the ECU."""
        return len(self._loaded_rows) == 16

    def axis_is_loaded(self) -> bool:
        return len(self.map_axis) == 16 and max(self.map_axis) > 0

    def affected_rows(self) -> list:
        """Row indices (0 = lowest MAP) the offset applies to."""
        if not self.axis_is_loaded():
            return []
        return [row for row in range(16) if self.map_axis[row] <= self.max_map_kpa]

    def get_cell(self, row: int, col: int) -> int:
        return self.working[row][col]

    # ── Offset ───────────────────────────────────────────────────────────────

    def adjust_offset(self, delta: int) -> bool:
        """Change the offset by `delta` degrees. Returns False (and changes nothing) when it cannot be done."""
        if not self.is_loaded() or not self.axis_is_loaded():
            return False
        self.offset += delta
        self._recompute()
        return True

    def reset(self):
        """Offset back to 0 and the original map restored; every row is queued for writing."""
        self.offset = 0
        self._recompute()
        self._forced_rows = set(range(16)) if self.is_loaded() else set()

    # ── Write lifecycle ──────────────────────────────────────────────────────

    def get_pending_rows(self) -> list:
        """Sorted row indices whose working values still have to be written to the ECU."""
        return [row for row in range(16)
                if row in self._forced_rows or self.working[row] != self.last_written[row]]

    def get_row_raw_values(self, row: int) -> list:
        """All 16 raw values of a working row (for building the ECU write command)."""
        return list(self.working[row])

    def mark_row_sent(self, row: int):
        """The row was handed to the ECU: it is no longer pending until the offset changes it again."""
        self.last_written[row] = list(self.working[row])
        self._forced_rows.discard(row)

    # ── Internals ────────────────────────────────────────────────────────────

    def _row_is_dirty(self, row: int) -> bool:
        return (row in self._forced_rows
                or self.last_written[row] != self.original[row]
                or self.working[row] != self.original[row])

    def _recompute(self):
        affected = set(self.affected_rows()) if self.offset != 0 else set()
        for row in range(16):
            if row in affected:
                self.working[row] = [max(0, min(self.ceiling, value + self.offset)) for value in self.original[row]]
            else:
                self.working[row] = list(self.original[row])


ignition_map_state = IgnitionMapState()
