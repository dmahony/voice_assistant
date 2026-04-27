#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/dan/voice_assistant_app"
MAIN_VENV="$APP_DIR/.venv"
XTTS_VENV="$APP_DIR/xtts-venv"

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

# If DISABLE_TLS=1 the app serves plain HTTP.
# Default is TLS because browsers often block microphone on plain HTTP in non-secure contexts.
DISABLE_TLS="${DISABLE_TLS:-0}"

# Llama is currently running with:
#   cd /home/dan && ./src/llama.cpp/build/bin/llama-server ... --api-prefix /v1 ... --port 8080
LLAMA_START_CMD='cd /home/dan && ./src/llama.cpp/build/bin/llama-server -m ./models/gemma-4-e2b-it/gemma-4-E2B-it-Q4_K_M.gguf -c 4096 --host 0.0.0.0 --port 8080 --api-prefix /v1 --threads-http 4 --threads 8 --log-file /tmp/llama-server.log'
LLAMA_CHAT_URL="http://127.0.0.1:8080/v1/chat/completions"
LLAMA_HEALTH_URL="http://127.0.0.1:8080/v1/health"

WAIT_TIMEOUT_SECONDS="${WAIT_TIMEOUT_SECONDS:-120}"

APP_PY="app.py"
XTTS_HELPER="xtts_synth.py"

# XTTS speaker reference
SPEAKER_WAV="/tmp/other-way.wav"
TEST_WAV="$APP_DIR/test.wav"

log() { echo "[start_voice_assistant] $*"; }

log "==> Using APP_DIR=$APP_DIR"
cd "$APP_DIR"

log "==> Ensure speaker reference exists: $SPEAKER_WAV"
if [ ! -f "$SPEAKER_WAV" ]; then
  if [ ! -f "$TEST_WAV" ]; then
    echo "ERROR: $TEST_WAV missing; cannot generate $SPEAKER_WAV" >&2
    exit 1
  fi
  log "Creating $SPEAKER_WAV from $TEST_WAV"
  ffmpeg -y -i "$TEST_WAV" -ac 1 -ar 24000 -sample_fmt s16 "$SPEAKER_WAV" >/dev/null 2>&1 || {
    # fallback without sample_fmt
    ffmpeg -y -i "$TEST_WAV" -ac 1 -ar 24000 "$SPEAKER_WAV" >/dev/null 2>&1
  }
fi

if ! ffprobe -v error -show_entries stream=sample_rate,channels -of default=nw=1:nk=1 "$SPEAKER_WAV" >/dev/null 2>&1; then
  echo "ERROR: $SPEAKER_WAV exists but ffprobe failed" >&2
  exit 1
fi

log "==> Ensure main app venv and deps"
if [ ! -f "$MAIN_VENV/bin/activate" ]; then
  python3 -m venv "$MAIN_VENV"
fi
# shellcheck disable=SC1090
source "$MAIN_VENV/bin/activate"

pip install -U pip setuptools wheel >/dev/null
pip install -r "$APP_DIR/requirements.txt" >/dev/null

log "==> Ensure XTTS helper env and deps"
if [ ! -f "$XTTS_VENV/bin/activate" ]; then
  python3.11 -m venv "$XTTS_VENV"
fi
# shellcheck disable=SC1090
source "$XTTS_VENV/bin/activate"

pip install -U pip setuptools wheel >/dev/null
pip install -q TTS torchcodec "transformers==4.41.2" "tokenizers==0.19.1" >/dev/null

log "==> Verify XTTS helper can run (smoke test). This will download the model on first run."
rm -f /tmp/xtts_smoke.wav >/dev/null 2>&1 || true
COQUI_TOS_AGREED=1 python "$APP_DIR/$XTTS_HELPER" \
  --model-name "tts_models/multilingual/multi-dataset/xtts_v2" \
  --speaker-wav "$SPEAKER_WAV" \
  --language "en" \
  --output /tmp/xtts_smoke.wav <<'EOF'
smoke test
EOF

log "==> Start llama-server if it's not already listening on 8080"
if ! ss -ltnp 2>/dev/null | grep -q ':8080'; then
  log "Starting llama with LLAMA_START_CMD (background)"
  nohup bash -lc "$LLAMA_START_CMD" >/tmp/llama_start.log 2>&1 &
fi

log "==> Waiting for llama health: $LLAMA_HEALTH_URL"
end=$((SECONDS + WAIT_TIMEOUT_SECONDS))
while true; do
  if curl -fsS "$LLAMA_HEALTH_URL" >/dev/null 2>&1; then
    log "Llama health OK"
    break
  fi
  if [ "$SECONDS" -ge "$end" ]; then
    echo "ERROR: Llama not reachable within ${WAIT_TIMEOUT_SECONDS}s" >&2
    echo "Check /tmp/llama_start.log" >&2
    exit 1
  fi
  sleep 2
done

log "==> Start voice assistant app on http://127.0.0.1:$PORT (DISABLE_TLS=$DISABLE_TLS)"
# return to main venv
# deactivate if currently in xtts-venv
{ deactivate >/dev/null 2>&1 || true; };
# shellcheck disable=SC1090
source "$MAIN_VENV/bin/activate"

# Stop any previous listener on $PORT (best-effort)
# (We avoid killing other services unless they are on the exact port.)
pids=$(ss -ltnp 2>/dev/null | awk -v p=":$PORT" '$4 ~ p"$" {print $NF}' | sed -E 's/.*pid=([0-9]+).*/\1/' | sort -u || true)
if [ -n "${pids:-}" ]; then
  for pid in $pids; do
    kill "$pid" >/dev/null 2>&1 || true
  done
fi

DISABLE_TLS="$DISABLE_TLS" \
PORT="$PORT" \
HOST="$HOST" \
LLAMA_CHAT_URL="$LLAMA_CHAT_URL" \
LLAMA_HEALTH_URL="$LLAMA_HEALTH_URL" \
TTS_BACKEND="xtts" \
XTTS_SPEAKER_WAV="$SPEAKER_WAV" \
nohup python "$APP_DIR/$APP_PY" >/tmp/voice_assistant_app.log 2>&1 &

log "Voice assistant started. Logs: /tmp/voice_assistant_app.log"

log "==> Waiting for app /api/health"
end=$((SECONDS + WAIT_TIMEOUT_SECONDS))
while true; do
  if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    log "App is up: http://127.0.0.1:$PORT/api/health"
    curl -sS "http://127.0.0.1:$PORT/api/health" | head -c 2000; echo
    break
  fi
  if [ "$SECONDS" -ge "$end" ]; then
    echo "ERROR: App did not come up on port $PORT within ${WAIT_TIMEOUT_SECONDS}s" >&2
    echo "Last 120 log lines:" >&2
    tail -n 120 /tmp/voice_assistant_app.log || true
    exit 1
  fi
  sleep 2
done
