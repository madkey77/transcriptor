import { useState } from 'react'
import { FileDropzone } from '@/components/upload/FileDropzone'
import { QueueList } from '@/components/upload/QueueList'
import { TranscriptionView } from '@/components/transcription/TranscriptionView'
import { SpeakerEditor } from '@/components/transcription/SpeakerEditor'
import { DownloadButton } from '@/components/transcription/DownloadButton'
import { HistoryList } from '@/components/history/HistoryList'
import { ApiKeyGate } from '@/components/auth/ApiKeyGate'
import { useQueue } from '@/hooks/useQueue'
import { useTranscription, useUpdateSpeaker } from '@/hooks/useTranscription'
import { clearApiKey } from '@/services/auth'
import { ArrowLeft } from 'lucide-react'

type View = 'upload' | 'transcription' | 'history'

function App() {
  const [view, setView] = useState<View>('upload')
  const [currentTranscriptionId, setCurrentTranscriptionId] = useState<string | null>(null)
  const [editingSpeaker, setEditingSpeaker] = useState<{
    label: string
    currentName: string
  } | null>(null)

  const queue = useQueue()
  const transcription = useTranscription(
    view === 'transcription' ? currentTranscriptionId : null
  )
  const updateSpeaker = useUpdateSpeaker(currentTranscriptionId || '')

  const handleFilesSelect = (files: File[]) => {
    queue.enqueueMany(files)
  }

  const handleViewTranscription = (id: string) => {
    setCurrentTranscriptionId(id)
    setView('transcription')
  }

  const handleSpeakerSave = (speakerLabel: string, newName: string | null) => {
    updateSpeaker.mutate(
      { speaker_label: speakerLabel, custom_speaker_name: newName },
      {
        onSuccess: () => setEditingSpeaker(null),
      }
    )
  }

  return (
    <ApiKeyGate>
      <div className="min-h-screen bg-background">
        <header className="border-b">
          <div className="container mx-auto px-4 py-4">
            <nav className="flex items-center justify-between">
              <h1 className="text-2xl font-bold">Transcriptor</h1>
              <div className="flex gap-4">
                <button
                  onClick={() => setView('upload')}
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
                <button
                  onClick={() => clearApiKey()}
                  className="px-4 py-2 rounded-md hover:bg-muted text-sm text-muted-foreground"
                  title="Trocar API key"
                >
                  Sair
                </button>
              </div>
            </nav>
          </div>
        </header>

        <main className="container mx-auto px-4 py-8">
          {view === 'upload' && (
            <div className="max-w-2xl mx-auto space-y-6">
              <h2 className="text-xl font-semibold text-center">
                Upload de áudio para transcrição
              </h2>

              <FileDropzone onFilesSelect={handleFilesSelect} />

              <QueueList
                items={queue.items}
                onOpen={handleViewTranscription}
                onRemove={queue.remove}
                onRetry={queue.retry}
              />
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
                  Voltar para o histórico
                </button>

                {transcription.data && (
                  <DownloadButton transcriptionId={currentTranscriptionId} />
                )}
              </div>

              {transcription.isLoading && (
                <div className="text-center py-8 text-muted-foreground">
                  Carregando transcrição…
                </div>
              )}

              {transcription.data && (
                <>
                  <h2 className="text-xl font-semibold mb-4">
                    {transcription.data.filename}
                  </h2>
                  <p className="text-sm text-muted-foreground mb-6">
                    Clique no nome de um falante para editá-lo
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
              <h2 className="text-xl font-semibold mb-6">Histórico</h2>
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
    </ApiKeyGate>
  )
}

export default App
