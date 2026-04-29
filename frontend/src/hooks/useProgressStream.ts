import { useState, useEffect, useCallback, useRef } from 'react'
import { getApiKey } from '@/services/auth'

export interface LogEntry {
  timestamp: string
  level: string
  message: string
}

export interface ProgressState {
  isConnected: boolean
  currentStage: string | null
  stageDescription: string | null
  progressPct: number | null
  logs: LogEntry[]
  isComplete: boolean
  error: string | null
}

interface ProgressEvent {
  event: 'connected' | 'stage' | 'log' | 'progress' | 'complete' | 'error' | 'status'
  timestamp?: string
  stage?: string
  description?: string
  pct?: number
  level?: string
  message?: string
  data?: Record<string, unknown>
}

export function useProgressStream(transcriptionId: string | null) {
  const [state, setState] = useState<ProgressState>({
    isConnected: false,
    currentStage: null,
    stageDescription: null,
    progressPct: null,
    logs: [],
    isComplete: false,
    error: null,
  })

  const eventSourceRef = useRef<EventSource | null>(null)

  const connect = useCallback(() => {
    if (!transcriptionId) return

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    const apiKey = getApiKey()
    const url = apiKey
      ? `/api/transcribe/${transcriptionId}/progress?api_key=${encodeURIComponent(apiKey)}`
      : `/api/transcribe/${transcriptionId}/progress`
    const eventSource = new EventSource(url)
    eventSourceRef.current = eventSource

    eventSource.onopen = () => {
      setState(prev => ({ ...prev, isConnected: true }))
    }

    eventSource.onmessage = (event) => {
      try {
        const data: ProgressEvent = JSON.parse(event.data)

        setState(prev => {
          switch (data.event) {
            case 'connected':
              return { ...prev, isConnected: true }

            case 'stage':
              return {
                ...prev,
                currentStage: data.stage || null,
                stageDescription: data.description || null,
              }

            case 'progress':
              return {
                ...prev,
                currentStage: data.stage || prev.currentStage,
                progressPct: typeof data.pct === 'number' ? data.pct : prev.progressPct,
              }

            case 'log':
              return {
                ...prev,
                logs: [
                  ...prev.logs,
                  {
                    timestamp: data.timestamp || new Date().toISOString(),
                    level: data.level || 'INFO',
                    message: data.message || '',
                  },
                ].slice(-100), // Keep last 100 logs
              }

            case 'complete':
              return { ...prev, isComplete: true }

            case 'error':
              return { ...prev, error: data.message || 'Unknown error' }

            case 'status': {
              // Handle immediate status response for completed/failed
              const status = data.data as Record<string, unknown>
              return {
                ...prev,
                currentStage: (status?.current_stage as string) || null,
                isComplete: status?.status === 'completed',
                error: status?.status === 'failed' ? (status?.error_message as string) : null,
              }
            }

            default:
              return prev
          }
        })

        // Close connection on complete or error
        if (data.event === 'complete' || data.event === 'error') {
          eventSource.close()
        }
      } catch (e) {
        console.error('Failed to parse progress event:', e)
      }
    }

    eventSource.onerror = () => {
      setState(prev => ({ ...prev, isConnected: false }))
      eventSource.close()
    }
  }, [transcriptionId])

  useEffect(() => {
    connect()

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [connect])

  const reset = useCallback(() => {
    setState({
      isConnected: false,
      currentStage: null,
      stageDescription: null,
      progressPct: null,
      logs: [],
      isComplete: false,
      error: null,
    })
  }, [])

  return { ...state, reset }
}
