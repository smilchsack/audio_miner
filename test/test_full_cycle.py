import unittest
import threading
import time
import os
from unittest.mock import patch, MagicMock
from audio_miner.main import RadioRecorder

class TestFullRunCycle(unittest.TestCase):

    def setUp(self):
        self.base_dir = "test_run_cycle"
        self.audio_dir = os.path.join(self.base_dir, "RunCycleTest", "audio")
        os.makedirs(self.audio_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.base_dir):
            import shutil
            shutil.rmtree(self.base_dir)

    @patch('audio_miner.main.subprocess.run')
    @patch('audio_miner.main.time.sleep', return_value=None)
    def test_full_run_cycle(self, mock_sleep, mock_subprocess_run):
        recorder = RadioRecorder("http://test", "RunCycleTest", segment_time=1, base_dir=self.base_dir, use_monitor=False)
        recorder.running = True

        temp_mp3 = os.path.join(self.audio_dir, "RunCycleTest_20250317_084145.mp3")
        with open(temp_mp3, "w") as f:
            f.write("fake audio data")

        test_thread = threading.Thread(target=recorder.run)
        test_thread.start()

        time.sleep(0.5)

        recorder.stop()
        test_thread.join()

        self.assertTrue(hasattr(recorder, 'record_thread'))
        self.assertTrue(hasattr(recorder, 'transcription_thread'))
        self.assertFalse(recorder.running)

if __name__ == '__main__':
    unittest.main()
