from app.ecu_connection.session import EcuSession

_ecu_session: EcuSession | None = None


def register_ecu_session(session: EcuSession) -> None:
    global _ecu_session
    _ecu_session = session


def get_ecu_session() -> EcuSession:
    if _ecu_session is None:
        raise RuntimeError("EcuSession não registrada — chamar register_ecu_session() primeiro")
    return _ecu_session


# Alias para compatibilidade (remover após confirmar que nenhum módulo usa)
def get_ecu_connection() -> EcuSession:
    return get_ecu_session()
