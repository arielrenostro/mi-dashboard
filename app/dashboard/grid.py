from app.master.signals import Signals

GRAPH = [
    [Signals.LAMBDA, Signals.LAMBDA_TARGET, Signals.FUEL_TRIM],
    [Signals.RPM, Signals.VSS, Signals.MAP],
]

GRID = [
    [Signals.RPM, Signals.VSS, Signals.MAP, Signals.CLT, Signals.IAT],
    [Signals.LAMBDA, Signals.LAMBDA_TARGET, Signals.FUEL_TRIM, Signals.INJ_UTIL, Signals.IGN],
]
