import { useState } from 'react'
import { Loader2, CheckCircle, XCircle, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ProcessingStage, STAGE_LABELS } from '@/services/transcription'
import { LogEntry } from '@/hooks/useProgressStream'

type Status = 'uploading' | 'pending' | 'processing' | 'completed' | 'failed'

interface UploadProgressProps {
  status: Status
  progress?: number
  filename?: string
  error?: string | null
  className?: string
  currentStage?: ProcessingStage | null
  stageDescription?: string | null
  logs?: LogEntry[]
  showLogs?: boolean
}

export function UploadProgress({
  status,
  progress = 0,
  filename,
  error,
  className,
  currentStage,
  stageDescription,
  logs = [],
  showLogs = true,
}: UploadProgressProps) {
  const [logsExpanded, setLogsExpanded] = useState(false)

  return (
    <div className={cn('rounded-lg border p-6', className)}>
      <div className="flex items-center gap-4">
        <StatusIcon status={status} />
        <div className="flex-1">
          <div className="flex justify-between items-center mb-2">
            <span className="font-medium">
              {filename || 'Processing...'}
            </span>
            <StatusText status={status} />
          </div>

          {(status === 'uploading' || status === 'processing') && (
            <div className="w-full bg-muted rounded-full h-2 mb-2">
              <div
                className="bg-primary rounded-full h-2 transition-all duration-300"
                style={{
                  width: status === 'processing' ? '100%' : `${progress}%`,
                }}
              />
            </div>
          )}

          {/* Stage indicator */}
          {status === 'processing' && currentStage && (
            <div className="mt-3">
              <StageIndicator
                currentStage={currentStage}
                description={stageDescription}
              />
            </div>
          )}

          {error && (
            <p className="text-sm text-destructive mt-2">{error}</p>
          )}
        </div>
      </div>

      {/* Collapsible log panel */}
      {showLogs && logs.length > 0 && (
        <div className="mt-4 border-t pt-4">
          <button
            onClick={() => setLogsExpanded(!logsExpanded)}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground w-full"
          >
            {logsExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            <span>Processing Logs ({logs.length})</span>
          </button>

          {logsExpanded && (
            <LogPanel logs={logs} />
          )}
        </div>
      )}
    </div>
  )
}

function StageIndicator({
  currentStage,
  description,
}: {
  currentStage: ProcessingStage
  description?: string | null
}) {
  const stages: ProcessingStage[] = ['loading_audio', 'transcribing', 'diarizing', 'saving']
  const currentIndex = stages.indexOf(currentStage)

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1">
        {stages.map((stage, index) => (
          <div key={stage} className="flex items-center gap-1">
            <div
              className={cn(
                'w-3 h-3 rounded-full transition-colors',
                index < currentIndex ? 'bg-green-500' :
                index === currentIndex ? 'bg-primary animate-pulse' :
                'bg-muted'
              )}
              title={STAGE_LABELS[stage]}
            />
            {index < stages.length - 1 && (
              <div
                className={cn(
                  'w-8 h-0.5',
                  index < currentIndex ? 'bg-green-500' : 'bg-muted'
                )}
              />
            )}
          </div>
        ))}
      </div>
      <p className="text-sm text-muted-foreground">
        {description || STAGE_LABELS[currentStage] || 'Processing...'}
      </p>
    </div>
  )
}

function LogPanel({ logs }: { logs: LogEntry[] }) {
  return (
    <div className="mt-2 max-h-48 overflow-y-auto bg-muted/50 rounded-md p-3 font-mono text-xs">
      {logs.map((log, index) => (
        <div
          key={index}
          className={cn(
            'py-0.5',
            log.level === 'ERROR' && 'text-destructive',
            log.level === 'WARNING' && 'text-yellow-600 dark:text-yellow-500'
          )}
        >
          <span className="text-muted-foreground">
            {new Date(log.timestamp).toLocaleTimeString()}
          </span>
          {' '}
          <span className="font-semibold">[{log.level}]</span>
          {' '}
          {log.message}
        </div>
      ))}
    </div>
  )
}

function StatusIcon({ status }: { status: Status }) {
  switch (status) {
    case 'uploading':
    case 'processing':
      return <Loader2 className="h-8 w-8 text-primary animate-spin" />
    case 'pending':
      return <Clock className="h-8 w-8 text-muted-foreground" />
    case 'completed':
      return <CheckCircle className="h-8 w-8 text-green-500" />
    case 'failed':
      return <XCircle className="h-8 w-8 text-destructive" />
    default:
      return null
  }
}

function StatusText({ status }: { status: Status }) {
  switch (status) {
    case 'uploading':
      return <span className="text-sm text-muted-foreground">Uploading...</span>
    case 'pending':
      return <span className="text-sm text-muted-foreground">Waiting to process...</span>
    case 'processing':
      return <span className="text-sm text-muted-foreground">Transcribing audio...</span>
    case 'completed':
      return <span className="text-sm text-green-500">Complete</span>
    case 'failed':
      return <span className="text-sm text-destructive">Failed</span>
    default:
      return null
  }
}
