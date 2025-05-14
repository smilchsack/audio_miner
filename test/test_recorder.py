import unittest
from unittest.mock import patch, MagicMock
import subprocess
import logging
from datetime import datetime
import os

from audio_miner.main import RadioRecorder

class TestRadioRecorder(unittest.TestCase):

    def setUp(self):
        self.stream_url = "http://example.com/stream.mp3"
        self.sender = "TestSender"
        self.segment_time = 1
        self.base_dir = "test_dir"
        # Stelle sicher, dass die notwendigen Verzeichnisse existieren
        os.makedirs(os.path.join(self.base_dir, self.sender, "audio"), exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, self.sender, "transkriptionen"), exist_ok=True)

    def timeout_side_effect(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=kwargs.get("timeout", 1))

    @patch('audio_miner.main.os.rename')
    @patch('audio_miner.main.datetime')
    @patch('audio_miner.main.subprocess.Popen')
    def test_record_stream_verbose_false(self, mock_popen, mock_datetime, mock_rename):
        # Bei verbose=False sollen stdout/stderr auf DEVNULL gesetzt werden.
        recorder = RadioRecorder(self.stream_url, self.sender, self.segment_time,
                                 self.base_dir, verbose=False, use_monitor=False)

        # Prüfe den Instanz-Logger
        self.assertEqual(recorder.logger.level, logging.INFO)

        # Simuliere now() Aufrufe
        mock_start_time = datetime(2024, 1, 1, 10, 0, 0)
        mock_end_time = datetime(2024, 1, 1, 10, 0, self.segment_time)
        mock_datetime.now.side_effect = [mock_start_time, mock_end_time] + [mock_end_time] * 10

        # Um den Prozessablauf in _attempt_record_segment zu vermeiden, patche _finalize_segment
        with patch.object(recorder, "_finalize_segment", return_value="dummy_file.mp3"):
            # Dummy-Prozessobjekt
            dummy_process = MagicMock()
            dummy_process.wait = MagicMock()
            dummy_process.kill = MagicMock()
            # Wir definieren einen Side-Effect, der im ersten Anlauf recorder.running auf False setzt.
            def popen_side_effect(*args, **kwargs):
                # Stoppe nach dem ersten Aufruf
                recorder.running = False
                return dummy_process

            mock_popen.side_effect = popen_side_effect

            recorder.running = True
            recorder.record_stream()

            # Prüfe, dass Popen genau einmal mit DEVNULL-Parametern aufgerufen wurde.
            mock_popen.assert_called_once()
            call_args, call_kwargs = mock_popen.call_args
            self.assertEqual(call_kwargs.get("stdout"), subprocess.DEVNULL)
            self.assertEqual(call_kwargs.get("stderr"), subprocess.DEVNULL)

    @patch('audio_miner.main.os.rename')
    @patch('audio_miner.main.datetime')
    @patch('audio_miner.main.subprocess.Popen')
    def test_record_stream_verbose_true(self, mock_popen, mock_datetime, mock_rename):
        # Bei verbose=True sollen stdout und stderr None bleiben.
        recorder = RadioRecorder(self.stream_url, self.sender, self.segment_time,
                                 self.base_dir, verbose=True, use_monitor=False)

        self.assertEqual(recorder.logger.level, logging.DEBUG)

        mock_start_time = datetime(2024, 1, 1, 10, 0, 0)
        mock_end_time = datetime(2024, 1, 1, 10, 0, self.segment_time)
        mock_datetime.now.side_effect = [mock_start_time, mock_end_time] + [mock_end_time] * 10

        with patch.object(recorder, "_finalize_segment", return_value="dummy_file.mp3"):
            dummy_process = MagicMock()
            dummy_process.wait = MagicMock()
            dummy_process.kill = MagicMock()

            def popen_side_effect(*args, **kwargs):
                recorder.running = False
                return dummy_process

            mock_popen.side_effect = popen_side_effect

            recorder.running = True
            recorder.record_stream()

            mock_popen.assert_called_once()
            call_args, call_kwargs = mock_popen.call_args
            self.assertIsNone(call_kwargs.get("stdout"))
            self.assertIsNone(call_kwargs.get("stderr"))

    @patch('audio_miner.main.os.rename')
    @patch('audio_miner.main.subprocess.Popen')
    def test_record_stream_multiple_iterations(self, mock_popen, mock_rename):
        """Testet, ob der Recorder bei run_once=False mehrere Iterationen durchläuft."""
        recorder = RadioRecorder(self.stream_url, self.sender, self.segment_time,
                                 self.base_dir, verbose=False, run_once=False, use_monitor=False)
        call_count = 0

        # Patche _finalize_segment, um einen Dummy-Dateinamen zurückzugeben und den Recorder nach 3 Iterationen zu stoppen.
        original_finalize = recorder._finalize_segment

        def finalize_side_effect(result, temp_output_file, start_timestamp):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                recorder.running = False
            return f"dummy_file_{call_count}.mp3"

        recorder._finalize_segment = finalize_side_effect

        dummy_process = MagicMock()
        dummy_process.wait = MagicMock()
        dummy_process.kill = MagicMock()

        def popen_side_effect(*args, **kwargs):
            return dummy_process

        mock_popen.side_effect = popen_side_effect

        recorder.running = True
        recorder.record_stream()

        self.assertEqual(call_count, 3, "Recorder sollte genau 3 Iterationen ausgeführt haben.")
        self.assertFalse(recorder.running, "Recorder sollte nach den Iterationen gestoppt sein.")

    @patch('audio_miner.main.subprocess.Popen')
    def test_record_segment_timeout(self, mock_popen):
        # Hier wird run_once=True gesetzt, um nach einem Timeout None zurückzugeben.
        recorder = RadioRecorder(
            self.stream_url,
            self.sender,
            segment_time=self.segment_time,
            base_dir=self.base_dir,
            verbose=False,
            run_once=True,
            use_monitor=False
        )
        # Um den Aufruf von _finalize_segment zu verhindern, patchen wir ihn (obwohl er im normalen Fall nicht erreicht wird).
        recorder._finalize_segment = MagicMock(return_value=None)

        # Simuliere einen Prozess, dessen wait() ein Timeout auslöst.
        dummy_process = MagicMock()
        dummy_process.wait.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)
        dummy_process.kill = MagicMock()
        mock_popen.return_value = dummy_process

        with patch.object(recorder.logger, 'error') as mock_logger_error:
            result = recorder._record_segment()
            self.assertIsNone(result)
            # Stelle sicher, dass ein Fehler geloggt wird. Die Parameter können variieren, weswegen wir hier
            # nur prüfen, dass logger.error mindestens einmal aufgerufen wurde.
            self.assertTrue(mock_logger_error.called)

if __name__ == '__main__':
    unittest.main()