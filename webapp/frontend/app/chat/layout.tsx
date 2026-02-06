'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import Link from 'next/link'

interface ChatSession {
  id: number
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const pathname = usePathname()
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editTitle, setEditTitle] = useState('')

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api'

  // Get current session ID from pathname
  const currentSessionId = pathname.match(/\/chat\/(\d+)/)?.[1]

  // Load chat sessions
  const loadSessions = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/chat/sessions`)
      if (response.ok) {
        const data = await response.json()
        setSessions(data)
      }
    } catch (err) {
      console.error('Failed to load sessions:', err)
    } finally {
      setIsLoading(false)
    }
  }, [API_URL])

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  // Refresh sessions periodically
  useEffect(() => {
    const interval = setInterval(loadSessions, 30000) // Every 30 seconds
    return () => clearInterval(interval)
  }, [loadSessions])

  // Create new chat
  const createNewChat = async () => {
    try {
      const response = await fetch(`${API_URL}/chat/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New Chat' })
      })
      if (response.ok) {
        const data = await response.json()
        const sessionId = data.data?.session_id || data.session_id
        loadSessions()
        router.push(`/chat/${sessionId}`)
      }
    } catch (err) {
      console.error('Failed to create chat:', err)
    }
  }

  // Delete chat
  const deleteChat = async (id: number, e: React.MouseEvent) => {
    // Prevent event bubbling to parent (which would navigate)
    e.preventDefault()
    e.stopPropagation()

    // Confirm deletion
    const confirmed = window.confirm('Delete this chat?')
    if (!confirmed) return

    // Navigate away if deleting current chat (do this first)
    if (currentSessionId === String(id)) {
      router.push('/chat')
    }

    // Optimistic update - remove from UI immediately
    setSessions(prev => prev.filter(s => s.id !== id))

    try {
      const response = await fetch(`${API_URL}/chat/sessions/${id}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        const errorText = await response.text()
        console.error('Delete failed:', response.status, errorText)
        // Revert on error
        loadSessions()
        alert('Failed to delete chat. Please try again.')
      }
    } catch (err) {
      console.error('Failed to delete chat:', err)
      // Revert on error
      loadSessions()
      alert('Failed to delete chat. Please try again.')
    }
  }

  // Rename chat
  const startRename = (session: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingId(session.id)
    setEditTitle(session.title)
  }

  const saveRename = async (id: number) => {
    if (!editTitle.trim()) {
      setEditingId(null)
      return
    }

    try {
      const response = await fetch(`${API_URL}/chat/sessions/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: editTitle.trim() })
      })
      if (response.ok) {
        loadSessions()
      }
    } catch (err) {
      console.error('Failed to rename chat:', err)
    } finally {
      setEditingId(null)
    }
  }

  // Format date
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {/* Sidebar */}
      <aside
        className={`${
          isSidebarOpen ? 'w-72' : 'w-0'
        } flex-shrink-0 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 transition-all duration-300 overflow-hidden`}
      >
        <div className="flex flex-col h-full w-72">
          {/* Sidebar Header */}
          <div className="flex-shrink-0 p-4 border-b border-gray-200 dark:border-gray-700">
            {/* Dashboard Link */}
            <Link
              href="/"
              className="flex items-center gap-2 px-3 py-2 mb-3 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
              </svg>
              <span className="font-medium">Dashboard</span>
            </Link>

            <button
              onClick={createNewChat}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-bio-dna-500 to-bio-rna-500 text-white rounded-lg hover:from-bio-dna-600 hover:to-bio-rna-600 transition-colors font-medium"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New Chat
            </button>
          </div>

          {/* Chat History */}
          <div className="flex-1 overflow-y-auto p-2">
            <h3 className="px-3 py-2 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Chat History
            </h3>

            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin h-6 w-6 border-2 border-bio-dna-500 border-t-transparent rounded-full" />
              </div>
            ) : sessions.length === 0 ? (
              <div className="text-center py-8 px-4">
                <svg className="w-12 h-12 mx-auto text-gray-300 dark:text-gray-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <p className="text-sm text-gray-500 dark:text-gray-400">No chats yet</p>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Start a new conversation</p>
              </div>
            ) : (
              <div className="space-y-1">
                {sessions.map((session) => (
                  <div
                    key={session.id}
                    onClick={() => router.push(`/chat/${session.id}`)}
                    className={`group relative flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
                      currentSessionId === String(session.id)
                        ? 'bg-bio-dna-50 dark:bg-bio-dna-900/20 text-bio-dna-700 dark:text-bio-dna-300'
                        : 'hover:bg-gray-100 dark:hover:bg-gray-700/50 text-gray-700 dark:text-gray-300'
                    }`}
                  >
                    <svg className="w-5 h-5 flex-shrink-0 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>

                    <div className="flex-1 min-w-0">
                      {editingId === session.id ? (
                        <input
                          type="text"
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          onBlur={() => saveRename(session.id)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') saveRename(session.id)
                            if (e.key === 'Escape') setEditingId(null)
                          }}
                          onClick={(e) => e.stopPropagation()}
                          autoFocus
                          className="w-full px-1 py-0.5 text-sm bg-white dark:bg-gray-700 border border-bio-dna-500 rounded focus:outline-none"
                        />
                      ) : (
                        <>
                          <p className="text-sm font-medium truncate">{session.title}</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            {formatDate(session.updated_at)} • {session.message_count} messages
                          </p>
                        </>
                      )}
                    </div>

                    {/* Actions - always visible for better UX */}
                    {editingId !== session.id && (
                      <div className="absolute right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={(e) => {
                            e.preventDefault()
                            e.stopPropagation()
                            startRename(session, e)
                          }}
                          className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
                          title="Rename"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </button>
                        <button
                          onClick={(e) => {
                            e.preventDefault()
                            e.stopPropagation()
                            deleteChat(session.id, e)
                          }}
                          className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                          title="Delete"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Sidebar Footer */}
          <div className="flex-shrink-0 p-4 border-t border-gray-200 dark:border-gray-700">
            <Link
              href="/"
              className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
              </svg>
              Back to Home
            </Link>
          </div>
        </div>
      </aside>

      {/* Floating Controls */}
      <div
        className="absolute top-4 z-10 flex items-center gap-2 transition-all duration-300"
        style={{ left: isSidebarOpen ? '280px' : '8px' }}
      >
        {/* Dashboard Button (visible when sidebar closed) */}
        {!isSidebarOpen && (
          <Link
            href="/"
            className="p-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            title="Back to Dashboard"
          >
            <svg className="w-5 h-5 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
          </Link>
        )}

        {/* Toggle Sidebar Button */}
        <button
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className="p-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          title={isSidebarOpen ? 'Close sidebar' : 'Open sidebar'}
        >
          <svg
            className={`w-5 h-5 text-gray-600 dark:text-gray-400 transition-transform ${isSidebarOpen ? '' : 'rotate-180'}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        {children}
      </main>
    </div>
  )
}
