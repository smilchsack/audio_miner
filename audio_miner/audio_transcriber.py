import contextlib
import torch
import whisper
import torchaudio
import os
import tempfile
import logging
from pyannote.audio import Pipeline

logging.getLogger("pyannote").setLevel(logging.WARNING)
logging.getLogger("speechbrain").setLevel(logging.WARNING)
logging.getLogger("whisper").setLevel(logging.WARNING)

class AudioTranscriber:
    """
    Eine Klasse zur Transkription von Audiodateien mit Sprecherdiarisierung.

    Verwendet Whisper für die Transkription und PyAnnote für die Sprecherdiarisierung.
    """
    def __init__(self, whisper_model_size="small", token=None, verbose=False):
        """
        Initialisiert den AudioTranscriber.

        Args:
            whisper_model_size (str, optional): Die Größe des zu verwendenden Whisper-Modells.
                                                Standardmäßig "small".
            token (str, optional): Authentifizierungstoken für das PyAnnote-Modell.
                                   Erforderlich für den Download des Modells.
            verbose (bool, optional): Aktiviert ausführliche Ausgaben. Standardmäßig False.                       
        
        Raises:
            ValueError: Wenn kein Token für das PyAnnote-Modell bereitgestellt wird.
        """
        self.verbose = verbose
        if torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"
        self._verbose_print(f"AudioTranscriber verwendet Gerät: {self.device}")
        self.token = token

        self.whisper_device = self.device
        if self.device == "mps":
            self._verbose_print("MPS erkannt. Whisper wird aufgrund möglicher Kompatibilitätsprobleme auf der CPU ausgeführt.")
            self.whisper_device = "cpu"
        else:
            self._verbose_print(f"Whisper wird auf Gerät ausgeführt: {self.whisper_device}")

        if self.token is not None:
            with open(os.devnull, 'w') as fnull:
                with contextlib.redirect_stdout(fnull), contextlib.redirect_stderr(fnull):
                    self.diarization_pipeline = Pipeline.from_pretrained(
                                "pyannote/speaker-diarization-3.1",
                                use_auth_token=self.token)
                    self.diarization_pipeline.to(torch.device(self.device))
                    
        with open(os.devnull, 'w') as fnull:
            with contextlib.redirect_stdout(fnull), contextlib.redirect_stderr(fnull):
                self.whisper_model = whisper.load_model(whisper_model_size, device=self.whisper_device)
        self.temp_dir = tempfile.gettempdir()

    def _verbose_print(self, *args, **kwargs):
        """Gibt nur aus, wenn self.verbose True ist."""
        if self.verbose:
            print(*args, **kwargs)

    def _extract_segment(self, waveform, sr, start, end):
        """
        Extrahiert ein Audiosegment aus einer Wellenform.

        Args:
            waveform (torch.Tensor): Die Audio-Wellenform.
            sr (int): Die Abtastrate der Wellenform.
            start (float): Die Startzeit des Segments in Sekunden.
            end (float): Die Endzeit des Segments in Sekunden.

        Returns:
            torch.Tensor: Das extrahierte Audiosegment.
        """
        start_frame = int(start * sr)
        end_frame   = int(end   * sr)
        return waveform[:, start_frame:end_frame]
    
    def transcribe_audio(self, audio_path):
        """
        Transkribiert eine Audiodatei und führt eine Sprecherdiarisierung durch.

        Args:
            audio_path (str): Der Pfad zur Audiodatei.

        Returns:
            list: Eine Liste von Dictionaries, die die Transkriptionsergebnisse
                  für jedes Segment enthalten, einschließlich Sprecher, Startzeit,
                  Endzeit und transkribiertem Text.
        """
        if self.token is None:
            return self._transcribe_audio_basic(audio_path)

        return self._transcribe_audio_diarization(audio_path)
    

    def _transcribe_audio_diarization(self, audio_path):
        waveform, sample_rate = torchaudio.load(audio_path)
        waveform = waveform.to(self.device)

        diarization_result = self.diarization_pipeline({"waveform": waveform, "sample_rate": sample_rate})

        results = []

        for turn, _, speaker in diarization_result.itertracks(yield_label=True):
            segment = self._extract_segment(waveform, sample_rate, turn.start, turn.end)
            
            tmp_filename = f"segment_{speaker}_{turn.start:.2f}_{turn.end:.2f}.mp3"
            tmp_path = os.path.join(self.temp_dir, tmp_filename)
            
            if segment.numel() == 0:
                print(f"Skipping empty segment for speaker {speaker} from {turn.start:.2f} to {turn.end:.2f}")
                continue
            
            with open(os.devnull, 'w') as fnull:
                with contextlib.redirect_stdout(fnull), contextlib.redirect_stderr(fnull):
                    torchaudio.save(tmp_path, segment.cpu(), sample_rate)
            
            try:
                with open(os.devnull, 'w') as fnull:
                    with contextlib.redirect_stdout(fnull), contextlib.redirect_stderr(fnull):
                        res = self.whisper_model.transcribe(tmp_path, task="transcribe", beam_size=5)
                        text = res["text"].strip()
            except Exception as e:
                print(f"Error transcribing segment {tmp_path}: {e}")
                text = "[Transkriptionsfehler]"
            
            results.append({
                "speaker": speaker,
                "start": turn.start,
                "end": turn.end,
                "text": text
            })
            
            try:
                os.remove(tmp_path)
            except OSError as e:
                print(f"Error deleting temporary file {tmp_path}: {e}")


        return results

    def _transcribe_audio_basic(self, audio_path):
        with open(os.devnull, 'w') as fnull:
            with contextlib.redirect_stdout(fnull), contextlib.redirect_stderr(fnull):
                result = self.whisper_model.transcribe(audio_path, task="transcribe", beam_size=5)
        
        segments = result.get("segments", [])
        transcription = "\n".join(segment["text"].strip() for segment in segments)
        return transcription
           

def save_results_to_file(results, output_filepath):
    """
    Speichert die Transkriptionsergebnisse in einer Textdatei.

    Args:
        results (list): Eine Liste von Dictionaries mit den Transkriptionsergebnissen.
        output_filepath (str): Der Pfad zur Ausgabedatei.
    """
    with open(output_filepath, "w", encoding="utf-8") as f:
        for r in results:
            f.write(f"[{r['speaker']} | {r['start']:.2f}-{r['end']:.2f}] {r['text']}\n")
    print(f"Ergebnisse gespeichert in: {output_filepath}")