import { useState } from 'react'
import { Download, ChevronDown } from 'lucide-react'
import { transcriptionApi } from '@/services/transcription'
import { cn } from '@/lib/utils'

interface DownloadButtonProps {
  transcriptionId: string
  className?: string
}

type Format = 'txt' | 'json' | 'srt'

const formats: { value: Format; label: string; description: string }[] = [
  { value: 'txt', label: 'Text (.txt)', description: 'Plain text with speaker labels' },
  { value: 'json', label: 'JSON (.json)', description: 'Full data with timestamps' },
  { value: 'srt', label: 'Subtitles (.srt)', description: 'SRT subtitle format' },
]

export function DownloadButton({
  transcriptionId,
  className,
}: DownloadButtonProps) {
  const [isOpen, setIsOpen] = useState(false)

  const handleDownload = (format: Format) => {
    const url = transcriptionApi.getDownloadUrl(transcriptionId, format)
    window.open(url, '_blank')
    setIsOpen(false)
  }

  return (
    <div className={cn('relative', className)}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
      >
        <Download className="h-4 w-4" />
        Download
        <ChevronDown className="h-4 w-4" />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute right-0 top-full mt-1 w-64 bg-background border rounded-md shadow-lg z-20">
            {formats.map((format) => (
              <button
                key={format.value}
                onClick={() => handleDownload(format.value)}
                className="w-full px-4 py-3 text-left hover:bg-muted transition-colors first:rounded-t-md last:rounded-b-md"
              >
                <div className="font-medium">{format.label}</div>
                <div className="text-sm text-muted-foreground">
                  {format.description}
                </div>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
