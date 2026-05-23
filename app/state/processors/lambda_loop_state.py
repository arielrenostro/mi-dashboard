import logging
from typing import Dict, List, Any

from app.masterinjection.protocol import EcuCommand
from app.masterinjection.signal import Signal, ParsedSignal
from app.state.processors.base import Processor
from app.state.state import vehicle_state

logger = logging.getLogger(__name__)

DECEL_MAP_THRESHOLD = 20


class LambdaLoopStateProcessor(Processor):

    def __init__(self):
        super().__init__()

    def on_command_received(self, cmd: EcuCommand, args: List[Any]) -> None:
        if cmd == EcuCommand.LAMBDA_LOOP_OPEN:
            logger.info("Lambda loop comandado: OPEN")
            vehicle_state.set_lambda_loop_state(False)
        elif cmd == EcuCommand.LAMBDA_LOOP_CLOSE:
            logger.info("Lambda loop comandado: CLOSE")
            vehicle_state.set_lambda_loop_state(True)

    def on_signal_received(self, signals: Dict[Signal, ParsedSignal]) -> None:
        loop_data = signals.get(Signal.LAMBDA_LOOP)
        if loop_data is None:
            return

        ecu_is_closed = loop_data.value == 1

        if ecu_is_closed:
            vehicle_state.set_lambda_loop_state(True)
        elif not self._is_decelerating(signals):
            vehicle_state.set_lambda_loop_state(False)

    def _is_decelerating(self, parsed_data: dict) -> bool:
        pedal = parsed_data.get(Signal.PEDAL)
        map_ = parsed_data.get(Signal.MAP)
        if pedal is not None and map_ is not None:
            return pedal.value == 0.0 and map_.value <= DECEL_MAP_THRESHOLD
        return False
