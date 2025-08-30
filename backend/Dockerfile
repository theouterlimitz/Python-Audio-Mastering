# Use Google's official, certified Python runtime as a parent image.
# This image is guaranteed to have all necessary system libraries for Google Cloud.
FROM gcr.io/google-appengine/python

# Set the working directory IN THE CONTAINER. This is where the app will live.
WORKDIR /app

# Copy all the files from the build context (the backend/ folder) into the container.
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Use Gunicorn as the production-grade web server.
# The timeout is increased to handle potentially slow initial requests.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "120", "app:app"]

