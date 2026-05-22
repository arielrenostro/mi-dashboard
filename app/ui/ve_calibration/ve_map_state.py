import bisect


class VeMapState:
    """
    Manages the 16×16 VE fuel map.

    Values are stored as raw ECU integers (VE% = raw / 10).
    Axes are populated from ECU responses (#I20, #I21) and must never be modified by the app.

    modified_cells: cells changed from ECU-confirmed original, pending the next write.
    After a row is sent to ECU, its cells are removed from modified_cells (mark_row_sent).
    Cells that were sent but differ from original are still visible via get_visually_modified().
    """

    # Placeholder axes used before ECU responds. Overwritten by load_breakpoints_*.
    DEFAULT_RPM_AXIS = [500, 750, 1000, 1250, 1500, 1750, 2000, 2500,
                        3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]
    DEFAULT_MAP_AXIS = [10, 20, 30, 40, 50, 60, 70, 80, 90,
                        100, 110, 120, 130, 140, 150, 160]

    def __init__(self):
        self.rpm_axis: list = list(self.DEFAULT_RPM_AXIS)
        self.map_axis: list = list(self.DEFAULT_MAP_AXIS)
        # Raw ECU integers: 1000 = 100.0% VE (placeholder until ECU responds)
        self.ve_map: list = [[1000] * 16 for _ in range(16)]
        self.original_ve_map: list = [[1000] * 16 for _ in range(16)]
        self.modified_cells: set = set()  # (row, col) pending ECU write

    # ── Axis loading (from ECU #I20 / #I21) ─────────────────────────────────

    def load_breakpoints_rpm(self, values: list):
        """Set RPM axis from ECU #I20 response (16 ints). Read-only after this."""
        if len(values) == 16:
            self.rpm_axis = [int(v) for v in values]

    def load_breakpoints_map(self, values: list):
        """Set MAP axis from ECU #I21 response (16 ints). Read-only after this."""
        if len(values) == 16:
            self.map_axis = [int(v) for v in values]

    # ── Row loading (from ECU #F01-#F16 responses) ──────────────────────────

    def load_row(self, row: int, values: list):
        """
        Load a single row from an ECU response (raw integer values).
        Always updates original_ve_map (ECU-confirmed state).
        Only overwrites ve_map for cells NOT pending a write (not in modified_cells),
        so in-flight user edits are preserved.
        """
        if not (0 <= row <= 15) or len(values) < 16:
            return
        for col in range(16):
            raw = int(values[col])
            self.original_ve_map[row][col] = raw
            if (row, col) not in self.modified_cells:
                self.ve_map[row][col] = raw

    # ── Cell access ──────────────────────────────────────────────────────────

    def get_cell(self, row: int, col: int) -> int:
        return self.ve_map[row][col]

    def set_cell(self, row: int, col: int, value):
        """Write a cell (raw int). Clamp to [0, 19999]. Updates modified_cells."""
        value = max(0, min(19999, int(round(value))))
        self.ve_map[row][col] = value
        if value != self.original_ve_map[row][col]:
            self.modified_cells.add((row, col))
        else:
            self.modified_cells.discard((row, col))

    # ── Write lifecycle ───────────────────────────────────────────────────────

    def mark_row_sent(self, row: int):
        """Remove all cells in this row from modified_cells (sent to ECU, awaiting confirm)."""
        for col in range(16):
            self.modified_cells.discard((row, col))

    def get_pending_rows(self) -> list:
        """Sorted list of row indices that have at least one cell pending ECU write."""
        return sorted({row for (row, _) in self.modified_cells})

    def get_row_raw_values(self, row: int) -> list:
        """All 16 raw integer values for a row (for building the ECU write command)."""
        return list(self.ve_map[row])

    def reset(self):
        """Restore all cells to ECU-confirmed original values. Clear all pending changes."""
        for row in range(16):
            for col in range(16):
                self.ve_map[row][col] = self.original_ve_map[row][col]
        self.modified_cells.clear()

    # ── Visual state ──────────────────────────────────────────────────────────

    def get_visually_modified(self) -> set:
        """
        All (row, col) where current value differs from ECU-confirmed original.
        Includes both pending-write and already-sent cells.
        """
        return {
            (row, col)
            for row in range(16)
            for col in range(16)
            if self.ve_map[row][col] != self.original_ve_map[row][col]
        }

    # ── Interpolation ─────────────────────────────────────────────────────────

    def calculate_interpolation_weights(self, rpm: float, map_val: float) -> dict:
        """
        Bilinear interpolation weights for up to 4 cells.
        Returns {(row, col): weight}. Weights sum to 1.0. Cells < 0.001 omitted.
        """
        if not self.rpm_axis or not self.map_axis:
            return {}

        if rpm <= self.rpm_axis[0]:
            col1, col2, t_rpm = 0, 0, 0.0
        elif rpm >= self.rpm_axis[-1]:
            col1, col2, t_rpm = 15, 15, 0.0
        else:
            col2 = bisect.bisect_right(self.rpm_axis, rpm)
            col1 = col2 - 1
            t_rpm = (rpm - self.rpm_axis[col1]) / (self.rpm_axis[col2] - self.rpm_axis[col1])

        if map_val <= self.map_axis[0]:
            row1, row2, t_map = 0, 0, 0.0
        elif map_val >= self.map_axis[-1]:
            row1, row2, t_map = 15, 15, 0.0
        else:
            row2 = bisect.bisect_right(self.map_axis, map_val)
            row1 = row2 - 1
            t_map = (map_val - self.map_axis[row1]) / (self.map_axis[row2] - self.map_axis[row1])

        raw = {
            (row1, col1): (1.0 - t_map) * (1.0 - t_rpm),
            (row1, col2): (1.0 - t_map) * t_rpm,
            (row2, col1): t_map * (1.0 - t_rpm),
            (row2, col2): t_map * t_rpm,
        }

        weights: dict = {}
        for key, w in raw.items():
            if w >= 0.001:
                weights[key] = weights.get(key, 0.0) + w
        return weights

    def adjust_ve(self, rpm: float, map_val: float, delta_pct: float):
        """
        Apply a VE% delta distributed by interpolation weights.
        delta_pct = 6.0 → +6.0% VE = +60 raw ECU units total.
        Each active cell receives round(delta_pct * 10 * weight) raw units.
        """
        weights = self.calculate_interpolation_weights(rpm, map_val)
        delta_raw = delta_pct * 10.0
        for (row, col), weight in weights.items():
            self.set_cell(row, col, self.get_cell(row, col) + delta_raw * weight)


ve_map_state = VeMapState()
