import logging
from typing import Dict

from PyQt6.QtCore import QObject
from pyqtgraph.Qt.QtCore import Signal

from app.masterinjection.protocol import EcuResponse
from app.masterinjection.signal import Signal as SignalEnum, ParsedSignal

logger = logging.getLogger(__name__)


class SignalProcessor(QObject):
    emitter = Signal(dict)

    def __init__(self):
        super().__init__()

    def process_line(self, line):
        if not line.startswith(EcuResponse.MESS_DATA_1.value):
            return

        parts = line.split(";")
        if len(parts) < 2:
            return

        parsed_data = dict()
        for signal in SignalEnum:
            try:
                if signal.value.get("calculated", False):
                    try:
                        raw = signal.value["value"](parsed_data)
                        value = raw
                    except:
                        raw = -1
                        value = -1
                else:
                    idx = signal.value["index"]
                    if idx >= len(parts):
                        continue
                    raw = parts[idx]
                    value = signal.value["converter"](raw)

                parsed_data[signal] = ParsedSignal(signal, raw, value)
            except Exception:
                logger.exception("Erro ao processar sinal %s", signal)
        self.emitter.emit(parsed_data)

        from app.event.bus import event_bus
        from app.event.app_events import SignalsReceivedEvent
        event_bus.publish(SignalsReceivedEvent(data=parsed_data))
