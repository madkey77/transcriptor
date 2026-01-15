# Transcriptor Frontend

React frontend for audio transcription web application.

## Setup

```bash
npm install
```

## Development

```bash
npm run dev
```

Open http://localhost:5173

## Build

```bash
npm run build
npm run preview  # Preview production build
```

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── ui/           # shadcn/ui base components
│   │   ├── upload/
│   │   │   ├── FileDropzone.tsx    # Drag & drop upload
│   │   │   └── UploadProgress.tsx  # Upload/processing status
│   │   ├── transcription/
│   │   │   ├── TranscriptionView.tsx  # Display transcription
│   │   │   ├── SpeakerEditor.tsx      # Edit speaker names
│   │   │   └── DownloadButton.tsx     # Export options
│   │   └── history/
│   │       └── HistoryList.tsx        # Transcription history
│   ├── hooks/
│   │   ├── useUpload.ts          # File upload logic
│   │   ├── useTranscription.ts   # Transcription data
│   │   └── useHistory.ts         # History list
│   ├── services/
│   │   ├── api.ts                # API client
│   │   └── transcription.ts      # Transcription API calls
│   ├── lib/
│   │   └── utils.ts              # Utility functions
│   ├── App.tsx                   # Main application
│   ├── main.tsx                  # Entry point
│   └── index.css                 # Global styles
├── public/
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

## Key Components

### FileDropzone
Drag-and-drop area for audio file upload. Validates file format and size.

### UploadProgress
Shows upload progress and transcription processing status.

### TranscriptionView
Displays transcription with speaker-labeled segments. Supports speaker name editing.

### SpeakerEditor
Modal for editing speaker names with validation.

### DownloadButton
Dropdown for downloading transcription in TXT, JSON, or SRT format.

### HistoryList
Lists all transcriptions with status and date. Click to view details.

## Styling

Uses Tailwind CSS with shadcn/ui design system. Theme colors defined in `src/index.css`.
