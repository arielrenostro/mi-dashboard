import logging

from PyQt6.QtCore import QObject

from app.event.app_events import (
    AppEventType,
    EcuMessFrameEvent,
    SignalsReceivedEvent,
)
from app.event.bus import event_bus
from app.masterinjection.signal import Signal, ParsedSignal

logger = logging.getLogger(__name__)


class SignalProcessor(QObject):

    def __init__(self):
        super().__init__()
        self._frame_buffers: dict[str, list[str]] = {}
        event_bus.subscribe(AppEventType.ECU_MESS_FRAME, self._on_mess_frame)

    def _on_mess_frame(self, event: EcuMessFrameEvent) -> None:
        parts = event.line.split(";")
        self._frame_buffers[event.frame_id] = parts

        parsed_data: dict[Signal, ParsedSignal] = {}

        # Sinais diretos (não calculados)
        for signal in Signal:
            cfg = signal.value
            if cfg.get("calculated"):
                continue
            frame_id = cfg.get("frame", "D01")
            frame_index = cfg.get("frame_index", cfg.get("index"))
            buf = self._frame_buffers.get(frame_id)
            if buf is None or frame_index is None or frame_index >= len(buf):
                continue
            try:
                raw = buf[frame_index]
                value = cfg["converter"](raw)
                parsed_data[signal] = ParsedSignal(signal, raw, value)
            except Exception:
                logger.debug("Erro ao converter sinal %s", signal.name, exc_info=True)
                continue

        # Sinais calculados (dependem de parsed_data)
        for signal in Signal:
            cfg = signal.value
            if not cfg.get("calculated"):
                continue
            try:
                value = cfg["value"](parsed_data)
                parsed_data[signal] = ParsedSignal(signal, value, value)
            except Exception:
                logger.debug("Erro ao calcular sinal %s", signal.name, exc_info=True)
                continue

        if parsed_data:
            event_bus.publish(SignalsReceivedEvent(data=parsed_data))
