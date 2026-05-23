import logging
import time
from typing import Any, List

from app.ecu_connection import EcuConnection
from app.ecu_connection.serial import EcuConnectionSerial
from app.masterinjection.protocol import EcuCommand
from app.state.state import vehicle_state

logger = logging.getLogger(__name__)


class EcuConnectionMock(EcuConnection):

    def __init__(self, mock_file):
        super().__init__()
        self.mock_file = mock_file
        self.line = 0

    def send_command(self, cmd: EcuCommand, args: List[Any] | None = None) -> None:
        # TODO: move ecu connection handshake out of EcuConnectionSerial
        if cmd == EcuCommand.MAP_BREAKPOINTS:
            self.emitter.emit('#I21;20;30;40;50;60;70;80;90;100;120;140;160;180;200;220;240')
        elif cmd == EcuCommand.RPM_BREAKPOINTS:
            self.emitter.emit('#I20;400;800;1200;1600;2000;2400;2800;3200;3600;4000;4400;4800;5200;5600;6200;6800')

    def run(self):
        last_timestamp = None

        map_breakpoint_response = '#I21;20;30;40;50;60;70;80;90;100;120;140;160;180;200;220;240'
        rpm_breakpoint_response = '#I20;400;800;1200;1600;2000;2400;2800;3200;3600;4000;4400;4800;5200;5600;6200;6800'
        map_breakpoint = list(map(lambda x: int(x), map_breakpoint_response.split(";")[1:]))
        rpm_breakpoint = list(map(lambda x: int(x), rpm_breakpoint_response.split(";")[1:]))
        vehicle_state.set_map_breakpoints(map_breakpoint)
        vehicle_state.set_rpm_breakpoints(rpm_breakpoint)
        logger.info(f"Breakpoints RPM: {rpm_breakpoint}")
        logger.info(f"Breakpoints MAP: {map_breakpoint}")

        fuel_str = """#F16;855;898;909;896;918;926;934;962;974;994;1022;1020;1010;971;933;897
#F15;843;885;898;885;906;916;925;952;964;984;1012;1010;1000;961;924;888
#F14;832;874;884;874;893;906;916;943;954;974;1002;1000;990;951;915;879
#F13;822;863;873;861;881;896;907;934;945;964;992;990;980;942;906;871
#F12;810;851;861;848;868;886;889;916;926;945;973;972;962;924;888;854
#F11;792;832;842;829;847;865;868;896;909;928;958;948;939;903;868;835
#F10;774;813;822;810;826;846;845;860;870;888;924;915;906;870;836;804
#F09;748;785;795;782;805;820;813;812;811;839;873;881;872;838;806;775
#F08;733;770;778;768;785;800;789;789;790;814;838;846;838;806;775;745
#F07;710;745;753;747;745;768;761;757;758;790;813;821;810;777;747;720
#F06;695;730;737;726;713;736;738;733;739;773;787;795;787;756;726;698
#F05;633;665;690;692;685;727;702;695;714;753;764;771;763;733;705;678
#F04;566;594;651;647;656;703;678;668;681;730;747;753;746;718;690;663
#F03;561;569;623;622;618;669;650;636;653;681;701;708;701;673;647;622
#F02;568;587;635;626;635;672;631;612;631;679;710;714;707;678;651;625
#F01;561;588;630;636;615;632;597;588;621;667;697;701;694;666;640;615"""

        for fuel_line in fuel_str.strip().split("\n"):
            fuel_line = fuel_line.strip().split(";")
            ve_idx = int(fuel_line[0][2:]) - 1
            ve_line = list(map(lambda x: int(x), fuel_line[1:]))
            vehicle_state.set_ve_map(ve_line, ve_idx)

        ve_map = vehicle_state.get_ve_map()
        for i, ve_line in reversed(list(enumerate(ve_map))):
            logger.info(f"Fuel Map: {i} {ve_line}")

        with open(self.mock_file, 'r') as f:
            log_origin = "master"
            line = f.readline().replace(',', ';').strip()

            if line.count(';') == 33:
                log_origin = "this"

            for line in f:
                self.line += 1
                if not self.running:
                    break
                if self.line < 12250:
                    continue
                parts = line.split(';')

                logger.debug(f'Emitting mock line: {line}')
                self.emitter.emit(line.strip())

                if log_origin == "this" and last_timestamp is not None:
                    try:
                        timestamp = int(parts[0])
                        time.sleep(timestamp - last_timestamp)
                        last_timestamp = timestamp
                        continue
                    except:
                        pass

                time.sleep(0.1)
                last_timestamp = time.time()

    def is_connected(self) -> bool:
        return self.running
