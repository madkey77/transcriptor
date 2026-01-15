import { useState, useCallback } from 'react'
import { transcriptionApi, TranscriptionCreated } from '@/services/transcription'
import { ApiError } from '@/services/api'

export interface UploadState {
  isUploading: boolean
  progress: number
  error: string | null
  transcriptionId: string | null
}

export function useUpload() {
  const [state, setState] = useState<UploadState>({
    isUploading: false,
    progress: 0,
    error: null,
    transcriptionId: null,
  })

  const upload = useCallback(async (file: File): Promise<TranscriptionCreated | null> => {
    setState({
      isUploading: true,
      progress: 0,
      error: null,
      transcriptionId: null,
    })

    try {
      const result = await transcriptionApi.upload(file, (progress) => {
        setState((prev) => ({ ...prev, progress }))
      })

      setState({
        isUploading: false,
        progress: 100,
        error: null,
        transcriptionId: result.id,
      })

      return result
    } catch (error) {
      const apiError = error as ApiError
      setState({
        isUploading: false,
        progress: 0,
        error: apiError.message || 'Upload failed',
        transcriptionId: null,
      })
      return null
    }
  }, [])

  const reset = useCallback(() => {
    setState({
      isUploading: false,
      progress: 0,
      error: null,
      transcriptionId: null,
    })
  }, [])

  return {
    ...state,
    upload,
    reset,
  }
}
