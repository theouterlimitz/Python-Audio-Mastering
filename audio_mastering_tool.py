# audio_mastering_tool.py (v4)
#
# A command-line Python script to apply mastering effects to an audio file.
# Version 4 replaces peak normalization with a professional LUFS loudness targeting system.
#
# Dependencies:
# pip install pydub scipy numpy pyloudnorm
#
# Usage:
# python audio_mastering_tool.py <input_file> <output_file> --lufs -14
#
# Example with a preset and LUFS target:
# python audio_mastering_tool.py "mix.wav" "mix_techno.wav" --preset techno --compress --lufs -12
#

import argparse
import os
import numpy as np
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range
from scipy.signal import butter, sosfilt
import pyloudnorm as pyln

# --- PRESET DEFINITIONS ---
EQ_PRESETS = {
    "techno": {
        "bass_boost": 4.0, "mid_cut": 3.0, "presence_boost": 1.0, "treble_boost": 3.0,
        "description": "Boosted sub-bass and highs, scooped mids for a powerful club sound."
    },
    "dubstep": {
        "bass_boost": 5.0, "mid_cut": 4.0, "presence_boost": 2.0, "treble_boost": 3.5,
        "description": "Aggressive low-end and crisp highs, with a significant mid-cut."
    },
    "pop": {
        "bass_boost": 2.0, "mid_cut": 0.0, "presence_boost": 3.5, "treble_boost": 2.5,
        "description": "Focused on vocal clarity with a solid low-end and bright highs."
    },
    "rock": {
        "bass_boost": 1.5, "mid_cut": -2.0, "presence_boost": 2.5, "treble_boost": 1.0,
        "description": "Warm low-mids for guitars and punchy presence for snare/vocals."
    }
}

def audio_segment_to_float_array(audio_segment):
    samples = np.array(audio_segment.get_array_of_samples())
    return samples.astype(np.float32) / (2**(audio_segment.sample_width * 8 - 1))

def float_array_to_audio_segment(float_array, audio_segment_template):
    clipped_array = np.clip(float_array, -1.0, 1.0)
    int_array = (clipped_array * (2**(audio_segment_template.sample_width * 8 - 1))).astype(np.int16)
    return audio_segment_template._spawn(int_array.tobytes())

def apply_shelf_filter(samples, sample_rate, cutoff_hz, gain_db, filter_type, order=5):
    if gain_db == 0: return samples
    nyquist = 0.5 * sample_rate
    normal_cutoff = cutoff_hz / nyquist
    sos = butter(order, normal_cutoff, btype=filter_type, analog=False, output='sos')
    filtered_samples = sosfilt(sos, samples)
    gain_factor = 10 ** (gain_db / 20.0)
    if gain_db > 0: return samples + (filtered_samples * (gain_factor - 1))
    else: return samples * gain_factor + (filtered_samples * (1 - gain_factor))

def apply_peak_filter(samples, sample_rate, center_hz, gain_db, q=1.0):
    if gain_db == 0: return samples
    nyquist = 0.5 * sample_rate
    normal_center = center_hz / nyquist
    sos = butter(2, [normal_center / np.sqrt(q), normal_center * np.sqrt(q)], btype='bandpass', output='sos')
    filtered_samples = sosfilt(sos, samples)
    gain_factor = 10 ** (gain_db / 20.0)
    return samples + (filtered_samples * (gain_factor - 1))

def normalize_to_lufs(samples, sample_rate, target_lufs=-14.0):
    """
    Measures and normalizes the loudness of a track to a target LUFS value.
    """
    # Create a loudness meter
    meter = pyln.Meter(sample_rate)
    
    # Measure the integrated loudness
    # The pyloudnorm library expects the samples in the shape (channels, samples)
    # but our processing uses (samples,). For stereo, we need to transpose.
    # For now, we assume mono or average stereo for loudness calculation.
    loudness = meter.integrated_loudness(samples)
    
    # Calculate the gain needed to reach the target LUFS
    # This is a simple linear gain adjustment
    gain_db = target_lufs - loudness
    gain_linear = 10.0 ** (gain_db / 20.0)
    
    print(f"Current loudness: {loudness:.2f} LUFS. Applying {gain_db:.2f} dB gain to reach {target_lufs} LUFS.")
    
    return samples * gain_linear

def soft_limiter(samples, threshold=0.98):
    clipped_indices = np.abs(samples) > threshold
    samples[clipped_indices] = np.tanh(samples[clipped_indices]) * threshold
    return samples

def main():
    preset_choices = list(EQ_PRESETS.keys())
    parser = argparse.ArgumentParser(description="A command-line tool for audio mastering.")
    parser.add_argument("input_file", help="Path to the input audio file.")
    parser.add_argument("output_file", help="Path to save the processed audio file.")
    
    # --- Processing Options ---
    parser.add_argument("--lufs", type=float, help="Target loudness in LUFS (e.g., -14.0 for Spotify).")
    parser.add_argument("--normalize", action="store_true", help="Legacy peak normalization (use --lufs for better results).")
    parser.add_argument("--compress", action="store_true", help="Apply dynamic range compression.")
    
    # --- EQ Options ---
    parser.add_argument("--preset", choices=preset_choices, help="Apply a genre-specific EQ preset.")
    parser.add_argument("--bass_boost", type=float, default=0.0, help="Boost/cut bass (250Hz) by a dB value.")
    parser.add_argument("--mid_cut", type=float, default=0.0, help="Cut/boost mids (1000Hz) by a dB value.")
    parser.add_argument("--presence_boost", type=float, default=0.0, help="Boost/cut vocal presence (4000Hz) by a dB value.")
    parser.add_argument("--treble_boost", type=float, default=0.0, help="Boost/cut treble (8000Hz) by a dB value.")

    args = parser.parse_args()
    
    if args.preset:
        preset = EQ_PRESETS[args.preset]
        print(f"Applying '{args.preset}' preset: {preset['description']}")
        args.bass_boost, args.mid_cut, args.presence_boost, args.treble_boost = \
            preset["bass_boost"], preset["mid_cut"], preset["presence_boost"], preset["treble_boost"]

    if not os.path.exists(args.input_file):
        print(f"Error: Input file not found at '{args.input_file}'"); return

    print(f"Loading audio file: {args.input_file}")
    audio = AudioSegment.from_file(args.input_file)

    # --- Start of Processing Chain ---
    if audio.channels == 2:
        left, right = audio.split_to_mono()
        samples_left, samples_right = audio_segment_to_float_array(left), audio_segment_to_float_array(right)
        
        # Process EQ
        samples_left = apply_shelf_filter(samples_left, audio.frame_rate, 250, args.bass_boost, 'low')
        samples_right = apply_shelf_filter(samples_right, audio.frame_rate, 250, args.bass_boost, 'low')
        samples_left = apply_peak_filter(samples_left, audio.frame_rate, 1000, -args.mid_cut)
        samples_right = apply_peak_filter(samples_right, audio.frame_rate, 1000, -args.mid_cut)
        samples_left = apply_peak_filter(samples_left, audio.frame_rate, 4000, args.presence_boost)
        samples_right = apply_peak_filter(samples_right, audio.frame_rate, 4000, args.presence_boost)
        samples_left = apply_shelf_filter(samples_left, audio.frame_rate, 8000, args.treble_boost, 'high')
        samples_right = apply_shelf_filter(samples_right, audio.frame_rate, 8000, args.treble_boost, 'high')
        
        # Combine channels for compression and loudness measurement
        processed_samples = np.array([samples_left, samples_right]).T
    else: # Mono
        processed_samples = audio_segment_to_float_array(audio)
        processed_samples = apply_shelf_filter(processed_samples, audio.frame_rate, 250, args.bass_boost, 'low')
        processed_samples = apply_peak_filter(processed_samples, audio.frame_rate, 1000, -args.mid_cut)
        processed_samples = apply_peak_filter(processed_samples, audio.frame_rate, 4000, args.presence_boost)
        processed_samples = apply_shelf_filter(processed_samples, audio.frame_rate, 8000, args.treble_boost, 'high')

    # Convert back to pydub AudioSegment for compression
    processed_audio = float_array_to_audio_segment(processed_samples.flatten(), audio)

    if args.compress:
        print("Applying dynamic range compression...")
        processed_audio = compress_dynamic_range(processed_audio)

    # --- Final Loudness and Limiting Stage ---
    final_samples = audio_segment_to_float_array(processed_audio)

    if args.lufs is not None:
        final_samples = normalize_to_lufs(final_samples, audio.frame_rate, args.lufs)
    elif args.normalize:
        # Legacy peak normalization
        print("Applying legacy peak normalization...")
        peak = np.max(np.abs(final_samples))
        if peak > 0:
            final_samples /= peak

    # Final limiting to catch any stray peaks
    final_samples = soft_limiter(final_samples)
    
    final_audio = float_array_to_audio_segment(final_samples, audio)

    print(f"Exporting processed audio to: {args.output_file}")
    output_format = os.path.splitext(args.output_file)[1][1:] or "wav"
    final_audio.export(args.output_file, format=output_format)
    print("Processing complete!")

if __name__ == "__main__":
    main()