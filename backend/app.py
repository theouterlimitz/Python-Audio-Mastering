# backend/app.py
# Final version using lazy initialization for robustness in the cloud.
# This is the complete and correct code for the public-facing API server.

import os
import json
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# These libraries will only be imported when needed inside a function.
# This prevents silent startup crashes and is a professional best practice.

app = Flask(__name__)
# This CORS configuration allows your Netlify frontend to communicate with this backend.
CORS(app, resources={r"/*": {"origins": "*"}})

# --- Configuration ---
# These are loaded from the environment when deployed in Google Cloud.
GCP_PROJECT_ID = os.environ.get('GCP_PROJECT_ID', 'tactile-temple-395019')
BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME', 'tactile-temple-395019-audio-uploads')
PUB_SUB_TOPIC = os.environ.get('PUB_SUB_TOPIC', 'mastering-jobs')

# This is the dedicated service account for our backend, which has the necessary permissions.
SERVICE_ACCOUNT_EMAIL = 'audio-mastering-app-sa@tactile-temple-395019.iam.gserviceaccount.com'

def get_credentials():
    """
    Loads credentials. In a Cloud Run environment, credentials are automatically 
    available from the attached service account. This is a secure best practice.
    """
    from google.auth import default
    creds, _ = default()
    return creds

@app.route('/')
def hello_world():
    """A simple health check endpoint to confirm the server is running."""
    return "Audio Mastering Backend is running."

@app.route('/generate-upload-url', methods=['POST'])
def generate_upload_url():
    """Generates a secure, short-lived URL for the client to upload a file directly to GCS."""
    from google.cloud import storage

    try:
        data = request.get_json()
        if not data or 'filename' not in data:
            return jsonify({"error": "Filename not provided"}), 400

        # Initialize the client inside the function ("lazy initialization")
        storage_client = storage.Client(credentials=get_credentials(), project=GCP_PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(data['filename'])

        # Generate a V4 signed URL, the modern and secure standard.
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            content_type=data.get('contentType', 'application/octet-stream'),
            service_account_email=SERVICE_ACCOUNT_EMAIL,
            access_token=None, # Let the library handle the token from credentials
        )
        
        gcs_uri = f"gs://{BUCKET_NAME}/{data['filename']}"
        return jsonify({"url": url, "gcs_uri": gcs_uri}), 200

    except Exception as e:
        print(f"CRITICAL ERROR in /generate-upload-url: {e}")
        return jsonify({"error": f"Internal server error: {e}"}), 500

@app.route('/start-processing', methods=['POST'])
def start_processing():
    """Receives confirmation of a successful upload and publishes a job to Pub/Sub."""
    from google.cloud import pubsub_v1
    
    try:
        data = request.get_json()
        if not data or 'gcs_uri' not in data or 'settings' not in data:
            return jsonify({"error": "Missing GCS URI or settings"}), 400

        # Initialize the client inside the function
        publisher = pubsub_v1.PublisherClient(credentials=get_credentials())
        topic_path = publisher.topic_path(GCP_PROJECT_ID, PUB_SUB_TOPIC)
        
        message_data = json.dumps(data).encode("utf-8")
        
        future = publisher.publish(topic_path, message_data)
        future.result() # Wait for the message to be published.

        original_filename = data['settings'].get('original_filename', 'unknown.wav')
        processed_filename = f"processed/mastered_{original_filename}"
        
        return jsonify({"message": "Processing job started.", "processed_filename": processed_filename}), 200

    except Exception as e:
        print(f"CRITICAL ERROR in /start-processing: {e}")
        return jsonify({"error": f"Internal server error: {e}"}), 500
        
@app.route('/status', methods=['GET'])
def get_status():
    """Checks if a processed file exists and provides a secure download link."""
    from google.cloud import storage
    
    filename = request.args.get('filename')
    if not filename:
        return jsonify({"error": "Filename parameter is required"}), 400
        
    try:
        storage_client = storage.Client(credentials=get_credentials(), project=GCP_PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        
        # Check for the ".complete" flag file first.
        complete_flag_blob = bucket.blob(f"{filename}.complete")
        if not complete_flag_blob.exists():
            return jsonify({"status": "processing"}), 200

        # If the flag exists, generate the download URL for the actual audio file.
        audio_blob = bucket.blob(filename)
        if not audio_blob.exists():
             return jsonify({"status": "error", "message": "Processing complete but output file is missing."}), 404
        
        download_url = audio_blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=60), # Link is valid for 1 hour
            method="GET",
            service_account_email=SERVICE_ACCOUNT_EMAIL,
            access_token=None, # Let the library handle the token
        )
        return jsonify({"status": "done", "download_url": download_url}), 200

    except Exception as e:
        print(f"CRITICAL ERROR in /status check: {e}")
        return jsonify({"status": "error", "message": f"Internal server error: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))