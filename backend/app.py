# app.py
# A minimal test to isolate the file upload functionality.
# This version ONLY attempts to upload to Google Cloud Storage.

import os
from flask import Flask, request, jsonify
from google.cloud import storage
from flask_cors import CORS

BUCKET_NAME = "tactile-temple-395019-audio-uploads"

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route('/')
def hello():
    return "Minimal Upload Test Server is running!"

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        print("Upload endpoint hit. Initializing GCS client.")
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        
        if 'file' not in request.files:
            print("ERROR: No file part in the request.")
            return jsonify({"error": "No file part in the request"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            print("ERROR: No file selected.")
            return jsonify({"error": "No file selected"}), 400
        
        print(f"File received: {file.filename}. Uploading to GCS bucket: {BUCKET_NAME}")
        
        blob = bucket.blob(file.filename)
        blob.upload_from_file(file.stream) # Use file.stream for better compatibility
        
        print(f"SUCCESS: File '{file.filename}' uploaded to gs://{BUCKET_NAME}/{file.filename}")
        
        return jsonify({
            "message": f"Minimal Test Success: File '{file.filename}' uploaded!",
            "gcs_uri": f"gs://{BUCKET_NAME}/{file.filename}"
        }), 200

    except Exception as e:
        # This will print the exact error to the Cloud Run logs
        print(f"CRITICAL ERROR in /upload: {e}")
        # Also print the traceback for detailed debugging
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

# This part is only for local development, not used by Gunicorn
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
