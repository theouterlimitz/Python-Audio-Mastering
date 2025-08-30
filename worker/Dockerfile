# Use Google's official, certified Python runtime as a parent image.
# This ensures all necessary system libraries for Google Cloud are included.
FROM gcr.io/google-appengine/python

# Install system dependencies required by pydub (the audio library)
RUN apt-get update && apt-get install -y ffmpeg

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code
COPY . .

# Use Gunicorn as the production-grade web server to run our worker app
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
