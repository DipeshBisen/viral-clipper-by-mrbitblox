# Viral Clipper By MrBitBlox - one-time setup for Windows
# Run:  powershell -ExecutionPolicy Bypass -File setup_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
function Ok($m)   { Write-Host "  [OK]  $m" -ForegroundColor Green }
function Bad($m)  { Write-Host "  [!!]  $m" -ForegroundColor Red }
function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }

Step "Checking tools"
$missing = @()

# Python 3.10-3.12 (3.11 recommended)
$pyExe = $null; $pyArgs = @()
foreach ($v in "3.11", "3.12", "3.10") {
    try { & py "-$v" --version *> $null; if ($LASTEXITCODE -eq 0) { $pyExe = "py"; $pyArgs = @("-$v"); break } } catch {}
}
if (-not $pyExe) {
    try {
        $ver = (& python --version 2>&1).ToString()
        if ($ver -match "Python 3\.(10|11|12)\.") { $pyExe = "python" }
    } catch {}
}
if ($pyExe) { Ok "Python: $(& $pyExe @pyArgs --version 2>&1)" } else { Bad "Python 3.10-3.12 not found  ->  winget install Python.Python.3.11"; $missing += "python" }

try { $nv = (& node --version); Ok "Node.js: $nv" } catch { Bad "Node.js not found  ->  winget install OpenJS.NodeJS.LTS"; $missing += "node" }
try { & ffmpeg -hide_banner -version *> $null; Ok "FFmpeg found" } catch { Bad "FFmpeg not found  ->  winget install Gyan.FFmpeg"; $missing += "ffmpeg" }
try { & nvidia-smi *> $null; Ok "NVIDIA GPU found (fast mode)" } catch { Write-Host "  [--]  No NVIDIA GPU detected: the app will run on CPU (slower, still works)" }

if ($missing.Count -gt 0) {
    Bad "Install the missing tools above, open a NEW terminal, then run this setup again."
    exit 1
}

Step "Creating Python environment (.venv)"
if (-not (Test-Path ".venv\Scripts\python.exe")) { & $pyExe @pyArgs -m venv .venv }
$vpy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $vpy -m pip install --upgrade pip --quiet
Step "Installing Python packages (first time takes a few minutes)"
& $vpy -m pip install -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { Bad "pip install failed"; exit 1 }
Ok "Python packages installed"

Step "Installing web app packages"
Push-Location frontend
& npm install
$npmOk = ($LASTEXITCODE -eq 0)
Pop-Location
if (-not $npmOk) { Bad "npm install failed"; exit 1 }
Ok "Web app packages installed"

Step "Settings file"
if (-not (Test-Path "backend\.env")) { Copy-Item "backend\.env.example" "backend\.env"; Ok "Created backend\.env" } else { Ok "backend\.env already exists (kept)" }

Write-Host "`nSetup complete!" -ForegroundColor Green
Write-Host "Optional: put your free Gemini key in backend\.env (GEMINI_API_KEY=...)  https://aistudio.google.com/apikey"
Write-Host "Start the app:  double-click start_windows.bat   (then open http://localhost:3000)"
