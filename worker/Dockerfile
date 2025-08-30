# Use Google's official, certified Python runtime as a parent image.
FROM gcr.io/google-appengine/python

# Install system dependencies required by pydub (the audio library)
# THIS LINE IS UNIQUE TO THE WORKER
RUN apt-get update && apt-get install -y ffmpeg

# Set the working directory IN THE CONTAINER. This is where the app will live.
WORKDIR /app

# Copy all the files from the build context (the worker/ folder) into the container.
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Use Gunicorn as the production-grade web server to run our worker app
# THIS LINE IS UNIQUE TO THE WORKER (it points to main:app)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]

