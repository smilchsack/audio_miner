import subprocess
import whisper
import os
import time
import threading
import logging
import queue
import socket
import contextlib
from datetime import datetime
from enum import Enum
import colorama
import shutil
from .version import __version__
colorama.init()

class ColoredFormatter(logging.Formatter):
    COLOR_CODES = {
        'DEBUG': "\033[94m",   # Blau
        'INFO': "\033[92m",    # Grün
        'WARNING': "\033[93m", # Gelb
        'ERROR': "\033[91m",   # Rot
        'CRITICAL': "\033[95m" # Magenta
    }
    RESET_CODE = "\033[0m"
    
    def format(self, record):
        message = super().format(record)
        color = self.COLOR_CODES.get(record.levelname, self.RESET_CODE)
        return f"{color}{message}{self.RESET_CODE}"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class WhisperModel(Enum):
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    TURBO = "turbo"

class ProcessResult:
    def __init__(self, returncode):
        self.returncode = returncode

class FileMonitor(threading.Thread):
    def __init__(self, file_path, callback, interval=10, check_duration=5, run_once=False):
        super().__init__(daemon=True)
        self.file_path = file_path
        self.callback = callback
        self.interval = interval
        self.check_duration = check_duration
        self.running = True
        self.last_size = 0
        self.run_once = run_once

    def run(self):
        idle_seconds = 0
        while self.running:
            if not os.path.exists(self.file_path):
                time.sleep(self.interval)
                continue

            current_size = os.path.getsize(self.file_path)
            if current_size > self.last_size:
                self.last_size = current_size
                idle_seconds = 0
            else:
                idle_seconds += self.interval
                if idle_seconds >= self.check_duration:
                    self.callback()
                    idle_seconds = 0
                    if self.run_once:
                        self.running = False
            time.sleep(self.interval)

    def stop(self):
        self.running = False

class RadioRecorder:
    five_percent = 5

    def __init__(self, stream_url, sender, segment_time=60, base_dir=None, poll_interval=5, whisper_model=WhisperModel.TURBO, quality="64k", record_only=False, transcribe_only=False, start_time_str=None, end_time_str=None, verbose=False, ffmpeg_path=None, run_once=False, use_monitor=True):
        if base_dir is None:
            base_dir = os.getcwd()
        
        sender_dir = os.path.join(base_dir, sender)
        self.audio_dir = os.path.join(sender_dir, "audio")
        self.transcription_dir = os.path.join(sender_dir, "transkriptionen")
        
        self.stream_url = stream_url
        self.sender = sender
        self.segment_time = segment_time
        self.poll_interval = poll_interval
        self.whisper_model = whisper_model
        self.quality = quality
        self.record_only = record_only
        self.transcribe_only = transcribe_only
        self.verbose = verbose
        self.running = True
        self.segment_queue = queue.Queue()
        self.queued_files = set()
        self.ffmpeg_path = ffmpeg_path or shutil.which("ffmpeg")
        self.run_once = run_once
        self.monitor = None
        self.use_monitor = use_monitor

        self.start_time = None
        if start_time_str and transcribe_only:
            try:
                self.start_time = datetime.strptime(start_time_str, "%Y%m%d_%H%M%S")
            except ValueError:
                self.logger.error(f"Ungültiges Datumsformat für start_time: {start_time_str}. Erwartet YYYYMMDD_HHMMSS.")

        self.end_time = None
        if end_time_str and transcribe_only:
            try:
                self.end_time = datetime.strptime(end_time_str, "%Y%m%d_%H%M%S")
            except ValueError:
                self.logger.error(f"Ungültiges Datumsformat für end_time: {end_time_str}. Erwartet YYYYMMDD_HHMMSS.")

        if not self.ffmpeg_path:
            self.ffmpeg_path = "ffmpeg"

        if self.record_only and self.transcribe_only:
            raise ValueError("Fehler: record-only und transcribe-only können nicht gleichzeitig True sein.")

        os.makedirs(self.audio_dir, exist_ok=True)
        os.makedirs(self.transcription_dir, exist_ok=True)
        
        self.logger = logging.getLogger(f"RadioRecorder:{self.sender}")
        handler = logging.StreamHandler()
        formatter_str = '%(asctime)s - %(levelname)s - %(message)s' if self.verbose else '%(message)s'
        formatter = ColoredFormatter(formatter_str)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.propagate = False
        self.logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)

        self.logger.debug(f"RadioRecorder für {self.sender} gestartet. Logging-Level: {self.logger.level}")

    def record_stream(self):
        while self.running:
            if not self.transcribe_only:
                final_output_file = self._record_segment()
                if not final_output_file:
                    continue

            if self.record_only:
                continue

            if self.transcribe_only:
                end_time = datetime.now()
                self.check_and_queue_old_files(end_time)
                break

            self._queue_segment_for_transcription(final_output_file)

            time.sleep(1)
            end_time = datetime.now()
            self.check_and_queue_old_files(end_time)

    def _get_timeout(self, margin_percent=5, reconnect_delay_max=15, max_retries=8):
        """
        Berechnet einen Timeout-Wert auf Basis von segment_time,
        z.B. +5% Sicherheitsaufschlag.
        """
        return int((self.segment_time + reconnect_delay_max * max_retries) + (self.segment_time * margin_percent / 100))

    def _record_segment(self, reconnect=1, reconnect_on_network_error=1, reconnect_on_http_error=1, reconnect_streamed=1, reconnect_delay_max=15):
        max_retries = 8
        for attempt in range(max_retries):
            try:
                final_output_file = self._attempt_record_segment(reconnect, reconnect_on_network_error, reconnect_on_http_error, reconnect_streamed, reconnect_delay_max, attempt, max_retries)
                if final_output_file:
                    return final_output_file
            except subprocess.TimeoutExpired as e:
                timeout_sec = self._get_timeout(5, reconnect_delay_max, max_retries)
                temp_output_file = os.path.join(self.audio_dir, f"{self.sender}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3")
                self.logger.error("FFmpeg-Aufruf überschritt Timeout von %s Sekunden für Segment: %s.", timeout_sec, temp_output_file)
                if self.run_once:
                    return None
            except Exception as e:
                self.logger.error(f"Fehler in _record_segment: {e}", exc_info=True)
                if self.run_once:
                    return None

        self.logger.error("Maximale Anzahl von Versuchen erreicht, Segment konnte nicht aufgenommen werden.")
        return None

    def _on_tempfile_inactive(self):
        self.logger.warning("temp_output_file wächst nicht mehr – beende ffmpeg.")
        if self.ffmpeg_process:
            self.ffmpeg_process.kill()


    def _attempt_record_segment(self, reconnect, reconnect_on_network_error, reconnect_on_http_error, reconnect_streamed, reconnect_delay_max, attempt, max_retries):
        start_time = datetime.now()
        start_timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        temp_output_file = os.path.join(self.audio_dir, f"{self.sender}_{start_timestamp}.mp3")

        if self.use_monitor:
            # FileMonitor starten:
            monitor = FileMonitor(
                file_path=temp_output_file,
                callback=self._on_tempfile_inactive,
                interval=5,
                check_duration=120,
                run_once=True
            )
            self.monitor = monitor
            self.monitor.start()

        timeout_sec = self._get_timeout(RadioRecorder.five_percent, reconnect_delay_max, max_retries)
        command = [
            self.ffmpeg_path, '-y',
            '-reconnect', str(reconnect),                                       # Aktiviert automatisches Wiederverbinden
            '-reconnect_on_network_error', str(reconnect_on_network_error),     # Versucht, bei Netzwerkfehlern erneut zu verbinden
            '-reconnect_on_http_error', str(reconnect_on_http_error),           # Reconnect bei HTTP-Fehlern (z.B. 4xx oder 5xx)
            '-reconnect_streamed', str(reconnect_streamed),                     # Erzwingt Wiederverbindung bei bereits gestreamten Inhalten
            '-reconnect_delay_max', str(reconnect_delay_max),                   # Legt fest, wie lange (in Sekunden) maximal zwischen den Verbindungsversuchen gewartet wird
            '-i', self.stream_url,
            '-t', str(self.segment_time),
            '-c:a', 'libmp3lame',
            '-b:a', self.quality,
            temp_output_file
        ]
        self.logger.info("Starte Aufnahme für Segment: %s (Versuch %d/%d)", temp_output_file, attempt+1, max_retries)
        
        self.ffmpeg_process = subprocess.Popen(
            command,
            stdout=None if self.verbose else subprocess.DEVNULL,
            stderr=None if self.verbose else subprocess.DEVNULL
        )
        try:
            self.ffmpeg_process.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            self.ffmpeg_process.kill()
            
        # Monitor stoppen und auf Thread-Ende warten
        if self.monitor:
            self.monitor.stop()
            self.monitor.join()

        return self._finalize_segment(0, temp_output_file, start_timestamp)

    def _finalize_segment(self, result, temp_output_file, start_timestamp):
        if result == 0:
            end_time = datetime.now()
            end_timestamp = end_time.strftime("%Y%m%d_%H%M%S")
            final_output_file = os.path.join(self.audio_dir, f"{self.sender}_{start_timestamp}_{end_timestamp}.mp3")
            os.rename(temp_output_file, final_output_file)
            return final_output_file
        else:
            self.logger.warning("ffmpeg fehlgeschlagen für Segment: %s, versuche erneut...", temp_output_file)
            return None

    def _queue_segment_for_transcription(self, final_output_file):
        if final_output_file and final_output_file not in self.queued_files:
            self.segment_queue.put(final_output_file)
            self.queued_files.add(final_output_file)
            self.logger.info("Segment fertiggestellt und zur Transkription bereit: %s", final_output_file)
        else:
            self.logger.info("Segment bereits in der Warteschlange: %s", final_output_file)

    def check_and_queue_old_files(self, reference_time):
        for file in os.listdir(self.audio_dir):
            if file.endswith(".mp3"):
                audio_file = os.path.join(self.audio_dir, file)
                if os.path.getsize(audio_file) == 0:
                    self.logger.info("Leere Datei gefunden und gelöscht: %s", audio_file)
                    os.remove(audio_file)
                    continue
                
                # Versuche, den Start-Timestamp aus dem Dateinamen zu extrahieren
                # Format: SENDER_YYYYMMDD_HHMMSS_YYYYMMDD_HHMMSS.mp3 oder SENDER_YYYYMMDD_HHMMSS.mp3
                parts = file.replace(".mp3", "").split('_')
                file_start_timestamp_str = None
                if len(parts) >= 2: # Mindestens SENDER_TIMESTAMP
                    # Der erste Timestamp ist der Start-Timestamp
                    potential_timestamp_str = parts[1]
                    if len(parts) > 2 and len(parts[2]) == 6 : # Prüfen ob es ein Zeitstempel ist HHMMSS
                         potential_timestamp_str = f"{parts[1]}_{parts[2]}" # Format YYYYMMDD_HHMMSS
                    elif len(parts) > 3 and len(parts[1]) == 8 and len(parts[2]) == 6: # Format SENDER_YYYYMMDD_HHMMSS_...
                        potential_timestamp_str = f"{parts[1]}_{parts[2]}"

                # Prüfen, ob der extrahierte String ein gültiger Timestamp ist
                file_start_time = None
                if potential_timestamp_str:
                    try:
                        file_start_time = datetime.strptime(potential_timestamp_str, "%Y%m%d_%H%M%S")
                    except ValueError:
                        self.logger.debug(f"Konnte keinen gültigen Start-Timestamp aus Dateinamen extrahieren: {file}")
                        # Fallback auf Modifikationszeit, wenn kein Timestamp im Namen ist oder nicht geparst werden kann
                        file_start_time = datetime.fromtimestamp(os.path.getmtime(audio_file))
                else:
                     # Fallback auf Modifikationszeit, wenn kein Timestamp im Namen ist
                    file_start_time = datetime.fromtimestamp(os.path.getmtime(audio_file))


                transcription_file = os.path.join(self.transcription_dir, file.replace(".mp3", ".txt"))
                
                should_queue = False
                if self.transcribe_only:
                    # Prüfen, ob die Datei bereits transkribiert wurde
                    if os.path.exists(transcription_file):
                        continue

                    # Zeitliche Bedingungen prüfen
                    within_start_time = True
                    if self.start_time:
                        within_start_time = file_start_time >= self.start_time
                    
                    within_end_time = True
                    if self.end_time:
                        within_end_time = file_start_time < self.end_time
                    
                    if within_start_time and within_end_time:
                        should_queue = True
                elif file_start_time < reference_time and not os.path.exists(transcription_file): # Originalbedingung für nicht transcribe_only
                    should_queue = True


                if should_queue:
                    if audio_file not in self.queued_files:
                        self.logger.info("Requeue Datei basierend auf Zeitkriterium: %s (Datei-Startzeit: %s)", audio_file, file_start_time.strftime("%Y%m%d_%H%M%S"))
                        self.segment_queue.put(audio_file)
                        self.queued_files.add(audio_file)

    def transcribe_audio(self, audio_file):
        self.logger.debug("Lade Whisper Modell: %s", self.whisper_model)
        model_name = self.whisper_model.value
        if self.verbose:
            model = whisper.load_model(model_name)
            self.logger.info("Starte Transkription: %s", audio_file)
            result = model.transcribe(audio_file)
        else:
            with open(os.devnull, 'w') as fnull, contextlib.redirect_stdout(fnull), contextlib.redirect_stderr(fnull):
                model = whisper.load_model(model_name)
                result = model.transcribe(audio_file)
        
        segments = result.get("segments", [])
        transcription = "\n".join(segment["text"].strip() for segment in segments)
        
        return transcription

    def transcription_worker(self, run_once=False):
        while self.running or run_once:
            try:
                audio_file = self.segment_queue.get(timeout=self.poll_interval)
                self.logger.info("Empfange Nachricht zur Transkription: %s", audio_file)
                transcription = self.transcribe_audio(audio_file)
                base_name = os.path.basename(audio_file).replace(".mp3", ".txt")
                transcription_file = os.path.join(self.transcription_dir, base_name)
                with open(transcription_file, "w", encoding="utf-8") as f:
                    f.write(transcription)
                self.logger.info("Transkription abgeschlossen: %s", transcription_file)
                self.segment_queue.task_done()
                self.queued_files.remove(audio_file)  # Remove from set when done
            except queue.Empty:
                if run_once or self.transcribe_only:
                    break
                continue
            if run_once:
                break

    def run(self):
        art = f"""
                 _ _                    _                 
  __ _ _   _  __| (_) ___     _ __ ___ (_)_ __   ___ _ __ 
 / _` | | | |/ _` | |/ _ \   | '_ ` _ \| | '_ \ / _ \ '__|
| (_| | |_| | (_| | | (_) |  | | | | | | | | | |  __/ |   
 \__,_|\__,_|\__,_|_|\___/___|_| |_| |_|_|_| |_|\___|_|   
                        |_____|                            Version: {__version__} 
        """

        print(art)

        if self.record_only:
            self.logger.info("Starte Thread für Aufzeichnungen...")
        
        self.record_thread = threading.Thread(target=self.record_stream, daemon=True)
        self.record_thread.start()

        if self.transcribe_only:
            self.logger.info("Starte Thread für Transkriptionen...")
        
        self.transcription_thread = threading.Thread(target=self.transcription_worker, daemon=True)
        self.transcription_thread.start()
       
        self.logger.info("RadioRecorder läuft.")
        try:
            while self.running:
                time.sleep(1)
                if not self.record_thread.is_alive() and not self.transcription_thread.is_alive():
                    if self.monitor:
                        self.monitor.stop()
                        self.monitor.join()
                    self.logger.info("Verarbeitung beendet.")
                    self.running = False
        except KeyboardInterrupt:
            self.logger.info("Interrupt erhalten, beende Anwendung...")
            self.stop()

    def stop(self):
        self.running = False
        self.logger.info("Beende Threads, warte auf deren Abschluss...")
        if hasattr(self, 'record_thread') and self.record_thread.is_alive():
            self.record_thread.join()
        if hasattr(self, 'transcription_thread') and self.transcription_thread.is_alive():
            self.transcription_thread.join()
        self.logger.info("Anwendung beendet.")