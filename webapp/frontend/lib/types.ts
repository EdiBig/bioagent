// API Types for BioAgent Web Application

// ==================== CHAT TYPES ====================

export type MessageRole = 'user' | 'assistant' | 'system'

export interface ChatMessage {
  id: number
  role: MessageRole
  content: string
  created_at: string
  token_count: number
  tool_calls: ToolCall[]
  tool_results: ToolResult[]
  attached_files: string[]
}

export interface ChatMessageCreate {
  content: string
  attached_files?: string[]
}

export interface ChatSession {
  id: number
  title: string
  created_at: string
  updated_at: string
  model_used: string
  total_tokens: number
  total_cost: string
  messages: ChatMessage[]
}

export interface ChatSessionCreate {
  title?: string
}

export interface ChatSessionSummary {
  id: number
  title: string
  created_at: string
  updated_at: string
  message_count: number
  total_tokens: number
}

// ==================== TOOL TYPES ====================

export interface ToolCall {
  tool: string
  input: Record<string, any>
  timestamp?: string
}

export interface ToolResult {
  tool: string
  output: any
  execution_time: number
  metadata?: Record<string, any>
}

// ==================== FILE TYPES ====================

export interface FileUpload {
  filename: string
  size: number
  content_type: string
  file_path: string
  uploaded_at: string
}

export interface FileInfo {
  filename: string
  size: number
  content_type: string
  url: string
  uploaded_at: string
}

// ==================== ANALYSIS TYPES ====================

export type AnalysisStatus = 'pending' | 'running' | 'completed' | 'failed'

export type AnalysisType =
  | 'rnaseq'
  | 'differential_expression'
  | 'pathway_enrichment'
  | 'variant_calling'
  | 'variant_annotation'
  | 'single_cell'
  | 'protein_structure'
  | 'literature_search'
  | 'custom'

export interface AnalysisCreate {
  title: string
  description?: string
  analysis_type: AnalysisType
  input_files?: string[]
}

export interface Analysis {
  id: number
  title: string
  description?: string
  analysis_type: string
  status: AnalysisStatus
  input_files: string[]
  output_files: string[]
  results_summary: Record<string, any>
  created_at: string
  started_at?: string
  completed_at?: string
  compute_time_seconds?: number
  memory_used_gb?: string
  cost_estimate?: string
}

export interface AnalysisStats {
  total_analyses: number
  completed_analyses: number
  running_analyses: number
  failed_analyses: number
  total_compute_hours: number
}

// ==================== USER TYPES ====================

export interface User {
  id: number
  clerk_user_id?: string
  email: string
  full_name?: string
  created_at: string
  preferences: Record<string, any>
}

// ==================== API RESPONSE TYPES ====================

export interface APIResponse<T = any> {
  success: boolean
  message: string
  data?: T
  error?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  has_next: boolean
  has_prev: boolean
}

// ==================== STREAMING TYPES ====================

export type StreamEventType =
  | 'thinking'
  | 'tool_start'
  | 'tool_result'
  | 'code_output'
  | 'text_delta'
  | 'error'
  | 'done'

export interface StreamEvent {
  event: StreamEventType
  data: Record<string, any>
  timestamp?: string
}

export interface ThinkingEventData {
  content: string
}

export interface ToolStartEventData {
  tool: string
  input: Record<string, any>
}

export interface ToolResultEventData {
  tool: string
  output: any
  execution_time: number
}

export interface CodeOutputEventData {
  stdout?: string
  stderr?: string
  plots?: string[]
  execution_time?: number
}

export interface TextDeltaEventData {
  delta: string
}

export interface ErrorEventData {
  error: string
  details?: string
}

export interface DoneEventData {
  message_id?: number
  total_tokens?: number
  execution_time?: number
  tools_used?: string[]
}

// ==================== API CLIENT INTERFACE ====================

export interface APIClient {
  chat: {
    createSession: (data: ChatSessionCreate) => Promise<ChatSession>
    getSession: (id: number) => Promise<ChatSession>
    getSessions: (skip?: number, limit?: number) => Promise<ChatSessionSummary[]>
    deleteSession: (id: number) => Promise<void>
    sendMessage: (sessionId: number, message: ChatMessageCreate) => Promise<ReadableStream>
    getMessages: (sessionId: number, skip?: number, limit?: number) => Promise<ChatMessage[]>
  }
  files: {
    upload: (file: File, description?: string) => Promise<FileUpload>
    uploadMultiple: (files: File[]) => Promise<{ uploaded: FileUpload[]; failed: any[] }>
    list: (skip?: number, limit?: number, fileType?: string) => Promise<FileInfo[]>
    download: (userId: number, filename: string) => Promise<Blob>
    delete: (filename: string) => Promise<void>
    preview: (filename: string, lines?: number) => Promise<{ lines: string[]; truncated: boolean }>
  }
  analyses: {
    create: (data: AnalysisCreate, chatSessionId?: number) => Promise<Analysis>
    get: (id: number) => Promise<Analysis>
    list: (
      skip?: number,
      limit?: number,
      analysisType?: AnalysisType,
      status?: AnalysisStatus
    ) => Promise<PaginatedResponse<Analysis>>
    updateStatus: (id: number, status: AnalysisStatus, results?: any) => Promise<Analysis>
    delete: (id: number) => Promise<void>
    getStats: () => Promise<AnalysisStats>
    getTypes: () => Promise<AnalysisType[]>
  }
}
