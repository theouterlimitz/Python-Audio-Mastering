# app.py
    #
    # This final version uses environment-aware authentication and has a
    # robust CORS policy for the public frontend.
    #

    import os
    import json
    import datetime
    from flask import Flask, request, jsonify
    from google.cloud import storage, pubsub_v1
    from google.oauth2 import service_account
    from flask_cors import CORS

    # --- Configuration ---
    BUCKET_NAME = "tactile-temple-395019-audio-uploads"
    PROJECT_ID = "tactile-temple-395019"
    TOPIC_ID = "mastering-jobs"
    SERVICE_ACCOUNT_KEY_PATH = "service-account-key.json"

    # Initialize Flask
    app = Flask(__name__)
    # --- THIS IS THE CRUCIAL LINE ---
    # Allow all origins to access all routes.
    CORS(app, resources={r"/*": {"origins": "*"}})

    # --- Environment-Aware Authentication ---
    if os.environ.get('K_SERVICE'):
        # We are in the Google Cloud Run environment
        print("Running in Cloud Run environment. Using default credentials.")
        storage_client = storage.Client()
        publisher = pubsub_v1.PublisherClient()
    else:
        # We are running locally
        print(f"Running in local environment. Using key from '{SERVICE_ACCOUNT_KEY_PATH}'.")
        try:
            credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_KEY_PATH)
            storage_client = storage.Client(credentials=credentials)
            publisher = pubsub_v1.PublisherClient(credentials=credentials)
        except FileNotFoundError:
            print(f"FATAL ERROR: Could not find '{SERVICE_ACCOUNT_KEY_PATH}'.")
            exit()

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
                future.result()
                
                return jsonify({
                    "message": f"File '{file.filename}' uploaded and sent for processing!",
                    "original_filename": file.filename
                }), 200

            except Exception as e:
                return jsonify({"error": f"An error occurred: {e}"}), 500

    @app.route('/status', methods=['GET'])
    def get_status():
        original_filename = request.args.get('filename')
        if not original_filename:
            return jsonify({"error": "Filename parameter is missing"}), 400

        complete_blob_name = f"processed/{original_filename}.complete"
        complete_blob = bucket.blob(complete_blob_name)

        if not complete_blob.exists():
            return jsonify({"status": "processing"}), 200
        
        mastered_blob_name = f"processed/{original_filename}"
        mastered_blob = bucket.blob(mastered_blob_name)
        
        try:
            download_url = mastered_blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(minutes=15),
                method="GET",
            )
            
            complete_blob.delete()
            
            return jsonify({
                "status": "complete",
                "download_url": download_url
            }), 200
            
        except Exception as e:
            return jsonify({"error": f"Could not generate download link: {e}"}), 500

    if __name__ == '__main__':
        app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))