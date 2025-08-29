# Use an official Python 3.11 runtime as a parent image
FROM python:3.11-slim

# Install system dependencies required by pydub
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg

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

# Run the application when the container launches
CMD ["python", "main.py"]
