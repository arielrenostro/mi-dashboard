from typing import List

from app.ecu_connection.ecu_connection import EcuConnection
from app.masterinjection.signal_processor import SignalProcessor
from app.state.processors.base import Processor
from app.state.processors.lambda_loop_state import LambdaLoopStateProcessor


class StateProcessorRegister:

    def __init__(self):
        self.processors: List[Processor] = list()
        self.processors.append(LambdaLoopStateProcessor())

    def register(self, signal_processor: SignalProcessor, ecu_connection: EcuConnection):
        for processor in self.processors:
            signal_processor.emitter.connect(processor.on_signal_received)
            ecu_connection.emitter.connect(processor.on_command_received)
