import logging

logger = logging.getLogger(__name__)


def shutdown(window, ecu_thread, alarm, log_writer, gyro=None):
    """Stop the whole app in a fixed order, whatever fails on the way.

    Window first, then the ECU source (so no new frame arrives), the inclinometer, the alarm, and the datalog last
    so it writes every frame that did arrive. Each step is isolated: a failure is logged and the rest still run.
    """
    steps = (
        ("window", window, "close"),
        ("ECU source", ecu_thread, "stop"),
        ("inclinometer", gyro, "stop"),
        ("alarm", alarm, "stop"),
        ("datalog", log_writer, "close"),
    )
    for name, component, method in steps:
        if component is None:
            continue
        try:
            getattr(component, method)()
        except Exception:
            logger.exception("Error while stopping the %s", name)
