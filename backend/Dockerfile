# Use an official Python 3.11 runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code
COPY . .

# Define environment variable for the port
ENV PORT 8080

# Use Gunicorn as the production web server
# This is more robust than the Flask development server
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
