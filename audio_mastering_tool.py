# audio_mastering_tool.py (v3)
#
# A command-line Python script to apply mastering effects to an audio file.
# Version 3 adds genre presets and more specific EQ controls for vocals and mids.
#
# Dependencies:
# pip install pydub scipy numpy
#
# Usage:
# python audio_mastering_tool.py <input_file> <output_file> [options]
#
# Example with a preset:
# python audio_mastering_tool.py "mix.wav" "mix_techno.wav" --preset techno --normalize --compress
#
# Example with manual vocal boost:
# python audio_mastering_tool.py "mix.wav" "mix_vocal_boost.wav" --presence_boost 3 --normalize
#

import argparse
import os
import numpy as np
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range
from scipy.signal import butter, sosfilt

# --- PRESET DEFINITIONS ---
# A dictionary holding the EQ settings for different genres.
# Values are in dB (decibels).
EQ_PRESETS = {
    "techno": {
        "bass_boost": 4.0,
        "mid_cut": 3.0,
        "presence_boost": 1.0,
        "treble_boost": 3.0,
        "description": "Boosted sub-bass and highs, scooped mids for a powerful club sound."
    },
    "dubstep": {
        "bass_boost": 5.0,
        "mid_cut": 4.0,
        "presence_boost": 2.0,
        "treble_boost": 3.5,
        "description": "Aggressive low-end and crisp highs, with a significant mid-cut."
    },
    "pop": {
        "bass_boost": 2.0,
        "mid_cut": 0.0,
        "presence_boost": 3.5,
        "treble_boost": 2.5,
        "description": "Focused on vocal clarity with a solid low-end and bright highs."
    },
    "rock": {
        "bass_boost": 1.5,
        "mid_cut": -2.0, # A negative cut is a boost
        "presence_boost": 2.5,
        "treble_boost": 1.0,
        "description": "Warm low-mids for guitars and punchy presence for snare/vocals."
    }
}


def audio_segment_to_float_array(audio_segment):
    """Converts a pydub AudioSegment to a NumPy float array."""
    samples = np.array(audio_segment.get_array_of_samples())
    return samples.astype(np.float32) / (2**(audio_segment.sample_width * 8 - 1))

def float_array_to_audio_segment(float_array, audio_segment_template):
    """Converts a NumPy float array back to a pydub AudioSegment."""
    clipped_array = np.clip(float_array, -1.0, 1.0)
    int_array = (clipped_array * (2**(audio_segment_template.sample_width * 8 - 1))).astype(np.int16)
    return audio_segment_template._spawn(int_array.tobytes())

def apply_shelf_filter(samples, sample_rate, cutoff_hz, gain_db, filter_type, order=5):
    """Applies a shelf filter (bass/treble) to a NumPy float array."""
    if gain_db == 0:
        return samples
    nyquist = 0.5 * sample_rate
    normal_cutoff = cutoff_hz / nyquist
    sos = butter(order, normal_cutoff, btype=filter_type, analog=False, output='sos')
    filtered_samples = sosfilt(sos, samples)
    gain_factor = 10 ** (gain_db / 20.0)
    if gain_db > 0:
        return samples + (filtered_samples * (gain_factor - 1))
    else:
        return samples * gain_factor + (filtered_samples * (1 - gain_factor))

def apply_peak_filter(samples, sample_rate, center_hz, gain_db, q=1.0):
    """Applies a peak/bell filter (mids/presence) to a NumPy float array."""
    if gain_db == 0:
        return samples
    
    # Design a peaking EQ filter (bandpass for the boost/cut part)
    nyquist = 0.5 * sample_rate
    normal_center = center_hz / nyquist
    
    # This is a simplified way to create a peak filter effect
    # A full implementation requires a biquad filter design
    # For our purpose, we can simulate it with a bandpass filter
    sos = butter(2, [normal_center / np.sqrt(q), normal_center * np.sqrt(q)], btype='bandpass', output='sos')
    filtered_samples = sosfilt(sos, samples)
    
    gain_factor = 10 ** (gain_db / 20.0)
    
    # Mix the filtered signal with the original
    return samples + (filtered_samples * (gain_factor - 1))


def soft_limiter(samples, threshold=0.98):
    """A simple soft limiter to prevent clipping."""
    clipped_indices = np.abs(samples) > threshold
    samples[clipped_indices] = np.tanh(samples[clipped_indices]) * threshold
    return samples

def main():
    # Build a list of available presets for the help message
    preset_choices = list(EQ_PRESETS.keys())
    preset_help_string = "Apply a genre-specific EQ preset. Choices: " + ", ".join(preset_choices)

    parser = argparse.ArgumentParser(description="A command-line tool for audio mastering.")
    parser.add_argument("input_file", help="Path to the input audio file.")
    parser.add_argument("output_file", help="Path to save the processed audio file.")
    
    # --- Processing Options ---
    parser.add_argument("--normalize", action="store_true", help="Normalize the audio to -0.1dBFS.")
    parser.add_argument("--compress", action="store_true", help="Apply dynamic range compression.")
    
    # --- EQ Options ---
    parser.add_argument("--preset", choices=preset_choices, help=preset_help_string)
    parser.add_argument("--bass_boost", type=float, default=0.0, help="Boost/cut bass (cutoff 250Hz) by a dB value.")
    parser.add_argument("--mid_cut", type=float, default=0.0, help="Cut/boost mids (center 1000Hz) by a dB value.")
    parser.add_argument("--presence_boost", type=float, default=0.0, help="Boost/cut vocal presence (center 4000Hz) by a dB value.")
    parser.add_argument("--treble_boost", type=float, default=0.0, help="Boost/cut treble (cutoff 8000Hz) by a dB value.")

    args = parser.parse_args()
    
    # --- Apply Preset if selected ---
    if args.preset:
        preset_settings = EQ_PRESETS[args.preset]
        print(f"Applying '{args.preset}' preset: {preset_settings['description']}")
        args.bass_boost = preset_settings["bass_boost"]
        args.mid_cut = preset_settings["mid_cut"]
        args.presence_boost = preset_settings["presence_boost"]
        args.treble_boost = preset_settings["treble_boost"]

    if not os.path.exists(args.input_file):
        print(f"Error: Input file not found at '{args.input_file}'")
        return

    print(f"Loading audio file: {args.input_file}")
    audio = AudioSegment.from_file(args.input_file)

    if audio.channels == 2:
        left, right = audio.split_to_mono()
        samples_left = audio_segment_to_float_array(left)
        samples_right = audio_segment_to_float_array(right)
    else:
        samples = audio_segment_to_float_array(audio)

    # --- Apply EQ on the float data ---
    # The order is: Bass -> Mids -> Presence -> Treble
    if audio.channels == 2:
        samples_left = apply_shelf_filter(samples_left, audio.frame_rate, 250, args.bass_boost, 'low')
        samples_right = apply_shelf_filter(samples_right, audio.frame_rate, 250, args.bass_boost, 'low')
        samples_left = apply_peak_filter(samples_left, audio.frame_rate, 1000, -args.mid_cut) # Note: negative for cut
        samples_right = apply_peak_filter(samples_right, audio.frame_rate, 1000, -args.mid_cut)
        samples_left = apply_peak_filter(samples_left, audio.frame_rate, 4000, args.presence_boost)
        samples_right = apply_peak_filter(samples_right, audio.frame_rate, 4000, args.presence_boost)
        samples_left = apply_shelf_filter(samples_left, audio.frame_rate, 8000, args.treble_boost, 'high')
        samples_right = apply_shelf_filter(samples_right, audio.frame_rate, 8000, args.treble_boost, 'high')
    else: # Mono
        samples = apply_shelf_filter(samples, audio.frame_rate, 250, args.bass_boost, 'low')
        samples = apply_peak_filter(samples, audio.frame_rate, 1000, -args.mid_cut)
        samples = apply_peak_filter(samples, audio.frame_rate, 4000, args.presence_boost)
        samples = apply_shelf_filter(samples, audio.frame_rate, 8000, args.treble_boost, 'high')

    # --- Re-assemble AudioSegment for final processing ---
    if audio.channels == 2:
        samples_left, samples_right = soft_limiter(samples_left), soft_limiter(samples_right)
        processed_left = float_array_to_audio_segment(samples_left, left)
        processed_right = float_array_to_audio_segment(samples_right, right)
        processed_audio = AudioSegment.from_mono_audiosegments(processed_left, processed_right)
    else:
        samples = soft_limiter(samples)
        processed_audio = float_array_to_audio_segment(samples, audio)

    if args.compress:
        print("Applying dynamic range compression...")
        processed_audio = compress_dynamic_range(processed_audio)

    if args.normalize:
        print("Normalizing audio...")
        processed_audio = processed_audio.normalize(headroom=0.1)

    print(f"Exporting processed audio to: {args.output_file}")
    output_format = os.path.splitext(args.output_file)[1][1:] or "wav"
    processed_audio.export(args.output_file, format=output_format)
    print("Processing complete!")

if __name__ == "__main__":
    main()
