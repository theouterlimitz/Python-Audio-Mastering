# audio_mastering_tool.py (v5)
#
# A command-line Python script to apply mastering effects to an audio file.
# Version 5 implements robust chunk-based processing to handle large files
# without running out of memory.
#
# Dependencies:
# pip install pydub scipy numpy pyloudnorm tqdm
#
# Usage:
# python audio_mastering_tool.py "mix.wav" "mix_mastered.wav" --preset techno --compress --lufs -12
#

import argparse
import os
import numpy as np
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range
from scipy.signal import butter, sosfilt
import pyloudnorm as pyln
from tqdm import tqdm # For a nice progress bar

# --- PRESET DEFINITIONS ---
EQ_PRESETS = {
    "techno": { "bass_boost": 4.0, "mid_cut": 3.0, "presence_boost": 1.0, "treble_boost": 3.0, "description": "Boosted sub-bass and highs, scooped mids for a powerful club sound." },
    "dubstep": { "bass_boost": 5.0, "mid_cut": 4.0, "presence_boost": 2.0, "treble_boost": 3.5, "description": "Aggressive low-end and crisp highs, with a significant mid-cut." },
    "pop": { "bass_boost": 2.0, "mid_cut": 0.0, "presence_boost": 3.5, "treble_boost": 2.5, "description": "Focused on vocal clarity with a solid low-end and bright highs." },
    "rock": { "bass_boost": 1.5, "mid_cut": -2.0, "presence_boost": 2.5, "treble_boost": 1.0, "description": "Warm low-mids for guitars and punchy presence for snare/vocals." }
}

# --- CORE PROCESSING FUNCTIONS ---

def audio_segment_to_float_array(audio_segment):
    samples = np.array(audio_segment.get_array_of_samples())
    return samples.astype(np.float32) / (2**(audio_segment.sample_width * 8 - 1))

def float_array_to_audio_segment(float_array, audio_segment_template):
    clipped_array = np.clip(float_array, -1.0, 1.0)
    int_array = (clipped_array * (2**(audio_segment_template.sample_width * 8 - 1))).astype(np.int16)
    return audio_segment_template._spawn(int_array.tobytes())

def apply_eq_to_samples(samples, sample_rate, args):
    """Applies the full EQ chain to a numpy array of samples."""
    if samples.ndim > 1 and samples.shape[1] == 2: # Stereo
        left, right = samples[:, 0], samples[:, 1]
        left = apply_shelf_filter(left, sample_rate, 250, args.bass_boost, 'low')
        right = apply_shelf_filter(right, sample_rate, 250, args.bass_boost, 'low')
        left = apply_peak_filter(left, sample_rate, 1000, -args.mid_cut)
        right = apply_peak_filter(right, sample_rate, 1000, -args.mid_cut)
        left = apply_peak_filter(left, sample_rate, 4000, args.presence_boost)
        right = apply_peak_filter(right, sample_rate, 4000, args.presence_boost)
        left = apply_shelf_filter(left, sample_rate, 8000, args.treble_boost, 'high')
        right = apply_shelf_filter(right, sample_rate, 8000, args.treble_boost, 'high')
        return np.array([left, right]).T
    else: # Mono
        samples = apply_shelf_filter(samples, sample_rate, 250, args.bass_boost, 'low')
        samples = apply_peak_filter(samples, sample_rate, 1000, -args.mid_cut)
        samples = apply_peak_filter(samples, sample_rate, 4000, args.presence_boost)
        samples = apply_shelf_filter(samples, sample_rate, 8000, args.treble_boost, 'high')
        return samples

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
    edge1, edge2 = normal_center / np.sqrt(q), normal_center * np.sqrt(q)
    low_freq, high_freq = min(edge1, edge2), max(edge1, edge2)
    if low_freq >= high_freq: high_freq = low_freq + 1e-9
    if high_freq >= 1.0: high_freq = 0.999999
    sos = butter(2, [low_freq, high_freq], btype='bandpass', output='sos')
    filtered_samples = sosfilt(sos, samples)
    gain_factor = 10 ** (gain_db / 20.0)
    return samples + (filtered_samples * (gain_factor - 1))

def normalize_to_lufs(samples, sample_rate, target_lufs=-14.0):
    meter = pyln.Meter(sample_rate)
    # Transpose samples for pyloudnorm if stereo: (samples, channels) -> (channels, samples)
    loudness_samples = samples.T if samples.ndim > 1 else samples
    loudness = meter.integrated_loudness(loudness_samples)
    gain_db = target_lufs - loudness
    gain_linear = 10.0 ** (gain_db / 20.0)
    print(f"\nCurrent loudness: {loudness:.2f} LUFS. Applying {gain_db:.2f} dB gain to reach {target_lufs} LUFS.")
    return samples * gain_linear

def soft_limiter(samples, threshold=0.98):
    clipped_indices = np.abs(samples) > threshold
    samples[clipped_indices] = np.tanh(samples[clipped_indices]) * threshold
    return samples

# --- MAIN EXECUTION ---

def main():
    parser = argparse.ArgumentParser(description="A robust, chunk-based audio mastering tool.")
    parser.add_argument("input_file", help="Path to the input audio file.")
    parser.add_argument("output_file", help="Path to save the processed audio file.")
    
    parser.add_argument("--lufs", type=float, help="Target loudness in LUFS (e.g., -14.0 for Spotify).")
    parser.add_argument("--compress", action="store_true", help="Apply dynamic range compression.")
    parser.add_argument("--preset", choices=list(EQ_PRESETS.keys()), help="Apply a genre-specific EQ preset.")
    parser.add_argument("--bass_boost", type=float, default=0.0, help="Boost/cut bass (250Hz).")
    parser.add_argument("--mid_cut", type=float, default=0.0, help="Cut/boost mids (1000Hz).")
    parser.add_argument("--presence_boost", type=float, default=0.0, help="Boost/cut vocal presence (4000Hz).")
    parser.add_argument("--treble_boost", type=float, default=0.0, help="Boost/cut treble (8000Hz).")

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
    
    # --- CHUNK-BASED PROCESSING LOOP ---
    chunk_size_ms = 30 * 1000 # 30 seconds
    processed_chunks = []
    
    print("Processing audio in chunks...")
    for i in tqdm(range(0, len(audio), chunk_size_ms)):
        chunk = audio[i:i+chunk_size_ms]
        
        # 1. Apply EQ to the chunk
        chunk_samples = audio_segment_to_float_array(chunk)
        eq_samples = apply_eq_to_samples(chunk_samples, chunk.frame_rate, args)
        eq_chunk = float_array_to_audio_segment(eq_samples, chunk)
        
        # 2. Apply Compression to the chunk
        if args.compress:
            eq_chunk = compress_dynamic_range(eq_chunk)
            
        processed_chunks.append(eq_chunk)
        
    # --- FINAL ASSEMBLY AND NORMALIZATION ---
    print("Assembling processed chunks...")
    processed_audio = sum(processed_chunks)
    
    final_samples = audio_segment_to_float_array(processed_audio)

    if args.lufs is not None:
        final_samples = normalize_to_lufs(final_samples, processed_audio.frame_rate, args.lufs)

    # Final limiting to catch any stray peaks after loudness normalization
    final_samples = soft_limiter(final_samples)
    final_audio = float_array_to_audio_segment(final_samples, processed_audio)

    print(f"Exporting processed audio to: {args.output_file}")
    output_format = os.path.splitext(args.output_file)[1][1:] or "wav"
    final_audio.export(args.output_file, format=output_format)
    print("Processing complete!")

if __name__ == "__main__":
    main()