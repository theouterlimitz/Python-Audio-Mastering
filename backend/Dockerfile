# Use the full Debian "Bullseye" version of the Python 3.11 image.
# This is a more robust base that includes all necessary system libraries.
FROM python:3.11-bullseye

# Install system dependencies required by pydub
RUN apt-get update && apt-get install -y ffmpeg

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code, ignoring the secret key
COPY . .

# Define environment variable for the port
ENV PORT 8080

# Run the application using Gunicorn when the container launches
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
