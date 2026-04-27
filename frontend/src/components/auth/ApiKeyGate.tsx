import { useEffect, useState } from 'react'
import { getApiKey, onApiKeyChange, onAuthRequired, setApiKey } from '@/services/auth'

interface Props {
  children: React.ReactNode
}

export function ApiKeyGate({ children }: Props) {
  const [hasKey, setHasKey] = useState<boolean>(() => Boolean(getApiKey()))
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const offChange = onApiKeyChange(() => setHasKey(Boolean(getApiKey())))
    const offAuth = onAuthRequired(() => {
      setHasKey(false)
      setError('A chave salva é inválida. Cole a chave correta para continuar.')
    })
    return () => {
      offChange()
      offAuth()
    }
  }, [])

  if (hasKey) return <>{children}</>

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-6">
      <form
        className="w-full max-w-sm space-y-4 border rounded-lg p-6 shadow-sm"
        onSubmit={(e) => {
          e.preventDefault()
          const value = draft.trim()
          if (!value) {
            setError('Digite a API key.')
            return
          }
          setApiKey(value)
          setDraft('')
          setError(null)
        }}
      >
        <div>
          <h1 className="text-xl font-semibold">Transcriptor</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Cole sua API key para acessar o serviço.
          </p>
        </div>
        <input
          type="password"
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="API key"
          className="w-full border rounded-md px-3 py-2 bg-background"
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <button
          type="submit"
          className="w-full bg-primary text-primary-foreground rounded-md px-4 py-2"
        >
          Entrar
        </button>
      </form>
    </div>
  )
}
