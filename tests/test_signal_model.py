"""Spec: openspec/specs/signal-model (catalog, conversions, calculated signals)."""
import pytest

from app.masterinjection.signal import Signal
from tests.helpers import parsed

# signal, position, unit, graph min, graph max, color, alarm enabled, alarm min, alarm max
CATALOG = [
    (Signal.RPM, 1, "RPM", 0, 7000, "red", True, 0, 6600),
    (Signal.MAP, 2, "kPa", 20, 250, "fuchsia", True, 0, 165),
    (Signal.BOOST, 3, "kPa", 20, 250, "blue", False, 0, 165),
    (Signal.LAMBDA, 6, "λ", 0.5, 1.5, "lime", False, 0.70, 9999.0),
    (Signal.INJ_UTIL, 8, "%", 0, 100, "lime", True, -999, 90),
    (Signal.VE, 9, "%", 0, 1200, "lime", False, None, None),
    (Signal.IGN, 10, "º", -45, 45, "lime", False, 0, 40),
    (Signal.CLT, 19, "ºC", -20, 120, "orange", True, 0, 95),
    (Signal.IAT, 20, "ºC", -20, 120, "DodgerBlue", False, 0, 80),
    (Signal.VSS, 23, "km/h", 0, 200, "blue", True, 0, 150),
    (Signal.LAMBDA_LOOP, 24, "", 0, 2, "orange", False, None, None),
    (Signal.LAMBDA_TARGET, 25, "λ", 0.5, 1.5, "blue", False, 0.70, 1.30),
    (Signal.FUEL_TRIM, 26, "%", -20, 20, "gray", True, -20, 20),
    (Signal.BOOST_TARGET, 28, "kPa", 20, 250, "MediumSeaGreen", False, None, None),
    (Signal.PEDAL, 29, "%", 0, 100, "MediumSeaGreen", False, None, None),
    (Signal.GEAR, 33, "", 0, 6, "lime", False, None, None),
]


@pytest.mark.parametrize("signal,pos,unit,gmin,gmax,color,enabled,amin,amax", CATALOG, ids=lambda v: getattr(v, "name", None))
def test_direct_signal_catalog_entry(signal, pos, unit, gmin, gmax, color, enabled, amin, amax):
    """Requirement: Direct signal catalog."""
    d = signal.value
    assert (d["index"], d["unit"], d["min"], d["max"], d["color"]) == (pos, unit, gmin, gmax, color)
    assert d["alarm"] == {"enabled": enabled, "min": amin, "max": amax}


def test_catalog_has_no_unlisted_direct_signals():
    """Requirement: Direct signal catalog (the table is exhaustive)."""
    direct = {s for s in Signal if not s.value.get("calculated")}
    assert direct == {row[0] for row in CATALOG}


@pytest.mark.parametrize(
    "signal,raw,value,display",
    [
        (Signal.RPM, "3415", 3415, "3415"),
        (Signal.CLT, "342", 69, "69"),  # scenario: Temperature conversion
        (Signal.IAT, "296", 23, "23"),
        (Signal.LAMBDA, "903", 0.903, "0.90"),  # scenario: Lambda conversion
        (Signal.LAMBDA_TARGET, "1000", 1.0, "1.00"),
        (Signal.FUEL_TRIM, "1001", 0.1, "0.1"),  # scenario: Fuel trim conversion
        (Signal.FUEL_TRIM, "980", -2.0, "-2.0"),
        (Signal.VE, "627", 62.7, "62.7"),
        (Signal.PEDAL, "495", 50.0, "50.0"),
        (Signal.PEDAL, "1200", 100.0, "100.0"),  # scenario: Pedal clamp
        (Signal.LAMBDA_LOOP, "0", 0, "Open"),  # scenario: Open loop
        (Signal.LAMBDA_LOOP, "1", 1, "Closed"),  # scenario: Closed loop
        (Signal.LAMBDA_LOOP, "2", 2, "Closed+C"),  # scenario: Closed loop with automatic correction
        (Signal.GEAR, "4", 4, "4"),
    ],
)
def test_conversion_and_display(signal, raw, value, display):
    """Requirement: Direct signal catalog (conversion and display columns)."""
    converted = signal.value["converter"](raw)
    assert converted == pytest.approx(value)
    assert signal.value["for_label"](converted) == display


def test_calculated_signals_come_after_their_dependencies():
    """Requirement: Calculated signals (computed after all direct signals, in order)."""
    order = list(Signal)
    calculated = [s for s in order if s.value.get("calculated")]
    assert calculated == [Signal.VE_LAMBDA, Signal.POWER, Signal.TORQUE]
    assert all(order.index(c) > order.index(s) for c in calculated for s in order if not s.value.get("calculated"))
    assert order.index(Signal.TORQUE) > order.index(Signal.POWER)


def _inputs(**values):
    return {Signal[name]: parsed(Signal[name], value) for name, value in values.items()}


def test_power_formula():
    """Requirement: Calculated signals (POWER)."""
    data = _inputs(MAP=100, VE=62.7, RPM=3000, IAT=25, LAMBDA=0.9)
    air_mass = (100 * 62.7 * 10 * 0.001587 * 3000) / (287 * (25 + 273) * 2 * 60)
    expected = (air_mass / (9 * 0.9) * 3600 * 2.20462) / 0.8
    assert Signal.POWER.value["value"](data) == pytest.approx(expected)


def test_torque_formula():
    """Requirement: Calculated signals (TORQUE)."""
    data = _inputs(RPM=4000)
    data[Signal.POWER] = parsed(Signal.POWER, 200.0)
    assert Signal.TORQUE.value["value"](data) == pytest.approx(200.0 * 716.2 / 4000)


def test_torque_guard_at_zero_rpm():
    """Scenario: Torque guard (division uses 1 when RPM is 0)."""
    data = _inputs(RPM=0)
    data[Signal.POWER] = parsed(Signal.POWER, 0.0)
    assert Signal.TORQUE.value["value"](data) == 0.0


def test_ve_lambda_formula_uses_raw_values():
    """Requirement: Calculated signals (VE_LAMBDA uses the raw integer fields)."""
    data = {
        Signal.LAMBDA: parsed(Signal.LAMBDA, 0.903, raw="903"),
        Signal.FUEL_TRIM: parsed(Signal.FUEL_TRIM, 0.1, raw="1001"),
        Signal.LAMBDA_TARGET: parsed(Signal.LAMBDA_TARGET, 1.0, raw="1000"),
        Signal.VE: parsed(Signal.VE, 62.7, raw="627"),
    }
    assert Signal.VE_LAMBDA.value["value"](data) == pytest.approx((903 + 1001 - 1000) * 627 / 10000)
