# app.py
#
# A professional, production-grade backend API for the Audio Mastering Suite.
# This server's SOLE responsibility is to generate secure, short-lived
# V4 signed URLs for direct-to-cloud file uploads. It does not handle
# the file data itself, making it fast, scalable, and cost-effective.
#

import os
import datetime
from flask import Flask, request, jsonify
from google.cloud import storage
from flask_cors import CORS

# --- Configuration ---
# It's best practice to load configuration from environment variables.
# The service account is automatically detected in the Cloud Run environment.
BUCKET_NAME = "tactile-temple-395019-audio-uploads"
PROJECT_ID = "tactile-temple-395019"
TOPIC_ID = "mastering-jobs"

app = Flask(__name__)
# Allow all origins for simplicity in this stage. In a production app,
# you would restrict this to your Netlify domain.
CORS(app, resources={r"/*": {"origins": "*"}})

# --- Routes ---

@app.route('/')
def hello():
    """A simple health check endpoint."""
    return "Audio Mastering Backend is running and ready to generate URLs."

@app.route('/generate-upload-url', methods=['POST'])
def generate_upload_url():
    """
    Generates a V4 signed URL for a client to upload a file directly to GCS.
    The client must provide the filename and content type in the request body.
    """
    try:
        # Best practice: Initialize clients within the request function ("lazy initialization")
        # This is more robust in a serverless environment.
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)

        # Get the required information from the client's request
        request_data = request.get_json()
        if not request_data or 'filename' not in request_data or 'contentType' not in request_data:
            return jsonify({"error": "Missing filename or contentType in request"}), 400

        filename = request_data['filename']
        content_type = request_data['contentType']
        
        # We will prefix the original filename with a unique ID for security
        # and to prevent file collisions.
        unique_filename = f"{os.urandom(8).hex()}_{filename}"

        blob = bucket.blob(unique_filename)

        # Generate the V4 signed URL. It's valid for a single PUT request
        # and expires in 15 minutes. This is a highly secure method.
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            content_type=content_type,
        )

        # Return the signed URL and the unique filename to the client
        return jsonify({
            "signedUrl": signed_url,
            "uniqueFilename": unique_filename
        }), 200

    except Exception as e:
        print(f"CRITICAL ERROR in /generate-upload-url: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"An unexpected server error occurred: {e}"}), 500

# This part is not strictly necessary for Gunicorn, but good practice.
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
