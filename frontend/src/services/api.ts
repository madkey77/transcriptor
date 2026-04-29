import { clearApiKey, getApiKey, notifyAuthRequired } from './auth'

const API_BASE_URL = '/api'

export interface ApiError {
  error_code: string
  message: string
  details?: string
}

function authHeaders(): Record<string, string> {
  const key = getApiKey()
  return key ? { 'X-API-Key': key } : {}
}

function handleUnauthorized(): void {
  clearApiKey()
  notifyAuthRequired()
}

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (response.status === 401) {
      handleUnauthorized()
    }
    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        error_code: 'network_error',
        message: 'Network error occurred',
      }))
      throw error
    }
    return response.json()
  }

  async get<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      headers: authHeaders(),
    })
    return this.handleResponse<T>(response)
  }

  async post<T>(endpoint: string, data?: FormData | object): Promise<T> {
    const headers: Record<string, string> = { ...authHeaders() }
    const options: RequestInit = { method: 'POST', headers }

    if (data instanceof FormData) {
      options.body = data
    } else if (data) {
      headers['Content-Type'] = 'application/json'
      options.body = JSON.stringify(data)
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, options)
    return this.handleResponse<T>(response)
  }

  async patch<T>(endpoint: string, data: object): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(data),
    })
    return this.handleResponse<T>(response)
  }

  async delete<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
    if (response.status === 401) {
      handleUnauthorized()
    }
    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        error_code: 'network_error',
        message: 'Network error occurred',
      }))
      throw error
    }
    if (response.status === 204) {
      return undefined as T
    }
    return response.json()
  }

  async uploadFile<T>(
    endpoint: string,
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<T> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      const formData = new FormData()
      formData.append('file', file)

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable && onProgress) {
          const progress = Math.round((event.loaded / event.total) * 100)
          onProgress(progress)
        }
      })

      xhr.addEventListener('load', () => {
        if (xhr.status === 401) {
          handleUnauthorized()
        }
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText))
        } else {
          try {
            reject(JSON.parse(xhr.responseText) as ApiError)
          } catch {
            reject({
              error_code: 'upload_failed',
              message: 'Upload failed',
            } as ApiError)
          }
        }
      })

      xhr.addEventListener('error', () => {
        reject({
          error_code: 'network_error',
          message: 'Network error during upload',
        } as ApiError)
      })

      xhr.open('POST', `${this.baseUrl}${endpoint}`)
      const key = getApiKey()
      if (key) xhr.setRequestHeader('X-API-Key', key)
      xhr.send(formData)
    })
  }

  getDownloadUrl(transcriptionId: string, format: 'txt' | 'json' | 'srt'): string {
    const key = getApiKey()
    const auth = key ? `&api_key=${encodeURIComponent(key)}` : ''
    return `${this.baseUrl}/transcribe/${transcriptionId}/download?format=${format}${auth}`
  }
}

export const apiClient = new ApiClient()
