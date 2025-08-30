# backend/app.py
# Final, robust version with environment-aware authentication and detailed logging.

import os
import json
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import storage, pubsub_v1
from google.oauth2 import service_account

# --- Constants ---
# The ID of your Pub/Sub topic.
TOPIC_ID = "mastering-jobs" 
# The name of your Cloud Storage bucket.
BUCKET_NAME = "tactile-temple-395019-audio-uploads"

app = Flask(__name__)
# Enable CORS for all domains on all routes, which is necessary for our public frontend.
CORS(app, resources={r"/*": {"origins": "*"}})

# --- Authentication ---
# This block determines how the application authenticates to Google Cloud.
if os.environ.get('K_SERVICE'):
    # We are in the Google Cloud Run environment.
    # Use the attached service account's identity, which is the best practice.
    print("Running in Cloud Run environment, using default credentials.")
    storage_client = storage.Client()
    publisher = pubsub_v1.PublisherClient()
    # The project ID is automatically detected from the environment.
    PROJECT_ID = os.environ.get('GCP_PROJECT') 
else:
    # We are running locally on a developer's machine.
    # Use the downloaded service account key file for authentication.
    print("Running in local environment, using service account key file.")
    KEY_FILE_PATH = 'service-account-key.json'
    credentials = service_account.Credentials.from_service_account_file(KEY_FILE_PATH)
    storage_client = storage.Client(credentials=credentials)
    publisher = pubsub_v1.PublisherClient(credentials=credentials)
    # The project ID is read from the key file.
    PROJECT_ID = credentials.project_id

# Construct the full topic path that the publisher will use.
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

@app.route('/')
def hello_world():
    """A simple health check endpoint to confirm the server is running."""
    return 'Audio Mastering Backend is running.'

@app.route('/generate-upload-url', methods=['POST'])
def generate_upload_url():
    """
    Generates a secure, short-lived URL that the frontend can use to upload a file
    directly to Google Cloud Storage. This is the professional, scalable approach.
    """
    try:
        data = request.get_json()
        if not data or 'filename' not in data:
            return jsonify({"error": "Filename is required."}), 400

        filename = data['filename']
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)

        # Generate the V4 signed URL for a PUT request.
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=300,  # 5 minutes
            method="PUT",
            content_type=data.get('contentType', 'application/octet-stream')
        )
        return jsonify({"signedUrl": signed_url, "filename": filename}), 200

    except Exception as e:
        print(f"CRITICAL ERROR in /generate-upload-url: {e}")
        return jsonify({"error": "Failed to generate upload URL."}), 500

@app.route('/start-processing', methods=['POST'])
def start_processing():
    """
    Once the frontend confirms the file is uploaded, this endpoint sends a
    "job ticket" to the Pub/Sub topic to trigger the background worker.
    """
    try:
        data = request.get_json()
        if not data or 'filename' not in data:
            return jsonify({"error": "Filename is required."}), 400

        # The message sent to the worker includes the filename and all mastering settings.
        message_data = json.dumps(data).encode("utf-8")

        # --- FINAL DEBUGGING STEP ---
        # Log the exact topic path we are about to use.
        print(f"Publishing job to topic: {topic_path}")
        
        # Publish the message to the Pub/Sub topic.
        future = publisher.publish(topic_path, data=message_data)
        
        # future.result() waits for the publish to complete and will raise an exception on failure.
        future.result() 

        return jsonify({"message": "Processing job has been successfully submitted."}), 200

    except Exception as e:
        print(f"CRITICAL ERROR in /start-processing: {e}")
        return jsonify({"error": "Failed to submit processing job."}), 500

@app.route('/status', methods=['GET'])
def get_status():
    """
    Checks if the mastered file is ready and provides a secure download link.
    The frontend polls this endpoint every few seconds.
    """
    try:
        filename = request.args.get('filename')
        if not filename:
            return jsonify({"error": "Filename is required."}), 400

        processed_filename = f"processed/{filename}"
        bucket = storage_client.bucket(BUCKET_NAME)
        
        # Check for the ".complete" flag file, which is a more reliable signal.
        flag_blob = bucket.blob(f"{processed_filename}.complete")

        if flag_blob.exists():
            # If the flag exists, the job is done. Generate a secure download link.
            audio_blob = bucket.blob(processed_filename)
            download_url = audio_blob.generate_signed_url(
                version="v4",
                expiration=3600,  # 1 hour
                method="GET"
            )
            return jsonify({"status": "complete", "downloadUrl": download_url}), 200
        else:
            # The job is not done yet.
            return jsonify({"status": "processing"}), 202

    except Exception as e:
        print(f"CRITICAL ERROR in /status: {e}")
        return jsonify({"error": "Failed to get job status."}), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
