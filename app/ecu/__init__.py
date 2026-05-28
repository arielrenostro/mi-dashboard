from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ecu.session import EcuSession

_ecu_session: "EcuSession | None" = None


def register_ecu_session(session: "EcuSession") -> None:
    global _ecu_session
    _ecu_session = session


def get_ecu_session() -> "EcuSession":
    if _ecu_session is None:
        raise RuntimeError("EcuSession não registrada. Chame register_ecu_session() primeiro.")
    return _ecu_session
