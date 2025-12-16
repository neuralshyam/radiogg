#!/bin/bash
set -e

service cron start

echo "Preparing Icecast logging..."
mkdir -p /var/log/icecast2
touch /var/log/icecast2/error.log /var/log/icecast2/access.log
chown -R nobody:nogroup /var/log/icecast2

echo "Starting Icecast..."
icecast2 -c /etc/icecast2/icecast.xml &

sleep 5

echo "Starting Liquidsoap..."
liquidsoap /app/liquidsoap.liq &

sleep 5

echo "Starting FFmpeg HLS..."
ffmpeg -loglevel warning -re \
  -i http://localhost:8000/stream.mp3 \
  -c:a copy \
  -f hls \
  -hls_time 6 \
  -hls_list_size 15 \
  -hls_flags delete_segments \
  /app/hls/stream.m3u8
