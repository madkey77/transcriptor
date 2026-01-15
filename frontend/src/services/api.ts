const API_BASE_URL = '/api'

export interface ApiError {
  error_code: string
  message: string
  details?: string
}

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  private async handleResponse<T>(response: Response): Promise<T> {
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
    const response = await fetch(`${this.baseUrl}${endpoint}`)
    return this.handleResponse<T>(response)
  }

  async post<T>(endpoint: string, data?: FormData | object): Promise<T> {
    const options: RequestInit = {
      method: 'POST',
    }

    if (data instanceof FormData) {
      options.body = data
    } else if (data) {
      options.headers = { 'Content-Type': 'application/json' }
      options.body = JSON.stringify(data)
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, options)
    return this.handleResponse<T>(response)
  }

  async patch<T>(endpoint: string, data: object): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    return this.handleResponse<T>(response)
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
      xhr.send(formData)
    })
  }

  getDownloadUrl(transcriptionId: string, format: 'txt' | 'json' | 'srt'): string {
    return `${this.baseUrl}/transcribe/${transcriptionId}/download?format=${format}`
  }
}

export const apiClient = new ApiClient()
