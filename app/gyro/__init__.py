from app.gyro.connection import GyroConnection

_gyro: GyroConnection | None = None


def register_gyro(instance: GyroConnection) -> None:
    global _gyro
    _gyro = instance


def get_gyro() -> GyroConnection:
    """The registered inclinometer; a disabled one (no port, no thread) when none was registered."""
    global _gyro
    if _gyro is None:
        _gyro = GyroConnection("")
    return _gyro
