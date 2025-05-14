import subprocess
import unittest
from unittest.mock import patch, MagicMock
import os
import queue
from datetime import datetime
import time
from audio_miner import main
from audio_miner.main import RadioRecorder, WhisperModel
import shutil
from unittest.mock import patch
import unittest
from unittest.mock import patch, MagicMock
import subprocess
import os
import shutil
import logging
from datetime import datetime
from audio_miner.main import RadioRecorder

import threading
original_thread_class = threading.Thread 

class TestRadioEdgeCases(unittest.TestCase):

    def test_no_base_dir(self):
        recorder = RadioRecorder("http://test", "NoBaseDir", segment_time=2, base_dir=None, use_monitor=False)
        self.assertIn("NoBaseDir", recorder.audio_dir)

    def test_verbose_in_constructor(self):
        recorder = RadioRecorder("http://test", "VerbosityTest", segment_time=2, verbose=True, use_monitor=False)
        self.assertTrue(recorder.verbose)

if __name__ == '__main__':
    unittest.main()
