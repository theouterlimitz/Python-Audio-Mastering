# audio_mastering_engine.py (Cloud Version)
# This is the core audio processing engine, adapted to run in the cloud.
# It reads files from GCS, processes them, and uploads the results.

import os
import numpy as np
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range
from scipy.signal import butter, sosfilt
import pyloudnorm as pyln
from google.cloud import storage
import io

# --- PRESET DEFINITIONS ---
EQ_PRESETS = {
    "techno": { "bass_boost": 4.0, "mid_cut": 3.0, "presence_boost": 1.0, "treble_boost": 3.0, "description": "Boosted sub-bass and highs, scooped mids for a powerful club sound." },
    "dubstep": { "bass_boost": 5.0, "mid_cut": 4.0, "presence_boost": 2.0, "treble_boost": 3.5, "description": "Aggressive low-end and crisp highs, with a significant mid-cut." },
    "pop": { "bass_boost": 2.0, "mid_cut": 0.0, "presence_boost": 3.5, "treble_boost": 2.5, "description": "Focused on vocal clarity with a solid low-end and bright highs." },
    "rock": { "bass_boost": 1.5, "mid_cut": -2.0, "presence_boost": 2.5, "treble_boost": 1.0, "description": "Warm low-mids for guitars and punchy presence for snare/vocals." }
}

# --- GCS-SPECIFIC MASTERING FUNCTION ---

def process_audio_from_gcs(gcs_uri, settings):
    """
    Main cloud function entry point. Downloads, processes, and re-uploads an audio file.
    """
    try:
        storage_client = storage.Client()
        
        # 1. DOWNLOAD THE FILE FROM GCS
        print(f"Downloading file from {gcs_uri}...")
        bucket_name, blob_name = gcs_uri.replace("gs://", "").split("/", 1)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Download the file's content into an in-memory bytes buffer
        in_mem_file = io.BytesIO()
        blob.download_to_file(in_mem_file)
        in_mem_file.seek(0) # Rewind the buffer to the beginning
        
        # Load the audio data from the in-memory buffer using pydub
        audio = AudioSegment.from_file(in_mem_file)
        print("File downloaded and loaded into memory.")

        # 2. RUN THE CORE PROCESSING LOGIC (CHUNK-BASED)
        print("Processing audio in chunks...")
        chunk_size_ms = 30 * 1000
        processed_chunks = []
        
        num_chunks = len(range(0, len(audio), chunk_size_ms))
        
        for i, start_ms in enumerate(range(0, len(audio), chunk_size_ms)):
            chunk = audio[start_ms:start_ms+chunk_size_ms]
            chunk_samples = audio_segment_to_float_array(chunk)
            
            # Apply all effects based on the user's settings
            processed_samples = apply_saturation(chunk_samples, settings.get("saturation", 0))
            processed_samples = apply_eq_to_samples(processed_samples, chunk.frame_rate, settings)
            if settings.get("width", 1.0) != 1.0:
                processed_samples = apply_stereo_width(processed_samples, settings.get("width"))
                
            processed_chunk = float_array_to_audio_segment(processed_samples, chunk)
            
            if settings.get("multiband"):
                # Use the new detailed settings for the multiband compressor
                low_thresh = settings.get('low_thresh', -25.0)
                low_ratio = settings.get('low_ratio', 6.0)
                mid_thresh = settings.get('mid_thresh', -20.0)
                mid_ratio = settings.get('mid_ratio', 3.0)
                high_thresh = settings.get('high_thresh', -15.0)
                high_ratio = settings.get('high_ratio', 4.0)
                processed_chunk = apply_multiband_compressor(processed_chunk, low_thresh, low_ratio, mid_thresh, mid_ratio, high_thresh, high_ratio)
            # The simple compressor is not used if multiband is on.
            
            processed_chunks.append(processed_chunk)
            print(f"Processed chunk {i+1}/{num_chunks}...")
            
        print("Assembling processed chunks...")
        processed_audio = sum(processed_chunks)
        
        final_samples = audio_segment_to_float_array(processed_audio)

        if settings.get("lufs") is not None:
            print("Normalizing loudness...")
            final_samples = normalize_to_lufs(final_samples, processed_audio.frame_rate, settings.get("lufs"))

        final_samples = soft_limiter(final_samples)
        final_audio = float_array_to_audio_segment(final_samples, processed_audio)

        # 3. UPLOAD THE PROCESSED FILE BACK TO GCS
        output_filename = f"processed/mastered_{os.path.basename(blob_name)}"
        output_blob = bucket.blob(output_filename)
        
        print(f"Exporting and uploading processed audio to {output_filename}...")
        # Export the file to an in-memory buffer
        out_mem_file = io.BytesIO()
        final_audio.export(out_mem_file, format="wav")
        out_mem_file.seek(0)
        
        # Upload the buffer's content to the new blob
        output_blob.upload_from_file(out_mem_file, content_type='audio/wav')
        print("Processed file uploaded.")

        # 4. CREATE THE ".complete" FLAG FILE
        complete_flag_blob = bucket.blob(f"{output_filename}.complete")
        complete_flag_blob.upload_from_string("")
        print(f"Completion flag created at {output_filename}.complete")

    except Exception as e:
        print(f"FATAL ERROR in mastering engine: {e}")
        # Re-raise the exception to be caught by the main function if needed
        raise

# --- CORE AUDIO HELPER FUNCTIONS ---

def audio_segment_to_float_array(audio_segment):
    samples = np.array(audio_segment.get_array_of_samples())
    if audio_segment.channels == 2:
        samples = samples.reshape((-1, 2))
    return samples.astype(np.float32) / (2**(audio_segment.sample_width * 8 - 1))

def float_array_to_audio_segment(float_array, audio_segment_template):
    clipped_array = np.clip(float_array, -1.0, 1.0)
    int_array = (clipped_array * (2**(audio_segment_template.sample_width * 8 - 1))).astype(np.int16)
    return audio_segment_template._spawn(int_array.tobytes())

def apply_saturation(samples, saturation_percent):
    if saturation_percent == 0:
        return samples
    mix = (saturation_percent / 100.0) ** 2
    clean_signal = samples
    distorted_signal = np.tanh(samples * (1 + mix * 4))
    return (1 - mix) * clean_signal + mix * distorted_signal

def apply_stereo_width(samples, width_factor):
    if samples.ndim == 1 or samples.shape[1] != 2: return samples
    left, right = samples[:, 0], samples[:, 1]
    mid = (left + right) / 2
    side = (left - right) / 2
    side *= width_factor
    new_left = mid + side
    new_right = mid - side
    return np.array([new_left, new_right]).T

def apply_eq_to_samples(samples, sample_rate, settings):
    bass_boost = settings.get("bass_boost", 0.0)
    mid_cut = settings.get("mid_cut", 0.0)
    presence_boost = settings.get("presence_boost", 0.0)
    treble_boost = settings.get("treble_boost", 0.0)
    
    if samples.ndim > 1 and samples.shape[1] == 2: # Stereo
        left, right = samples[:, 0], samples[:, 1]
        left = apply_shelf_filter(left, sample_rate, 250, bass_boost, 'low')
        right = apply_shelf_filter(right, sample_rate, 250, bass_boost, 'low')
        left = apply_peak_filter(left, sample_rate, 1000, -mid_cut)
        right = apply_peak_filter(right, sample_rate, 1000, -mid_cut)
        left = apply_peak_filter(left, sample_rate, 4000, presence_boost)
        right = apply_peak_filter(right, sample_rate, 4000, presence_boost)
        left = apply_shelf_filter(left, sample_rate, 8000, treble_boost, 'high')
        right = apply_shelf_filter(right, sample_rate, 8000, treble_boost, 'high')
        return np.array([left, right]).T
    else: # Mono
        samples = apply_shelf_filter(samples, sample_rate, 250, bass_boost, 'low')
        samples = apply_peak_filter(samples, sample_rate, 1000, -mid_cut)
        samples = apply_peak_filter(samples, sample_rate, 4000, presence_boost)
        samples = apply_shelf_filter(samples, sample_rate, 8000, treble_boost, 'high')
        return samples

def apply_shelf_filter(samples, sample_rate, cutoff_hz, gain_db, filter_type, q=0.707):
    if gain_db == 0: return samples
    nyquist = 0.5 * sample_rate
    Wn = cutoff_hz / nyquist
    gain = 10.0**(gain_db / 20.0)
    alpha = np.sin(Wn*2*np.pi) / (2.0 * q)
    if filter_type == 'low':
        b0, b1, b2 = gain*((gain+1)-(gain-1)*np.cos(Wn*2*np.pi)+2*np.sqrt(gain)*alpha), 2*gain*((gain-1)-(gain+1)*np.cos(Wn*2*np.pi)), gain*((gain+1)-(gain-1)*np.cos(Wn*2*np.pi)-2*np.sqrt(gain)*alpha)
        a0, a1, a2 = (gain+1)+(gain-1)*np.cos(Wn*2*np.pi)+2*np.sqrt(gain)*alpha, -2*((gain-1)+(gain+1)*np.cos(Wn*2*np.pi)), (gain+1)+(gain-1)*np.cos(Wn*2*np.pi)-2*np.sqrt(gain)*alpha
    else:
        b0, b1, b2 = gain*((gain+1)+(gain-1)*np.cos(Wn*2*np.pi)+2*np.sqrt(gain)*alpha), -2*gain*((gain-1)+(gain+1)*np.cos(Wn*2*np.pi)), gain*((gain+1)+(gain-1)*np.cos(Wn*2*np.pi)-2*np.sqrt(gain)*alpha)
        a0, a1, a2 = (gain+1)-(gain-1)*np.cos(Wn*2*np.pi)+2*np.sqrt(gain)*alpha, 2*((gain-1)-(gain+1)*np.cos(Wn*2*np.pi)), (gain+1)-(gain-1)*np.cos(Wn*2*np.pi)-2*np.sqrt(gain)*alpha
    sos = np.array([[b0/a0, b1/a0, b2/a0, 1, a1/a0, a2/a0]])
    return sosfilt(sos, samples)

def apply_peak_filter(samples, sample_rate, center_hz, gain_db, q=1.0):
    if gain_db == 0: return samples
    nyquist = 0.5 * sample_rate
    Wn = center_hz / nyquist
    gain = 10.0**(gain_db / 20.0)
    alpha = np.sin(Wn*2*np.pi) / (2.0 * q)
    b0, b1, b2 = 1+alpha*gain, -2*np.cos(Wn*2*np.pi), 1-alpha*gain
    a0, a1, a2 = 1+alpha/gain, -2*np.cos(Wn*2*np.pi), 1-alpha/gain
    sos = np.array([[b0/a0, b1/a0, b2/a0, 1, a1/a0, a2/a0]])
    return sosfilt(sos, samples)
    
def apply_multiband_compressor(chunk, low_thresh, low_ratio, mid_thresh, mid_ratio, high_thresh, high_ratio, low_crossover=250, high_crossover=4000):
    low_pass_sos = butter(4, low_crossover, btype='lowpass', fs=chunk.frame_rate, output='sos')
    high_pass_sos = butter(4, high_crossover, btype='highpass', fs=chunk.frame_rate, output='sos')
    samples = audio_segment_to_float_array(chunk)
    low_band_samples = sosfilt(low_pass_sos, samples, axis=0)
    high_band_samples_for_sub = sosfilt(high_pass_sos, samples, axis=0)
    mid_band_samples = samples - low_band_samples - high_band_samples_for_sub
    high_band_samples = high_band_samples_for_sub
    low_band_chunk = float_array_to_audio_segment(low_band_samples, chunk)
    mid_band_chunk = float_array_to_audio_segment(mid_band_samples, chunk)
    high_band_chunk = float_array_to_audio_segment(high_band_samples, chunk)
    low_compressed = compress_dynamic_range(low_band_chunk, threshold=low_thresh, ratio=low_ratio, attack=10.0, release=200.0)
    mid_compressed = compress_dynamic_range(mid_band_chunk, threshold=mid_thresh, ratio=mid_ratio, attack=5.0, release=150.0)
    high_compressed = compress_dynamic_range(high_band_chunk, threshold=high_thresh, ratio=high_ratio, attack=1.0, release=50.0)
    return low_compressed.overlay(mid_compressed).overlay(high_compressed)

def normalize_to_lufs(samples, sample_rate, target_lufs=-14.0):
    meter = pyln.Meter(sample_rate)
    if samples.ndim == 2:
        mono_samples_for_measurement = samples.mean(axis=1)
    else:
        mono_samples_for_measurement = samples
    loudness = meter.integrated_loudness(mono_samples_for_measurement)
    gain_db = target_lufs - loudness
    gain_linear = 10.0 ** (gain_db / 20.0)
    print(f"Current loudness: {loudness:.2f} LUFS. Applying {gain_db:.2f} dB gain...")
    return samples * gain_linear

def soft_limiter(samples, threshold=0.98):
    clipped_indices = np.abs(samples) > threshold
    samples[clipped_indices] = (threshold + (np.abs(samples[clipped_indices]) - threshold) / (1 + ((np.abs(samples[clipped_indices]) - threshold)/0.02)**2)**0.5) * np.sign(samples[clipped_indices])
    return samples