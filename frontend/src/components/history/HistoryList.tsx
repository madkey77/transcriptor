import { useState } from 'react'
import { useDeleteTranscription, useHistory } from '@/hooks/useHistory'
import { Clock, CheckCircle, XCircle, Loader2, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ConfirmModal } from '@/components/ui/ConfirmModal'

interface HistoryListProps {
  onSelect: (id: string) => void
  className?: string
}

interface PendingDelete {
  id: string
  filename: string
}

export function HistoryList({ onSelect, className }: HistoryListProps) {
  const { data, isLoading, error } = useHistory()
  const deleteMutation = useDeleteTranscription()
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-8 text-destructive">
        Failed to load history. Please try again.
      </div>
    )
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No transcriptions yet. Upload an audio file to get started.
      </div>
    )
  }

  const canDelete = (status: string) => status === 'completed' || status === 'failed'

  const handleConfirmDelete = () => {
    if (!pendingDelete) return
    deleteMutation.mutate(pendingDelete.id, {
      onSettled: () => setPendingDelete(null),
    })
  }

  return (
    <div className={cn('space-y-2', className)}>
      {data.items.map((item) => (
        <div
          key={item.id}
          className="w-full p-4 rounded-lg border hover:bg-muted/50 transition-colors flex items-center justify-between gap-3"
        >
          <button
            onClick={() => onSelect(item.id)}
            className="flex items-center gap-3 flex-1 min-w-0 text-left"
          >
            <StatusIcon status={item.status} />
            <div className="min-w-0">
              <div className="font-medium truncate">{item.filename}</div>
              <div className="text-sm text-muted-foreground">
                {formatDate(item.created_at)}
                {item.speaker_count !== undefined && item.speaker_count !== null && (
                  <span className="ml-2">
                    {item.speaker_count} speaker{item.speaker_count !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
            </div>
          </button>
          <div className="flex items-center gap-2 shrink-0">
            <StatusBadge status={item.status} />
            {canDelete(item.status) && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setPendingDelete({ id: item.id, filename: item.filename })
                }}
                aria-label={`Excluir ${item.filename}`}
                title="Excluir"
                className="p-2 rounded-md hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      ))}

      {data.total > data.items.length && (
        <div className="text-center text-sm text-muted-foreground py-2">
          Showing {data.items.length} of {data.total} transcriptions
        </div>
      )}

      <ConfirmModal
        open={pendingDelete !== null}
        title="Excluir transcrição?"
        description={
          pendingDelete
            ? `"${pendingDelete.filename}" e todos os seus segmentos serão excluídos permanentemente. Essa ação não pode ser desfeita.`
            : ''
        }
        confirmLabel="Excluir"
        cancelLabel="Cancelar"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  )
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'completed':
      return <CheckCircle className="h-5 w-5 text-green-500" />
    case 'failed':
      return <XCircle className="h-5 w-5 text-destructive" />
    case 'processing':
      return <Loader2 className="h-5 w-5 text-primary animate-spin" />
    default:
      return <Clock className="h-5 w-5 text-muted-foreground" />
  }
}

function StatusBadge({ status }: { status: string }) {
  const classes = {
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    processing: 'bg-blue-100 text-blue-800',
    pending: 'bg-gray-100 text-gray-800',
  }

  return (
    <span
      className={cn(
        'px-2 py-1 rounded text-xs font-medium',
        classes[status as keyof typeof classes] || classes.pending
      )}
    >
      {status}
    </span>
  )
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
