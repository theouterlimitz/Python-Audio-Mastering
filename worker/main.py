# worker/main.py
# Final version that listens to Pub/Sub and calls the mastering engine.
# This is the complete and correct code for the audio processing worker.

import os
import json
import base64
from flask import Flask, request

# Import our existing mastering engine! This file must be in the same folder.
from audio_mastering_engine import process_audio_from_gcs

app = Flask(__name__)

@app.route('/', methods=['POST'])
def process_mastering_job():
    """
    Receives a Pub/Sub message, parses it, and calls the mastering engine.
    This is the entry point for all processing jobs.
    """
    envelope = request.get_json()
    if not envelope or 'message' not in envelope:
        print("ERROR: Invalid Pub/Sub message format")
        return "Bad Request: invalid Pub/Sub message format", 400

    try:
        # Pub/Sub messages are base64-encoded, so we must decode them.
        pubsub_message = base64.b64decode(envelope['message']['data']).decode('utf-8')
        job_data = json.loads(pubsub_message)
        
        gcs_uri = job_data.get('gcs_uri')
        settings = job_data.get('settings')

        if not gcs_uri or not settings:
            print(f"ERROR: Missing GCS URI or settings in job data: {job_data}")
            return "Bad Request: missing GCS URI or settings", 400

        print(f"Starting processing job for {gcs_uri} with settings: {settings}")
        process_audio_from_gcs(gcs_uri, settings)
        print(f"Successfully completed processing for {gcs_uri}")
        
        # Return a 204 Success (No Content) to acknowledge the message.
        # This tells Pub/Sub the job was handled and not to send it again.
        return "", 204

    except Exception as e:
        print(f"CRITICAL ERROR processing job: {e}")
        # We still return a success code so that Pub/Sub doesn't try to resend a failing message.
        # The error is logged for us to debug.
        return "", 204

if __name__ == "__main__":
    # The Gunicorn command in the Dockerfile will run this application.
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))