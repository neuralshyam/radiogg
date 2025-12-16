FROM debian:12-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    icecast2 \
    liquidsoap \
    megatools \
    cron \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/log/icecast2 \
 && chown -R nobody:nogroup /var/log/icecast2

COPY icecast.xml /etc/icecast2/icecast.xml
COPY liquidsoap.liq /app/liquidsoap.liq
COPY start.sh /app/start.sh
COPY update-mega.sh /app/update-mega.sh

WORKDIR /app
RUN chmod +x start.sh update-mega.sh

RUN echo "0 3 * * * /app/update-mega.sh >> /var/log/mega_update.log 2>&1" \
    > /etc/cron.d/mega-cron && \
    chmod 0644 /etc/cron.d/mega-cron && \
    crontab /etc/cron.d/mega-cron

RUN mkdir -p /app/music /app/hls /var/log

CMD ["./start.sh"]
