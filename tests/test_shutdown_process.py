"""Spec: openspec/specs/app-lifecycle (Orderly shutdown).

The abort this change fixes ("QThread: Destroyed while thread is still running") only happens when the
interpreter exits, so the real components run in a child process whose exit status and stderr are checked.
"""
import csv
import os
import subprocess
import sys
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHILD = textwrap.dedent('''
    import os, sys, time
    sys.path.insert(0, {root!r})
    from PyQt6.QtCore import QObject, QTimer, pyqtSlot
    from PyQt6.QtWidgets import QApplication
    from app.alarm.processor import AlarmProcessor
    from app.ecu_connection import register_ecu_connection, get_ecu_connection, get_ecu_connection_thread
    from app.ecu_connection.ecu_connection import EcuConnection
    from app.ecu_connection.serial import EcuConnectionSerial
    from app.lifecycle import shutdown
    from app.log_writer.log_writer import LogWriter
    from app.masterinjection.signal_processor import SignalProcessor
    from app.ui.window import AppWindow

    FRAME = {frame!r}

    class Counter(QObject):  # a QObject slot is connected weakly, exactly like main() connects log_writer.write
        def __init__(self):
            super().__init__()
            self.n = 0

        @pyqtSlot(str)
        def count(self, line):
            self.n += line.startswith("#D01")

    class FakeEcu(EcuConnection):
        def send_command(self, cmd, args=None): pass
        def is_connected(self): return self.running
        def run(self):
            self.emitter.emit(FRAME)
            time.sleep(0.01)

    # Everything lives in a function, like main(): the abort happens when its locals are destroyed.
    def run():
        app = QApplication([])
        log_writer = LogWriter({csv_path!r})
        counter = Counter()

        alarm = AlarmProcessor("does-not-exist.wav")
        alarm.start()
        window = AppWindow(SignalProcessor())
        window.show()
        register_ecu_connection(FakeEcu() if {source!r} == "fake" else EcuConnectionSerial("/dev/does-not-exist", 115200))
        get_ecu_connection().emitter.connect(log_writer.write)
        get_ecu_connection().emitter.connect(counter.count)
        get_ecu_connection_thread().start()

        QTimer.singleShot(600, app.quit)
        app.exec()
        started = time.time()
        shutdown(window, get_ecu_connection_thread(), alarm, log_writer)
        print("WRITES=%d SHUTDOWN_SECONDS=%.2f" % (counter.n, time.time() - started))

    run()
''')

FRAME = (
    "#D01;3415;20;10;41;41;1119;107;6;638;39;0;1;1000;1101;0;0;"
    "#D02;141;360;327;543;347;86;0;1000;1009;1170;150;0;784;5000;0;4"
)


def run_child(tmp_path, source):
    csv_path = str(tmp_path / "log_stream_child.csv")
    code = CHILD.format(root=ROOT, frame=FRAME, csv_path=csv_path, source=source)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_LOGGING_RULES="qt.multimedia*=false",
               MI_DASHBOARD_CONFIG_FILE=os.devnull)
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60, cwd=ROOT, env=env)
    return result, csv_path


def parse(result):
    fields = dict(part.split("=") for part in result.stdout.split() if "=" in part)
    return int(fields["WRITES"]), float(fields["SHUTDOWN_SECONDS"])


def test_the_process_exits_cleanly_while_frames_are_streaming(tmp_path):
    """Scenario: Normal exit."""
    result, _ = run_child(tmp_path, "fake")

    assert result.returncode == 0, result.stderr
    assert "Destroyed while thread" not in result.stderr
    assert "QThread" not in result.stderr


def test_every_frame_received_before_exit_is_in_the_csv(tmp_path):
    """Scenario: Last frames are kept."""
    result, csv_path = run_child(tmp_path, "fake")
    writes, _ = parse(result)

    with open(csv_path, newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))

    assert writes > 10
    assert len(rows) - 1 == writes  # header excluded


def test_the_process_exits_cleanly_when_the_serial_port_is_unavailable(tmp_path):
    """Scenario: Exit while the port is unavailable."""
    result, _ = run_child(tmp_path, "serial")

    assert result.returncode == 0, result.stderr
    assert "QThread" not in result.stderr
    assert parse(result)[1] < 3.0  # the retry loop did not keep the thread alive until the bounded wait ran out
