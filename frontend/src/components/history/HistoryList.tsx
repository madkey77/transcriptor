import { useHistory } from '@/hooks/useHistory'
import { Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface HistoryListProps {
  onSelect: (id: string) => void
  className?: string
}

export function HistoryList({ onSelect, className }: HistoryListProps) {
  const { data, isLoading, error } = useHistory()

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

  return (
    <div className={cn('space-y-2', className)}>
      {data.items.map((item) => (
        <button
          key={item.id}
          onClick={() => onSelect(item.id)}
          className="w-full p-4 text-left rounded-lg border hover:bg-muted/50 transition-colors"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <StatusIcon status={item.status} />
              <div>
                <div className="font-medium">{item.filename}</div>
                <div className="text-sm text-muted-foreground">
                  {formatDate(item.created_at)}
                  {item.speaker_count !== undefined && item.speaker_count !== null && (
                    <span className="ml-2">
                      {item.speaker_count} speaker{item.speaker_count !== 1 ? 's' : ''}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <StatusBadge status={item.status} />
          </div>
        </button>
      ))}

      {data.total > data.items.length && (
        <div className="text-center text-sm text-muted-foreground py-2">
          Showing {data.items.length} of {data.total} transcriptions
        </div>
      )}
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
