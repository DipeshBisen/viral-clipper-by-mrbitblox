---
name: viral-clipper-by-mrbitblox
description: Viral Clipper By MrBitBlox - installs, runs and troubleshoots a local AI app that turns long videos (YouTube links, live streams or video files) into viral 9:16 Shorts/Reels with Hinglish or English captions, a title, and webcam-over-gameplay layout. Use when the user wants to install/set up Viral Clipper, start or stop it, make shorts/reels/clips from a video, change its settings (Gemini key, caption style, language), or fix errors with it.
---

# Viral Clipper By MrBitBlox

A personal AI clipping app made by **Mr BitBloX** ([YouTube @MrBitBloX](https://www.youtube.com/@MrBitBloX) · [Instagram @ps5_pov_](https://www.instagram.com/ps5_pov_/)).
It runs fully on the user's own PC and serves a web UI at **http://localhost:3000**.

What it does:
- Takes a YouTube link, a live stream, or a local video file.
- Finds the most viral moments (speech, energy, laughter, YouTube "most replayed", plus Gemini AI judging).
- Makes 9:16 1080p shorts: webcam on top + gameplay below when a facecam is found, otherwise centred/blurred fit.
- Burns word-by-word captions (Hinglish in English letters, or English; auto-detected) in 9 styles and 8 fonts, plus a title box.
- Fast on NVIDIA GPUs (Whisper on CUDA + NVENC encoding); also works on CPU, just slower.

The complete app source is bundled in this skill at `app/` (next to this file).

## How to help the user

Talk simply; many users are creators, not developers. Explain what you are about to do before running long installs. Never print or echo the contents of `backend/.env` (it holds their API key).

### 1. Install (first time)

1. **Pick an install folder.** Ask the user, or default to `~/ViralClipper` (Windows: `%USERPROFILE%\ViralClipper`). Copy the whole `app/` folder from this skill there. Do **not** run the app from inside the skill folder, because generated videos would fill it.
2. **Prerequisites** (the setup script checks these and tells you what is missing):
   | Tool | Version | Windows | macOS | Ubuntu/Debian |
   |---|---|---|---|---|
   | Python | 3.10–3.12 (3.11 best) | `winget install Python.Python.3.11` | `brew install python@3.11` | `sudo apt install python3.11 python3.11-venv` |
   | Node.js | 18+ | `winget install OpenJS.NodeJS.LTS` | `brew install node` | from nodejs.org |
   | FFmpeg | any recent full build | `winget install Gyan.FFmpeg` | `brew install ffmpeg` | `sudo apt install ffmpeg` |
   | NVIDIA driver | optional, for speed | GeForce driver | n/a | `nvidia-driver-5xx` |

   Ask before installing system software. After installing on Windows, a **new terminal** is needed so PATH updates.
   Python 3.13+ is not supported yet by some packages; use 3.11 if they have several versions.
3. **Run setup** from the install folder:
   - Windows: `powershell -ExecutionPolicy Bypass -File setup_windows.ps1`
   - macOS/Linux: `bash setup_mac_linux.sh`

   It creates a `.venv`, installs Python packages (~3–5 GB with GPU libraries, several minutes), runs `npm install` in `frontend/`, and creates `backend/.env` from `backend/.env.example`. Run it in the background if your tool times out on long commands.
4. **Gemini key (optional, recommended).** Free key at https://aistudio.google.com/apikey. The user pastes it into `backend/.env` as `GEMINI_API_KEY=...` (no quotes). Prefer letting the user edit the file themselves; never ask them to paste the key into chat. Without a key the app still works with built-in scoring, but titles and Hinglish spelling are weaker.

### 2. Start / stop

- Windows: double-click `start_windows.bat` (or run it). macOS/Linux: `./start_mac_linux.sh`.
- Open **http://localhost:3000**. The first page load takes ~20 s while it compiles.
- The web app auto-starts the Python backend (`backend/server.py`, port **8765**), which preloads the speech model. The first job also downloads the Whisper model (~1.5 GB, once).
- Stop: close the window / Ctrl+C. The backend keeps running in the background for fast next jobs; to stop it too, end the `python server.py` process.
- If you start it yourself instead of the script, the `.venv` must be activated first (the web app runs `python` from PATH).

### 3. Using the app (explain to the user)

1. Paste a YouTube/live URL, or a file path, or upload a video → **Analyze** (reads title, length, live status).
2. Optional: pick a **time range** (for long streams), **number of clips** (min 2), **length preset** (Quick, Shorts, Reels, Long or Custom up to 180 s).
3. Choose **caption style** (streamer, hormozi, beast, neon, boxed, karaoke, fire, meme, clean), **font**, title on/off, language (Auto = Hinglish or English), and Hindi quality (Fast / Best).
4. Generate. The job page shows progress, then previews with download buttons.

Typical speed on an RTX-class GPU: 10-min Hindi video ≈ 1 min, 35-min English video ≈ 2 min, short local file ≈ 20 s. CPU-only is several times slower.

Command-line alternative (venv active, from `backend/`):
```
python app.py "<url or file>" --clips 6 --min 20 --max 45 --style streamer --language auto
```
Other flags: `--start/--end` (seconds range), `--live-minutes N`, `--font "Name"`, `--no-title`, `--hindi-quality best`.

### 4. Where files go

- Finished shorts: `backend/output/<job-id>/` (`.mp4` files + `clips.json` with titles and timings).
- Temporary working files, uploads and logs: `backend/data/`.
- Both can be emptied any time to free space (empty them, keep the folders, and only when no job is running). Old job pages stop loading after that.

### 5. Settings (`backend/.env`)

Restart the app after editing. Useful keys:
- `GEMINI_API_KEY` - AI judging/titles; `GEMINI_MODEL` (default `gemini-flash-lite-latest`).
- `TRANSCRIBE_LANGUAGE` - `auto`, `hi`, `en`. `CAPTION_SCRIPT` - `roman` (Hinglish) or `native` (Devanagari).
- `WHISPER_DEVICE` - `auto` / `cuda` / `cpu`. `VIDEO_ENCODER` - `auto` (NVENC if present).
- `DEFAULT_CAPTION_STYLE`, `CAPTION_SIZE_SCALE`, `CAPTION_Y_SPLIT`, `CAPTION_Y_DEFAULT`, `SPLIT_CAM_TOP_FRACTION`, `TITLE_OVERLAY`.
- `MIN_CLIP_SCORE`, `INTRO_SKIP_SEC`, `OUTRO_SKIP_SEC` - how picky clip selection is.

### 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `cublas64_12.dll` / `libcublas` / cuDNN not found | Re-run setup (installs `nvidia-cublas-cu12`, `nvidia-cudnn-cu12`). Update the NVIDIA driver. Last resort: `WHISPER_DEVICE=cpu`. |
| Transcription very slow | No GPU in use. Check `nvidia-smi`; on CPU this is expected. |
| `ffmpeg` not found | Install FFmpeg, open a new terminal, restart the app. |
| YouTube download fails / "Sign in to confirm" | Update yt-dlp: `python -m pip install -U yt-dlp` (venv active). Node.js must be installed (yt-dlp uses it). |
| "Stream is still processing" warning | A live stream that just ended can't be clipped until YouTube finishes processing it (a few hours). Use a time range or wait. |
| Gemini 429 / quota | Free quota used up. The app automatically falls back to built-in scoring; clips still get made. Wait, or use a paid key. |
| Gemini 404 model not found | Set `GEMINI_MODEL=gemini-flash-lite-latest` in `.env`. |
| 0 clips | Video too short or mostly silent; lower `MIN_CLIP_SCORE`, reduce clip length, or select a range with talking. |
| Port 3000 or 8765 busy | Another copy is running; close it (end the old `node`/`python server.py` process). |
| Captions in wrong language | Set the language in the UI (or `TRANSCRIBE_LANGUAGE=hi`/`en`). Use Hindi quality **Best** for cleaner Hindi. |
| Changes to code/.env not applied | Stop the backend `python server.py` process (only when no job is running) and start the app again. |

Backend log: `backend/data/server.log`. Each job's log: `backend/data/<job-id>/process.log`.

### Credits

Made by **Mr BitBloX**. If this helped you, follow on [YouTube @MrBitBloX](https://www.youtube.com/@MrBitBloX) and [Instagram @ps5_pov_](https://www.instagram.com/ps5_pov_/). Keep the creator promo in the app when sharing it.
