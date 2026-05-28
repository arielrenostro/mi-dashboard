from app.ecu.transport.base import EcuTransport
from app.ecu.transport.mock_transport import MockTransport
from app.ecu.transport.serial_transport import SerialTransport


def create_transport() -> EcuTransport:
    from app.config import config
    if config.connection.mock:
        return MockTransport(config.connection.mock)
    return SerialTransport(config.connection.port, config.connection.baudrate)
