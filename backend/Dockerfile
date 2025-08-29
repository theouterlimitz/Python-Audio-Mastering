# --- Stage 1: The Builder ---
# This stage is a clean environment whose only job is to install our dependencies.
FROM python:3.11-bullseye as builder

# Set the working directory
WORKDIR /install

# Copy only the requirements file
COPY requirements.txt .

# Install the packages into a temporary directory
RUN pip install --no-cache-dir --prefix="/install" -r requirements.txt


# --- Stage 2: The Final Production Image ---
# This is our final, lean application environment.
FROM python:3.11-bullseye

# Install system dependencies required by pydub
RUN apt-get update && apt-get install -y ffmpeg

# Set the working directory in the final container
WORKDIR /app

# Copy the pre-installed packages from the "builder" stage
COPY --from=builder /install /usr/local

# Copy the rest of the application's code
COPY . .

# Define environment variable for the port
ENV PORT 8080

# Run the application with the Gunicorn production server.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
