const chatEl = document.getElementById('chat');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const clearBtn = document.getElementById('clear-btn');
const statusText = document.getElementById('status-text');
const statusPill = document.getElementById('status-pill');
const audioPlayer = document.getElementById('audio-player');
const handsFreeToggle = document.getElementById('hands-free-mode');
const vadIndicator = document.getElementById('vad-indicator');
const volumeBar = document.getElementById('volume-bar');

let mediaRecorder = null;
let chunks = [];
let recordingStream = null;
let activeAudioUrl = null;

// Audio Queue for sentence-by-sentence TTS
let audioQueue = [];
let isPlayingQueue = false;

// VAD State
let audioContext = null;
let analyser = null;
let microphone = null;
let javascriptNode = null;
let isSpeaking = false;
let silenceStart = null;
const SILENCE_THRESHOLD = 0.015;
const SILENCE_DURATION = 1500;

// Config
let config = {};

async function loadConfig() {
  const res = await fetch('/api/config');
  config = await res.json();
  handsFreeToggle.checked = config.hands_free_mode || false;
}

function setStatus(text, mode = 'idle') {
  statusText.textContent = text;
  statusPill.textContent = mode;
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
  return { row, body };
}

async function clearChat() {
  await fetch('/api/clear', { method: 'POST' });
  chatEl.innerHTML = '';
  setStatus('Chat cleared.', 'idle');
}

function stopPlayback() {
  audioQueue = [];
  isPlayingQueue = false;
  audioPlayer.pause();
  audioPlayer.src = '';
}

async function playNextInQueue() {
  if (audioQueue.length === 0) {
    isPlayingQueue = false;
    if (statusPill.textContent === 'speaking') setStatus('Ready.', 'idle');
    return;
  }
  isPlayingQueue = true;
  const url = audioQueue.shift();
  audioPlayer.src = url;
  try {
    await audioPlayer.play();
  } catch (e) {
    console.error("Playback failed", e);
    playNextInQueue();
  }
}

audioPlayer.onended = () => {
  playNextInQueue();
};

async function startRecording(auto = false) {
  if (mediaRecorder && mediaRecorder.state === 'recording') return;
  
  stopPlayback();
  if (!recordingStream) {
    recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  }
  
  chunks = [];
  const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus'].find(t => MediaRecorder.isTypeSupported(t));
  mediaRecorder = new MediaRecorder(recordingStream, mimeType ? { mimeType } : undefined);

  mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
  mediaRecorder.onstop = () => {
    sendRecording();
  };

  mediaRecorder.start();
  startBtn.disabled = true;
  stopBtn.disabled = false;
  setStatus('Listening...', 'listening');
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
  }
  startBtn.disabled = false;
  stopBtn.disabled = true;
  setStatus('Processing...', 'uploading');
}

async function sendRecording() {
  if (!chunks.length) {
    setStatus('Ready.', 'idle');
    startBtn.disabled = false;
    return;
  }

  const blob = new Blob(chunks, { type: mediaRecorder.mimeType });
  const formData = new FormData();
  formData.append('audio', blob, 'recording.webm');

  setStatus('Transcribing...', 'transcribing');
  
  try {
    const response = await fetch('/api/chat', { method: 'POST', body: formData });
    
    if (response.status === 204) {
        // Wake word not heard or silent
        setStatus('Ready.', 'idle');
        return;
    }

    if (response.headers.get('content-type')?.includes('text/event-stream')) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantMsg = null;
        let assistantText = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const data = JSON.parse(line);
                    if (data.type === 'transcript') {
                        addMessage('user', data.text);
                    } else if (data.type === 'token') {
                        assistantText += data.text;
                        if (!assistantMsg) assistantMsg = addMessage('assistant', assistantText);
                        else assistantMsg.body.textContent = assistantText;
                        scrollChatToBottom();
                    } else if (data.type === 'sentence') {
                        if (data.audio_url) {
                            audioQueue.push(data.audio_url);
                            if (!isPlayingQueue) {
                                setStatus('Speaking...', 'speaking');
                                playNextInQueue();
                            }
                        }
                    } else if (data.type === 'tool_result') {
                        addMessage('assistant', `[Tool ${data.tool}] Result: ${data.result}`);
                    } else if (data.type === 'error') {
                        throw new Error(data.text);
                    }
                } catch (e) { console.warn("Parse error", e); }
            }
        }
    } else {
        const data = await response.json();
        if (!data.ok) throw new Error(data.error);
        addMessage('user', data.transcript);
        addMessage('assistant', data.assistant_reply);
        if (data.audio_url) {
            audioQueue.push(data.audio_url);
            playNextInQueue();
        }
    }
  } catch (err) {
    setStatus(`Error: ${err.message}`, 'error');
  } finally {
    if (!handsFreeToggle.checked) setStatus('Ready.', 'idle');
  }
}

async function initVAD() {
    if (audioContext) return;
    try {
        recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        microphone = audioContext.createMediaStreamSource(recordingStream);
        javascriptNode = audioContext.createScriptProcessor(2048, 1, 1);

        analyser.smoothingTimeConstant = 0.8;
        analyser.fftSize = 1024;

        microphone.connect(analyser);
        analyser.connect(javascriptNode);
        javascriptNode.connect(audioContext.destination);

        javascriptNode.onaudioprocess = () => {
            const array = new Uint8Array(analyser.frequencyBinCount);
            analyser.getByteFrequencyData(array);
            let values = 0;
            for (let i = 0; i < array.length; i++) values += array[i];
            const average = values / array.length;
            const volume = average / 128;
            
            volumeBar.style.width = Math.min(100, volume * 100) + '%';

            if (handsFreeToggle.checked) {
                if (volume > SILENCE_THRESHOLD) {
                    if (!isSpeaking) {
                        isSpeaking = true;
                        if (statusPill.textContent !== 'listening' && statusPill.textContent !== 'speaking' && statusPill.textContent !== 'uploading' && statusPill.textContent !== 'transcribing') {
                            startRecording(true);
                        }
                    }
                    silenceStart = null;
                } else {
                    if (isSpeaking) {
                        if (!silenceStart) silenceStart = Date.now();
                        if (Date.now() - silenceStart > SILENCE_DURATION) {
                            isSpeaking = false;
                            silenceStart = null;
                            stopRecording();
                        }
                    }
                }
            }
        };
    } catch (e) {
        console.warn("VAD init failed", e);
    }
}

handsFreeToggle.onchange = () => {
    if (handsFreeToggle.checked) {
        vadIndicator.style.display = 'block';
        initVAD();
    } else {
        vadIndicator.style.display = 'none';
        if (mediaRecorder && mediaRecorder.state === 'recording') stopRecording();
    }
};

window.onkeydown = (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (e.key === (config.push_to_talk_key || ' ')) {
        if (statusPill.textContent === 'idle' || statusPill.textContent === 'ready') {
            startRecording();
        }
    }
};
window.onkeyup = (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (e.key === (config.push_to_talk_key || ' ')) {
        if (statusPill.textContent === 'listening') {
            stopRecording();
        }
    }
};

startBtn.onclick = () => startRecording();
stopBtn.onclick = () => stopRecording();
clearBtn.onclick = () => clearChat();

loadConfig();
initVAD();
