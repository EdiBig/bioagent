import axios, { AxiosInstance, AxiosResponse } from 'axios'
import {
  APIResponse,
  PaginatedResponse,
  ChatSession,
  ChatSessionSummary,
  ChatSessionCreate,
  ChatMessage,
  ChatMessageCreate,
  FileUpload,
  FileInfo,
  Analysis,
  AnalysisCreate,
  AnalysisStats,
  AnalysisType,
  AnalysisStatus,
  StoragePreferences,
  StoragePreferencesUpdate,
  FolderStructurePreview,
  StorageInfo,
} from './types'

/**
 * BioAgent API Client
 *
 * Handles all API communication with the backend.
 */
class BioAgentAPIClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api',
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Request interceptor for auth
    this.client.interceptors.request.use(
      (config) => {
        // TODO: Add authentication token from Clerk when integrated
        // const token = getAuthToken()
        // if (token) {
        //   config.headers.Authorization = `Bearer ${token}`
        // }
        return config
      },
      (error) => Promise.reject(error)
    )

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        const message = error.response?.data?.error || error.message || 'An error occurred'
        throw new Error(message)
      }
    )
  }

  // ==================== Chat API ====================

  chat = {
    createSession: async (data: ChatSessionCreate): Promise<ChatSession> => {
      const response: AxiosResponse<APIResponse<ChatSession>> = await this.client.post(
        '/chat/sessions',
        data
      )
      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to create session')
      }
      return response.data.data!
    },

    getSession: async (id: number): Promise<ChatSession> => {
      const response: AxiosResponse<ChatSession> = await this.client.get(
        `/chat/sessions/${id}`
      )
      return response.data
    },

    getSessions: async (skip = 0, limit = 20): Promise<ChatSessionSummary[]> => {
      const response: AxiosResponse<ChatSessionSummary[]> = await this.client.get(
        '/chat/sessions',
        { params: { skip, limit } }
      )
      return response.data
    },

    deleteSession: async (id: number): Promise<void> => {
      await this.client.delete(`/chat/sessions/${id}`)
    },

    sendMessage: (sessionId: number, message: ChatMessageCreate): Promise<ReadableStream> => {
      return new Promise((resolve, reject) => {
        const url = `${this.client.defaults.baseURL}/chat/sessions/${sessionId}/messages`

        fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            // TODO: Add auth headers when integrated
          },
          body: JSON.stringify(message),
        })
          .then((response) => {
            if (!response.ok) {
              throw new Error(`HTTP ${response.status}: ${response.statusText}`)
            }
            if (!response.body) {
              throw new Error('No response body')
            }
            resolve(response.body)
          })
          .catch(reject)
      })
    },

    getMessages: async (
      sessionId: number,
      skip = 0,
      limit = 50
    ): Promise<ChatMessage[]> => {
      const response: AxiosResponse<ChatMessage[]> = await this.client.get(
        `/chat/sessions/${sessionId}/messages`,
        { params: { skip, limit } }
      )
      return response.data
    },
  }

  // ==================== Files API ====================

  files = {
    upload: async (file: File, description?: string): Promise<FileUpload> => {
      const formData = new FormData()
      formData.append('file', file)
      if (description) {
        formData.append('description', description)
      }

      const response: AxiosResponse<APIResponse<FileUpload>> = await this.client.post(
        '/files/upload',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      )

      if (!response.data.success) {
        throw new Error(response.data.error || 'Upload failed')
      }
      return response.data.data!
    },

    uploadMultiple: async (
      files: File[]
    ): Promise<{ uploaded: FileUpload[]; failed: any[] }> => {
      const formData = new FormData()
      files.forEach((file) => formData.append('files', file))

      const response: AxiosResponse<
        APIResponse<{ uploaded: FileUpload[]; failed: any[] }>
      > = await this.client.post('/files/upload-multiple', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      if (!response.data.success) {
        throw new Error(response.data.error || 'Upload failed')
      }
      return response.data.data!
    },

    list: async (skip = 0, limit = 50, fileType?: string): Promise<FileInfo[]> => {
      const response: AxiosResponse<FileInfo[]> = await this.client.get('/files/list', {
        params: { skip, limit, file_type: fileType },
      })
      return response.data
    },

    download: async (userId: number, filename: string): Promise<Blob> => {
      const response: AxiosResponse<Blob> = await this.client.get(
        `/files/download/${userId}/${filename}`,
        { responseType: 'blob' }
      )
      return response.data
    },

    delete: async (filename: string): Promise<void> => {
      await this.client.delete(`/files/delete/${filename}`)
    },

    preview: async (
      filename: string,
      lines = 50
    ): Promise<{ lines: string[]; truncated: boolean }> => {
      const response: AxiosResponse<
        APIResponse<{ lines: string[]; truncated: boolean }>
      > = await this.client.get(`/files/preview/${filename}`, {
        params: { lines },
      })

      if (!response.data.success) {
        throw new Error(response.data.error || 'Preview failed')
      }
      return response.data.data!
    },
  }

  // ==================== Settings API ====================

  settings = {
    getStoragePreferences: async (): Promise<StoragePreferences> => {
      const response: AxiosResponse<StoragePreferences> = await this.client.get(
        '/settings/storage'
      )
      return response.data
    },

    updateStoragePreferences: async (
      preferences: StoragePreferencesUpdate
    ): Promise<StoragePreferences> => {
      const response: AxiosResponse<StoragePreferences> = await this.client.put(
        '/settings/storage',
        preferences
      )
      return response.data
    },

    previewFolderStructure: async (
      preferences: StoragePreferencesUpdate
    ): Promise<FolderStructurePreview> => {
      const params = new URLSearchParams()
      params.append('create_subfolders', String(preferences.create_subfolders))
      params.append('subfolder_by_date', String(preferences.subfolder_by_date))
      params.append('subfolder_by_type', String(preferences.subfolder_by_type))

      const response: AxiosResponse<FolderStructurePreview> = await this.client.get(
        `/settings/storage/preview?${params.toString()}`
      )
      return response.data
    },

    getStorageInfo: async (): Promise<StorageInfo> => {
      const response: AxiosResponse<StorageInfo> = await this.client.get(
        '/settings/storage/info'
      )
      return response.data
    },

    ensureWorkspaceStructure: async (): Promise<{ success: boolean; directories: Record<string, string> }> => {
      const response: AxiosResponse<{ success: boolean; directories: Record<string, string> }> = await this.client.post(
        '/settings/storage/ensure-structure'
      )
      return response.data
    },
  }

  // ==================== Analyses API ====================

  analyses = {
    create: async (data: AnalysisCreate, chatSessionId?: number): Promise<Analysis> => {
      const response: AxiosResponse<APIResponse<Analysis>> = await this.client.post(
        '/analyses',
        data,
        {
          params: chatSessionId ? { chat_session_id: chatSessionId } : undefined,
        }
      )

      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to create analysis')
      }
      return response.data.data!
    },

    get: async (id: number): Promise<Analysis> => {
      const response: AxiosResponse<Analysis> = await this.client.get(`/analyses/${id}`)
      return response.data
    },

    list: async (
      skip = 0,
      limit = 20,
      analysisType?: AnalysisType,
      status?: AnalysisStatus
    ): Promise<PaginatedResponse<Analysis>> => {
      const response: AxiosResponse<PaginatedResponse<Analysis>> = await this.client.get(
        '/analyses',
        {
          params: { skip, limit, analysis_type: analysisType, status },
        }
      )
      return response.data
    },

    updateStatus: async (
      id: number,
      status: AnalysisStatus,
      results?: any
    ): Promise<Analysis> => {
      const response: AxiosResponse<APIResponse<Analysis>> = await this.client.patch(
        `/analyses/${id}/status`,
        {
          status,
          ...results,
        }
      )

      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to update analysis')
      }
      return response.data.data!
    },

    delete: async (id: number): Promise<void> => {
      await this.client.delete(`/analyses/${id}`)
    },

    getStats: async (): Promise<AnalysisStats> => {
      const response: AxiosResponse<APIResponse<AnalysisStats>> = await this.client.get(
        '/analyses/stats/summary'
      )

      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to fetch stats')
      }
      return response.data.data!
    },

    getTypes: async (): Promise<AnalysisType[]> => {
      const response: AxiosResponse<AnalysisType[]> = await this.client.get(
        '/analyses/types/available'
      )
      return response.data
    },
  }
}

// Create singleton instance
export const apiClient = new BioAgentAPIClient()

/**
 * Helper function for file uploads with progress
 */
export const uploadWithProgress = (
  file: File,
  onProgress?: (progress: number) => void,
  description?: string
): Promise<FileUpload> => {
  return new Promise((resolve, reject) => {
    const formData = new FormData()
    formData.append('file', file)
    if (description) {
      formData.append('description', description)
    }

    const xhr = new XMLHttpRequest()

    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable && onProgress) {
        const progress = (event.loaded / event.total) * 100
        onProgress(progress)
      }
    })

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const response = JSON.parse(xhr.responseText)
          if (response.success) {
            resolve(response.data)
          } else {
            reject(new Error(response.error || 'Upload failed'))
          }
        } catch (error) {
          reject(new Error('Invalid response format'))
        }
      } else {
        reject(new Error(`HTTP ${xhr.status}: ${xhr.statusText}`))
      }
    })

    xhr.addEventListener('error', () => {
      reject(new Error('Upload failed'))
    })

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api'
    xhr.open('POST', `${apiUrl}/files/upload`)

    // TODO: Add auth headers when integrated
    // xhr.setRequestHeader('Authorization', `Bearer ${token}`)

    xhr.send(formData)
  })
}
