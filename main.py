import os
import glob
import time
import threading
import subprocess
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

# ---------- CONFIG ----------
MEGA_FOLDER_URL = "https://mega.nz/folder/Hxo1RaTL#qojarvoO1mODsQIdc7V2mQ"
MUSIC_DIR = "/app/music"
TMP_DIR = "/app/music_tmp"
SYNC_INTERVAL = 24 * 3600  # seconds
STREAM_CHUNK_SIZE = 4096

# Make sure directories exist
os.makedirs(MUSIC_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)

app = FastAPI()
CURRENT_TRACK = None
FFMPEG_PROCESS = None

# ---------- MEGA SYNC ----------
def mega_sync():
    """
    Downloads/updates public MEGA folder every SYNC_INTERVAL seconds.
    Uses a temporary folder to avoid breaking currently playing tracks.
    """
    while True:
        print("[INFO] Starting Mega sync...")
        try:
            # Sync to temporary folder first
            subprocess.run([
                "rclone", "copyurl",
                MEGA_FOLDER_URL,
                TMP_DIR,
                "--update",
                "-P"
            ], check=True)
            
            # Move downloaded files to main folder atomically
            for filename in os.listdir(TMP_DIR):
                src = os.path.join(TMP_DIR, filename)
                dst = os.path.join(MUSIC_DIR, filename)
                os.replace(src, dst)
            
            print("[INFO] Mega sync complete!")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Mega sync failed: {e}")
        except Exception as e:
            print(f"[ERROR] Unexpected error during Mega sync: {e}")
        
        time.sleep(SYNC_INTERVAL)

# ---------- RADIO LOOP ----------
def start_radio():
    """
    Loops through tracks in MUSIC_DIR and streams them live via FFmpeg.
    All listeners hear the same track at the same time.
    """
    global CURRENT_TRACK, FFMPEG_PROCESS
    while True:
        tracks = sorted(glob.glob(os.path.join(MUSIC_DIR, "*.*")))
        if not tracks:
            print("[WARN] No tracks found. Waiting 30 seconds...")
            time.sleep(30)
            continue
        
        for track in tracks:
            CURRENT_TRACK = track
            print(f"[INFO] Now playing: {track}")
            
            try:
                FFMPEG_PROCESS = subprocess.Popen([
                    "ffmpeg", "-re", "-i", track,
                    "-f", "mp3", "-b:a", "128k",
                    "pipe:1"
                ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                
                FFMPEG_PROCESS.wait()
            except Exception as e:
                print(f"[ERROR] FFmpeg failed: {e}")
            finally:
                FFMPEG_PROCESS = None

# ---------- STREAM ENDPOINT ----------
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
threading.Thread(target=mega_sync, daemon=True).start()
threading.Thread(target=start_radio, daemon=True).start()
