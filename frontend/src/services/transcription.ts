import { apiClient } from './api'

export interface TranscriptionCreated {
  id: string
  status: string
  filename: string
  position: number
}

export type ProcessingStage =
  | 'queued'
  | 'loading_audio'
  | 'transcribing'
  | 'diarizing'
  | 'saving'
  | 'complete'

export const STAGE_LABELS: Record<ProcessingStage, string> = {
  queued: 'Queued',
  loading_audio: 'Loading Audio',
  transcribing: 'Transcribing',
  diarizing: 'Identifying Speakers',
  saving: 'Saving Results',
  complete: 'Complete',
}

export interface TranscriptionStatus {
  id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  current_stage?: ProcessingStage | null
  error_message?: string
}

export interface Segment {
  id: number
  speaker: string
  text: string
  start_time: number
  end_time: number
  is_custom_name: boolean
}

export interface Speaker {
  speaker_label: string
  custom_speaker_name?: string
  segment_count: number
}

export interface TranscriptionDetail {
  id: string
  filename: string
  file_size: number
  upload_timestamp: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  error_message?: string
  created_at: string
  updated_at: string
  segments: Segment[]
  speakers: Speaker[]
}

export interface SpeakerUpdate {
  speaker_label: string
  custom_speaker_name: string | null
}

export interface SpeakerUpdateResponse {
  success: boolean
  updated_segments: number
}

export interface ProgressEventPayload {
  event: 'progress'
  stage: ProcessingStage
  pct: number
  timestamp?: string
}

export interface TranscriptionSummary {
  id: string
  filename: string
  status: string
  created_at: string
  speaker_count?: number
}

export interface TranscriptionList {
  total: number
  items: TranscriptionSummary[]
}

export const transcriptionApi = {
  upload: (file: File, onProgress?: (progress: number) => void) =>
    apiClient.uploadFile<TranscriptionCreated>('/transcribe', file, onProgress),

  getStatus: (id: string) =>
    apiClient.get<TranscriptionStatus>(`/transcribe/${id}/status`),

  getTranscription: (id: string) =>
    apiClient.get<TranscriptionDetail>(`/transcribe/${id}`),

  updateSpeaker: (id: string, update: SpeakerUpdate) =>
    apiClient.patch<SpeakerUpdateResponse>(`/transcribe/${id}/speakers`, update),

  cancel: (id: string) =>
    apiClient.delete<void>(`/transcribe/${id}`),

  getHistory: (limit = 50, offset = 0) =>
    apiClient.get<TranscriptionList>(`/history?limit=${limit}&offset=${offset}`),

  getDownloadUrl: (id: string, format: 'txt' | 'json' | 'srt') =>
    apiClient.getDownloadUrl(id, format),
}
