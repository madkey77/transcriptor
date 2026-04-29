import { Inbox } from 'lucide-react'
import { QueueItem } from './QueueItem'
import type { QueueLocalItem } from '@/hooks/useQueue'

interface QueueListProps {
  items: QueueLocalItem[]
  onOpen: (id: string) => void
  onRemove: (localId: string) => void
}

export function QueueList({ items, onOpen, onRemove }: QueueListProps) {
  if (items.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <Inbox className="mx-auto h-10 w-10 mb-3 opacity-50" />
        <p className="text-sm">Nenhuma transcrição na fila.</p>
        <p className="text-xs mt-1">Solte arquivos acima para começar.</p>
      </div>
    )
  }

  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item.localId}>
          <QueueItem item={item} onOpen={onOpen} onRemove={onRemove} />
        </li>
      ))}
    </ul>
  )
}
