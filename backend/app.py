# backend/app.py
# A special diagnostic "canary" script to isolate the Pub/Sub connection issue.
# This is a temporary tool for our SRE investigation.

import os
import json
from flask import Flask, jsonify
from flask_cors import CORS
from google.cloud import pubsub_v1

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# --- Constants ---
# We will hardcode these to ensure there are no typos from the frontend.
PROJECT_ID = "tactile-temple-395019"
TOPIC_ID = "mastering-jobs"

print("Canary script loaded. Server is starting.")

@app.route('/')
def hello_world():
    """Confirms the server is alive."""
    return 'Pub/Sub Canary Test Server is running.'

@app.route('/test-pubsub', methods=['POST'])
def test_pubsub():
    """
    The only job of this function is to try and publish a message.
    It will log every step of the process.
    """
    print("--- Received request for /test-pubsub ---")
    try:
        print("STEP 1: Initializing Pub/Sub PublisherClient...")
        publisher = pubsub_v1.PublisherClient()
        print("SUCCESS: PublisherClient initialized.")

        print(f"STEP 2: Constructing topic path for project '{PROJECT_ID}' and topic '{TOPIC_ID}'...")
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
        print(f"SUCCESS: Constructed topic path: {topic_path}")

        message_data = json.dumps({"test": "canary", "status": "testing"}).encode("utf-8")
        print("STEP 3: Attempting to publish message...")
        future = publisher.publish(topic_path, data=message_data)
        
        # This is the line that was failing before.
        message_id = future.result()
        print(f"SUCCESS: Message published with ID: {message_id}")

        return jsonify({"status": "SUCCESS", "message_id": message_id}), 200

    except Exception as e:
        # If ANY error occurs, we will log it with a full traceback.
        print("--- CRITICAL ERROR in /test-pubsub ---")
        import traceback
        traceback.print_exc() # This prints the full error to the logs.
        return jsonify({"status": "ERROR", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))