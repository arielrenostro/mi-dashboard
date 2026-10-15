import enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.config import config
from app.masterinjection.signal import Signal

# Two consecutive samples further apart than this are not part of the same continuous run.
GAP_LIMIT_SECONDS = 1.0

# Signals every sample must carry.
_REQUIRED = (
    Signal.RPM, Signal.GEAR, Signal.LAMBDA_LOOP, Signal.INJ_PULSE, Signal.MAP,
    Signal.PEDAL, Signal.LAMBDA, Signal.IGN, Signal.KNOCK,
)

# Sensors compared between scenarios; lower is better for all of them.
COMPARED = (Signal.INJ_PULSE, Signal.MAP, Signal.PEDAL)


class AnalysisStatus(enum.Enum):
    PAUSED = "PAUSADO"
    WAITING_ECU = "AGUARDANDO ECU"
    SETTLING = "ESTABILIZANDO"
    OUT_OF_RANGE = "FORA DA FAIXA"
    ANALYSING = "ANALISANDO"


@dataclass
class ScenarioStats:
    offset: int
    gear: int
    time_s: float
    samples: int
    inj_pulse: float
    map: float
    pedal: float
    lambda_: float
    ign: float
    knock: int
    eligible: bool = False
    # Percentage difference to the best value of each compared sensor; None when not eligible or undefined.
    diff: Dict[Signal, Optional[float]] = field(default_factory=dict)
    is_best: bool = False
    discarded: bool = False


class _Accumulator:
    def __init__(self):
        self.time_s = 0.0
        self.samples = 0
        self.sums = {Signal.INJ_PULSE: 0.0, Signal.MAP: 0.0, Signal.PEDAL: 0.0, Signal.LAMBDA: 0.0, Signal.IGN: 0.0}
        self.knock = 0


class IgnitionAnalysis:
    """
    Filters telemetry and accumulates it per gear and ignition offset. The offset is global; scenarios are
    only ever compared inside one gear. No Qt, no clock: the caller passes a monotonic timestamp (seconds)
    with every telemetry set and every event.
    """

    def __init__(self, rpm_min: Optional[int] = None, rpm_max: Optional[int] = None,
                 gears: Optional[List[int]] = None, settle_seconds: Optional[float] = None, min_scenario_seconds: Optional[float] = None):
        cfg = config.ignition_tuning
        self.rpm_min = cfg.rpm_min if rpm_min is None else rpm_min
        self.rpm_max = cfg.rpm_max if rpm_max is None else rpm_max
        self.gears = list(cfg.gears if gears is None else gears)
        self.settle_seconds = cfg.settle_seconds if settle_seconds is None else settle_seconds
        self.min_scenario_seconds = cfg.min_scenario_seconds if min_scenario_seconds is None else min_scenario_seconds
        self.paused = False
        self._scenarios: Dict[Tuple[int, int], _Accumulator] = {}  # (gear, offset) -> accumulator
        self._discarded: List[ScenarioStats] = []
        # Increases with every accepted sample, discard and reset, so a consumer can tell "changed".
        self.revision = 0
        self._awaiting_write = False
        self._settle_until: Optional[float] = None
        self._loop_closed = False
        self._prev: Optional[tuple] = None  # (time, knock, offset, gear) of the previous sample of the current run

    # ── Events ───────────────────────────────────────────────────────────────

    def offset_changed(self, now: float):
        """The offset changed: discard sets until the write happened and the setting settled."""
        self._awaiting_write = True
        self._prev = None

    def write_finished(self, now: float):
        """The debounced write ran (even if there was nothing to send): start settling."""
        self._awaiting_write = False
        self._settle_until = now + self.settle_seconds
        self._prev = None

    def pause(self):
        self.paused = True
        self._prev = None

    def resume(self, now: float):
        if self.paused:
            self.paused = False
            self._settle_until = now + self.settle_seconds
            self._prev = None

    def reset(self):
        """Forget every scenario of every gear (discarded ones included) and start from a clean, running analysis."""
        self._scenarios.clear()
        self._discarded.clear()
        self.revision += 1
        self.paused = False
        self._awaiting_write = False
        self._settle_until = None
        self._prev = None

    def discard_worst(self, gear: int, current_offset: int) -> bool:
        """
        Drop the worst eligible scenario of `gear` (highest mean injection time, ties to the lower offset).
        Nothing is dropped with fewer than two eligible scenarios in that gear, nor when the worst one is the
        scenario of `current_offset`. The dropped scenario is kept, flagged, among `discarded()`.
        Returns whether a scenario was dropped.
        """
        eligible = [s for s in self.scenarios(gear) if s.eligible]
        if len(eligible) < 2:
            return False
        worst = eligible[0]
        for s in eligible[1:]:
            if s.inj_pulse > worst.inj_pulse:
                worst = s
        if worst.offset == current_offset:
            return False
        acc = self._scenarios.pop((gear, worst.offset))
        self._discarded.append(self._stats(gear, worst.offset, acc, discarded=True))
        if self._prev is not None and self._prev[2:] == (worst.offset, gear):
            self._prev = None
        self.revision += 1
        return True

    # ── Telemetry ────────────────────────────────────────────────────────────

    def process(self, signals: dict, now: float, offset: int, map_loaded: bool) -> bool:
        """
        Feed one telemetry set. Returns True when the scenario of `offset` just reached the minimum
        analysed time (the "ready" notification).
        """
        self._track_lambda_loop(signals, now)

        if self.paused or not map_loaded or self._is_settling(now) or not self._conditions_met(signals):
            self._prev = None
            return False

        gear = int(signals[Signal.GEAR].value)
        acc = self._scenarios.setdefault((gear, offset), _Accumulator())
        before = acc.time_s
        knock = int(signals[Signal.KNOCK].value)

        if self._prev is not None:
            prev_time, prev_knock, prev_offset, prev_gear = self._prev
            dt = now - prev_time
            if (prev_offset, prev_gear) == (offset, gear) and 0 < dt <= GAP_LIMIT_SECONDS:
                acc.time_s += dt
                acc.knock += max(0, knock - prev_knock)

        acc.samples += 1
        for signal in acc.sums:
            acc.sums[signal] += signals[signal].value
        self._prev = (now, knock, offset, gear)
        self.revision += 1

        return before < self.min_scenario_seconds <= acc.time_s

    # ── Queries ──────────────────────────────────────────────────────────────

    def status(self, signals: dict, now: float, map_loaded: bool) -> AnalysisStatus:
        """What the screen reports, in priority order."""
        if self.paused:
            return AnalysisStatus.PAUSED
        if not map_loaded:
            return AnalysisStatus.WAITING_ECU
        if self._is_settling(now):
            return AnalysisStatus.SETTLING
        if not self._conditions_met(signals):
            return AnalysisStatus.OUT_OF_RANGE
        return AnalysisStatus.ANALYSING

    def scenarios(self, gear: int) -> List[ScenarioStats]:
        """The active scenarios of one gear in ascending offset order, with percentage differences and best flag."""
        offsets = sorted(offset for g, offset in self._scenarios if g == gear)
        stats = [self._stats(gear, offset, self._scenarios[(gear, offset)]) for offset in offsets]

        eligible = [s for s in stats if s.eligible]
        means = {Signal.INJ_PULSE: "inj_pulse", Signal.MAP: "map", Signal.PEDAL: "pedal"}
        for signal, attr in means.items():
            best = min((getattr(s, attr) for s in eligible), default=None)
            for s in eligible:
                value = getattr(s, attr)
                s.diff[signal] = None if not best else (value - best) / best * 100.0

        if len(eligible) >= 2:
            best_scenario = eligible[0]
            for s in eligible[1:]:
                if s.inj_pulse < best_scenario.inj_pulse:
                    best_scenario = s
            best_scenario.is_best = True
        return stats

    def gears_with_data(self) -> List[int]:
        """The gears that hold at least one active scenario, ascending."""
        return sorted({gear for gear, _ in self._scenarios})

    def discarded(self) -> List[ScenarioStats]:
        """The discarded scenarios, in the order they were discarded, as they were when discarded."""
        return list(self._discarded)

    # ── Internals ────────────────────────────────────────────────────────────

    def _stats(self, gear: int, offset: int, acc: _Accumulator, discarded: bool = False) -> ScenarioStats:
        n = acc.samples
        return ScenarioStats(
            offset=offset,
            gear=gear,
            time_s=acc.time_s,
            samples=n,
            inj_pulse=acc.sums[Signal.INJ_PULSE] / n,
            map=acc.sums[Signal.MAP] / n,
            pedal=acc.sums[Signal.PEDAL] / n,
            lambda_=acc.sums[Signal.LAMBDA] / n,
            ign=acc.sums[Signal.IGN] / n,
            knock=acc.knock,
            eligible=acc.time_s >= self.min_scenario_seconds,
            discarded=discarded,
        )

    def _track_lambda_loop(self, signals: dict, now: float):
        parsed = signals.get(Signal.LAMBDA_LOOP)
        closed = parsed is not None and parsed.value in (1, 2)
        if closed and not self._loop_closed:
            self._settle_until = now + self.settle_seconds
        if not closed:
            self._prev = None
        self._loop_closed = closed

    def _is_settling(self, now: float) -> bool:
        return self._awaiting_write or (self._settle_until is not None and now < self._settle_until)

    def _conditions_met(self, signals: dict) -> bool:
        if any(signal not in signals for signal in _REQUIRED):
            return False
        return (self.rpm_min <= signals[Signal.RPM].value <= self.rpm_max
                and signals[Signal.GEAR].value in self.gears
                and signals[Signal.LAMBDA_LOOP].value in (1, 2))
