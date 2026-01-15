// State
let currentView = 'upload';
let currentTranscriptionId = null;
let eventSource = null;
let logs = [];

// Stage labels
const STAGE_LABELS = {
    loading_audio: 'Loading Audio',
    transcribing: 'Transcribing',
    diarizing: 'Identifying Speakers',
    saving: 'Saving Results',
    complete: 'Complete'
};

// DOM Elements
const elements = {
    // Navigation
    btnUpload: document.getElementById('btn-upload'),
    btnHistory: document.getElementById('btn-history'),

    // Views
    viewUpload: document.getElementById('view-upload'),
    viewTranscription: document.getElementById('view-transcription'),
    viewHistory: document.getElementById('view-history'),

    // Upload
    dropzone: document.getElementById('dropzone'),
    fileInput: document.getElementById('file-input'),

    // Progress
    progressSection: document.getElementById('progress-section'),
    progressFilename: document.getElementById('progress-filename'),
    progressStatus: document.getElementById('progress-status'),
    progressBar: document.getElementById('progress-bar'),
    progressError: document.getElementById('progress-error'),

    // Stage
    stageIndicator: document.getElementById('stage-indicator'),
    stageDescription: document.getElementById('stage-description'),

    // Logs
    logsPanel: document.getElementById('logs-panel'),
    logsToggle: document.getElementById('logs-toggle'),
    logsCount: document.getElementById('logs-count'),
    logsContent: document.getElementById('logs-content'),

    // Progress actions
    progressActions: document.getElementById('progress-actions'),
    btnViewResult: document.getElementById('btn-view-result'),
    btnDownloadResult: document.getElementById('btn-download-result'),

    // Transcription
    btnBack: document.getElementById('btn-back'),
    transcriptionFilename: document.getElementById('transcription-filename'),
    transcriptionContent: document.getElementById('transcription-content'),

    // History
    historyList: document.getElementById('history-list'),

    // Download
    btnDownload: document.getElementById('btn-download'),

    // Modal
    speakerModal: document.getElementById('speaker-modal'),
    modalSpeakerLabel: document.getElementById('modal-speaker-label'),
    modalSpeakerInput: document.getElementById('modal-speaker-input'),
    modalCancel: document.getElementById('modal-cancel'),
    modalSave: document.getElementById('modal-save')
};

// View Management
function showView(view) {
    currentView = view;

    elements.viewUpload.classList.toggle('hidden', view !== 'upload');
    elements.viewTranscription.classList.toggle('hidden', view !== 'transcription');
    elements.viewHistory.classList.toggle('hidden', view !== 'history');

    elements.btnUpload.classList.toggle('active', view === 'upload');
    elements.btnHistory.classList.toggle('active', view === 'history');

    if (view === 'history') {
        loadHistory();
    }
}

// File Upload
function setupDropzone() {
    const dropzone = elements.dropzone;
    const fileInput = elements.fileInput;

    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) uploadFile(file);
    });

    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        if (file) uploadFile(file);
    });
}

async function uploadFile(file) {
    // Show progress section
    elements.dropzone.classList.add('hidden');
    elements.progressSection.classList.remove('hidden');
    elements.progressFilename.textContent = file.name;
    elements.progressStatus.textContent = 'Uploading...';
    elements.progressStatus.className = 'status';
    elements.progressBar.style.width = '0%';
    elements.progressError.classList.add('hidden');
    elements.stageIndicator.classList.add('hidden');
    elements.logsPanel.classList.add('hidden');
    elements.progressActions.classList.add('hidden');
    logs = [];

    const formData = new FormData();
    formData.append('file', file);

    try {
        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                elements.progressBar.style.width = percent + '%';
            }
        });

        xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                const response = JSON.parse(xhr.responseText);
                currentTranscriptionId = response.id;
                startProgressStream(response.id);
                pollStatus(response.id);
            } else {
                let error = 'Upload failed';
                try {
                    const resp = JSON.parse(xhr.responseText);
                    error = resp.message || resp.detail || error;
                } catch (e) {}
                showError(error);
            }
        });

        xhr.addEventListener('error', () => {
            showError('Network error during upload');
        });

        xhr.open('POST', '/api/transcribe');
        xhr.send(formData);

    } catch (error) {
        showError(error.message || 'Upload failed');
    }
}

// Progress Stream (SSE)
function startProgressStream(transcriptionId) {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource(`/api/transcribe/${transcriptionId}/progress`);

    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleProgressEvent(data);
        } catch (e) {
            console.error('Failed to parse progress event:', e);
        }
    };

    eventSource.onerror = () => {
        eventSource.close();
        eventSource = null;
    };
}

function handleProgressEvent(data) {
    switch (data.event) {
        case 'stage':
            updateStage(data.stage, data.description);
            break;
        case 'log':
            addLog(data.timestamp, data.level, data.message);
            break;
        case 'complete':
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
            break;
        case 'error':
            showError(data.message);
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
            break;
    }
}

function updateStage(stage, description) {
    elements.stageIndicator.classList.remove('hidden');

    const stages = ['loading_audio', 'transcribing', 'diarizing', 'saving'];
    const currentIndex = stages.indexOf(stage);

    document.querySelectorAll('.stage').forEach((el, idx) => {
        el.classList.remove('completed', 'active');
        if (idx < currentIndex) {
            el.classList.add('completed');
        } else if (idx === currentIndex) {
            el.classList.add('active');
        }
    });

    elements.stageDescription.textContent = description || STAGE_LABELS[stage] || 'Processing...';
}

function addLog(timestamp, level, message) {
    logs.push({ timestamp, level, message });
    if (logs.length > 100) logs.shift();

    elements.logsPanel.classList.remove('hidden');
    elements.logsCount.textContent = logs.length;

    const entry = document.createElement('div');
    entry.className = 'log-entry' + (level === 'ERROR' ? ' error' : level === 'WARNING' ? ' warning' : '');

    const time = new Date(timestamp).toLocaleTimeString();
    entry.innerHTML = `<span class="timestamp">${time}</span> <span class="level">[${level}]</span> ${escapeHtml(message)}`;

    elements.logsContent.appendChild(entry);
    elements.logsContent.scrollTop = elements.logsContent.scrollHeight;
}

// Status Polling
async function pollStatus(transcriptionId) {
    elements.progressStatus.textContent = 'Processing...';
    elements.progressStatus.className = 'status processing';
    elements.progressBar.style.width = '100%';
    elements.progressActions.classList.add('hidden');

    const poll = async () => {
        try {
            const response = await fetch(`/api/transcribe/${transcriptionId}/status`);
            const data = await response.json();

            if (data.status === 'completed') {
                elements.progressStatus.textContent = 'Complete!';
                elements.progressStatus.className = 'status completed';
                elements.progressActions.classList.remove('hidden');
            } else if (data.status === 'failed') {
                showError(data.error_message || 'Transcription failed');
            } else {
                setTimeout(poll, 2000);
            }
        } catch (error) {
            setTimeout(poll, 2000);
        }
    };

    poll();
}

function showError(message) {
    elements.progressStatus.textContent = 'Failed';
    elements.progressStatus.className = 'status failed';
    elements.progressError.textContent = message;
    elements.progressError.classList.remove('hidden');
}

// Transcription View
async function loadTranscription(transcriptionId) {
    currentTranscriptionId = transcriptionId;
    showView('transcription');

    elements.transcriptionContent.innerHTML = '<div class="loading">Loading transcription...</div>';

    try {
        const response = await fetch(`/api/transcribe/${transcriptionId}`);
        const data = await response.json();

        elements.transcriptionFilename.textContent = data.filename;
        renderTranscription(data);
    } catch (error) {
        elements.transcriptionContent.innerHTML = '<div class="error">Failed to load transcription</div>';
    }
}

function renderTranscription(data) {
    const content = elements.transcriptionContent;
    content.innerHTML = '';

    data.segments.forEach((segment) => {
        const div = document.createElement('div');
        div.className = 'segment';

        // Use speaker_label for consistent coloring (even with custom names)
        const speakerLabel = segment.speaker_label || segment.speaker;
        const speakerIndex = parseInt(speakerLabel.replace('SPEAKER_', '')) % 6;

        div.innerHTML = `
            <div class="segment-header">
                <button class="speaker-btn speaker-${speakerIndex}" data-label="${escapeHtml(speakerLabel)}" data-name="${escapeHtml(segment.speaker)}">
                    ${escapeHtml(segment.speaker)}
                </button>
                <span class="timestamp">${formatTime(segment.start_time)} - ${formatTime(segment.end_time)}</span>
            </div>
            <p class="segment-text">${escapeHtml(segment.text)}</p>
        `;

        div.querySelector('.speaker-btn').addEventListener('click', (e) => {
            openSpeakerModal(e.target.dataset.label, e.target.dataset.name);
        });

        content.appendChild(div);
    });
}

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Speaker Modal
let editingSpeakerLabel = null;

function openSpeakerModal(label, currentName) {
    editingSpeakerLabel = label;
    elements.modalSpeakerLabel.textContent = label;
    elements.modalSpeakerInput.value = currentName !== label ? currentName : '';
    elements.speakerModal.classList.remove('hidden');
    elements.modalSpeakerInput.focus();
}

function closeSpeakerModal() {
    elements.speakerModal.classList.add('hidden');
    editingSpeakerLabel = null;
}

async function saveSpeakerName() {
    const newName = elements.modalSpeakerInput.value.trim() || null;

    try {
        const response = await fetch(`/api/transcribe/${currentTranscriptionId}/speakers`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                speaker_label: editingSpeakerLabel,
                custom_speaker_name: newName
            })
        });

        if (response.ok) {
            closeSpeakerModal();
            loadTranscription(currentTranscriptionId);
        }
    } catch (error) {
        console.error('Failed to update speaker:', error);
    }
}

// Download
function downloadTranscription(transcriptionId) {
    window.location.href = `/api/transcribe/${transcriptionId}/download`;
}

// History
async function loadHistory() {
    elements.historyList.innerHTML = '<div class="loading">Loading history...</div>';

    try {
        const response = await fetch('/api/history');
        const data = await response.json();

        if (data.items.length === 0) {
            elements.historyList.innerHTML = '<div class="empty-state">No transcriptions yet</div>';
            return;
        }

        elements.historyList.innerHTML = '';
        data.items.forEach((item) => {
            const div = document.createElement('div');
            div.className = 'history-item';
            div.innerHTML = `
                <div class="history-item-header">
                    <span class="history-item-filename">${escapeHtml(item.filename)}</span>
                    <span class="history-item-status ${item.status}">${item.status}</span>
                </div>
                <span class="history-item-date">${new Date(item.created_at).toLocaleString('pt-BR')}</span>
                ${item.status === 'completed' ? `
                <div class="history-item-actions">
                    <button class="btn btn-secondary btn-sm btn-view" data-id="${item.id}">View</button>
                    <button class="btn btn-primary btn-sm btn-download-item" data-id="${item.id}">Download MD</button>
                </div>
                ` : ''}
            `;

            // Add event listeners for buttons
            const viewBtn = div.querySelector('.btn-view');
            const downloadBtn = div.querySelector('.btn-download-item');

            if (viewBtn) {
                viewBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    loadTranscription(item.id);
                });
            }

            if (downloadBtn) {
                downloadBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    downloadTranscription(item.id);
                });
            }

            elements.historyList.appendChild(div);
        });
    } catch (error) {
        elements.historyList.innerHTML = '<div class="error">Failed to load history</div>';
    }
}

// Utilities
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Reset upload view
function resetUpload() {
    elements.dropzone.classList.remove('hidden');
    elements.progressSection.classList.add('hidden');
    elements.fileInput.value = '';
    currentTranscriptionId = null;
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
}

// Event Listeners
function setupEventListeners() {
    elements.btnUpload.addEventListener('click', () => {
        resetUpload();
        showView('upload');
    });

    elements.btnHistory.addEventListener('click', () => showView('history'));

    elements.btnBack.addEventListener('click', () => showView('history'));

    elements.btnDownload.addEventListener('click', () => {
        if (currentTranscriptionId) {
            downloadTranscription(currentTranscriptionId);
        }
    });

    elements.btnViewResult.addEventListener('click', () => {
        if (currentTranscriptionId) {
            loadTranscription(currentTranscriptionId);
        }
    });

    elements.btnDownloadResult.addEventListener('click', () => {
        if (currentTranscriptionId) {
            downloadTranscription(currentTranscriptionId);
        }
    });

    elements.logsToggle.addEventListener('click', () => {
        elements.logsToggle.classList.toggle('expanded');
        elements.logsContent.classList.toggle('hidden');
    });

    elements.modalCancel.addEventListener('click', closeSpeakerModal);
    elements.modalSave.addEventListener('click', saveSpeakerName);

    elements.speakerModal.addEventListener('click', (e) => {
        if (e.target === elements.speakerModal) {
            closeSpeakerModal();
        }
    });

    elements.modalSpeakerInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') saveSpeakerName();
        if (e.key === 'Escape') closeSpeakerModal();
    });
}

// Initialize
function init() {
    setupDropzone();
    setupEventListeners();
    showView('upload');
}

document.addEventListener('DOMContentLoaded', init);
