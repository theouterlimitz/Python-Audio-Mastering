# app.py
#
# A minimal diagnostic tool to isolate the Google Cloud client startup issue.
# Its only job is to try to import and initialize the storage client
# and report success or failure.
#

from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# We will try to initialize the client here, at the global scope.
# This will either succeed or cause a crash that we can finally see.
try:
    print("Attempting to import google.cloud.storage...")
    from google.cloud import storage
    print("Import successful. Attempting to initialize client...")
    storage_client = storage.Client()
    print("SUCCESS: Storage client initialized without errors.")
    CLIENT_INITIALIZED = True
except Exception as e:
    print("--- CRITICAL STARTUP ERROR ---")
    import traceback
    traceback.print_exc()
    print(f"Failed to initialize storage client: {e}")
    print("----------------------------")
    CLIENT_INITIALIZED = False

@app.route('/')
def hello():
    if CLIENT_INITIALIZED:
        return "Diagnostic server is running. Storage client was initialized successfully!"
    else:
        return "Diagnostic server is running, but FAILED to initialize the storage client. Check the logs.", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
