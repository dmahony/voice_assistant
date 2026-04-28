const chatEl = document.getElementById('chat');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const clearBtn = document.getElementById('clear-btn');
const statusText = document.getElementById('status-text');
const statusPill = document.getElementById('status-pill');
const audioPlayer = document.getElementById('audio-player');
const voiceNameInput = document.getElementById('voice-name');
const voiceStartBtn = document.getElementById('voice-start-btn');
const voiceStopBtn = document.getElementById('voice-stop-btn');
const voiceFileInput = document.getElementById('voice-file');
const voiceUploadBtn = document.getElementById('voice-upload-btn');
const voiceListEl = document.getElementById('voice-list');
const connectionNoteEl = document.getElementById('connection-note');
const textInput = document.getElementById('text-input');
const textSendBtn = document.getElementById('text-send-btn');

const chatState = { mediaRecorder: null, chunks: [], stream: null };
const voiceState = { mediaRecorder: null, chunks: [], stream: null };
let activeAudioUrl = null;
let transcribingRow = null;

function setStatus(text, mode = 'idle') {
  statusText.textContent = text;
  statusPill.textContent = mode === 'transcribing' ? 'transcribing…' : mode;
  statusPill.dataset.mode = mode;
}

function setConnectionNote(text, tone = '') {
  if (!connectionNoteEl) return;
  connectionNoteEl.textContent = text;
  connectionNoteEl.className = 'connection-note';
  if (tone) {
    connectionNoteEl.classList.add(tone);
  }
}

function scrollChatToBottom() {
  chatEl.scrollTop = chatEl.scrollHeight;
}

function addMessage(role, text) {
  removeChatEmptyState();
  const row = document.createElement('article');
  row.className = `message ${role}`;
  const head = document.createElement('div');
  head.className = 'message-head';
  head.textContent = role === 'user' ? 'You' : 'Assistant';
  const body = document.createElement('div');
  body.className = 'message-body';
  body.textContent = text;
  row.appendChild(head);
  row.appendChild(body);
  chatEl.appendChild(row);
  scrollChatToBottom();
  return row;
}

function addTranscribingIndicator() {
  removeChatEmptyState();
  removeTranscribingIndicator();
  const row = document.createElement('article');
  row.className = 'message assistant transient transcribing';
  row.setAttribute('aria-live', 'polite');

  const head = document.createElement('div');
  head.className = 'message-head';
  head.textContent = 'Assistant';

  const body = document.createElement('div');
  body.className = 'message-body transcribing-body';

  const label = document.createElement('span');
  label.className = 'transcribing-label';
  label.textContent = 'Transcribing audio';

  const dots = document.createElement('span');
  dots.className = 'transcribing-dots';
  dots.innerHTML = '<span></span><span></span><span></span>';

  body.appendChild(label);
  body.appendChild(dots);
  row.appendChild(head);
  row.appendChild(body);
  chatEl.appendChild(row);
  scrollChatToBottom();
  transcribingRow = row;
  return row;
}

function removeTranscribingIndicator() {
  if (transcribingRow) {
    transcribingRow.remove();
    transcribingRow = null;
  }
}

function setChatEmptyState() {
  removeTranscribingIndicator();
  chatEl.innerHTML = `
    <article class="chat-empty" id="chat-empty">
      <h2>Ready to listen</h2>
      <p>Press Start recording, speak naturally, and the assistant will reply locally.</p>
      <div class="chat-empty-actions">
        <span>1. Record</span>
        <span>2. Transcribe</span>
        <span>3. Reply + play</span>
      </div>
    </article>
  `;
}

function removeChatEmptyState() {
  const empty = document.getElementById('chat-empty');
  if (empty) empty.remove();
}

function clearChat() {
  setChatEmptyState();
  setStatus('Chat cleared.', 'idle');
}

function stopPlayback() {
  if (activeAudioUrl) {
    URL.revokeObjectURL(activeAudioUrl);
    activeAudioUrl = null;
  }
  audioPlayer.pause();
  audioPlayer.removeAttribute('src');
  audioPlayer.load();
}

function stopStream(stream) {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
  }
}

function preferredMimeType() {
  const preferredTypes = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ];
  return preferredTypes.find((type) => window.MediaRecorder?.isTypeSupported?.(type)) || '';
}

function ensureMicCaptureAvailable() {
  if (!window.isSecureContext) {
    setStatus('Microphone capture requires HTTPS or localhost.', 'error');
    return false;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    setStatus('This browser does not support microphone capture.', 'error');
    return false;
  }
  return true;
}

function recorderHasAudio(state) {
  return state.mediaRecorder && state.mediaRecorder.state !== 'inactive';
}

function setChatControls(isRecording) {
  startBtn.disabled = isRecording;
  stopBtn.disabled = !isRecording;
}

function setVoiceControls(isRecording) {
  voiceStartBtn.disabled = isRecording;
  voiceStopBtn.disabled = !isRecording;
}

function resetChatRecorderState() {
  chatState.mediaRecorder = null;
  chatState.stream = null;
  chatState.chunks = [];
  setChatControls(false);
}

function resetVoiceRecorderState() {
  voiceState.mediaRecorder = null;
  voiceState.stream = null;
  voiceState.chunks = [];
  setVoiceControls(false);
}

async function startRecorder(state, onStop) {
  if (!ensureMicCaptureAvailable()) return false;
  state.chunks = [];
  state.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mimeType = preferredMimeType();
  state.mediaRecorder = new MediaRecorder(state.stream, mimeType ? { mimeType } : undefined);

  state.mediaRecorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) {
      state.chunks.push(event.data);
    }
  };

  state.mediaRecorder.onstop = () => {
    stopStream(state.stream);
    state.stream = null;
    onStop().catch((err) => {
      console.error(err);
      setStatus(`Error: ${err.message}`, 'error');
    });
  };

  state.mediaRecorder.start();
  return true;
}

async function startChatRecording() {
  if (recorderHasAudio(voiceState)) {
    setStatus('Stop voice recording before starting chat recording.', 'error');
    return;
  }
  stopPlayback();
  setStatus('Requesting microphone permission...', 'listening');
  try {
    const started = await startRecorder(chatState, handleChatRecordingStop);
    if (!started) return;
    setChatControls(true);
    setStatus('Listening...', 'listening');
  } catch (err) {
    console.error(err);
    setStatus(`Error: ${err.message}`, 'error');
    resetChatRecorderState();
  }
}

function stopChatRecording() {
  if (!recorderHasAudio(chatState)) return;
  setChatControls(false);
  setStatus('Uploading audio...', 'uploading');
  chatState.mediaRecorder.stop();
}

async function handleChatRecordingStop() {
  if (!chatState.chunks.length) {
    setStatus('No audio captured.', 'error');
    resetChatRecorderState();
    return;
  }

  const blob = new Blob(chatState.chunks, { type: chatState.mediaRecorder?.mimeType || 'audio/webm' });
  const formData = new FormData();
  formData.append('audio', blob, 'recording.webm');

  setStatus('Transcribing...', 'transcribing');
  addTranscribingIndicator();

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      body: formData,
    });

    // /api/chat may return 204 No Content (e.g., wake phrase not detected).
    const raw = await response.text();
    const rawTrimmed = raw.trim();

    if (!rawTrimmed) {
      if (response.status === 204) {
        setStatus('No wake phrase detected.', 'idle');
        return;
      }
      throw new Error(`HTTP ${response.status}`);
    }

    const data = JSON.parse(raw);
    if (!response.ok || !data.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }

    addMessage('user', data.transcript);
    addMessage('assistant', data.assistant_reply);
    setStatus('Speaking...', 'speaking');

    if (data.audio_url) {
      stopPlayback();
      audioPlayer.src = data.audio_url;
      activeAudioUrl = null;
      try {
        await audioPlayer.play();
      } catch (err) {
        console.warn(err);
        setStatus('Reply ready. Tap Play to hear audio.', 'idle');
      }
    }

    setStatus('Ready.', 'idle');
  } finally {
    removeTranscribingIndicator();
    resetChatRecorderState();
  }
}

async function startVoiceRecording() {
  if (recorderHasAudio(chatState)) {
    setStatus('Stop chat recording before recording a voice sample.', 'error');
    return;
  }
  if (!voiceNameInput.value.trim()) {
    setStatus('Enter a name for this voice before recording.', 'error');
    voiceNameInput.focus();
    return;
  }
  setStatus('Requesting microphone permission...', 'listening');
  try {
    const started = await startRecorder(voiceState, handleVoiceRecordingStop);
    if (!started) return;
    setVoiceControls(true);
    setStatus('Recording voice sample...', 'listening');
  } catch (err) {
    console.error(err);
    setStatus(`Error: ${err.message}`, 'error');
    resetVoiceRecorderState();
  }
}

function stopVoiceRecording() {
  if (!recorderHasAudio(voiceState)) return;
  setVoiceControls(false);
  setStatus('Saving voice sample...', 'saving');
  voiceState.mediaRecorder.stop();
}

async function handleVoiceRecordingStop() {
  if (!voiceState.chunks.length) {
    setStatus('No voice sample captured.', 'error');
    resetVoiceRecorderState();
    return;
  }

  const name = voiceNameInput.value.trim();
  if (!name) {
    setStatus('Enter a voice name before saving.', 'error');
    resetVoiceRecorderState();
    return;
  }

  const blob = new Blob(voiceState.chunks, { type: voiceState.mediaRecorder?.mimeType || 'audio/webm' });
  const formData = new FormData();
  formData.append('name', name);
  formData.append('audio', blob, 'voice-sample.webm');

  try {
    const response = await fetch('/api/voices', {
      method: 'POST',
      body: formData,
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }

    voiceNameInput.value = '';
    setStatus(`Saved voice “${data.voice.name}”.`, 'idle');
    renderVoiceList(data.voices);
  } finally {
    resetVoiceRecorderState();
    await refreshVoiceLibrary();
  }
}

async function uploadVoiceFile() {
  if (recorderHasAudio(chatState) || recorderHasAudio(voiceState)) {
    setStatus('Stop any active recording before uploading a voice file.', 'error');
    return;
  }

  const name = voiceNameInput.value.trim();
  if (!name) {
    setStatus('Enter a voice name before uploading a file.', 'error');
    voiceNameInput.focus();
    return;
  }

  const file = voiceFileInput?.files?.[0];
  if (!file) {
    setStatus('Choose an audio file to upload.', 'error');
    return;
  }

  const formData = new FormData();
  formData.append('name', name);
  formData.append('audio', file, file.name || 'voice-upload');

  try {
    voiceUploadBtn.disabled = true;
    voiceUploadBtn.textContent = 'Uploading...';
    setStatus('Uploading voice file...', 'uploading');
    const data = await fetchJson('/api/voices', { method: 'POST', body: formData });
    voiceNameInput.value = '';
    voiceFileInput.value = '';
    setStatus(`Uploaded voice “${data.voice.name}”. Converted to WAV automatically.`, 'idle');
    renderVoiceList(data.voices);
  } catch (err) {
    console.error(err);
    setStatus(`Error: ${err.message}`, 'error');
  } finally {
    voiceUploadBtn.disabled = false;
    voiceUploadBtn.textContent = 'Upload file';
    await refreshVoiceLibrary();
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const raw = await response.text();
  const trimmed = raw.trim();

  if (!trimmed) {
    if (response.status === 204) return {};
    // Some endpoints may return an empty body on error.
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return {};
  }

  const data = JSON.parse(raw);
  if (!response.ok || !data.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

function renderVoiceList(voices) {
  if (!voiceListEl) return;
  voiceListEl.innerHTML = '';

  if (!voices.length) {
    const empty = document.createElement('div');
    empty.className = 'voice-empty';
    empty.textContent = 'No saved voices yet.';
    voiceListEl.appendChild(empty);
    return;
  }

  voices.forEach((voice) => {
    const card = document.createElement('article');
    card.className = `voice-card${voice.selected ? ' selected' : ''}`;

    const header = document.createElement('div');
    header.className = 'voice-card-header';

    const titleWrap = document.createElement('div');
    titleWrap.className = 'voice-card-title-wrap';

    const title = document.createElement('strong');
    title.className = 'voice-card-title';
    title.textContent = voice.name;

    const badge = document.createElement('span');
    badge.className = `voice-badge${voice.selected ? ' active' : ''}`;
    badge.textContent = voice.selected ? 'Active' : 'Stored';

    titleWrap.appendChild(title);
    titleWrap.appendChild(badge);

    const meta = document.createElement('div');
    meta.className = 'voice-card-meta';
    meta.textContent = voice.wav_exists ? 'Ready for XTTS' : 'Missing reference WAV';

    header.appendChild(titleWrap);
    header.appendChild(meta);

    const actions = document.createElement('div');
    actions.className = 'voice-card-actions';

    const selectBtn = document.createElement('button');
    selectBtn.textContent = voice.selected ? 'Selected' : 'Use for TTS';
    selectBtn.disabled = voice.selected;
    selectBtn.addEventListener('click', async () => {
      try {
        const formData = new FormData();
        formData.append('voice_id', voice.id);
        const data = await fetchJson('/api/voices/select', { method: 'POST', body: formData });
        setStatus(`Using voice “${data.voice.name}”.`, 'idle');
        renderVoiceList(data.voices);
      } catch (err) {
        console.error(err);
        setStatus(`Error: ${err.message}`, 'error');
      }
    });

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'danger';
    deleteBtn.textContent = 'Delete';
    deleteBtn.addEventListener('click', async () => {
      const ok = window.confirm(`Delete voice “${voice.name}”?`);
      if (!ok) return;
      try {
        const data = await fetchJson(`/api/voices/${encodeURIComponent(voice.id)}`, { method: 'DELETE' });
        renderVoiceList(data.voices);
        setStatus('Voice deleted.', 'idle');
      } catch (err) {
        console.error(err);
        setStatus(`Error: ${err.message}`, 'error');
      }
    });

    actions.appendChild(selectBtn);
    actions.appendChild(deleteBtn);

    card.appendChild(header);
    card.appendChild(actions);
    voiceListEl.appendChild(card);
  });
}

async function refreshVoiceLibrary() {
  try {
    const data = await fetchJson('/api/voices');
    renderVoiceList(data.voices);
  } catch (err) {
    console.warn(err);
    if (voiceListEl) {
      voiceListEl.innerHTML = '<div class="voice-empty error">Could not load saved voices.</div>';
    }
  }
}

// ── Text chat ──────────────────────────────────────────────────────

function isChatting() {
  return textSendBtn.disabled || startBtn.disabled;
}

async function handleTextChat() {
  const text = textInput.value.trim();
  if (!text || isChatting()) return;

  textInput.value = '';
  textSendBtn.disabled = true;
  textInput.disabled = true;

  stopPlayback();
  removeTranscribingIndicator();

  addMessage('user', text);
  setStatus('Thinking...', 'transcribing');

  try {
    const response = await fetch('/api/chat/text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.error || `HTTP ${response.status}`);
    }

    const contentType = response.headers.get('content-type') || '';

    if (contentType.includes('text/event-stream')) {
      // ── Streaming (SSE) ──
      const assistantRow = document.createElement('article');
      assistantRow.className = 'message assistant streaming';
      const head = document.createElement('div');
      head.className = 'message-head';
      head.textContent = 'Assistant';
      const body = document.createElement('div');
      body.className = 'message-body';
      body.textContent = '';
      assistantRow.appendChild(head);
      assistantRow.appendChild(body);
      chatEl.appendChild(assistantRow);
      scrollChatToBottom();

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullReply = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data: ')) continue;
          const dataStr = trimmed.slice(6);
          if (dataStr === '[DONE]') continue;

          try {
            const event = JSON.parse(dataStr);

            if (event.type === 'transcript') {
              // Already shown as user message above; skip.
              continue;
            }

            if (event.type === 'token') {
              body.textContent += event.text;
              fullReply += event.text;
              scrollChatToBottom();
              continue;
            }

            if (event.type === 'sentence') {
              body.textContent += event.text;
              fullReply += event.text;
              scrollChatToBottom();
              if (event.audio_url) {
                stopPlayback();
                audioPlayer.src = event.audio_url;
                activeAudioUrl = null;
                audioPlayer.play().catch(() => {});
              }
              continue;
            }

            if (event.type === 'error') {
              setStatus(`Error: ${event.text}`, 'error');
              continue;
            }
          } catch { /* skip malformed JSON lines */ }
        }
      }

      if (fullReply) {
        setStatus('Ready.', 'idle');
      }
    } else {
      // ── Non-streaming (JSON) ──
      const data = JSON.parse(await response.text());
      addMessage('assistant', data.assistant_reply);
      setStatus('Speaking...', 'speaking');

      if (data.audio_url) {
        stopPlayback();
        audioPlayer.src = data.audio_url;
        activeAudioUrl = null;
        try {
          await audioPlayer.play();
        } catch (err) {
          console.warn(err);
          setStatus('Reply ready. Tap Play to hear audio.', 'idle');
        }
      }
      setStatus('Ready.', 'idle');
    }
  } catch (err) {
    console.error(err);
    setStatus(`Error: ${err.message}`, 'error');
  } finally {
    textSendBtn.disabled = false;
    textInput.disabled = false;
    textInput.focus();
  }
}

textInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    handleTextChat().catch((err) => {
      console.error(err);
      setStatus(`Error: ${err.message}`, 'error');
      textSendBtn.disabled = false;
      textInput.disabled = false;
    });
  }
});

textSendBtn.addEventListener('click', () => {
  handleTextChat().catch((err) => {
    console.error(err);
    setStatus(`Error: ${err.message}`, 'error');
    textSendBtn.disabled = false;
    textInput.disabled = false;
  });
});

// ── Audio events ───────────────────────────────────────────────────

audioPlayer.addEventListener('ended', () => {
  setStatus('Ready.', 'idle');
});

startBtn.addEventListener('click', () => {
  startChatRecording().catch((err) => {
    console.error(err);
    setStatus(`Error: ${err.message}`, 'error');
    resetChatRecorderState();
  });
});

stopBtn.addEventListener('click', stopChatRecording);
clearBtn.addEventListener('click', clearChat);
voiceStartBtn.addEventListener('click', () => {
  startVoiceRecording().catch((err) => {
    console.error(err);
    setStatus(`Error: ${err.message}`, 'error');
    resetVoiceRecorderState();
  });
});
voiceStopBtn.addEventListener('click', stopVoiceRecording);
voiceUploadBtn.addEventListener('click', () => {
  uploadVoiceFile().catch((err) => {
    console.error(err);
    setStatus(`Error: ${err.message}`, 'error');
  });
});

window.addEventListener('beforeunload', () => {
  stopPlayback();
  stopStream(chatState.stream);
  stopStream(voiceState.stream);
});

(async function init() {
  if (!window.isSecureContext) {
    setConnectionNote(
      'Microphone capture requires HTTPS or localhost. For Android over USB, run: adb reverse tcp:8000 tcp:8000 then open http://127.0.0.1:8000 on the phone.',
      'warning',
    );
  } else {
    setConnectionNote(`Connected on ${window.location.origin}.`, 'ok');
  }

  try {
    const sessionData = await fetchJson('/api/session');
    if (sessionData.messages?.length) {
      sessionData.messages.filter((m) => m.role !== 'system').forEach((m) => addMessage(m.role, m.content));
    } else {
      setChatEmptyState();
    }
    await refreshVoiceLibrary();
    setStatus('Ready.', 'idle');
  } catch (err) {
    console.warn(err);
    setChatEmptyState();
    setStatus('Ready, but session history could not be loaded.', 'error');
  }
})();
