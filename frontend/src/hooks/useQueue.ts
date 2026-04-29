import { useCallback, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { transcriptionApi } from '@/services/transcription'
import { ApiError } from '@/services/api'

export interface QueueLocalItem {
  // Local-only entry, used between selecting a file and getting back an id.
  localId: string
  filename: string
  size: number
  // Original File kept so retry can re-upload without prompting again.
  file: File
  // Becomes set once POST succeeds.
  transcriptionId?: string
  status: 'uploading' | 'queued' | 'failed'
  error?: string
}

let counter = 0
const nextLocalId = () => `local-${Date.now()}-${counter++}`

export function useQueue() {
  const queryClient = useQueryClient()
  const [items, setItems] = useState<QueueLocalItem[]>([])

  const upload = useCallback(async (file: File) => {
    const localId = nextLocalId()
    setItems((prev) => [
      ...prev,
      { localId, filename: file.name, size: file.size, file, status: 'uploading' },
    ])

    try {
      const created = await transcriptionApi.upload(file)
      setItems((prev) =>
        prev.map((it) =>
          it.localId === localId
            ? {
                ...it,
                transcriptionId: created.id,
                status: 'queued',
              }
            : it
        )
      )
      // Refresh history so the new item appears in the list elsewhere.
      queryClient.invalidateQueries({ queryKey: ['history'] })
    } catch (e) {
      const err = e as ApiError
      setItems((prev) =>
        prev.map((it) =>
          it.localId === localId
            ? { ...it, status: 'failed', error: err.message || 'Upload failed' }
            : it
        )
      )
    }
  }, [queryClient])

  const enqueueMany = useCallback(
    async (files: File[]) => {
      // Upload sequentially so the user-visible "position" reflects arrival order.
      for (const f of files) {
        await upload(f)
      }
    },
    [upload]
  )

  const remove = useCallback(
    async (localId: string) => {
      const it = items.find((i) => i.localId === localId)
      if (!it) return
      if (it.transcriptionId && it.status === 'queued') {
        try {
          await transcriptionApi.cancel(it.transcriptionId)
        } catch {
          // Item may have started processing; UI will reflect via SSE.
        }
      }
      setItems((prev) => prev.filter((i) => i.localId !== localId))
    },
    [items]
  )

  const retry = useCallback(
    async (localId: string) => {
      const it = items.find((i) => i.localId === localId)
      if (!it) return
      const file = it.file
      setItems((prev) => prev.filter((i) => i.localId !== localId))
      await upload(file)
    },
    [items, upload]
  )

  const clear = useCallback(() => setItems([]), [])

  return { items, enqueueMany, remove, retry, clear }
}
