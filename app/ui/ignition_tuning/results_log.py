import csv
import logging
import os
import time
from collections.abc import Callable
from datetime import datetime
from typing import Optional

from app.config import config
from app.masterinjection.signal import Signal
from app.ui.ignition_tuning.analysis import IgnitionAnalysis, ScenarioStats

logger = logging.getLogger(__name__)

# Snapshots of a run that keeps changing are written at most this often.
WRITE_INTERVAL_SECONDS = 5.0

HEADER = ["Gear", "Offset", "RPM min", "RPM max", "Time s", "Samples", "Inj. Pulse", "MAP", "Pedal", "Lambda",
          "Ign. Adv.", "Knock", "Eligible", "Inj. Pulse diff %", "MAP diff %", "Pedal diff %", "Best", "Discarded"]

_DIFF_SIGNALS = (Signal.INJ_PULSE, Signal.MAP, Signal.PEDAL)


class IgnitionResultsLog:
    """
    Keeps a CSV snapshot of one analysis run (every gear and offset, discarded scenarios included) in the
    datalog directory. A run starts with its first accepted sample and ends with `end_run()`. Every write
    replaces the whole file; a failed write is logged and never raised.
    """

    def __init__(self, analysis: IgnitionAnalysis, directory: Optional[str] = None,
                 wall_clock: Callable[[], datetime] = datetime.now, clock: Callable[[], float] = time.monotonic):
        self._analysis = analysis
        self._directory = directory
        self._wall_clock = wall_clock
        self._clock = clock
        self._path: Optional[str] = None
        self._written_revision: Optional[int] = None
        self._last_attempt: Optional[float] = None
        self._failing = False

    @property
    def path(self) -> Optional[str]:
        """The file of the current run, None while no run has started."""
        return self._path

    def tick(self):
        """Call after every analysed telemetry set: starts the run and rewrites a changed snapshot every 5 s."""
        if self._analysis.revision == self._written_revision:
            return
        if self._path is None:
            if not (self._analysis.gears_with_data() or self._analysis.discarded()):
                return
            name = f"ignition_results_{self._wall_clock().strftime('%Y%m%d_%H%M%S')}.csv"
            self._path = os.path.join(self._directory if self._directory is not None else config.datalog.path, name)
        elif self._last_attempt is not None and self._clock() - self._last_attempt < WRITE_INTERVAL_SECONDS:
            return
        self._write()

    def flush(self):
        """Write now, whatever the interval, when something changed since the last successful write."""
        if self._path is not None and self._analysis.revision != self._written_revision:
            self._write()

    def end_run(self):
        """Write what is pending and close the run: the next accepted sample starts a new file."""
        self.flush()
        self._path = None
        self._written_revision = None
        self._last_attempt = None
        self._failing = False

    # ── Internals ────────────────────────────────────────────────────────────

    def _write(self):
        self._last_attempt = self._clock()
        revision = self._analysis.revision
        temporary = f"{self._path}.tmp"
        try:
            with open(temporary, "w", newline="") as file:
                writer = csv.writer(file, delimiter=";", lineterminator="\n")
                writer.writerow(HEADER)
                writer.writerows(self._rows())
            os.replace(temporary, self._path)
        except Exception:
            if not self._failing:
                logger.warning("Could not write the ignition results to %s", self._path, exc_info=True)
            self._failing = True
            try:
                os.remove(temporary)
            except OSError:
                pass
            return
        self._failing = False
        self._written_revision = revision

    def _rows(self) -> list:
        analysis = self._analysis
        discarded = analysis.discarded()
        gears = sorted(set(analysis.gears_with_data()) | {s.gear for s in discarded})
        scenarios = [s for gear in gears for s in analysis.scenarios(gear)] + discarded
        scenarios.sort(key=lambda s: (s.gear, s.offset, s.discarded))  # stable: discards keep their order
        return [self._row(s) for s in scenarios]

    def _row(self, s: ScenarioStats) -> list:
        analysis = self._analysis
        diffs = [self._diff(s, signal) for signal in _DIFF_SIGNALS]
        return [s.gear, s.offset, analysis.rpm_min, analysis.rpm_max, f"{s.time_s:.1f}", s.samples,
                f"{s.inj_pulse:.2f}", f"{s.map:.1f}", f"{s.pedal:.1f}", f"{s.lambda_:.3f}", f"{s.ign:.1f}",
                s.knock, int(s.eligible), *diffs, int(s.is_best), int(s.discarded)]

    @staticmethod
    def _diff(s: ScenarioStats, signal: Signal) -> str:
        value = None if s.discarded else s.diff.get(signal)
        return "" if value is None else f"{value:.1f}"
