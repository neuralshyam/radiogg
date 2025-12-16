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
# Use local workspace music folder to avoid permission issues in some containers
MUSIC_DIR = "./music"
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
    # Serve a responsive Tailwind-based page that polls now-playing
    track_name = CURRENT_TRACK.split('/')[-1] if CURRENT_TRACK else "Loading..."
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>RadioGG — Live</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="min-h-screen bg-gradient-to-tr from-purple-600 to-indigo-500 flex items-center justify-center p-4">
        <div class="w-full max-w-3xl bg-white/95 backdrop-blur-md rounded-xl shadow-2xl overflow-hidden">
            <div class="p-6 md:p-8 lg:p-12">
                <div class="flex items-center gap-4">
                    <div class="flex-1">
                        <h1 class="text-2xl md:text-3xl font-extrabold text-gray-900">🎧 RadioGG</h1>
                        <p class="mt-1 text-sm text-gray-600">Live streaming radio — same track for all listeners</p>
                    </div>
                    <div class="hidden sm:block">
                        <div class="text-sm text-gray-500">Stream</div>
                        <div class="text-lg font-semibold text-indigo-600">Live</div>
                    </div>
                </div>

                <div class="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
                    <div class="md:col-span-2">
                        <div class="bg-gray-50 p-4 rounded-lg">
                            <div class="text-xs text-gray-500">Now Playing</div>
                            <div id="trackName" class="mt-1 text-sm md:text-base font-medium text-gray-900 truncate">{track_name}</div>
                            <div id="trackUrl" class="hidden"></div>
                        </div>
                    </div>

                    <div class="flex flex-col items-stretch gap-2">
                        <audio id="player" controls autoplay preload="auto" class="w-full rounded-md">
                            <source src="/stream" type="audio/mpeg">
                            Your browser does not support the audio element.
                        </audio>
                        <button id="playToggle" class="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700">Play / Retry</button>
                    </div>
                </div>

                <p class="mt-6 text-xs text-gray-500">If playback takes a few seconds, click "Play / Retry" to resume. This polls the server for the current track.</p>
            </div>
        </div>

        <script>
            async function fetchNowPlaying(){
                try{
                    const r = await fetch('/nowplaying');
                    if(!r.ok) return;
                    const j = await r.json();
                    const name = j.track_name || 'Loading...';
                    document.getElementById('trackName').textContent = name;
                    const player = document.getElementById('player');
                    // Attempt to play if paused or if track changed
                    if(j.track_url){
                        // If the source differs, reload the player
                        const currentSrc = player.querySelector('source')?.src || '';
                        if(!currentSrc.endsWith('/stream')){
                            player.querySelector('source').src = '/stream';
                            player.load();
                        }
                    }
                    // Try to play (may be blocked by browser autoplay rules)
                    try{ await player.play(); } catch(e){}
                }catch(e){
                    console.debug('nowplaying fetch failed', e);
                }
            }

            // Poll every 2.5 seconds
            fetchNowPlaying();
            setInterval(fetchNowPlaying, 2500);

            document.getElementById('playToggle').addEventListener('click', async ()=>{
                const player = document.getElementById('player');
                if(player.paused){
                    try{ await player.play(); } catch(e){ console.debug(e); }
                } else {
                    player.pause();
                    player.currentTime = 0;
                    try{ await player.play(); } catch(e){ console.debug(e); }
                }
            });
        </script>
    </body>
    </html>
    """
    # Inject track name into the template (avoid f-string to keep braces intact)
    html_content = html_content.replace("{track_name}", track_name)
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


@app.get('/nowplaying')
def nowplaying():
    """Return current track info as JSON for client-side polling."""
    if CURRENT_TRACK:
        track_name = CURRENT_TRACK.split('/')[-1]
        return {"track_name": track_name, "track_url": CURRENT_TRACK}
    return {"track_name": None, "track_url": None}

# ---------- START THREADS ----------
threading.Thread(target=sync_loop, daemon=True).start()
threading.Thread(target=start_radio, daemon=True).start()
