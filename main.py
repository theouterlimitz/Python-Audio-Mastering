import os
import json
import base64
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
    This Cloud Function is triggered by a message on a Pub/Sub topic.
    The event data is sent via an HTTP POST request from Eventarc.
    """
    # The event data is wrapped in a Pub/Sub message format.
    envelope = request.get_json()
    if not envelope or 'message' not in envelope:
        print("Error: Invalid Pub/Sub message format")
        return "Bad Request: Invalid Pub/Sub message format", 400

    # The actual job ticket is a base64-encoded string in the 'data' field.
    pubsub_message = base64.b64decode(envelope['message']['data']).decode('utf-8')
    data = json.loads(pubsub_message)
    
    # Extract file details and settings from the job ticket
    bucket_name = data['bucket_name']
    file_name = data['file_name']
    settings = data['settings']
    
    if 'processed/' in file_name:
        print(f"File {file_name} is already processed. Ignoring.")
        return "OK", 200

    print(f"Processing file: {file_name} from bucket: {bucket_name} with settings: {settings}")

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    
    temp_input_path = f"/tmp/{os.path.basename(file_name)}"
    blob.download_to_filename(temp_input_path)
    
    # --- Run the Mastering Engine using settings from the frontend ---
    audio = AudioSegment.from_file(temp_input_path)
    
    chunk_size_ms = 30 * 1000
    processed_chunks = []
    for start_ms in range(0, len(audio), chunk_size_ms):
        chunk = audio[start_ms:start_ms+chunk_size_ms]
        chunk_samples = audio_segment_to_float_array(chunk)
        
        if float(settings.get("saturation", 0.0)) > 0:
            chunk_samples = apply_saturation(chunk_samples, float(settings.get("saturation")))
        processed_samples = apply_eq_to_samples(chunk_samples, chunk.frame_rate, settings)
        if float(settings.get("width", 1.0)) != 1.0:
            processed_samples = apply_stereo_width(processed_samples, float(settings.get("width")))
        processed_chunk = float_array_to_audio_segment(processed_samples, chunk)
        if settings.get("use_multiband"):
            processed_chunk = apply_multiband_compressor(processed_chunk, settings)
        processed_chunks.append(processed_chunk)
        
    processed_audio = sum(processed_chunks)
    final_samples = audio_segment_to_float_array(processed_audio)
    if settings.get("lufs") is not None:
        final_samples = normalize_to_lufs(final_samples, processed_audio.frame_rate, float(settings.get("lufs")))
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

# --- Helper functions ---
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
    if samples.ndim > 1 and samples.shape[1] == 2:
        left, right = samples[:, 0], samples[:, 1]
        left = apply_shelf_filter(left, sample_rate, 250, float(settings.get("bass_boost", 0.0)), 'low')
        right = apply_shelf_filter(right, sample_rate, 250, float(settings.get("bass_boost", 0.0)), 'low')
        left = apply_peak_filter(left, sample_rate, 1000, -float(settings.get("mid_cut", 0.0)))
        right = apply_peak_filter(right, sample_rate, 1000, -float(settings.get("mid_cut", 0.0)))
        left = apply_peak_filter(left, sample_rate, 4000, float(settings.get("presence_boost", 0.0)))
        right = apply_peak_filter(right, sample_rate, 4000, float(settings.get("presence_boost", 0.0)))
        left = apply_shelf_filter(left, sample_rate, 8000, float(settings.get("treble_boost", 0.0)), 'high')
        right = apply_shelf_filter(right, sample_rate, 8000, float(settings.get("treble_boost", 0.0)), 'high')
        return np.array([left, right]).T
    else:
        # Mono processing (can be simplified if only stereo is expected)
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
    low_thresh, low_ratio = float(settings.get("low_band_threshold", -25.0)), float(settings.get("low_band_ratio", 6.0))
    mid_thresh, mid_ratio = float(settings.get("mid_band_threshold", -20.0)), float(settings.get("mid_band_ratio", 3.0))
    high_thresh, high_ratio = float(settings.get("high_band_threshold", -15.0)), float(settings.get("high_band_ratio", 4.0))
    low_pass_sos = butter(4, low_crossover, btype='lowpass', fs=chunk.frame_rate, output='sos')
    high_pass_sos = butter(4, high_crossover, btype='highpass', fs=chunk.frame_rate, output='sos')
    samples = audio_segment_to_float_array(chunk)
    low_band_samples = sosfilt(low_pass_sos, samples, axis=0)
    temp_high_pass_for_mid = butter(4, low_crossover, btype='highpass', fs=chunk.frame_rate, output='sos')
    mid_band_samples = sosfilt(temp_high_pass_for_mid, samples, axis=0)
    temp_low_pass_for_mid = butter(4, high_crossover, btype='lowpass', fs=chunk.frame_rate, output='sos')
    mid_band_samples = sosfilt(temp_low_pass_for_mid, mid_band_samples, axis=0)
    high_band_samples = sosfilt(high_pass_sos, samples, axis=0)
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
    return samples * gain_linear

def soft_limiter(samples, threshold=0.98):
    clipped_indices = np.abs(samples) > threshold
    samples[clipped_indices] = np.tanh(samples[clipped_indices]) * threshold
    return samples

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
