FROM python:3.12-slim

WORKDIR /app

# Install yt-dlp and system deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir yt-dlp

# Install yt-dlp binary
RUN pip install --no-cache-dir yt-dlp

COPY . .

# Create data and temp directories
RUN mkdir -p /app/data /tmp/yt2vk

VOLUME ["/app/data"]

CMD ["python", "main.py"]
