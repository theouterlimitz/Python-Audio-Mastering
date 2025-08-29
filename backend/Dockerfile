# Use the full Debian base image for compatibility
FROM python:3.11-bullseye

# Install system dependencies required by pydub
RUN apt-get update && apt-get install -y ffmpeg

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code
COPY . .

# --- FORENSIC STARTUP COMMAND ---
# This is a temporary command to force the real startup error into the logs.
# It will be replaced with the Gunicorn command once we find and fix the bug.
CMD ["sh", "-c", "echo '--- FORENSIC STARTUP ---' && ls -lR /app && echo '--- PYTHON VERSION ---' && python --version && echo '--- ATTEMPTING TO RUN APP ---' && python app.py"]
