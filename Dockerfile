FROM python:3.10-slim

# Install ffmpeg, curl, rclone
RUN apt-get update && \
    apt-get install -y ffmpeg curl unzip && \
    curl https://rclone.org/install.sh | bash && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
COPY rclone.conf .config/rclone/rclone.conf
# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
