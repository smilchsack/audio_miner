import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stream-url', required=False,
                    help='URL des Radiosenders (optional bei --transcribe-only)')
    parser.add_argument('--sender', required=True,
                        help='Name des Radiosenders')
    parser.add_argument('--segment-time', type=int, default=3600,
                        help='Länge eines Segments in Sekunden')
    parser.add_argument('--base-dir', default=None,
                        help='Zielverzeichnis für Aufzeichnungen')
    parser.add_argument('--poll-interval', type=int, default=5,
                        help='Intervall zwischen den Aufnahmen (Sekunden)')
    parser.add_argument('--whisper-model', default='TURBO',
                        help='Whisper Modell (z.B. TURBO, BASE, etc.)')
    parser.add_argument('--quality', default='64k',
                        help='Audio-Qualität für die Aufnahme')
    parser.add_argument('--record-only', action='store_true',
                        help='Nur aufzeichnen, ohne Transkription.')
    parser.add_argument('--transcribe-only', action='store_true',
                        help='Es wird nicht aufgezeichnet sondern nur transkribiert.')
    parser.add_argument('--start-time', type=str, default=None,
                        help='Startzeitpunkt für die Transkription (Format: YYYYMMDD_HHMMSS), nur relevant bei --transcribe-only.')
    parser.add_argument('--end-time', type=str, default=None,
                        help='Endzeitpunkt für die Transkription (Format: YYYYMMDD_HHMMSS), nur relevant bei --transcribe-only.')
    parser.add_argument('--token', type=str, default=None,
                        help='Huggingface Token für PyAnnote, wenn benötigt.')
    parser.add_argument('--ffmpeg-path', default=None,
                        help='Pafd zur ffmpeg-Binary. Ansonsnten wird ffmpeg im PATH gesucht.')
    parser.add_argument('--verbose', action='store_true',
                        help='Ausführliche Ausgabe')
    args = parser.parse_args()

    if not args.transcribe_only and not args.stream_url:
        parser.error("--stream-url ist erforderlich, wenn nicht --transcribe-only genutzt wird.")

    from .main import RadioRecorder, WhisperModel

    whisper_model = WhisperModel[args.whisper_model.upper()]

    recorder = RadioRecorder(
        stream_url=args.stream_url,
        sender=args.sender,
        segment_time=args.segment_time,
        base_dir=args.base_dir,
        poll_interval=args.poll_interval,
        whisper_model=whisper_model,
        quality=args.quality,
        record_only=args.record_only,
        transcribe_only=args.transcribe_only,
        start_time_str=args.start_time if args.transcribe_only else None,
        end_time_str=args.end_time if args.transcribe_only else None,
        token=args.token,
        ffmpeg_path=args.ffmpeg_path,
        verbose=args.verbose,
    )
    recorder.run()

if __name__ == '__main__':
    main()