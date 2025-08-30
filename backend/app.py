# backend/app.py
# Final version using lazy initialization for robustness in the cloud.
# This version is designed to run on the official GAE base image.

import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS

# These libraries will only be imported when needed inside a function.
# This prevents startup crashes.

app = Flask(__name__)
# Allow all origins for simplicity in this public API
CORS(app, resources={r"/*": {"origins": "*"}})

# --- Constants ---
# These are loaded from environment variables for flexibility,
# but we have fallbacks for our specific project.
PROJECT_ID = os.environ.get("GCP_PROJECT", "tactile-temple-395019")
TOPIC_ID = "mastering-jobs"
BUCKET_NAME = "tactile-temple-395019-audio-uploads"
# The service account our backend is explicitly running as.
SERVICE_ACCOUNT_EMAIL = f"audio-backend-identity@{PROJECT_ID}.iam.gserviceaccount.com"


@app.route('/')
def hello_world():
    """A simple health check endpoint to confirm the server is running."""
    return 'Audio Mastering Backend is running.'


@app.route('/generate-upload-url', methods=['POST'])
def generate_upload_url():
    """Generates a secure, short-lived URL for direct-to-cloud uploads."""
    # Lazy import and initialization
    from google.cloud import storage

    try:
        data = request.get_json()
        if not data or 'filename' not in data:
            return jsonify({"error": "Missing filename"}), 400

        filename = data['filename']
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)

        # Explicitly tell the signing function which identity to use. This is robust.
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=300,  # 5 minutes
            method="PUT",
            content_type=data.get('contentType', 'application/octet-stream'),
            service_account_email=SERVICE_ACCOUNT_EMAIL,
        )
        return jsonify({"signedUrl": signed_url, "filename": filename}), 200
    except Exception as e:
        print(f"ERROR in /generate-upload-url: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to generate upload URL."}), 500


@app.route('/start-processing', methods=['POST'])
def start_processing():
    """Sends a job ticket to the Pub/Sub topic to trigger the worker."""
    # Lazy import and initialization
    from google.cloud import pubsub_v1

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing job data"}), 400

        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
        
        message_data = json.dumps(data).encode("utf-8")
        future = publisher.publish(topic_path, data=message_data)
        future.result()  # Wait for the publish to complete.
        return jsonify({"message": "Processing job has been successfully submitted."}), 200
    except Exception as e:
        print(f"ERROR in /start-processing: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to submit processing job."}), 500


@app.route('/status', methods=['GET'])
def get_status():
    """Checks for the processed file and provides a secure download link."""
    # Lazy import and initialization
    from google.cloud import storage

    try:
        filename = request.args.get('filename')
        if not filename:
            return jsonify({"error": "Missing filename parameter"}), 400

        processed_filename = f"processed/{filename}"
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        flag_blob = bucket.blob(f"{processed_filename}.complete")

        if flag_blob.exists():
            audio_blob = bucket.blob(processed_filename)
            # Explicitly tell the signing function which identity to use. This is robust.
            download_url = audio_blob.generate_signed_url(
                version="v4",
                expiration=3600,  # 1 hour
                method="GET",
                service_account_email=SERVICE_ACCOUNT_EMAIL,
            )
            return jsonify({"status": "complete", "downloadUrl": download_url}), 200
        else:
            return jsonify({"status": "processing"}), 202
    except Exception as e:
        print(f"ERROR in /status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to get job status."}), 500


if __name__ == "__main__":
    # This part is for local testing only. Gunicorn runs the app in production.
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))