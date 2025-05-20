import unittest
import os
import tempfile
import time
from unittest.mock import patch, MagicMock
from audio_miner.main import FileMonitor

class TestFileMonitor(unittest.TestCase):
    @patch('time.sleep', side_effect=lambda x: None)
    def test_file_monitor_invokes_callback_after_inactivity(self, _):
        """
        Verifiziert, dass der Callback aufgerufen wird,
        wenn die Datei für >= check_duration nicht mehr wächst.
        """
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file_path = tmp.name

        callback_mock = MagicMock()
        monitor = FileMonitor(file_path, callback=callback_mock, interval=1, check_duration=2, run_once=True)

        try:
            monitor.start()

            with open(file_path, 'w') as f:
                f.write("Initial data")

            time.sleep(0.1)
            with open(file_path, 'a') as f:
                f.write("More data")

            time.sleep(0.3)

            monitor.stop()
            monitor.join()

            callback_mock.assert_called_once()
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

if __name__ == "__main__":
    unittest.main()