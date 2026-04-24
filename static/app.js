const chatEl = document.getElementById('chat');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const clearBtn = document.getElementById('clear-btn');
const statusText = document.getElementById('status-text');
const statusPill = document.getElementById('status-pill');
const audioPlayer = document.getElementById('audio-player');

let mediaRecorder = null;
let chunks = [];
let recordingStream = null;
let activeAudioUrl = null;
let transcribingRow = null;

function setStatus(text, mode = 'idle') {
  statusText.textContent = text;
  statusPill.textContent = mode === 'transcribing' ? 'transcribing…' : mode;
  statusPill.dataset.mode = mode;
}

function scrollChatToBottom() {
  chatEl.scrollTop = chatEl.scrollHeight;
}

function addMessage(role, text) {
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

function clearChat() {
  removeTranscribingIndicator();
  chatEl.innerHTML = '';
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

async function startRecording() {
  if (!window.isSecureContext) {
    setStatus('Microphone capture requires HTTPS or localhost.', 'error');
    return;
  }

  if (!navigator.mediaDevices?.getUserMedia) {
    setStatus('This browser does not support microphone capture.', 'error');
    return;
  }

  stopPlayback();
  setStatus('Requesting microphone permission...', 'listening');

  recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  chunks = [];

  const preferredTypes = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ];
  const mimeType = preferredTypes.find((type) => window.MediaRecorder?.isTypeSupported?.(type)) || '';
  mediaRecorder = new MediaRecorder(recordingStream, mimeType ? { mimeType } : undefined);

  mediaRecorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) chunks.push(event.data);
  };

  mediaRecorder.onstop = () => {
    if (recordingStream) {
      recordingStream.getTracks().forEach((track) => track.stop());
      recordingStream = null;
    }
    sendRecording().catch((err) => {
      console.error(err);
      setStatus(`Error: ${err.message}`, 'error');
    });
  };

  mediaRecorder.start();
  startBtn.disabled = true;
  stopBtn.disabled = false;
  setStatus('Listening...', 'listening');
}

function stopRecording() {
  if (!mediaRecorder || mediaRecorder.state === 'inactive') return;
  mediaRecorder.stop();
  startBtn.disabled = false;
  stopBtn.disabled = true;
  setStatus('Uploading audio...', 'uploading');
}

async function sendRecording() {
  if (!chunks.length) {
    setStatus('No audio captured.', 'error');
    return;
  }

  const blob = new Blob(chunks, { type: mediaRecorder?.mimeType || 'audio/webm' });
  const formData = new FormData();
  formData.append('audio', blob, 'recording.webm');

  setStatus('Transcribing...', 'transcribing');
  addTranscribingIndicator();

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      body: formData,
    });

    const data = await response.json();
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
      await audioPlayer.play();
    }

    setStatus('Ready.', 'idle');
  } finally {
    removeTranscribingIndicator();
  }
}

audioPlayer.addEventListener('ended', () => {
  setStatus('Ready.', 'idle');
});

startBtn.addEventListener('click', () => {
  startRecording().catch((err) => {
    console.error(err);
    setStatus(`Error: ${err.message}`, 'error');
    startBtn.disabled = false;
    stopBtn.disabled = true;
  });
});

stopBtn.addEventListener('click', stopRecording);
clearBtn.addEventListener('click', clearChat);

window.addEventListener('beforeunload', () => {
  stopPlayback();
  if (recordingStream) recordingStream.getTracks().forEach((track) => track.stop());
});

(async function init() {
  try {
    const res = await fetch('/api/session');
    const data = await res.json();
    if (data.messages?.length) {
      data.messages.filter((m) => m.role !== 'system').forEach((m) => addMessage(m.role, m.content));
    }
    setStatus('Ready.', 'idle');
  } catch (err) {
    console.warn(err);
    setStatus('Ready, but session history could not be loaded.', 'error');
  }
})();
