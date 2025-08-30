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

# Define environment variable for the port
ENV PORT 8080

# Run the application with the Gunicorn production server.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]

