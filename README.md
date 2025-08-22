# Python Audio Mastering Tool

A command-line Python script to apply basic mastering effects to audio files. This tool allows you to process your DJ mixes or other audio tracks to enhance their sound with equalization, compression, and normalization, right from the terminal.

## Features

-   **Multi-band Equalization:** Adjust bass, mids, presence, and treble frequencies.
-   **Genre Presets:** Instantly apply EQ curves tailored for genres like Techno, Pop, Dubstep, and Rock.
-   **Dynamic Range Compression:** Glue your mix together and increase perceived loudness.
-   **Normalization:** Bring your track up to a standard commercial loudness without clipping.
-   **Safe Processing:** Uses 32-bit float processing and a soft limiter to prevent digital clipping and artifacts.

## Requirements

Before running the script, you need to have Python 3 and the following dependencies installed.

1.  **Python Libraries:** Install them using pip:
    ```bash
    pip install pydub scipy numpy
    ```

2.  **FFmpeg:** `pydub` requires FFmpeg for handling different audio formats like MP3 and WAV. You can install it on your system using your package manager.
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
1. Using a Genre Preset:
To apply the "techno" preset, which boosts bass/treble and scoops the mids, and then normalize the final output:

python audio_mastering_tool.py "my_mix.wav" "my_mix_techno.wav" --preset techno --normalize --compress

2. Manually Boosting Vocals:
To make the vocals brighter and clearer, you can use the --presence_boost flag. This example applies a 3.5dB boost to the vocal presence range and normalizes the track.

python audio_mastering_tool.py "song.wav" "song_vocals_up.wav" --presence_boost 3.5 --normalize

3. Applying a Gentle Bass Boost and Compression:
A simple mastering chain to add some low-end warmth and glue the track together.

python audio_mastering_tool.py "track.mp3" "track_mastered.mp3" --bass_boost 2.0 --compress --normalize
