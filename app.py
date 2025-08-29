# app.py
#
# This final version adds the /status endpoint for the frontend to poll,
# and logic to generate a secure download link.
#

import os
import json
import datetime
from flask import Flask, request, jsonify
from google.cloud import storage, pubsub_v1
from flask_cors import CORS

# --- Configuration ---
BUCKET_NAME = "tactile-temple-395019-audio-uploads"
PROJECT_ID = "tactile-temple-395019"
TOPIC_ID = "mastering-jobs"

# Initialize Flask and clients
app = Flask(__name__)
CORS(app)

storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()
bucket = storage_client.bucket(BUCKET_NAME)
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

@app.route('/')
def hello_world():
    return 'Hello, the mastering server is running!'

@app.route('/upload', methods=['POST'])
def upload_file():
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
            # 1. Upload the original file to Cloud Storage
            blob = bucket.blob(file.filename)
            blob.upload_from_file(file)
            print(f"File '{file.filename}' uploaded to bucket '{BUCKET_NAME}'.")

            # 2. Prepare the job message for the worker
            settings = json.loads(settings_str)
            message_data = {
                "gcs_uri": f"gs://{BUCKET_NAME}/{file.filename}",
                "file_name": file.filename,
                "bucket_name": BUCKET_NAME,
                "settings": settings
            }
            
            # 3. Publish the job to the Pub/Sub topic
            future = publisher.publish(topic_path, data=json.dumps(message_data).encode("utf-8"))
            future.result()

            print(f"Job for '{file.filename}' published to topic '{TOPIC_ID}'.")
            
            # Return the original filename to the frontend so it knows what to poll for
            return jsonify({
                "message": f"File '{file.filename}' uploaded and sent for processing!",
                "original_filename": file.filename
            }), 200

        except Exception as e:
            print(f"An error occurred: {e}")
            return jsonify({"error": f"An error occurred: {e}"}), 500

@app.route('/status', methods=['GET'])
def get_status():
    """
    Checks if a processed file is ready and returns a download link if it is.
    """
    original_filename = request.args.get('filename')
    if not original_filename:
        return jsonify({"error": "Filename parameter is missing"}), 400

    # Check for the existence of the ".complete" signal file
    complete_blob_name = f"processed/{original_filename}.complete"
    complete_blob = bucket.blob(complete_blob_name)

    if not complete_blob.exists():
        return jsonify({"status": "processing"}), 200
    
    # If the .complete file exists, the audio is ready.
    # Generate a signed URL for the mastered audio file.
    mastered_blob_name = f"processed/{original_filename}"
    mastered_blob = bucket.blob(mastered_blob_name)
    
    try:
        # This URL is secure and will expire in 15 minutes.
        download_url = mastered_blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="GET",
        )
        
        # Clean up the signal file after generating the link
        complete_blob.delete()
        
        return jsonify({
            "status": "complete",
            "download_url": download_url
        }), 200
        
    except Exception as e:
        print(f"Error generating signed URL: {e}")
        return jsonify({"error": f"Could not generate download link: {e}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
