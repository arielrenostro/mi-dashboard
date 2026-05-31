import logging

from PyQt6.QtCore import QObject

from app.event.app_events import AppEventType, EcuFrameReceivedEvent, EcuFrameType, SignalsReceivedEvent
from app.event.bus import event_bus
from app.masterinjection.signal import Signal as SignalEnum, ParsedSignal

logger = logging.getLogger(__name__)


class SignalProcessor(QObject):

    def __init__(self):
        super().__init__()
        self._accumulated: dict = {}
        event_bus.subscribe(AppEventType.ECU_FRAME_RECEIVED, self._on_frame_received)

    def _on_frame_received(self, event: EcuFrameReceivedEvent) -> None:
        values = event.values   # tuple of str, 0-indexed (values[0] = field index 1)
        frame_type = event.frame_type

        parsed_data: dict = {}

        for signal in SignalEnum:
            sig_def = signal.value
            if sig_def.get("calculated", False):
                continue
            if sig_def.get("frame") != frame_type:
                continue

            idx = sig_def["index"]          # 1-based relative to frame
            arr_idx = idx - 1               # 0-based into values tuple
            if arr_idx >= len(values):
                continue

            try:
                raw = values[arr_idx]
                value = sig_def["converter"](raw)
                parsed_data[signal] = ParsedSignal(signal, raw, value)
            except Exception:
                logger.exception("Erro ao processar sinal %s", signal)

        # Merge into accumulator so calculated signals have cross-frame data
        self._accumulated.update(parsed_data)

        # Compute calculated signals using the full accumulated snapshot
        for signal in SignalEnum:
            sig_def = signal.value
            if not sig_def.get("calculated", False):
                continue
            try:
                raw = sig_def["value"](self._accumulated)
                value = raw
                self._accumulated[signal] = ParsedSignal(signal, raw, value)
                parsed_data[signal] = self._accumulated[signal]
            except Exception:
                pass

        if parsed_data:
            event_bus.publish(SignalsReceivedEvent(data=parsed_data))
