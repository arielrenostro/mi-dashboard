import time

ALARM_DURATION = 2
_state = {}


def is_any_alarm_firing():
    global _state

    for signal in _state.keys():
        if is_alarm_firing(signal):
            return True
    return False


def is_alarm_firing(signal):
    global _state

    last_triggered = _state.get(signal)
    if last_triggered:
        return time.time() - last_triggered < ALARM_DURATION
    return False


def set_alarm_state(signal, active):
    global _state

    if active:
        _state[signal] = time.time()
