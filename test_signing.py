# test_signing.py
# A minimal script to test the generate_signed_url function.

import datetime
from google.cloud import storage

# --- CONFIGURATION ---
SERVICE_ACCOUNT_KEY_PATH = "service-account-key.json"
BUCKET_NAME = "tactile-temple-395019-audio-uploads"
# Use a file that you know exists in your bucket
FILE_NAME_TO_SIGN = "my_test_beat.wav" 

def test_url_signing():
    """
    Tries to generate a signed URL using the specified key file.
    """
    try:
        print("Attempting to create storage client from key file...")
        storage_client = storage.Client.from_service_account_json(SERVICE_ACCOUNT_KEY_PATH)
        
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"processed/{FILE_NAME_TO_SIGN}")

        print(f"Checking if blob 'processed/{FILE_NAME_TO_SIGN}' exists...")
        if not blob.exists():
            print(f"ERROR: The file 'processed/{FILE_NAME_TO_SIGN}' does not exist in the bucket.")
            print("Please process a file first, then run this test.")
            return

        print("Blob exists. Attempting to generate signed URL...")
        
        download_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="GET",
        )

        print("\n--- SUCCESS! ---")
        print("Successfully generated a signed URL:")
        print(download_url)

    except Exception as e:
        print("\n--- FAILED ---")
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    test_url_signing()