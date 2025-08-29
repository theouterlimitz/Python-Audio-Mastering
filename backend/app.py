# app.py
#
# This final version uses a "lazy initialization" pattern to guarantee
# that the server starts successfully in the cloud environment.
# Cloud clients are created only when they are needed.
#

import os
import json
import datetime
from flask import Flask, request, jsonify
from google.cloud import storage, pubsub_v1
from flask_cors import CORS

# --- Configuration (remains global) ---
BUCKET_NAME = "tactile-temple-395019-audio-uploads"
PROJECT_ID = "tactile-temple-395019"
TOPIC_ID = "mastering-jobs"

# Initialize Flask App
app = Flask(__name__)
# Allow all origins for simplicity in this final step
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route('/')
def hello_world():
    return 'Hello, the mastering server is running!'

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        # LAZY INITIALIZATION: Create clients only when this function is called.
        storage_client = storage.Client()
        publisher = pubsub_v1.PublisherClient()
        bucket = storage_client.bucket(BUCKET_NAME)
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

        if 'file' not in request.files:
            return jsonify({"error": "No file part in the request"}), 400
        
        file = request.files['file']
        settings_str = request.form.get('settings')

        if file.filename == '' or not settings_str:
            return jsonify({"error": "Missing file or settings"}), 400

        
        blob = bucket.blob(file.filename)
        blob.upload_from_file(file)
        
        settings = json.loads(settings_str)
        message_data = {
            "gcs_uri": f"gs://{BUCKET_NAME}/{file.filename}",
            "file_name": file.filename,
            "bucket_name": BUCKET_NAME,
            "settings": settings
        }
        
        future = publisher.publish(topic_path, data=json.dumps(message_data).encode("utf-8"))
        future.result() # Wait for the message to be published
        
        return jsonify({
            "message": f"File '{file.filename}' uploaded and sent for processing!",
            "original_filename": file.filename
        }), 200

    except Exception as e:
        print(f"ERROR in /upload: {e}")
        return jsonify({"error": f"An error occurred: {e}"}), 500

@app.route('/status', methods=['GET'])
def get_status():
    try:
        # LAZY INITIALIZATION: Create a client only when this function is called.
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)

        original_filename = request.args.get('filename')
        if not original_filename:
            return jsonify({"error": "Filename parameter is missing"}), 400

        complete_blob_name = f"processed/{original_filename}.complete"
        complete_blob = bucket.blob(complete_blob_name)

        if not complete_blob.exists():
            return jsonify({"status": "processing"}), 200
        
        mastered_blob_name = f"processed/{original_filename}"
        mastered_blob = bucket.blob(mastered_blob_name)
        
        # NOTE: The service account for the Cloud Run service needs the
        # "Service Account Token Creator" role for this to work.
        download_url = mastered_blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="GET",
        )
        
        # Clean up the .complete file after generating the link
        complete_blob.delete()
        
        return jsonify({
            "status": "complete",
            "download_url": download_url
        }), 200
        
    except Exception as e:
        print(f"ERROR in /status: {e}")
        return jsonify({"error": f"Could not generate download link: {e}"}), 500

# This part is only for local development, not used by Gunicorn
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)

