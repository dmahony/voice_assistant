#!/usr/bin/env python3
"""
Test script to verify Windows compatibility changes.
"""
import sys
import os
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

def test_config_imports():
    """Test that config module imports correctly."""
    print("Testing config imports...")
    try:
        from config import config, IS_WINDOWS, IS_FROZEN, APP_BASE_DIR, get_bin_path, get_default_piper_model
        print(f"  IS_WINDOWS: {IS_WINDOWS}")
        print(f"  IS_FROZEN: {IS_FROZEN}")
        print(f"  APP_BASE_DIR: {APP_BASE_DIR}")
        print("  Config imports: OK")
        return True
    except Exception as e:
        print(f"  Config imports: FAILED - {e}")
        return False

def test_binary_path_detection():
    """Test binary path detection."""
    print("\nTesting binary path detection...")
    try:
        from config import get_bin_path, IS_WINDOWS

        # Test piper path
        piper_path = get_bin_path("piper")
        print(f"  Piper path: {piper_path}")

        # Test ffmpeg path
        ffmpeg_path = get_bin_path("ffmpeg")
        print(f"  FFmpeg path: {ffmpeg_path}")

        print("  Binary path detection: OK")
        return True
    except Exception as e:
        print(f"  Binary path detection: FAILED - {e}")
        return False

def test_piper_model_path():
    """Test Piper model path detection."""
    print("\nTesting Piper model path detection...")
    try:
        from config import get_default_piper_model

        piper_model = get_default_piper_model()
        print(f"  Piper model path: {piper_model}")

        print("  Piper model path detection: OK")
        return True
    except Exception as e:
        print(f"  Piper model path detection: FAILED - {e}")
        return False

def test_config_values():
    """Test that config values are set correctly."""
    print("\nTesting config values...")
    try:
        from config import config

        # Check key config values
        llama_chat_url = config.get("llama_chat_url")
        piper_bin = config.get("piper_bin")
        piper_voice_model = config.get("piper_voice_model")

        print(f"  llama_chat_url: {llama_chat_url}")
        print(f"  piper_bin: {piper_bin}")
        print(f"  piper_voice_model: {piper_voice_model}")

        # Verify URLs are correct
        assert llama_chat_url == "http://127.0.0.1:8080/v1/chat/completions", "llama_chat_url mismatch"

        print("  Config values: OK")
        return True
    except Exception as e:
        print(f"  Config values: FAILED - {e}")
        return False

def test_app_imports():
    """Test that app module imports correctly."""
    print("\nTesting app imports...")
    try:
        # Just import, don't run
        import app
        print("  App imports: OK")
        return True
    except Exception as e:
        print(f"  App imports: FAILED - {e}")
        return False

def test_directory_structure():
    """Test that required directories exist or can be created."""
    print("\nTesting directory structure...")
    try:
        from config import APP_BASE_DIR

        required_dirs = [
            APP_BASE_DIR / "bin" / "windows",
            APP_BASE_DIR / "models" / "llm",
            APP_BASE_DIR / "models" / "piper",
        ]

        for dir_path in required_dirs:
            if not dir_path.exists():
                print(f"  Creating directory: {dir_path}")
                dir_path.mkdir(parents=True, exist_ok=True)

        print("  Directory structure: OK")
        return True
    except Exception as e:
        print(f"  Directory structure: FAILED - {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Windows Compatibility Tests")
    print("=" * 60)

    tests = [
        test_config_imports,
        test_binary_path_detection,
        test_piper_model_path,
        test_config_values,
        test_app_imports,
        test_directory_structure,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  Test failed with exception: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
