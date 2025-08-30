# Use Google's official, certified Python runtime as a parent image.
FROM gcr.io/google-appengine/python

# Set the working directory IN THE CONTAINER. This is where the app will live.
WORKDIR /app

# Copy all the files from the build context (the backend/ folder) into the container.
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Use Gunicorn as the production-grade web server
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]

