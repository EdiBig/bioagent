'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'

// Types for chat
interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
  tool_calls?: any[]
  tool_results?: any[]
}

interface StreamEvent {
  event: string
  data: any
}

interface ToolExecution {
  tool: string
  status: 'running' | 'complete' | 'error'
  input?: any
  output?: any
  execution_time?: number
}

interface AnalysisContext {
  id: number
  analysis_id: string
  title: string
  description?: string
  analysis_type: string
  status: string
  input_files: Array<{ id: number; filename: string; file_type: string; file_size: number }>
  created_at: string
}

export default function ChatSessionPage() {
  const params = useParams()
  const router = useRouter()
  const sessionId = params.id as string

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentThinking, setCurrentThinking] = useState<string | null>(null)
  const [currentTools, setCurrentTools] = useState<ToolExecution[]>([])
  const [streamingContent, setStreamingContent] = useState('')
  const [analysisContext, setAnalysisContext] = useState<AnalysisContext | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api'

  // Scroll to bottom when messages change
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, streamingContent])

  // Load existing messages and analysis context
  useEffect(() => {
    const loadMessages = async () => {
      try {
        const response = await fetch(`${API_URL}/chat/sessions/${sessionId}/messages`)
        if (response.ok) {
          const data = await response.json()
          setMessages(data)
        }
      } catch (err) {
        console.error('Failed to load messages:', err)
      }
    }

    const loadAnalysisContext = async () => {
      try {
        const response = await fetch(`${API_URL}/analyses/by-chat/${sessionId}`)
        if (response.ok) {
          const data = await response.json()
          if (data) {
            setAnalysisContext(data)
          }
        }
      } catch (err) {
        console.error('Failed to load analysis context:', err)
      }
    }

    if (sessionId) {
      loadMessages()
      loadAnalysisContext()
    }
  }, [sessionId, API_URL])

  // Handle sending a message
  const sendMessage = useCallback(async () => {
    if (!input.trim() || isStreaming) return

    const userMessage = input.trim()
    setInput('')
    setIsStreaming(true)
    setError(null)
    setCurrentThinking(null)
    setCurrentTools([])
    setStreamingContent('')

    // Add user message immediately
    const tempUserMessage: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString()
    }
    setMessages(prev => [...prev, tempUserMessage])

    try {
      const response = await fetch(`${API_URL}/chat/sessions/${sessionId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content: userMessage,
          attached_files: []
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      if (!response.body) {
        throw new Error('No response body')
      }

      // Process SSE stream
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullContent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            const eventType = line.slice(7)
            continue
          }
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))

              // Handle different event types based on data structure
              if (data.content && !data.delta) {
                // Thinking event
                setCurrentThinking(data.content)
              } else if (data.tool && data.input) {
                // Tool start event
                setCurrentTools(prev => [...prev, {
                  tool: data.tool,
                  status: 'running',
                  input: data.input
                }])
              } else if (data.tool && data.output !== undefined) {
                // Tool result event
                setCurrentTools(prev => prev.map(t =>
                  t.tool === data.tool && t.status === 'running'
                    ? { ...t, status: 'complete', output: data.output, execution_time: data.execution_time }
                    : t
                ))
              } else if (data.delta) {
                // Text delta event
                fullContent += data.delta
                setStreamingContent(fullContent)
                setCurrentThinking(null)
              } else if (data.error) {
                // Error event
                setError(data.error)
              }
            } catch (e) {
              // Ignore parse errors
            }
          }
        }
      }

      // Add assistant message after streaming completes
      if (fullContent) {
        const assistantMessage: ChatMessage = {
          id: Date.now() + 1,
          role: 'assistant',
          content: fullContent,
          created_at: new Date().toISOString(),
          tool_calls: currentTools.filter(t => t.status === 'complete')
        }
        setMessages(prev => [...prev, assistantMessage])
        setStreamingContent('')
      }

    } catch (err) {
      console.error('Failed to send message:', err)
      setError(err instanceof Error ? err.message : 'Failed to send message')
    } finally {
      setIsStreaming(false)
      setCurrentThinking(null)
    }
  }, [input, isStreaming, sessionId, API_URL, currentTools])

  // Handle Enter key
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900">
      {/* Compact Header */}
      <header className="flex-shrink-0 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-2">
        <div className="flex items-center justify-between ml-10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-bio-dna-500 to-bio-rna-500 flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <div>
              <h1 className="font-semibold text-gray-900 dark:text-white text-sm">BioAgent</h1>
              <p className="text-xs text-gray-500 dark:text-gray-400">Session #{sessionId}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 rounded-full">
              72 Tools
            </span>
            <Link
              href="/files"
              className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 rounded-full hover:bg-blue-200 dark:hover:bg-blue-800 transition-colors"
            >
              Files
            </Link>
          </div>
        </div>
      </header>

      {/* Analysis Context Banner */}
      {analysisContext && (
        <div className="flex-shrink-0 bg-gradient-to-r from-bio-dna-50 to-bio-rna-50 dark:from-bio-dna-900/20 dark:to-bio-rna-900/20 border-b border-bio-dna-200 dark:border-bio-dna-800 px-4 py-3">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-bio-dna-100 dark:bg-bio-dna-900 flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 text-bio-dna-600 dark:text-bio-dna-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-mono text-bio-dna-600 dark:text-bio-dna-400 bg-bio-dna-100 dark:bg-bio-dna-900/50 px-2 py-0.5 rounded">
                    {analysisContext.analysis_id}
                  </span>
                  <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                    analysisContext.status === 'completed' ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' :
                    analysisContext.status === 'running' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' :
                    analysisContext.status === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300' :
                    'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300'
                  }`}>
                    {analysisContext.status}
                  </span>
                </div>
                <h3 className="font-medium text-gray-900 dark:text-white mt-1 truncate">{analysisContext.title}</h3>
                {analysisContext.input_files && analysisContext.input_files.length > 0 && (
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    {analysisContext.input_files.map((file, idx) => (
                      <span key={idx} className="px-2 py-1 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded text-gray-700 dark:text-gray-300">
                        {file.filename}
                        <span className="text-gray-400 ml-1">({file.file_type?.toUpperCase()})</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Messages Area */}
      <main className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Welcome message if no messages */}
          {messages.length === 0 && !isStreaming && analysisContext && (
            <div className="text-center py-8">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-bio-dna-500 to-bio-rna-500 mb-4">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                Ready to Analyze Your Data
              </h2>
              <p className="text-gray-600 dark:text-gray-300 max-w-md mx-auto mb-4">
                I have access to your files. Tell me what analysis you'd like to perform.
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {[
                  `Summarize the data in ${analysisContext.input_files[0]?.filename || 'my file'}`,
                  'Run differential expression analysis',
                  'Show basic statistics',
                  'What can you tell me about this data?'
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setInput(suggestion)}
                    className="px-3 py-1.5 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-full hover:border-bio-dna-500 hover:text-bio-dna-600 transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Welcome message if no messages and no analysis */}
          {messages.length === 0 && !isStreaming && !analysisContext && (
            <div className="text-center py-12">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-bio-dna-500 to-bio-rna-500 mb-4">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                Welcome to BioAgent
              </h2>
              <p className="text-gray-600 dark:text-gray-300 max-w-md mx-auto">
                Your AI-powered bioinformatics assistant. Ask me about gene expression analysis,
                pathway enrichment, variant annotation, literature search, and more.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {['Analyze RNA-seq data', 'Search PubMed', 'Predict protein structure', 'Pathway enrichment'].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setInput(suggestion)}
                    className="px-3 py-1.5 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-full hover:border-bio-dna-500 hover:text-bio-dna-600 transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] ${
                  message.role === 'user'
                    ? 'bg-bio-dna-500 text-white rounded-2xl rounded-br-md'
                    : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-2xl rounded-bl-md shadow-sm border border-gray-200 dark:border-gray-700'
                } px-4 py-3`}
              >
                <div className="whitespace-pre-wrap">{message.content}</div>
                {message.tool_calls && message.tool_calls.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Tools used:</p>
                    <div className="flex flex-wrap gap-1">
                      {message.tool_calls.map((tool: any, idx: number) => (
                        <span key={idx} className="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-700 rounded">
                          {tool.tool}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Streaming content */}
          {isStreaming && (
            <div className="space-y-4">
              {/* Thinking indicator */}
              {currentThinking && (
                <div className="flex items-start gap-3 text-gray-600 dark:text-gray-400">
                  <div className="animate-pulse">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                  </div>
                  <span className="text-sm italic">{currentThinking}</span>
                </div>
              )}

              {/* Tool executions */}
              {currentTools.length > 0 && (
                <div className="space-y-2">
                  {currentTools.map((tool, idx) => (
                    <div key={idx} className="bg-gray-100 dark:bg-gray-800 rounded-lg p-3 text-sm">
                      <div className="flex items-center gap-2">
                        {tool.status === 'running' ? (
                          <div className="animate-spin h-4 w-4 border-2 border-bio-dna-500 border-t-transparent rounded-full" />
                        ) : (
                          <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                        <span className="font-medium">{tool.tool}</span>
                        {tool.execution_time && (
                          <span className="text-gray-500 text-xs">({tool.execution_time.toFixed(2)}s)</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Streaming response */}
              {streamingContent && (
                <div className="flex justify-start">
                  <div className="max-w-[80%] bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-2xl rounded-bl-md shadow-sm border border-gray-200 dark:border-gray-700 px-4 py-3">
                    <div className="whitespace-pre-wrap">{streamingContent}</div>
                    <span className="inline-block w-2 h-4 bg-bio-dna-500 animate-pulse ml-1" />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Error message */}
          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300">
              <p className="font-medium">Error</p>
              <p className="text-sm">{error}</p>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input Area */}
      <footer className="flex-shrink-0 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-end gap-3">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask BioAgent about bioinformatics..."
                disabled={isStreaming}
                rows={1}
                className="w-full resize-none rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-4 py-3 pr-12 text-gray-900 dark:text-white placeholder-gray-500 focus:border-bio-dna-500 focus:ring-2 focus:ring-bio-dna-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ minHeight: '48px', maxHeight: '200px' }}
              />
            </div>
            <button
              onClick={sendMessage}
              disabled={!input.trim() || isStreaming}
              className="flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-r from-bio-dna-500 to-bio-rna-500 text-white flex items-center justify-center hover:from-bio-dna-600 hover:to-bio-rna-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {isStreaming ? (
                <div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full" />
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              )}
            </button>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 text-center">
            BioAgent can make mistakes. Verify important results with primary sources.
          </p>
        </div>
      </footer>
    </div>
  )
}
