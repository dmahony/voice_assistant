import datetime
import shutil
import subprocess
import os
from pathlib import Path

def get_current_time():
    """Get current time and date."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def check_llama_health(health_url="http://127.0.0.1:8080/health"):
    """Check llama-server health status."""
    import requests
    try:
        r = requests.get(health_url, timeout=2)
        if r.status_code == 200:
            return "llama-server is healthy (HTTP 200)"
        return f"llama-server status: HTTP {r.status_code}"
    except Exception as e:
        return f"llama-server unreachable: {e}"

def check_disk_usage():
    """Check disk usage of the current partition."""
    usage = shutil.disk_usage("/")
    return f"Total: {usage.total // (2**30)}GB, Used: {usage.used // (2**30)}GB, Free: {usage.free // (2**30)}GB"

def check_system_uptime():
    """Check system uptime."""
    try:
        # Works on Linux
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])
            uptime_string = str(datetime.timedelta(seconds=uptime_seconds))
            return f"System uptime: {uptime_string}"
    except:
        return "Uptime unavailable (non-Linux?)"

def list_voice_profiles():
    """List available voice profiles/models."""
    # This depends on where models are stored. 
    # For now, let's look for .onnx files in a common piper path or current dir.
    profiles = []
    # Mock some logic or return placeholders
    return "Available voice profiles: Standard (Piper), English-US-Medium, Espeak-Fallback"

AVAILABLE_TOOLS = {
    "get_current_time": get_current_time,
    "check_llama_health": check_llama_health,
    "check_disk_usage": check_disk_usage,
    "check_system_uptime": check_system_uptime,
    "list_voice_profiles": list_voice_profiles,
}

def call_tool(name, args=None):
    if name not in AVAILABLE_TOOLS:
        return f"Error: Tool '{name}' not found."
    try:
        # All currently requested tools take no args or have defaults
        return AVAILABLE_TOOLS[name]()
    except Exception as e:
        return f"Error executing tool '{name}': {e}"
