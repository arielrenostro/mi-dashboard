from app.ecu_connection.ecu_connection import EcuConnection
from app.ecu_connection.thread import EcuConnectionThread

ecu_connection: EcuConnection
ecu_connection_thread: EcuConnectionThread


def register_ecu_connection(instance: EcuConnection):
    global ecu_connection
    global ecu_connection_thread
    ecu_connection = instance
    ecu_connection_thread = EcuConnectionThread(ecu_connection)


def get_ecu_connection() -> EcuConnection:
    return ecu_connection


def get_ecu_connection_thread() -> EcuConnectionThread:
    return ecu_connection_thread
