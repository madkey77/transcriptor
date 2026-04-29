import { Inbox } from 'lucide-react'
import { QueueItem } from './QueueItem'
import type { QueueLocalItem } from '@/hooks/useQueue'

interface QueueListProps {
  items: QueueLocalItem[]
  onOpen: (id: string) => void
  onRemove: (localId: string) => void
  onRetry: (localId: string) => void
}

export function QueueList({ items, onOpen, onRemove, onRetry }: QueueListProps) {
  if (items.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <Inbox className="mx-auto h-10 w-10 mb-3 opacity-50" />
        <p className="text-sm">Nenhuma transcrição na fila.</p>
        <p className="text-xs mt-1">Solte arquivos acima para começar.</p>
      </div>
    )
  }

  // Compute relative queue position from local order: among items still
  // queued/uploading (i.e. not yet picked up), this item's index = how many
  // are ahead of it. Re-derived on every render so it stays correct after
  // a cancel.
  const queuedIds = items
    .filter((it) => it.status === 'uploading' || it.status === 'queued')
    .map((it) => it.localId)

  return (
    <ul className="space-y-3">
      {items.map((item) => {
        const idx = queuedIds.indexOf(item.localId)
        const relativePosition = idx === -1 ? 0 : idx
        return (
          <li key={item.localId}>
            <QueueItem
              item={item}
              relativePosition={relativePosition}
              onOpen={onOpen}
              onRemove={onRemove}
              onRetry={onRetry}
            />
          </li>
        )
      })}
    </ul>
  )
}
