#!/bin/bash
set -e

MEGA_LINK="https://mega.nz/folder/Hxo1RaTL#qojarvoO1mODsQIdc7V2mQ"

echo "$(date) - Updating music from MEGA..."

megadl "$MEGA_LINK" \
  --path /app/music \
  --no-progress \
  --continue

echo "$(date) - MEGA update done!"
