from app.master.signal import Signal

GRAPH = [
    [Signal.LAMBDA, Signal.LAMBDA_TARGET, Signal.FUEL_TRIM],
    [Signal.RPM, Signal.VSS, Signal.MAP],
    [Signal.POWER, Signal.TORQUE],
]

GRID = [
    [Signal.RPM, Signal.VSS, Signal.MAP, Signal.BOOST, Signal.CLT, Signal.IAT, Signal.POWER],
    [Signal.LAMBDA, Signal.LAMBDA_TARGET, Signal.FUEL_TRIM, Signal.BOOST_TARGET, Signal.INJ_UTIL, Signal.IGN, Signal.TORQUE],
]
