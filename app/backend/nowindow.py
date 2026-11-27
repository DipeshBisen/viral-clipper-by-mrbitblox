"""Windows only: stop every ffmpeg / ffprobe / yt-dlp / node child from opening its own
terminal window.

The web app starts the backend in the background without a console. On Windows, each console
program that backend then launches would pop up a new black window. Importing this module once
makes every subprocess start with CREATE_NO_WINDOW (output is still captured as before).
"""
import os
import subprocess

if os.name == "nt" and not getattr(subprocess, "_mc_no_window", False):
    _CREATE_NO_WINDOW = 0x08000000
    _orig_init = subprocess.Popen.__init__

    def _init(self, *args, **kwargs):
        kwargs["creationflags"] = (kwargs.get("creationflags") or 0) | _CREATE_NO_WINDOW
        _orig_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _init
    subprocess._mc_no_window = True
