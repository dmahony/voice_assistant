#!/usr/bin/env python3
"""
Windows launcher for voice_assistant.
Starts llama-server.exe if present, then the FastAPI app, and opens the browser.
"""
import os
import sys
import subprocess
import time
import webbrowser
import signal
import atexit
from pathlib import Path

# Get the app base directory (works for both dev and PyInstaller builds)
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    BASE_DIR = Path(sys.executable).parent
else:
    # Running from source
    BASE_DIR = Path(__file__).resolve().parent.parent

# Paths
LLAMA_SERVER_EXE = BASE_DIR / "bin" / "windows" / "llama-server.exe"
APP_HOST = "127.0.0.1"
APP_PORT = 8000
APP_URL = f"http://{APP_HOST}:{APP_PORT}"

# Track child processes
child_processes = []

def cleanup():
    """Clean up child processes on exit."""
    for proc in child_processes:
        try:
            if proc.poll() is None:
                proc.terminate()
                # Give it a moment to terminate gracefully
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception:
            pass

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print("\nShutting down...")
    cleanup()
    sys.exit(0)

# Register cleanup
atexit.register(cleanup)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def start_llama_server():
    """Start llama-server.exe if it exists."""
    if not LLAMA_SERVER_EXE.exists():
        print(f"llama-server.exe not found at {LLAMA_SERVER_EXE}")
        print("LLM features will not be available.")
        return None

    print(f"Starting llama-server.exe...")
    try:
        # Start llama-server with CPU-safe defaults
        # Use models/llm directory for model files
        models_dir = BASE_DIR / "models" / "llm"
        models_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(LLAMA_SERVER_EXE),
            "--host", "127.0.0.1",
            "--port", "8080",
            "--model-path", str(models_dir),
            "--ctx-size", "2048",  # Conservative context size
            "--n-gpu-layers", "0",  # CPU-only by default
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        child_processes.append(proc)
        print(f"llama-server started with PID {proc.pid}")
        return proc
    except Exception as e:
        print(f"Failed to start llama-server: {e}")
        return None

def wait_for_server(url, timeout=30):
    """Wait for the server to be reachable."""
    import requests
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=2)
            if r.ok:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

def start_app():
    """Start the FastAPI app."""
    print(f"Starting voice_assistant on {APP_URL}...")

    # Set environment to use bundled binaries
    bin_dir = BASE_DIR / "bin" / "windows"
    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")

    # Disable TLS for local development (browsers allow mic on localhost)
    os.environ["DISABLE_TLS"] = "1"

    # Import and run the app
    app_dir = BASE_DIR
    sys.path.insert(0, str(app_dir))

    # Import uvicorn and run the app
    import uvicorn
    from app import app

    try:
        uvicorn.run(
            app,
            host=APP_HOST,
            port=APP_PORT,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\nShutting down...")
        cleanup()
    except Exception as e:
        print(f"Error starting app: {e}")
        cleanup()
        sys.exit(1)

def open_browser():
    """Open the browser to the app URL."""
    print(f"Opening browser to {APP_URL}...")
    # Wait a moment for the server to start
    time.sleep(2)
    webbrowser.open(APP_URL)

def main():
    """Main entry point."""
    print("=" * 60)
    print("Voice Assistant - Windows Launcher")
    print("=" * 60)
    print(f"Base directory: {BASE_DIR}")

    # Start llama-server if available
    llama_proc = start_llama_server()
    if llama_proc:
        # Wait for llama-server to be ready
        print("Waiting for llama-server to start...")
        if not wait_for_server("http://127.0.0.1:8080/health", timeout=30):
            print("Warning: llama-server did not start within timeout")
        else:
            print("llama-server is ready")

    # Start the app in a separate thread so we can open the browser
    import threading
    app_thread = threading.Thread(target=start_app, daemon=True)
    app_thread.start()

    # Open browser
    open_browser()

    # Wait for app thread to finish
    try:
        app_thread.join()
    except KeyboardInterrupt:
        print("\nShutting down...")
        cleanup()

if __name__ == "__main__":
    main()
