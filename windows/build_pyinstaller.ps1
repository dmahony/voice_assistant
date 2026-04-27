# PyInstaller build script for voice_assistant on Windows
# Run this from the voice_assistant directory: .\windows\build_pyinstaller.ps1

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Building voice_assistant for Windows" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check if PyInstaller is installed
Write-Host "Checking for PyInstaller..." -ForegroundColor Yellow
try {
    $pyinstaller = python -m PyInstaller --version 2>&1
    Write-Host "PyInstaller version: $pyinstaller" -ForegroundColor Green
} catch {
    Write-Host "PyInstaller not found. Installing..." -ForegroundColor Yellow
    pip install pyinstaller
}

# Clean previous builds
Write-Host "Cleaning previous builds..." -ForegroundColor Yellow
Remove-Item -Path "build" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "dist" -Recurse -Force -ErrorAction SilentlyContinue

# Create PyInstaller spec file
Write-Host "Creating PyInstaller spec file..." -ForegroundColor Yellow
$specContent = @"
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['windows/run_windows.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('voices', 'voices'),
        ('config.local.json', '.'),
    ],
    hiddenimports=[
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.websockets',
        'fastapi',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'fastapi.responses',
        'faster_whisper',
        'requests',
        'jinja2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='voice_assistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
"@

$specContent | Out-File -FilePath "voice_assistant.spec" -Encoding UTF8

# Build with PyInstaller
Write-Host "Building with PyInstaller..." -ForegroundColor Yellow
python -m PyInstaller voice_assistant.spec --clean

# Create directory structure in dist
Write-Host "Creating directory structure..." -ForegroundColor Yellow
$distDir = "dist\voice_assistant"
$binDir = "$distDir\bin\windows"
$modelsDir = "$distDir\models"

# Create directories
New-Item -ItemType Directory -Force -Path $binDir | Out-Null
New-Item -ItemType Directory -Force -Path "$modelsDir\llm" | Out-Null
New-Item -ItemType Directory -Force -Path "$modelsDir\piper" | Out-Null
New-Item -ItemType Directory -Force -Path "$distDir\tts_out" | Out-Null
New-Item -ItemType Directory -Force -Path "$distDir\tts_cache" | Out-Null
New-Item -ItemType Directory -Force -Path "$distDir\temp" | Out-Null

# Copy README
Write-Host "Copying README..." -ForegroundColor Yellow
Copy-Item -Path "windows\README_WINDOWS.md" -Destination "$distDir\README.md" -Force

# Create placeholder files for binaries
Write-Host "Creating placeholder files for binaries..." -ForegroundColor Yellow
@("ffmpeg.exe", "llama-server.exe", "piper.exe") | ForEach-Object {
    $placeholder = "$binDir\$_"
    if (-not (Test-Path $placeholder)) {
        "# Place $_ here" | Out-File -FilePath $placeholder -Encoding ASCII
        Write-Host "  Created placeholder: $placeholder" -ForegroundColor Gray
    }
}

# Create a simple batch file launcher
Write-Host "Creating batch file launcher..." -ForegroundColor Yellow
$batchContent = @"
@echo off
echo Starting Voice Assistant...
voice_assistant.exe
pause
"@
$batchContent | Out-File -FilePath "$distDir\start.bat" -Encoding ASCII

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Build complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output directory: $distDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Download and place binaries in $binDir" -ForegroundColor White
Write-Host "   - ffmpeg.exe: https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-full.7z" -ForegroundColor Gray
Write-Host "   - llama-server.exe: https://github.com/ggerganov/llama.cpp/releases" -ForegroundColor Gray
Write-Host "   - piper.exe: https://github.com/rhasspy/piper/releases" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Download models and place in $modelsDir" -ForegroundColor White
Write-Host "   - LLM models: models\llm\" -ForegroundColor Gray
Write-Host "   - Piper models: models\piper\" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Run: start.bat or voice_assistant.exe" -ForegroundColor White
Write-Host ""
Write-Host "See README.md in the dist directory for detailed instructions." -ForegroundColor Cyan
