# Use Google's official, certified Python runtime as a parent image.
# This image is guaranteed to have all necessary system libraries for Google Cloud.
FROM gcr.io/google-appengine/python

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code
COPY . .

# Use Gunicorn as the production-grade web server
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
