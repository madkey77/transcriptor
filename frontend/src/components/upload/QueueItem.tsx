import { useState } from 'react'
import { CheckCircle2, AlertCircle, Loader2, X, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react'
import { useTranscriptionStatus } from '@/hooks/useTranscription'
import { useProgressStream } from '@/hooks/useProgressStream'
import { STAGE_LABELS, ProcessingStage } from '@/services/transcription'
import { cn } from '@/lib/utils'
import type { QueueLocalItem } from '@/hooks/useQueue'

interface QueueItemProps {
  item: QueueLocalItem
  onOpen: (id: string) => void
  onRemove: (localId: string) => void
}

function formatBytes(bytes: number): string {
  const mb = bytes / (1024 * 1024)
  return mb < 1 ? `${(bytes / 1024).toFixed(0)} KB` : `${mb.toFixed(1)} MB`
}

export function QueueItem({ item, onOpen, onRemove }: QueueItemProps) {
  const [showLogs, setShowLogs] = useState(false)
  const status = useTranscriptionStatus(item.transcriptionId ?? null)
  const stream = useProgressStream(
    status.data?.status === 'processing' || status.data?.status === 'pending'
      ? item.transcriptionId ?? null
      : null
  )

  const serverStatus = status.data?.status
  const stage = (stream.currentStage || status.data?.current_stage || null) as ProcessingStage | null
  const pct = stream.progressPct

  let badgeText: string
  let badgeClass: string
  if (item.status === 'uploading') {
    badgeText = 'Enviando…'
    badgeClass = 'bg-blue-500/15 text-blue-700 dark:text-blue-300'
  } else if (item.status === 'failed') {
    badgeText = 'Falhou'
    badgeClass = 'bg-red-500/15 text-red-700 dark:text-red-300'
  } else if (serverStatus === 'completed') {
    badgeText = 'Concluído'
    badgeClass = 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
  } else if (serverStatus === 'failed') {
    badgeText = 'Falhou'
    badgeClass = 'bg-red-500/15 text-red-700 dark:text-red-300'
  } else if (serverStatus === 'processing') {
    badgeText = 'Processando'
    badgeClass = 'bg-amber-500/15 text-amber-700 dark:text-amber-300'
  } else {
    badgeText = item.position && item.position > 0 ? `Aguardando (${item.position} à frente)` : 'Iniciando…'
    badgeClass = 'bg-slate-500/15 text-slate-700 dark:text-slate-300'
  }

  const stageLabel = stage ? STAGE_LABELS[stage] : null
  const isTranscribing = stage === 'transcribing' && pct !== null
  const showIndeterminate = serverStatus === 'processing' && !isTranscribing

  return (
    <div className="border rounded-lg p-4 bg-card">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {serverStatus === 'completed' && <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />}
            {serverStatus === 'failed' && <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />}
            {serverStatus === 'processing' && <Loader2 className="h-4 w-4 animate-spin text-amber-500 shrink-0" />}
            <p className="font-medium truncate">{item.filename}</p>
          </div>
          <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
            <span>{formatBytes(item.size)}</span>
            <span>·</span>
            <span className={cn('px-2 py-0.5 rounded-full font-medium', badgeClass)}>
              {badgeText}
            </span>
            {stageLabel && serverStatus === 'processing' && (
              <>
                <span>·</span>
                <span aria-live="polite">
                  {isTranscribing ? `${stageLabel}… ${Math.round((pct ?? 0) * 100)}%` : `${stageLabel}…`}
                </span>
              </>
            )}
          </div>

          {(isTranscribing || showIndeterminate) && (
            <div className="mt-2 h-1.5 bg-muted rounded-full overflow-hidden">
              {isTranscribing ? (
                <div
                  className="h-full bg-primary transition-all duration-300"
                  style={{ width: `${Math.round((pct ?? 0) * 100)}%` }}
                />
              ) : (
                <div className="h-full w-1/3 bg-primary animate-pulse" />
              )}
            </div>
          )}

          {(serverStatus === 'failed' || item.status === 'failed') && (
            <p className="mt-2 text-xs text-red-600 dark:text-red-400">
              {item.error || status.data?.error_message || 'Erro desconhecido'}
            </p>
          )}
        </div>

        <div className="flex items-center gap-1">
          {serverStatus === 'completed' && item.transcriptionId && (
            <button
              onClick={() => onOpen(item.transcriptionId!)}
              className="px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 inline-flex items-center gap-1"
            >
              <ExternalLink className="h-3.5 w-3.5" /> Abrir
            </button>
          )}
          {(item.status === 'queued' && serverStatus === 'pending') && (
            <button
              onClick={() => onRemove(item.localId)}
              aria-label="Remover da fila"
              className="p-2 rounded-md hover:bg-destructive/10 text-destructive"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          {(serverStatus === 'failed' || item.status === 'failed') && (
            <button
              onClick={() => onRemove(item.localId)}
              aria-label="Limpar"
              className="p-2 rounded-md hover:bg-muted"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {serverStatus === 'processing' && stream.logs.length > 0 && (
        <div className="mt-3">
          <button
            onClick={() => setShowLogs((v) => !v)}
            className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
          >
            {showLogs ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            Logs ({stream.logs.length})
          </button>
          {showLogs && (
            <div className="mt-2 max-h-32 overflow-y-auto bg-muted/50 rounded p-2 text-xs font-mono">
              {stream.logs.slice(-20).map((log, i) => (
                <div key={i} className="text-muted-foreground">
                  <span className="opacity-60">{log.timestamp.slice(11, 19)} </span>
                  {log.message}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
