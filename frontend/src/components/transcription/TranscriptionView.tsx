import { TranscriptionDetail, Segment } from '@/services/transcription'
import { cn } from '@/lib/utils'

// Speaker colors for visual distinction
const SPEAKER_COLORS = [
  'bg-blue-100 text-blue-800',
  'bg-green-100 text-green-800',
  'bg-purple-100 text-purple-800',
  'bg-orange-100 text-orange-800',
  'bg-pink-100 text-pink-800',
  'bg-cyan-100 text-cyan-800',
  'bg-yellow-100 text-yellow-800',
  'bg-red-100 text-red-800',
]

interface TranscriptionViewProps {
  transcription: TranscriptionDetail
  onSpeakerClick?: (speakerLabel: string, currentName: string) => void
  className?: string
}

export function TranscriptionView({
  transcription,
  onSpeakerClick,
  className,
}: TranscriptionViewProps) {
  // Create a map of speaker labels to colors
  const speakerColors = new Map<string, string>()
  transcription.speakers.forEach((speaker, index) => {
    speakerColors.set(
      speaker.speaker_label,
      SPEAKER_COLORS[index % SPEAKER_COLORS.length]
    )
  })

  return (
    <div className={cn('space-y-4', className)}>
      <div className="flex flex-wrap gap-2 mb-6">
        {transcription.speakers.map((speaker) => (
          <button
            key={speaker.speaker_label}
            onClick={() =>
              onSpeakerClick?.(
                speaker.speaker_label,
                speaker.custom_speaker_name || speaker.speaker_label
              )
            }
            className={cn(
              'px-3 py-1 rounded-full text-sm font-medium transition-opacity hover:opacity-80',
              speakerColors.get(speaker.speaker_label)
            )}
          >
            {speaker.custom_speaker_name || speaker.speaker_label}
            <span className="ml-1 opacity-60">({speaker.segment_count})</span>
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {transcription.segments.map((segment) => (
          <SegmentItem
            key={segment.id}
            segment={segment}
            colorClass={speakerColors.get(
              transcription.speakers.find(
                (s) =>
                  s.custom_speaker_name === segment.speaker ||
                  s.speaker_label === segment.speaker
              )?.speaker_label || ''
            )}
            onSpeakerClick={onSpeakerClick}
          />
        ))}
      </div>
    </div>
  )
}

interface SegmentItemProps {
  segment: Segment
  colorClass?: string
  onSpeakerClick?: (speakerLabel: string, currentName: string) => void
}

function SegmentItem({ segment, colorClass, onSpeakerClick }: SegmentItemProps) {
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <div className="flex gap-4 p-3 rounded-lg hover:bg-muted/50 transition-colors">
      <div className="flex-shrink-0 text-xs text-muted-foreground w-16">
        {formatTime(segment.start_time)}
      </div>
      <div className="flex-1">
        <span
          className={cn(
            'inline-block px-2 py-0.5 rounded text-xs font-medium mr-2 cursor-pointer',
            colorClass || 'bg-muted'
          )}
          onClick={() => onSpeakerClick?.(segment.speaker, segment.speaker)}
        >
          {segment.speaker}
        </span>
        <span className="text-foreground">{segment.text}</span>
      </div>
    </div>
  )
}
