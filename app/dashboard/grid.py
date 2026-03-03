from app.master.signal import Signal

GRAPH = [
    [Signal.LAMBDA, Signal.LAMBDA_TARGET, Signal.FUEL_TRIM],
    [Signal.RPM, Signal.VSS, Signal.MAP, Signal.PEDAL],
    [Signal.POWER, Signal.TORQUE],
]

GRID = [
    [Signal.RPM, Signal.VSS, Signal.MAP, Signal.CLT, Signal.IAT, Signal.GEAR, Signal.POWER],
    [Signal.LAMBDA, Signal.LAMBDA_TARGET, Signal.FUEL_TRIM, Signal.INJ_UTIL, Signal.PEDAL, Signal.IGN, Signal.TORQUE],
]
