# app.py
#
# This final version forces the URL signing function to use the
# service account key directly by passing the credentials object.
#

import os
import json
import datetime
from flask import Flask, request, jsonify
from google.cloud import storage, pubsub_v1
from google.oauth2 import service_account # Import the service_account module
from flask_cors import CORS

# --- Configuration ---
BUCKET_NAME = "tactile-temple-395019-audio-uploads"
PROJECT_ID = "tactile-temple-395019"
TOPIC_ID = "mastering-jobs"
SERVICE_ACCOUNT_KEY_PATH = "service-account-key.json"

# Initialize Flask
app = Flask(__name__)
CORS(app)

# --- Initialize clients that don't need signing ---
try:
    # Use the key for the publisher, which is less problematic
    publisher = pubsub_v1.PublisherClient.from_service_account_json(SERVICE_ACCOUNT_KEY_PATH)
    storage_client_for_uploads = storage.Client.from_service_account_json(SERVICE_ACCOUNT_KEY_PATH)
    bucket_for_uploads = storage_client_for_uploads.bucket(BUCKET_NAME)
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
except FileNotFoundError:
    print(f"FATAL ERROR: The service account key file was not found at '{SERVICE_ACCOUNT_KEY_PATH}'")
    exit()

@app.route('/')
def hello_world():
    return 'Hello, the mastering server is running!'

@app.route('/upload', methods=['POST'])
def upload_file():
    # This function remains the same
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    settings_str = request.form.get('settings')

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    if not settings_str:
        return jsonify({"error": "No settings received"}), 400

    if file:
        try:
            blob = bucket_for_uploads.blob(file.filename)
            blob.upload_from_file(file)
            print(f"File '{file.filename}' uploaded to bucket '{BUCKET_NAME}'.")

            settings = json.loads(settings_str)
            message_data = {
                "gcs_uri": f"gs://{BUCKET_NAME}/{file.filename}",
                "file_name": file.filename,
                "bucket_name": BUCKET_NAME,
                "settings": settings
            }
            
            future = publisher.publish(topic_path, data=json.dumps(message_data).encode("utf-8"))
            future.result()

            print(f"Job for '{file.filename}' published to topic '{TOPIC_ID}'.")
            
            return jsonify({
                "message": f"File '{file.filename}' uploaded and sent for processing!",
                "original_filename": file.filename
            }), 200

        except Exception as e:
            print(f"An error occurred during upload: {e}")
            return jsonify({"error": f"An error occurred during upload: {e}"}), 500

@app.route('/status', methods=['GET'])
def get_status():
    original_filename = request.args.get('filename')
    if not original_filename:
        return jsonify({"error": "Filename parameter is missing"}), 400

    try:
        # --- THIS IS THE CRUCIAL CHANGE ---
        # 1. Create a credentials object directly from the key file.
        credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_KEY_PATH)
        
        # 2. Create a storage client using these specific credentials.
        signing_client = storage.Client(credentials=credentials)
        bucket = signing_client.bucket(BUCKET_NAME)
        # --- END OF CHANGE ---

        complete_blob_name = f"processed/{original_filename}.complete"
        complete_blob = bucket.blob(complete_blob_name)

        if not complete_blob.exists():
            return jsonify({"status": "processing"}), 200
        
        mastered_blob_name = f"processed/{original_filename}"
        mastered_blob = bucket.blob(mastered_blob_name)
        
        # 3. Use the credentials object to sign the URL.
        download_url = mastered_blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="GET",
            credentials=credentials, # Explicitly pass the credentials here
        )
        
        complete_blob.delete()
        
        return jsonify({
            "status": "complete",
            "download_url": download_url
        }), 200
        
    except Exception as e:
        print(f"Error in status check: {e}")
        return jsonify({"error": f"Could not generate download link: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
