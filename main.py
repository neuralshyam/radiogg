import os
import glob
import time
import threading
import subprocess
import requests
import sys
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse

# Disable output buffering
sys.stdout.flush()
sys.stderr.flush()

# ---------- CONFIG ----------
AUDIO_SITE_URL = "https://scd-1.pages.dev/"
MUSIC_DIR = "/app/music"
SYNC_INTERVAL = 24 * 3600  # seconds
STREAM_CHUNK_SIZE = 4096

# Make sure directories exist
os.makedirs(MUSIC_DIR, exist_ok=True)

app = FastAPI()
CURRENT_TRACK = None
FFMPEG_PROCESS = None
AUDIO_TRACKS = []

# ---------- FETCH AUDIO TRACKS ----------
def fetch_audio_tracks():
    """
    Fetches the list of audio tracks from the website.
    """
    global AUDIO_TRACKS
    try:
        print("[INFO] Fetching audio tracks from website...")
        response = requests.get(AUDIO_SITE_URL, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.find_all('a', href=True)
        
        tracks = []
        for link in links:
            href = link['href']
            # Filter for audio files
            if href.endswith('.m4a') or href.endswith('.mp3'):
                full_url = AUDIO_SITE_URL.rstrip('/') + '/' + href.lstrip('/')
                tracks.append(full_url)
        
        AUDIO_TRACKS = sorted(tracks)
        print(f"[INFO] Found {len(AUDIO_TRACKS)} audio tracks")
        for track in AUDIO_TRACKS[:5]:  # Print first 5
            print(f"  - {track}")
        if len(AUDIO_TRACKS) > 5:
            print(f"  ... and {len(AUDIO_TRACKS) - 5} more")
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch tracks: {e}")
        AUDIO_TRACKS = []

# ---------- SYNC LOOP ----------
def sync_loop():
    """
    Periodically fetches the list of available audio tracks.
    """
    fetch_audio_tracks()  # Initial fetch
    while True:
        time.sleep(SYNC_INTERVAL)
        fetch_audio_tracks()

# ---------- RADIO LOOP ----------
def start_radio():
    """
    Loops through audio tracks and streams them live via FFmpeg.
    All listeners hear the same track at the same time.
    """
    global CURRENT_TRACK, FFMPEG_PROCESS
    while True:
        if not AUDIO_TRACKS:
            print("[WARN] No tracks available. Waiting 30 seconds...")
            time.sleep(30)
            continue
        
        for track_url in AUDIO_TRACKS:
            CURRENT_TRACK = track_url
            track_name = track_url.split('/')[-1]
            print(f"[INFO] Now playing: {track_name}")
            
            try:
                FFMPEG_PROCESS = subprocess.Popen([
                    "ffmpeg", "-re", "-i", track_url,
                    "-f", "mp3", "-b:a", "128k",
                    "pipe:1"
                ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                
                FFMPEG_PROCESS.wait()
            except Exception as e:
                print(f"[ERROR] FFmpeg failed: {e}")
            finally:
                FFMPEG_PROCESS = None

# ---------- STREAM ENDPOINT ----------
@app.get("/")
def root():
    """
    Root endpoint showing currently playing track and embedded audio player.
    """
    track_name = CURRENT_TRACK.split('/')[-1] if CURRENT_TRACK else "Loading..."
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>RadioGG - Live Stream</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
                text-align: center;
                max-width: 500px;
            }}
            h1 {{
                color: #333;
                margin: 0 0 10px 0;
            }}
            .now-playing {{
                color: #666;
                font-size: 14px;
                margin-bottom: 30px;
                padding: 15px;
                background: #f5f5f5;
                border-radius: 5px;
                word-break: break-all;
            }}
            .track-name {{
                color: #667eea;
                font-weight: bold;
                font-size: 16px;
            }}
            audio {{
                width: 100%;
                margin: 20px 0;
            }}
            .info {{
                color: #999;
                font-size: 12px;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎵 RadioGG</h1>
            <p style="color: #666;">Live Streaming Radio Station</p>
            
            <div class="now-playing">
                <div>Now Playing:</div>
                <div class="track-name">{track_name}</div>
            </div>
            
            <audio controls autoplay>
                <source src="/stream" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
            
            <div class="info">
                <p>This is a continuous live stream that loops through all available tracks.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/stream")
def stream():
    """
    Streams the currently playing track to clients in real-time.
    """
    def audio_generator():
        global FFMPEG_PROCESS
        # Wait until a track is playing
        while FFMPEG_PROCESS is None:
            time.sleep(0.1)
        
        try:
            while True:
                chunk = FFMPEG_PROCESS.stdout.read(STREAM_CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
        except Exception as e:
            print(f"[ERROR] Streaming error: {e}")

    return StreamingResponse(audio_generator(), media_type="audio/mpeg")

# ---------- START THREADS ----------
threading.Thread(target=sync_loop, daemon=True).start()
threading.Thread(target=start_radio, daemon=True).start()
