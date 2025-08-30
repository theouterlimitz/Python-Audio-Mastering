# backend/app.py
# Final version using Google Secret Manager for robust, secure credential handling.
# This is the industry-standard, architecturally correct solution.

import os
import json
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import storage, pubsub_v1, secretmanager
from google.oauth2 import service_account

# --- Constants ---
PROJECT_ID = "tactile-temple-395019"
SECRET_ID = "backend-sa-key"  # The name of the secret you created in Secret Manager.
TOPIC_ID = "mastering-jobs"
BUCKET_NAME = "tactile-temple-395019-audio-uploads"

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# --- Secure Credential Loading ---
# This is the core of our fix. This block runs ONCE when the server starts.
# It securely retrieves our powerful service account key from the vault (Secret Manager).
def access_secret_version(project_id, secret_id, version_id="latest"):
    """Access the payload for the given secret version."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

print("Attempting to load credentials from Secret Manager...")
try:
    # Retrieve the secret JSON string from the vault.
    key_json_str = access_secret_version(PROJECT_ID, SECRET_ID)
    # Load the JSON string into a dictionary.
    key_info = json.loads(key_json_str)
    # Create the powerful credentials object from the key.
    credentials = service_account.Credentials.from_service_account_info(key_info)
    
    # Initialize our clients using these powerful, explicit credentials.
    storage_client = storage.Client(credentials=credentials)
    publisher = pubsub_v1.PublisherClient(credentials=credentials)
    
    print("Successfully loaded credentials and initialized clients from Secret Manager.")
except Exception as e:
    print(f"CRITICAL STARTUP ERROR: Could not initialize credentials from Secret Manager. {e}")
    # We will let the application crash here if it can't get its credentials.
    # This is better than running in a broken state.
    raise e

# Construct the full topic path that the publisher will use.
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

@app.route('/')
def hello_world():
    """A simple health check endpoint to confirm the server is running."""
    return 'Audio Mastering Backend is running.'

@app.route('/generate-upload-url', methods=['POST'])
def generate_upload_url():
    """Generates a secure, short-lived URL for direct-to-cloud uploads."""
    try:
        data = request.get_json()
        filename = data['filename']
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)

        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=300,  # 5 minutes
            method="PUT",
            content_type=data.get('contentType', 'application/octet-stream')
        )
        return jsonify({"signedUrl": signed_url, "filename": filename}), 200
    except Exception as e:
        print(f"ERROR in /generate-upload-url: {e}")
        return jsonify({"error": "Failed to generate upload URL."}), 500

@app.route('/start-processing', methods=['POST'])
def start_processing():
    """Sends a job ticket to the Pub/Sub topic to trigger the worker."""
    try:
        data = request.get_json()
        message_data = json.dumps(data).encode("utf-8")
        future = publisher.publish(topic_path, data=message_data)
        future.result()  # Wait for the publish to complete.
        return jsonify({"message": "Processing job has been successfully submitted."}), 200
    except Exception as e:
        print(f"ERROR in /start-processing: {e}")
        return jsonify({"error": "Failed to submit processing job."}), 500

@app.route('/status', methods=['GET'])
def get_status():
    """Checks for the processed file and provides a secure download link."""
    try:
        filename = request.args.get('filename')
        processed_filename = f"processed/{filename}"
        bucket = storage_client.bucket(BUCKET_NAME)
        flag_blob = bucket.blob(f"{processed_filename}.complete")

        if flag_blob.exists():
            audio_blob = bucket.blob(processed_filename)
            download_url = audio_blob.generate_signed_url(
                version="v4",
                expiration=3600,  # 1 hour
                method="GET"
            )
            return jsonify({"status": "complete", "downloadUrl": download_url}), 200
        else:
            return jsonify({"status": "processing"}), 202
    except Exception as e:
        print(f"ERROR in /status: {e}")
        return jsonify({"error": "Failed to get job status."}), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))