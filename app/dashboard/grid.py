from app.master.signals import Signals

GRAPH = [
    [Signals.LAMBDA, Signals.LAMBDA_TARGET, Signals.FUEL_TRIM],
    [Signals.RPM, Signals.VSS, Signals.MAP,Signals.PEDAL],
    [Signals.POWER, Signals.TORQUE],
]

GRID = [
    [Signals.RPM, Signals.VSS, Signals.MAP, Signals.CLT, Signals.IAT, Signals.POWER],
    [Signals.LAMBDA, Signals.LAMBDA_TARGET, Signals.FUEL_TRIM, Signals.INJ_UTIL, Signals.IGN, Signals.TORQUE],
]
