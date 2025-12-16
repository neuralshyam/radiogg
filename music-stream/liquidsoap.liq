settings.init.allow_root.set(true)

music = playlist("/app/music", mode="random")
radio = fallback(track_sensitive=false, [music, blank()])

output.icecast(
  %mp3,
  host="localhost",
  port=8000,
  password="hackme",
  mount="stream.mp3",
  radio
)
