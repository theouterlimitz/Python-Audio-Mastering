# app.py
#
# A professional, production-grade backend API for the Audio Mastering Suite.
# This final version uses Google Secret Manager to securely load the service
# account key with the private key needed for URL signing.
#

import os
import datetime
import json
import traceback
from flask import Flask, request, jsonify
from google.cloud import storage, pubsub_v1, secretmanager
from google.oauth2 import service_account
from flask_cors import CORS

# --- Configuration ---
PROJECT_ID = "tactile-temple-395019"
BUCKET_NAME = "tactile-temple-395019-audio-uploads"
TOPIC_ID = "mastering-jobs"
SECRET_ID = "backend-sa-key"
SECRET_VERSION_ID = "latest"

# --- Global Variables ---
# We will load the credentials on startup. If this fails, the container
# will crash, and the logs will show the error immediately.
credentials = None

def access_secret_version():
    """Access the secret from Secret Manager and load credentials."""
    try:
        print("STEP 1: Initializing Secret Manager client...")
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{PROJECT_ID}/secrets/{SECRET_ID}/versions/{SECRET_VERSION_ID}"
        
        print(f"STEP 2: Accessing secret: {name}")
        response = client.access_secret_version(request={"name": name})
        
        print("STEP 3: Secret accessed. Decoding payload...")
        secret_payload = response.payload.data.decode("UTF-8")
        secret_json = json.loads(secret_payload)
        
        print("STEP 4: Creating credentials from secret JSON...")
        creds = service_account.Credentials.from_service_account_info(secret_json)
        
        print("SUCCESS: Credentials loaded successfully from Secret Manager.")
        return creds
    except Exception as e:
        print(f"CRITICAL STARTUP ERROR: Failed to load credentials from Secret Manager. {e}")
        traceback.print_exc()
        # Raise the exception to ensure the container crashes and we see the error.
        raise

# Load credentials on application startup.
credentials = access_secret_version()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# --- Routes ---

@app.route('/')
def hello():
    """A simple health check endpoint."""
    return "Audio Mastering Backend is running."

@app.route('/generate-upload-url', methods=['POST'])
def generate_upload_url():
    try:
        storage_client = storage.Client(credentials=credentials)
        bucket = storage_client.bucket(BUCKET_NAME)

        request_data = request.get_json()
        if not request_data or 'filename' not in request_data:
             return jsonify({"error": "Missing filename in request"}), 400

        filename = request_data['filename']
        content_type = request_data.get('contentType', 'application/octet-stream')
        unique_filename = f"{os.urandom(8).hex()}_{filename}"
        blob = bucket.blob(unique_filename)

        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            content_type=content_type,
            credentials=credentials # Explicitly use the loaded credentials
        )
        return jsonify({"signedUrl": signed_url, "uniqueFilename": unique_filename}), 200
    except Exception as e:
        print(f"ERROR in /generate-upload-url: {e}")
        traceback.print_exc()
        return jsonify({"error": "Server failed to generate upload URL."}), 500

@app.route('/start-processing', methods=['POST'])
def start_processing():
    try:
        publisher = pubsub_v1.PublisherClient(credentials=credentials)
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

        request_data = request.get_json()
        if not request_data or 'filename' not in request_data or 'settings' not in request_data:
            return jsonify({"error": "Missing filename or settings in request"}), 400

        job_data = { "filename": request_data['filename'], "settings": request_data['settings'] }
        message_data = json.dumps(job_data).encode("utf-8")
        future = publisher.publish(topic_path, message_data)
        future.result()

        return jsonify({"message": "Processing job started successfully."}), 200
    except Exception as e:
        print(f"ERROR in /start-processing: {e}")
        traceback.print_exc()
        return jsonify({"error": "Server failed to start processing job."}), 500

@app.route('/status', methods=['GET'])
def get_status():
    try:
        filename = request.args.get('filename')
        if not filename:
            return jsonify({"error": "Filename parameter is required"}), 400

        storage_client = storage.Client(credentials=credentials)
        bucket = storage_client.bucket(BUCKET_NAME)
        signal_blob = bucket.blob(f"processed/{filename}.complete")
        
        if signal_blob.exists():
            audio_blob = bucket.blob(f"processed/{filename}")
            if audio_blob.exists():
                download_url = audio_blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.timedelta(minutes=60),
                    method="GET",
                    credentials=credentials # Explicitly use the loaded credentials
                )
                return jsonify({"status": "ready", "downloadUrl": download_url})
            else:
                 return jsonify({"status": "processing", "message": "Signal found but audio file is missing."})
        else:
            return jsonify({"status": "processing"})
    except Exception as e:
        print(f"ERROR in /status: {e}")
        traceback.print_exc()
        return jsonify({"error": "Server failed to get job status."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
