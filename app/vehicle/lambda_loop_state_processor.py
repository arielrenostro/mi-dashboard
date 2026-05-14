import logging

from PyQt6.QtCore import QObject

from app.master.ecu import EcuCommand
from app.master.signal import Signal
from app.vehicle.state import vehicle_state

logger = logging.getLogger(__name__)

DECEL_MAP_THRESHOLD = 20  # kPa — pedal=0 + MAP abaixo disso indica fuel cut/desaceleração


class LambdaLoopStateProcessor(QObject):

    def __init__(self):
        super().__init__()

    def process_signals(self, parsed_data: dict) -> None:
        loop_data = parsed_data.get(Signal.LAMBDA_LOOP)
        if loop_data is None:
            return

        ecu_is_closed = loop_data["value"] == 1

        if ecu_is_closed:
            vehicle_state.set_lambda_loop_state(True)
        elif not self._is_decelerating(parsed_data):
            vehicle_state.set_lambda_loop_state(False)
        # open durante desaceleração: manter estado anterior (transitório da ECU)

    def on_command_sent(self, cmd) -> None:
        if cmd == EcuCommand.LAMBDA_LOOP_OPEN:
            logger.info("Lambda loop comandado: OPEN")
            vehicle_state.set_lambda_loop_state(False)
        elif cmd == EcuCommand.LAMBDA_LOOP_CLOSE:
            logger.info("Lambda loop comandado: CLOSE")
            vehicle_state.set_lambda_loop_state(True)

    def _is_decelerating(self, parsed_data: dict) -> bool:
        pedal = parsed_data.get(Signal.PEDAL)
        map_ = parsed_data.get(Signal.MAP)
        if pedal is None or map_ is None:
            return False
        return pedal["value"] == 0.0 and map_["value"] <= DECEL_MAP_THRESHOLD
