# Python Audio Mastering Tool

A robust, command-line Python script to apply a full mastering chain to your audio files. This tool allows you to process large DJ mixes or other audio tracks efficiently, enhancing their sound with professional-grade equalization, compression, and LUFS loudness normalization.

## Features

-   **Robust Chunk-Based Processing:** Handles audio files of any size without running out of memory by processing them in manageable 30-second chunks.
-   **LUFS Loudness Normalization:** Target professional, streaming-ready loudness levels (e.g., -14 LUFS for Spotify) for consistent volume and punch without digital clipping.
-   **Multi-band Equalization:** Manually adjust bass, mids, presence, and treble frequencies to shape your sound.
-   **Genre Presets:** Instantly apply EQ curves tailored for genres like Techno, Pop, Dubstep, and Rock.
-   **Dynamic Range Compression:** Glue your mix together, control dynamics, and increase perceived loudness.
-   **Safe Final Limiting:** A soft limiter at the end of the chain catches any stray peaks, guaranteeing a clean, artifact-free master.

## Requirements

Before running the script, you need to have Python 3 and the following dependencies installed.

1.  **Python Libraries:** Install them all with one command using pip:
    ```bash
    pip install pydub scipy numpy pyloudnorm tqdm
    ```

2.  **FFmpeg:** `pydub` requires FFmpeg for handling different audio formats like MP3 and WAV.
    -   **On Debian/Ubuntu:**
        ```bash
        sudo apt update && sudo apt install ffmpeg
        ```
    -   **On macOS (using Homebrew):**
        ```bash
        brew install ffmpeg
        ```

## Usage

The script is run from the command line with the input file and output file as the first two arguments, followed by optional flags for the effects you want to apply.

### Basic Syntax

```bash
python audio_mastering_tool.py <input_file> <output_file> [options]

Examples
1. Master for Streaming (Spotify, Apple Music, etc.):
This is the most common use case. It applies the "pop" preset for vocal clarity, adds compression, and targets -14 LUFS.

python audio_mastering_tool.py "song.wav" "song_mastered_streaming.wav" --preset pop --compress --lufs -14

2. Create a Loud Club Master:
This example uses the "techno" preset for a powerful low-end, adds compression, and targets a louder -10 LUFS for club playback.

python audio_mastering_tool.py "dj_mix.wav" "dj_mix_club_master.wav" --preset techno --compress --lufs -10

3. Manually Boost Bass without a Preset:
If you just want to add some warmth and loudness without a full genre EQ, you can use the flags individually.

python audio_mastering_tool.py "track.mp3" "track_mastered.mp3" --bass_boost 2.5 --compress --lufs -13
