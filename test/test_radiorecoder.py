import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import queue
import threading
import time
from datetime import datetime
from audio_miner.main import RadioRecorder, WhisperModel

class TestRadioRecorder(unittest.TestCase):
    def setUp(self):
        self.base_dir = "test_dir"
        self.recorder = RadioRecorder(
            stream_url="http://example.com/stream.mp3",
            sender="TestSender",
            segment_time=5,
            base_dir=self.base_dir,
            poll_interval=1,
            whisper_model=WhisperModel.TINY,
            quality="32k",
            verbose=False,
            use_monitor=False
        )

    @patch("os.listdir", return_value=["old_file.mp3"])
    @patch("os.path.getmtime", return_value=(datetime.now().timestamp() - 3600))  # 1h alt
    @patch("os.path.exists", return_value=False)
    @patch("os.path.getsize", return_value=1024)
    def test_check_and_queue_old_files(self, mock_getsize, mock_exists, mock_getmtime, mock_listdir):
        """Testet, ob alte nicht transkribierte Dateien in die Warteschlange aufgenommen werden."""
        self.recorder.check_and_queue_old_files(datetime.now())
        self.assertEqual(self.recorder.segment_queue.qsize(), 1)

    @patch("whisper.load_model")
    @patch("builtins.open", new_callable=mock_open)
    def test_transcribe_audio(self, mock_open, mock_whisper):
        """Testet die Transkription einer Datei."""
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"segments": [{"text": "Hallo Welt"}]}
        mock_whisper.return_value = mock_model

        result = self.recorder.transcribe_audio("test.mp3")

        self.assertEqual(result, "Hallo Welt")
        mock_whisper.assert_called_once_with("tiny")

    @patch("audio_miner.main.RadioRecorder.transcribe_audio")
    @patch("builtins.open", new_callable=mock_open)
    def test_transcription_worker(self, mock_open, mock_transcribe):
        """Testet die Transkriptionswarteschlange."""
        test_audio_file = "test_dir/TestSender/audio/test.mp3"
        expected_file = "test_dir/TestSender/transkriptionen/test.txt"
        self.recorder.segment_queue.put(test_audio_file)
        self.recorder.queued_files.add(test_audio_file)

        self.recorder.running = False  # Einmal ausführen
        self.recorder.transcription_worker(run_once=True)

        mock_open.assert_any_call(expected_file, "w", encoding="utf-8")
        mock_transcribe.assert_called_once_with(test_audio_file)

    @patch("audio_miner.main.RadioRecorder.transcribe_audio")
    @patch("builtins.open", new_callable=mock_open)
    def test_transcription_worker_for_empty_queue(self, mock_open, mock_transcribe):
        """Testet, ob bei leerer Queue kein Transkriptionsaufruf erfolgt."""
        self.recorder.running = False
        # direkt eine leere Queue zuweisen
        self.recorder.segment_queue = queue.Queue()
        self.recorder.queued_files = queue.Queue()
        
        self.recorder.transcription_worker(run_once=True)

        # Bei leerer Queue wird ein queue.Empty gefangen (Zeile 135) und weitergemacht,
        # daher darf kein Transkriptions-Aufruf passieren.
        mock_transcribe.assert_not_called()
        mock_open.assert_not_called()

    @patch("threading.Thread.start")
    def test_run(self, mock_thread_start):
        """Testet, ob die Hauptthreads gestartet werden."""
        with patch("time.sleep", side_effect=KeyboardInterrupt):
            self.recorder.run()

        mock_thread_start.assert_any_call()
        self.assertFalse(self.recorder.running)

    @patch("threading.Thread.join")
    def test_stop(self, mock_join):
        """Testet das Stoppen aller Threads."""
        self.recorder.running = True
        self.recorder.record_thread = threading.Thread(target=lambda: None)
        self.recorder.transcription_thread = threading.Thread(target=lambda: None)
        self.recorder.record_thread.start()
        self.recorder.transcription_thread.start()

        self.recorder.stop()

        self.assertFalse(self.recorder.running)

if __name__ == "__main__":
    unittest.main()