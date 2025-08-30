# Use Google's official, certified Python runtime as a parent image.
FROM gcr.io/google-appengine/python

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file using the full path from the repo root
COPY backend/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend application's code using the full path
COPY backend/app.py .

# Use Gunicorn as the production-grade web server
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]

