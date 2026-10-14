FROM python:3.14-slim

# Python behaviour in containers:
# - don't write .pyc files
# - print logs immediately (no buffering), so `docker compose logs` works in real time
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System libraries needed by audio/video processing (Essentia, MediaPipe, ffmpeg)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first, so this layer is cached
# and only rebuilt when the requirements file changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project code last
COPY . .

# Documentation only: the port Django listens on
EXPOSE 8000