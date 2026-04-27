const STORAGE_KEY = 'transcriptor_api_key'
const EVENT_TARGET = new EventTarget()

export const AUTH_REQUIRED_EVENT = 'auth-required'

export function getApiKey(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function setApiKey(value: string): void {
  localStorage.setItem(STORAGE_KEY, value)
  EVENT_TARGET.dispatchEvent(new Event('changed'))
}

export function clearApiKey(): void {
  localStorage.removeItem(STORAGE_KEY)
  EVENT_TARGET.dispatchEvent(new Event(AUTH_REQUIRED_EVENT))
  EVENT_TARGET.dispatchEvent(new Event('changed'))
}

export function onApiKeyChange(handler: () => void): () => void {
  EVENT_TARGET.addEventListener('changed', handler)
  return () => EVENT_TARGET.removeEventListener('changed', handler)
}

export function onAuthRequired(handler: () => void): () => void {
  EVENT_TARGET.addEventListener(AUTH_REQUIRED_EVENT, handler)
  return () => EVENT_TARGET.removeEventListener(AUTH_REQUIRED_EVENT, handler)
}

export function notifyAuthRequired(): void {
  EVENT_TARGET.dispatchEvent(new Event(AUTH_REQUIRED_EVENT))
}
