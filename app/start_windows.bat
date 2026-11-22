@echo off
title Viral Clipper By MrBitBlox
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo Setup has not been run yet. Run:  powershell -ExecutionPolicy Bypass -File setup_windows.ps1
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
echo ===================================================
echo   Viral Clipper By MrBitBlox
echo   Opening http://localhost:3000  (first load can take ~20 s)
echo   Keep this window open. Close it to stop the app.
echo ===================================================
start "" cmd /c "timeout /t 8 >nul & start http://localhost:3000"
cd frontend
npm run dev
