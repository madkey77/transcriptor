import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload } from 'lucide-react'
import { cn } from '@/lib/utils'

const ACCEPTED_FORMATS = {
  'audio/mpeg': ['.mp3'],
  'audio/wav': ['.wav'],
  'audio/x-m4a': ['.m4a'],
  'audio/ogg': ['.ogg'],
  'audio/flac': ['.flac'],
}

const MAX_FILE_SIZE = 1024 * 1024 * 1024 // 1GB

interface FileDropzoneProps {
  onFilesSelect: (files: File[]) => void
  disabled?: boolean
  className?: string
}

export function FileDropzone({
  onFilesSelect,
  disabled = false,
  className,
}: FileDropzoneProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        onFilesSelect(acceptedFiles)
      }
    },
    [onFilesSelect]
  )

  const { getRootProps, getInputProps, isDragActive, fileRejections } =
    useDropzone({
      onDrop,
      accept: ACCEPTED_FORMATS,
      maxSize: MAX_FILE_SIZE,
      multiple: true,
      disabled,
    })

  const error =
    fileRejections.length > 0 ? fileRejections[0].errors[0].message : null

  return (
    <div
      {...getRootProps()}
      className={cn(
        'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors',
        isDragActive && 'border-primary bg-primary/5',
        disabled && 'opacity-50 cursor-not-allowed',
        !isDragActive && !disabled && 'hover:border-primary/50',
        className
      )}
    >
      <input {...getInputProps()} />
      <Upload className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
      {isDragActive ? (
        <p className="text-lg">Solte os arquivos aqui…</p>
      ) : (
        <div>
          <p className="text-lg mb-2">
            Arraste arquivos de áudio aqui ou clique para selecionar
          </p>
          <p className="text-sm text-muted-foreground">
            MP3, WAV, M4A, OGG, FLAC (máx 1GB cada). Pode soltar vários.
          </p>
        </div>
      )}
      {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
    </div>
  )
}
