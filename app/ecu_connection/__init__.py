from app.ecu_connection.ecu_protocol import EcuProtocol
from app.ecu_connection.thread import EcuConnectionThread

ecu_protocol: EcuProtocol
ecu_connection_thread: EcuConnectionThread


def register_ecu_protocol(instance: EcuProtocol):
    global ecu_protocol
    global ecu_connection_thread
    ecu_protocol = instance
    ecu_connection_thread = EcuConnectionThread(ecu_protocol)


def get_ecu_protocol() -> EcuProtocol:
    return ecu_protocol


def get_ecu_connection_thread() -> EcuConnectionThread:
    return ecu_connection_thread
