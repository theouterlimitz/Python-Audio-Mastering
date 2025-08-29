# app.py
#
# A professional, production-grade backend API for the Audio Mastering Suite.
# This version uses "lazy initialization" for cloud clients to ensure a stable startup.
#

import os
import datetime
import json
from flask import Flask, request, jsonify
from google.cloud import storage, pubsub_v1
from flask_cors import CORS

# --- Configuration ---
# It's best practice to load configuration from environment variables.
BUCKET_NAME = "tactile-temple-395019-audio-uploads"
PROJECT_ID = "tactile-temple-395019"
TOPIC_ID = "mastering-jobs"

app = Flask(__name__)
# Allow all origins for simplicity. In a production app, you would restrict
# this to your Netlify domain for enhanced security.
CORS(app, resources={r"/*": {"origins": "*"}})

# --- Routes ---

@app.route('/')
def hello():
    """A simple health check endpoint."""
    return "Audio Mastering Backend is running."

@app.route('/generate-upload-url', methods=['POST'])
def generate_upload_url():
    """
    Generates a V4 signed URL for a client to upload a file directly to GCS.
    """
    try:
        # Lazy Initialization: Create the client only when needed.
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)

        request_data = request.get_json()
        if not request_data or 'filename' not in request_data or 'contentType' not in request_data:
            return jsonify({"error": "Missing filename or contentType in request"}), 400

        filename = request_data['filename']
        content_type = request_data['contentType']
        unique_filename = f"{os.urandom(8).hex()}_{filename}"
        blob = bucket.blob(unique_filename)

        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            content_type=content_type,
        )

        return jsonify({"signedUrl": signed_url, "uniqueFilename": unique_filename}), 200

    except Exception as e:
        print(f"CRITICAL ERROR in /generate-upload-url: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Server failed to generate upload URL."}), 500

@app.route('/start-processing', methods=['POST'])
def start_processing():
    """
    Receives the filename and settings from the client and publishes a job
    to the Pub/Sub topic to trigger the worker.
    """
    try:
        # Lazy Initialization: Create the client only when needed.
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

        request_data = request.get_json()
        if not request_data or 'filename' not in request_data or 'settings' not in request_data:
            return jsonify({"error": "Missing filename or settings in request"}), 400

        job_data = {
            "filename": request_data['filename'],
            "settings": request_data['settings']
        }

        message_data = json.dumps(job_data).encode("utf-8")
        future = publisher.publish(topic_path, message_data)
        future.result()

        return jsonify({"message": "Processing job started successfully."}), 200

    except Exception as e:
        print(f"CRITICAL ERROR in /start-processing: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Server failed to start processing job."}), 500

@app.route('/status', methods=['GET'])
def get_status():
    """
    Checks if a processed file and its '.complete' signal file exist in GCS
    and provides a download link if they do.
    """
    try:
        filename = request.args.get('filename')
        if not filename:
            return jsonify({"error": "Filename parameter is required"}), 400

        # Lazy Initialization: Create the client only when needed.
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        
        signal_blob = bucket.blob(f"processed/{filename}.complete")
        
        if signal_blob.exists():
            audio_blob = bucket.blob(f"processed/{filename}")
            if audio_blob.exists():
                download_url = audio_blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.timedelta(minutes=60),
                    method="GET",
                )
                return jsonify({"status": "ready", "downloadUrl": download_url})
            else:
                 return jsonify({"status": "processing", "message": "Signal found but audio file is missing."})
        else:
            return jsonify({"status": "processing"})

    except Exception as e:
        print(f"CRITICAL ERROR in /status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Server failed to get job status."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

