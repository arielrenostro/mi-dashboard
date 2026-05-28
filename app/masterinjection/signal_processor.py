from __future__ import annotations

import logging

from PyQt6.QtCore import QObject

from app.event.app_events import AppEventType, EcuMessFrameEvent, SignalsReceivedEvent
from app.event.bus import event_bus
from app.masterinjection.signal import Signal as SignalEnum, ParsedSignal

logger = logging.getLogger(__name__)

# D01 has fields at absolute indices 0–16 (inclusive), D02 starts at index 17.
_D02_OFFSET = 17


class SignalProcessor(QObject):

    def __init__(self):
        super().__init__()
        event_bus.subscribe(AppEventType.ECU_MESS_FRAME, self._on_mess_frame)

    def _on_mess_frame(self, event: EcuMessFrameEvent) -> None:
        if event.frame_type == "D01":
            parts = event.line.split(";")
        elif event.frame_type == "D02":
            # Pad so absolute indices from the joined format still work
            parts = [""] * _D02_OFFSET + event.line.split(";")
        else:
            return  # D03 not yet mapped

        parsed_data: dict = {}

        for signal in SignalEnum:
            try:
                signal_def = signal.value
                if signal_def.get("calculated", False):
                    continue  # calculated signals processed after
                idx = signal_def["index"]
                if idx >= len(parts) or parts[idx] == "":
                    continue
                raw = parts[idx]
                value = signal_def["converter"](raw)
                parsed_data[signal] = ParsedSignal(signal, raw, value)
            except Exception:
                logger.exception("Erro ao processar sinal %s", signal)

        if not parsed_data:
            return

        # Computed signals — use vehicle_state to fill in missing dependencies
        if event.frame_type == "D02":
            self._compute_calculated(parsed_data)

        event_bus.publish(SignalsReceivedEvent(data=parsed_data))

    def _compute_calculated(self, parsed_data: dict) -> None:
        from app.state.state import vehicle_state
        merged = {**vehicle_state.get_all(), **parsed_data}
        for signal in SignalEnum:
            if not signal.value.get("calculated", False):
                continue
            try:
                value = signal.value["value"](merged)
                parsed_data[signal] = ParsedSignal(signal, value, value)
            except Exception:
                pass
