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

class TestRadioTranscription(unittest.TestCase):

    def setUp(self):
        self.stream_url = "http://example.com/stream.mp3"
        self.sender = "TestSender"
        self.base_dir = "test_dir"
        self.recorder = RadioRecorder(self.stream_url, self.sender, 1, self.base_dir, verbose=True, use_monitor=False)

    @patch('audio_miner.main.whisper.load_model')
    def test_transcribe_audio(self, mock_load_model):
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"segments": [{"text": "Hallo Welt."}]}
        mock_load_model.return_value = mock_model

        transcription = self.recorder.transcribe_audio("dummy.mp3")
        self.assertIn("Hallo Welt.", transcription)

if __name__ == '__main__':
    unittest.main()
