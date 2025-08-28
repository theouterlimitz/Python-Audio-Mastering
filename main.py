import os
import numpy as np
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range
from scipy.signal import butter, sosfilt
import pyloudnorm as pyln
from google.cloud import storage
from flask import Flask, request

# Initialize Flask App and GCS Client
app = Flask(__name__)
storage_client = storage.Client()

@app.route('/', methods=['POST'])
def process_mastering():
    """
    This Cloud Function is triggered when a file is uploaded to a Cloud Storage bucket.
    The event data is sent via an HTTP POST request from Eventarc.
    """
    # The event data is in the request body as JSON
    event = request.get_json()
    
    # Extract file details from the Cloud Storage event
    bucket_name = event['bucket']
    file_name = event['name']
    
    if 'processed/' in file_name:
        print(f"File {file_name} is already processed. Ignoring.")
        return "OK", 200

    print(f"Processing file: {file_name} from bucket: {bucket_name}")

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    
    temp_input_path = f"/tmp/{os.path.basename(file_name)}"
    blob.download_to_filename(temp_input_path)
    
    # --- Hardcoded Mastering Settings for this Phase ---
    settings = {
        "saturation": 10.0, "bass_boost": 2.0, "mid_cut": 0.0,
        "presence_boost": 1.5, "treble_boost": 1.0, "width": 1.15,
        "lufs": -14.0, "multiband": True, "low_band_threshold": -25.0,
        "low_band_ratio": 6.0, "mid_band_threshold": -20.0, "mid_band_ratio": 3.0,
        "high_band_threshold": -15.0, "high_band_ratio": 4.0,
    }

    # --- Run the Mastering Engine ---
    audio = AudioSegment.from_file(temp_input_path)
    
    chunk_size_ms = 30 * 1000
    processed_chunks = []
    for start_ms in range(0, len(audio), chunk_size_ms):
        chunk = audio[start_ms:start_ms+chunk_size_ms]
        chunk_samples = audio_segment_to_float_array(chunk)
        
        if settings.get("saturation", 0.0) > 0:
            chunk_samples = apply_saturation(chunk_samples, settings.get("saturation"))
        processed_samples = apply_eq_to_samples(chunk_samples, chunk.frame_rate, settings)
        if settings.get("width", 1.0) != 1.0:
            processed_samples = apply_stereo_width(processed_samples, settings.get("width"))
        processed_chunk = float_array_to_audio_segment(processed_samples, chunk)
        if settings.get("multiband"):
            processed_chunk = apply_multiband_compressor(processed_chunk, settings)
        processed_chunks.append(processed_chunk)
        
    processed_audio = sum(processed_chunks)
    final_samples = audio_segment_to_float_array(processed_audio)
    if settings.get("lufs") is not None:
        final_samples = normalize_to_lufs(final_samples, processed_audio.frame_rate, settings.get("lufs"))
    final_samples = soft_limiter(final_samples)
    final_audio = float_array_to_audio_segment(final_samples, processed_audio)

    # --- Upload the Processed File ---
    temp_output_path = f"/tmp/processed-{os.path.basename(file_name)}"
    output_format = os.path.splitext(file_name)[1][1:] or "wav"
    final_audio.export(temp_output_path, format=output_format)
    
    output_blob_name = f"processed/{os.path.basename(file_name)}"
    output_blob = bucket.blob(output_blob_name)
    output_blob.upload_from_filename(temp_output_path)
    
    print(f"Successfully processed {file_name} and uploaded to {output_blob_name}")

    os.remove(temp_input_path)
    os.remove(temp_output_path)
    
    return "OK", 200

# --- Helper functions (copied from our engine) ---
def apply_saturation(samples, amount):
    if amount == 0: return samples
    gain = 1.0 + (amount / 100.0) * 4.0
    return np.tanh(samples * gain) / gain

def audio_segment_to_float_array(audio_segment):
    samples = np.array(audio_segment.get_array_of_samples())
    if audio_segment.channels == 2:
        samples = samples.reshape((-1, 2))
    return samples.astype(np.float32) / (2**(audio_segment.sample_width * 8 - 1))

def float_array_to_audio_segment(float_array, audio_segment_template):
    clipped_array = np.clip(float_array, -1.0, 1.0)
    int_array = (clipped_array * (2**(audio_segment_template.sample_width * 8 - 1))).astype(np.int16)
    return audio_segment_template._spawn(int_array.tobytes())

def apply_stereo_width(samples, width_factor):
    if samples.ndim == 1 or samples.shape[1] != 2: return samples
    left, right = samples[:, 0], samples[:, 1]
    mid, side = (left + right) / 2, (left - right) / 2
    side *= width_factor
    new_left, new_right = mid + side, mid - side
    return np.array([new_left, new_right]).T

def apply_eq_to_samples(samples, sample_rate, settings):
    if samples.ndim > 1 and samples.shape[1] == 2: # Stereo
        left, right = samples[:, 0], samples[:, 1]
        left = apply_shelf_filter(left, sample_rate, 250, settings.get("bass_boost", 0.0), 'low')
        right = apply_shelf_filter(right, sample_rate, 250, settings.get("bass_boost", 0.0), 'low')
        left = apply_peak_filter(left, sample_rate, 1000, -settings.get("mid_cut", 0.0))
        right = apply_peak_filter(right, sample_rate, 1000, -settings.get("mid_cut", 0.0))
        left = apply_peak_filter(left, sample_rate, 4000, settings.get("presence_boost", 0.0))
        right = apply_peak_filter(right, sample_rate, 4000, settings.get("presence_boost", 0.0))
        left = apply_shelf_filter(left, sample_rate, 8000, settings.get("treble_boost", 0.0), 'high')
        right = apply_shelf_filter(right, sample_rate, 8000, settings.get("treble_boost", 0.0), 'high')
        return np.array([left, right]).T
    else: # Mono
        samples = apply_shelf_filter(samples, sample_rate, 250, settings.get("bass_boost", 0.0), 'low')
        samples = apply_peak_filter(samples, sample_rate, 1000, -settings.get("mid_cut", 0.0))
        samples = apply_peak_filter(samples, sample_rate, 4000, settings.get("presence_boost", 0.0))
        samples = apply_shelf_filter(samples, sample_rate, 8000, settings.get("treble_boost", 0.0), 'high')
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

def apply_multiband_compressor(chunk, settings):
    low_crossover, high_crossover = 250, 4000
    low_thresh, low_ratio = settings.get("low_band_threshold", -25.0), settings.get("low_band_ratio"