import { useState, useEffect } from 'react'
import { FileDropzone } from '@/components/upload/FileDropzone'
import { UploadProgress } from '@/components/upload/UploadProgress'
import { TranscriptionView } from '@/components/transcription/TranscriptionView'
import { SpeakerEditor } from '@/components/transcription/SpeakerEditor'
import { DownloadButton } from '@/components/transcription/DownloadButton'
import { HistoryList } from '@/components/history/HistoryList'
import { useUpload } from '@/hooks/useUpload'
import { useTranscriptionStatus, useTranscription, useUpdateSpeaker } from '@/hooks/useTranscription'
// import { useProgressStream } from '@/hooks/useProgressStream'
// import { ProcessingStage } from '@/services/transcription'
import { ArrowLeft } from 'lucide-react'

type View = 'upload' | 'transcription' | 'history'

function App() {
  const [view, setView] = useState<View>('upload')
  const [currentTranscriptionId, setCurrentTranscriptionId] = useState<string | null>(null)
  const [editingSpeaker, setEditingSpeaker] = useState<{
    label: string
    currentName: string
  } | null>(null)

  const upload = useUpload()
  const status = useTranscriptionStatus(currentTranscriptionId)
  const transcription = useTranscription(
    status.data?.status === 'completed' ? currentTranscriptionId : null
  )
  const updateSpeaker = useUpdateSpeaker(currentTranscriptionId || '')

  // // Use SSE progress stream when processing
  // const shouldStreamProgress =
  //   status.data?.status === 'processing' || status.data?.status === 'pending'
  // const progressStream = useProgressStream(
  //   shouldStreamProgress ? currentTranscriptionId : null
  // )

  // When upload completes, set the transcription ID
  useEffect(() => {
    if (upload.transcriptionId) {
      setCurrentTranscriptionId(upload.transcriptionId)
    }
  }, [upload.transcriptionId])

  // When transcription completes, switch to transcription view
  useEffect(() => {
    if (status.data?.status === 'completed') {
      setView('transcription')
    }
  }, [status.data?.status])

  const handleFileSelect = async (file: File) => {
    await upload.upload(file)
  }

  const handleViewTranscription = (id: string) => {
    setCurrentTranscriptionId(id)
    setView('transcription')
  }

  const handleBackToUpload = () => {
    upload.reset()
    setCurrentTranscriptionId(null)
    setView('upload')
  }

  const handleSpeakerSave = (speakerLabel: string, newName: string | null) => {
    updateSpeaker.mutate(
      { speaker_label: speakerLabel, custom_speaker_name: newName },
      {
        onSuccess: () => {
          setEditingSpeaker(null)
        },
      }
    )
  }

  const getUploadStatus = (): 'uploading' | 'pending' | 'processing' | 'completed' | 'failed' => {
    if (upload.isUploading) return 'uploading'
    if (status.data?.status) return status.data.status
    return 'pending'
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <nav className="flex items-center justify-between">
            <h1 className="text-2xl font-bold">Transcriptor</h1>
            <div className="flex gap-4">
              <button
                onClick={handleBackToUpload}
                className={`px-4 py-2 rounded-md ${view === 'upload' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}
              >
                Upload
              </button>
              <button
                onClick={() => setView('history')}
                className={`px-4 py-2 rounded-md ${view === 'history' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}
              >
                History
              </button>
            </div>
          </nav>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {view === 'upload' && (
          <div className="max-w-2xl mx-auto">
            <h2 className="text-xl font-semibold mb-6 text-center">
              Upload Audio for Transcription
            </h2>

            {!currentTranscriptionId && !upload.isUploading && (
              <FileDropzone
                onFileSelect={handleFileSelect}
                disabled={upload.isUploading}
              />
            )}

            {(upload.isUploading || currentTranscriptionId) && (
              <UploadProgress
                status={getUploadStatus()}
                progress={upload.progress}
                filename={transcription.data?.filename}
                error={upload.error || status.data?.error_message}
              />
            )}

            {upload.error && (
              <button
                onClick={handleBackToUpload}
                className="mt-4 w-full px-4 py-2 text-sm border rounded-md hover:bg-muted"
              >
                Try Again
              </button>
            )}
          </div>
        )}

        {view === 'transcription' && currentTranscriptionId && (
          <div className="max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-6">
              <button
                onClick={() => setView('history')}
                className="flex items-center gap-2 text-muted-foreground hover:text-foreground"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to History
              </button>

              {transcription.data && (
                <DownloadButton transcriptionId={currentTranscriptionId} />
              )}
            </div>

            {transcription.isLoading && (
              <div className="text-center py-8 text-muted-foreground">
                Loading transcription...
              </div>
            )}

            {transcription.data && (
              <>
                <h2 className="text-xl font-semibold mb-4">
                  {transcription.data.filename}
                </h2>
                <p className="text-sm text-muted-foreground mb-6">
                  Click on a speaker name to edit it
                </p>
                <TranscriptionView
                  transcription={transcription.data}
                  onSpeakerClick={(label, name) =>
                    setEditingSpeaker({ label, currentName: name })
                  }
                />
              </>
            )}
          </div>
        )}

        {view === 'history' && (
          <div className="max-w-2xl mx-auto">
            <h2 className="text-xl font-semibold mb-6">Transcription History</h2>
            <HistoryList onSelect={handleViewTranscription} />
          </div>
        )}
      </main>

      {editingSpeaker && currentTranscriptionId && (
        <SpeakerEditor
          speakerLabel={editingSpeaker.label}
          currentName={editingSpeaker.currentName}
          onSave={handleSpeakerSave}
          onCancel={() => setEditingSpeaker(null)}
          isLoading={updateSpeaker.isPending}
        />
      )}
    </div>
  )
}

export default App
