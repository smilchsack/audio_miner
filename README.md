# README for audio_miner

![Test Status](https://github.com/smilchsack/audio_miner/actions/workflows/ci.yml/badge.svg)

## audio_miner

audio_miner is a Python application that records audio streams and transcribes them using the Whisper model. It allows users to capture radio broadcasts and convert them into text files for easy access and analysis.

### Features

- Record audio streams in specified segments.
- Transcribe recorded audio using the Whisper model.
- Organize recordings and transcriptions in a structured directory.

### Installation

To install audio_miner, you can use pip. Clone the repository and run the following command:

```bash
pip install .
```

Additionally, you need to have `ffmpeg` installed on your system. You can install it using the following command:

```bash
sudo apt-get install ffmpeg
```

### Usage

After installation, you can run audio_miner from the command line. Use the following command format:

```bash
audio_miner --stream-url <STREAM_URL> --sender <SENDER_NAME> [--segment-time <SEGMENT_TIME>] [--base-dir <BASE_DIR>] [--poll-interval <POLL_INTERVAL>] [--whisper-model <WHISPER_MODEL>] [--quality <QUALITY>] [--record-only] [--transcribe-only] [--verbose] [--ffmpeg-path <FFMPEG_PATH>]
```

#### Parameters

- `--stream-url`: The URL of the audio stream to record (required).
- `--sender`: The name of the radio station (required).
- `--segment-time`: Length of each audio segment in seconds (default: 3600).
- `--base-dir`: Base directory for storing audio and transcription files (default: current directory).
- `--poll-interval`: Interval in seconds between recordings (default: 5).
- `--whisper-model`: The Whisper model to use for transcription (default: TURBO; options include TINY, BASE, SMALL, MEDIUM, LARGE, TURBO).
- `--quality`: Audio bitrate for re-encoding (default: 64k).
- `--start-time`: Start time for transcription in YYYYMMDD_HHMMSS format. Only relevant when using `--transcribe-only`.
- `--end-time`: End time for transcription in YYYYMMDD_HHMMSS format. Only relevant when using `--transcribe-only`.
- `--record-only`: Record audio without transcribing.
- `--transcribe-only`: Transcribe existing audio files without recording.
- `--verbose`: Enable detailed output.
- `--ffmpeg-path`: Path to the `ffmpeg` executable. This is only necessary if `ffmpeg` cannot be started directly from the terminal.

### Example

To record from a stream and transcribe it, you can use:

```bash
audio_miner --stream-url 'https://liveradio.swr.de/sw282p3/swr1rp/' --sender 'swr1' --segment-time 3600 --base-dir './output' --poll-interval 5 --whisper-model TURBO --quality '64k'
```

### Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any suggestions or improvements.

### License

This project is licensed under the MIT License. See the LICENSE file for more details.