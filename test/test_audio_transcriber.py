import unittest
from unittest.mock import patch, MagicMock, mock_open
import torch

from audio_miner.audio_transcriber import AudioTranscriber, save_results_to_file

class TestAudioTranscriber(unittest.TestCase):

    def setUp(self):
        self.test_token = "test_hf_token"

        self.patcher_pipeline = patch('pyannote.audio.Pipeline.from_pretrained')
        self.patcher_whisper_load = patch('whisper.load_model')
        self.patcher_torchaudio_load = patch('torchaudio.load')
        self.patcher_torchaudio_save = patch('torchaudio.save')
        self.patcher_os_remove = patch('os.remove')
        self.patcher_torch_cuda_is_available = patch('torch.cuda.is_available')
        self.patcher_torch_mps_is_available = patch('torch.backends.mps.is_available')


        self.mock_pipeline_from_pretrained = self.patcher_pipeline.start()
        self.mock_whisper_load_model = self.patcher_whisper_load.start()
        self.mock_torchaudio_load = self.patcher_torchaudio_load.start()
        self.mock_torchaudio_save = self.patcher_torchaudio_save.start()
        self.mock_os_remove = self.patcher_os_remove.start()
        self.mock_torch_cuda_is_available = self.patcher_torch_cuda_is_available.start()
        self.mock_torch_mps_is_available = self.patcher_torch_mps_is_available.start()

        self.mock_pipeline_instance = MagicMock()
        self.mock_pipeline_from_pretrained.return_value = self.mock_pipeline_instance

        self.mock_whisper_model_instance = MagicMock()
        self.mock_whisper_load_model.return_value = self.mock_whisper_model_instance

        self.dummy_waveform = torch.randn(1, 16000)
        self.dummy_sample_rate = 16000
        self.mock_torchaudio_load.return_value = (self.dummy_waveform, self.dummy_sample_rate)

        self.mock_torch_cuda_is_available.return_value = False
        self.mock_torch_mps_is_available.return_value = False


    def tearDown(self):
        self.patcher_pipeline.stop()
        self.patcher_whisper_load.stop()
        self.patcher_torchaudio_load.stop()
        self.patcher_torchaudio_save.stop()
        self.patcher_os_remove.stop()
        self.patcher_torch_cuda_is_available.stop()
        self.patcher_torch_mps_is_available.stop()

    def test_initialization_cpu(self):
        transcriber = AudioTranscriber(whisper_model_size="tiny", token=self.test_token)
        self.assertEqual(transcriber.device, "cpu")
        self.assertEqual(transcriber.whisper_device, "cpu")
        self.mock_pipeline_from_pretrained.assert_called_once_with(
            "pyannote/speaker-diarization-3.1", use_auth_token=self.test_token
        )
        self.mock_pipeline_instance.to.assert_called_once_with(torch.device("cpu"))
        self.mock_whisper_load_model.assert_called_once_with("tiny", device="cpu")

    def test_initialization_cuda(self):
        self.mock_torch_cuda_is_available.return_value = True
        transcriber = AudioTranscriber(whisper_model_size="small", token=self.test_token)
        self.assertEqual(transcriber.device, "cuda")
        self.assertEqual(transcriber.whisper_device, "cuda")
        self.mock_pipeline_instance.to.assert_called_once_with(torch.device("cuda"))
        self.mock_whisper_load_model.assert_called_once_with("small", device="cuda")

    def test_initialization_mps(self):
        self.mock_torch_cuda_is_available.return_value = False
        self.mock_torch_mps_is_available.return_value = True
        transcriber = AudioTranscriber(whisper_model_size="base", token=self.test_token)
        self.assertEqual(transcriber.device, "cpu")
        self.assertEqual(transcriber.whisper_device, "cpu")
        self.mock_pipeline_instance.to.assert_called_once_with(torch.device("cpu"))
        self.mock_whisper_load_model.assert_called_once_with("base", device="cpu")


    def test_transcribe_audio_successful(self):
        transcriber = AudioTranscriber(token=self.test_token)

        mock_turn = MagicMock()
        mock_turn.start = 0.5
        mock_turn.end = 2.5
        diarization_result_mock = MagicMock()
        diarization_result_mock.itertracks.return_value = [(mock_turn, None, "SPEAKER_01")]
        self.mock_pipeline_instance.return_value = diarization_result_mock

        self.mock_whisper_model_instance.transcribe.return_value = {"text": "Hallo Welt"}

        audio_path = "dummy/audio.mp3"
        results = transcriber.transcribe_audio(audio_path)

        self.mock_torchaudio_load.assert_called_once_with(audio_path)
        self.mock_pipeline_instance.assert_called_once_with({
            "waveform": self.dummy_waveform.to(transcriber.device),
            "sample_rate": self.dummy_sample_rate
        })
        self.mock_torchaudio_save.assert_called_once()
        self.mock_whisper_model_instance.transcribe.assert_called_once()
        self.mock_os_remove.assert_called_once()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["speaker"], "SPEAKER_01")
        self.assertEqual(results[0]["start"], 0.5)
        self.assertEqual(results[0]["end"], 2.5)
        self.assertEqual(results[0]["text"], "Hallo Welt")

    def test_transcribe_audio_empty_segment(self):
        transcriber = AudioTranscriber(token=self.test_token)

        mock_turn = MagicMock()
        mock_turn.start = 0.5
        mock_turn.end = 2.5
        diarization_result_mock = MagicMock()
        diarization_result_mock.itertracks.return_value = [(mock_turn, None, "SPEAKER_01")]
        self.mock_pipeline_instance.return_value = diarization_result_mock

        with patch.object(transcriber, '_extract_segment', return_value=torch.empty(1, 0)) as mock_extract:
            audio_path = "dummy/audio.mp3"
            results = transcriber.transcribe_audio(audio_path)

            mock_extract.assert_called_once()
            self.mock_torchaudio_save.assert_not_called()
            self.mock_whisper_model_instance.transcribe.assert_not_called()
            self.mock_os_remove.assert_not_called()
            self.assertEqual(len(results), 0)


    def test_transcribe_audio_transcription_error(self):
        transcriber = AudioTranscriber(token=self.test_token)
        mock_turn = MagicMock()
        mock_turn.start = 0.5
        mock_turn.end = 2.5
        diarization_result_mock = MagicMock()
        diarization_result_mock.itertracks.return_value = [(mock_turn, None, "SPEAKER_01")]
        self.mock_pipeline_instance.return_value = diarization_result_mock

        self.mock_whisper_model_instance.transcribe.side_effect = Exception("Transkriptionsfehler")

        audio_path = "dummy/audio.mp3"
        results = transcriber.transcribe_audio(audio_path)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["text"], "[Transkriptionsfehler]")
        self.mock_os_remove.assert_called_once()

    def test_extract_segment(self):
        transcriber = AudioTranscriber(token=self.test_token)
        waveform = torch.arange(0, 100).float().unsqueeze(0)
        sr = 10
        start_time = 2.0
        end_time = 5.0

        segment = transcriber._extract_segment(waveform, sr, start_time, end_time)

        expected_start_frame = int(start_time * sr)
        expected_end_frame = int(end_time * sr)
        expected_segment = waveform[:, expected_start_frame:expected_end_frame]

        self.assertTrue(torch.equal(segment, expected_segment))
        self.assertEqual(segment.shape[1], expected_end_frame - expected_start_frame)

class TestSaveResultsToFile(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open)
    def test_save_results(self, mock_file_open):
        results = [
            {"speaker": "SPK_01", "start": 0.123, "end": 1.456, "text": "Hallo"},
            {"speaker": "SPK_02", "start": 2.0, "end": 3.5, "text": "Welt"},
        ]
        output_filepath = "test_output.txt"
        save_results_to_file(results, output_filepath)

        mock_file_open.assert_called_once_with(output_filepath, "w", encoding="utf-8")
        handle = mock_file_open()
        expected_calls = [
            unittest.mock.call("[SPK_01 | 0.12-1.46] Hallo\n"),
            unittest.mock.call("[SPK_02 | 2.00-3.50] Welt\n"),
        ]
        handle.write.assert_has_calls(expected_calls)

if __name__ == '__main__':
    unittest.main()