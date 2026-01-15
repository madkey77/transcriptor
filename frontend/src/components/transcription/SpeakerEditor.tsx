import { useState } from 'react'
import { X, Check } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SpeakerEditorProps {
  speakerLabel: string
  currentName: string
  onSave: (speakerLabel: string, newName: string | null) => void
  onCancel: () => void
  isLoading?: boolean
}

export function SpeakerEditor({
  speakerLabel,
  currentName,
  onSave,
  onCancel,
  isLoading = false,
}: SpeakerEditorProps) {
  const [name, setName] = useState(currentName)
  const [error, setError] = useState<string | null>(null)

  const validateName = (value: string): string | null => {
    if (value.length > 100) {
      return 'Name must be 100 characters or less'
    }
    if (value && !/^[a-zA-Z0-9\s\-']+$/.test(value)) {
      return 'Only letters, numbers, spaces, hyphens, and apostrophes allowed'
    }
    return null
  }

  const handleSave = () => {
    const validationError = validateName(name)
    if (validationError) {
      setError(validationError)
      return
    }

    // If name is empty or same as original label, reset to default
    const newName = name.trim() === '' || name === speakerLabel ? null : name.trim()
    onSave(speakerLabel, newName)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSave()
    } else if (e.key === 'Escape') {
      onCancel()
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background rounded-lg shadow-lg p-6 w-full max-w-md mx-4">
        <h3 className="text-lg font-semibold mb-4">Edit Speaker Name</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Editing: <span className="font-mono">{speakerLabel}</span>
        </p>

        <input
          type="text"
          value={name}
          onChange={(e) => {
            setName(e.target.value)
            setError(null)
          }}
          onKeyDown={handleKeyDown}
          placeholder="Enter speaker name"
          className={cn(
            'w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary',
            error && 'border-destructive'
          )}
          disabled={isLoading}
          autoFocus
        />

        {error && (
          <p className="text-sm text-destructive mt-2">{error}</p>
        )}

        <div className="flex justify-end gap-2 mt-4">
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="px-4 py-2 text-sm rounded-md hover:bg-muted transition-colors"
          >
            <X className="h-4 w-4 inline mr-1" />
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isLoading}
            className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            <Check className="h-4 w-4 inline mr-1" />
            {isLoading ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
