# Viral Clipper By MrBitBlox - how to install

Make viral 9:16 Shorts/Reels with Hinglish or English captions from any long video, on your own PC.
Made by Mr BitBloX - YouTube https://www.youtube.com/@MrBitBloX · Instagram https://www.instagram.com/ps5_pov_/

## Easiest: let your AI agent do it

1. Unzip this folder.
2. Add it as a skill:
   - **Claude Code**: copy the `viral-clipper-by-mrbitblox` folder into `~/.claude/skills/` (Windows: `C:\Users\<you>\.claude\skills\`).
     **Claude app (claude.ai / desktop)**: Settings → Capabilities → Skills → upload the zip.
   - **Codex**: copy the folder into `~/.codex/skills/`.
   - **Any other AI agent**: open the folder in the agent and say "read SKILL.md and follow it".
3. Tell your agent: **"Install Viral Clipper By MrBitBlox and start it."**

## Or do it yourself

You need: Python 3.11, Node.js 18+, FFmpeg. An NVIDIA GPU makes it much faster (optional).

1. Copy the `app` folder somewhere, e.g. `C:\ViralClipper`.
2. Setup (once):
   - Windows: right-click in the folder → Open in Terminal → `powershell -ExecutionPolicy Bypass -File setup_windows.ps1`
   - Mac/Linux: `bash setup_mac_linux.sh`
3. Optional: get a free Gemini key at https://aistudio.google.com/apikey and paste it into `backend/.env` after `GEMINI_API_KEY=`.
4. Start: `start_windows.bat` (Windows) or `./start_mac_linux.sh` (Mac/Linux), then open http://localhost:3000.

Your shorts are saved in `backend/output/`.
