import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { transcriptionApi } from '@/services/transcription'

export function useHistory(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ['history', limit, offset],
    queryFn: () => transcriptionApi.getHistory(limit, offset),
    staleTime: 1000 * 30, // 30 seconds
  })
}

export function useDeleteTranscription() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => transcriptionApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['history'] })
    },
  })
}
