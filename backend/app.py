# final_test_app.py
#
# A minimal diagnostic tool to isolate the Secret Manager connection issue.
# This is our "known good" code for the final test.
#

import os
import traceback
from flask import Flask
from google.cloud import secretmanager

PROJECT_ID = "tactile-temple-395019"
SECRET_ID = "backend-sa-key"

app = Flask(__name__)

# --- Credential Loading Logic ---
# We will attempt to load the secret on startup.
# If this fails, the container will crash, and the logs will show the error.
try:
    print("--- STARTUP DIAGNOSTIC ---")
    print("STEP 1: Initializing Secret Manager client...")
    client = secretmanager.SecretManagerServiceClient()
    
    name = f"projects/{PROJECT_ID}/secrets/{SECRET_ID}/versions/latest"
    print(f"STEP 2: Preparing to access secret: {name}")
    
    response = client.access_secret_version(request={"name": name})
    
    secret_payload = response.payload.data.decode("UTF-8")
    
    print("STEP 3: Secret payload retrieved successfully.")
    
    if secret_payload:
        print("SUCCESS: Diagnostic tool started and successfully accessed the secret.")
        STARTUP_SUCCESS = True
    else:
        print("CRITICAL STARTUP ERROR: Secret payload was empty.")
        STARTUP_SUCCESS = False

except Exception as e:
    print(f"CRITICAL STARTUP ERROR: The application crashed while accessing Secret Manager.")
    traceback.print_exc()
    STARTUP_SUCCESS = False

# --- Routes ---
@app.route('/')
def hello():
    if STARTUP_SUCCESS:
        return "Diagnostic server is running. Secret was accessed successfully!"
    else:
        return "Diagnostic server is running, but FAILED to access the secret on startup. Check the logs.", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
