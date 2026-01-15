import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { transcriptionApi, SpeakerUpdate } from '@/services/transcription'

export function useTranscriptionStatus(id: string | null) {
  return useQuery({
    queryKey: ['transcription-status', id],
    queryFn: () => transcriptionApi.getStatus(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data
      // Poll every 2 seconds while processing
      if (data?.status === 'processing' || data?.status === 'pending') {
        return 2000
      }
      return false
    },
  })
}

export function useTranscription(id: string | null) {
  return useQuery({
    queryKey: ['transcription', id],
    queryFn: () => transcriptionApi.getTranscription(id!),
    enabled: !!id,
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

export function useUpdateSpeaker(transcriptionId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (update: SpeakerUpdate) =>
      transcriptionApi.updateSpeaker(transcriptionId, update),
    onSuccess: () => {
      // Invalidate and refetch transcription data
      queryClient.invalidateQueries({
        queryKey: ['transcription', transcriptionId],
      })
    },
  })
}

export function useTranscriptionHistory(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ['history', limit, offset],
    queryFn: () => transcriptionApi.getHistory(limit, offset),
    staleTime: 1000 * 30, // 30 seconds
  })
}
