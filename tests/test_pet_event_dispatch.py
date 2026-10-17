import os
import importlib.machinery
import sys
import threading
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))

from PyQt5.QtCore import QCoreApplication

main_module = importlib.machinery.SourceFileLoader(
    "yayan_main_event_test", str(Path(__file__).resolve().parents[1] / "desktop" / "main.pyw")
).load_module()
PetEventDispatcher = main_module.PetEventDispatcher


class PetEventDispatchTests(unittest.TestCase):
    def test_events_from_worker_thread_are_delivered_on_qt_thread(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        main_thread = threading.get_ident()
        received = []
        dispatcher = PetEventDispatcher(lambda event: received.append((event, threading.get_ident())))

        worker = threading.Thread(target=lambda: dispatcher.received.emit({"event": "clicked"}))
        worker.start()
        worker.join()
        app.processEvents()

        self.assertEqual(received, [({"event": "clicked"}, main_thread)])


if __name__ == "__main__":
    unittest.main()
