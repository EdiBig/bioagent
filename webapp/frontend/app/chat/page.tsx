'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function ChatPage() {
  const router = useRouter()
  const [isCreating, setIsCreating] = useState(false)

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api'

  const createNewChat = async () => {
    setIsCreating(true)
    try {
      const response = await fetch(`${API_URL}/chat/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New Chat' })
      })
      if (response.ok) {
        const data = await response.json()
        const sessionId = data.data?.session_id || data.session_id
        router.push(`/chat/${sessionId}`)
      }
    } catch (err) {
      console.error('Failed to create chat:', err)
      setIsCreating(false)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center h-full bg-gray-50 dark:bg-gray-900 p-8">
      <div className="text-center max-w-lg">
        {/* Logo */}
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-bio-dna-500 to-bio-rna-500 mb-6 shadow-lg">
          <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        </div>

        {/* Title */}
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-3">
          Welcome to BioAgent
        </h1>
        <p className="text-gray-600 dark:text-gray-300 mb-8">
          Your AI-powered bioinformatics assistant with 72+ specialized tools for
          genomics, transcriptomics, proteomics, and more.
        </p>

        {/* Start Chat Button */}
        <button
          onClick={createNewChat}
          disabled={isCreating}
          className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-bio-dna-500 to-bio-rna-500 text-white rounded-xl hover:from-bio-dna-600 hover:to-bio-rna-600 transition-all font-medium text-lg shadow-lg hover:shadow-xl disabled:opacity-50"
        >
          {isCreating ? (
            <>
              <div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full" />
              Creating...
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Start New Chat
            </>
          )}
        </button>

        {/* Feature Pills */}
        <div className="mt-10 flex flex-wrap justify-center gap-2">
          {[
            'Gene Expression Analysis',
            'Pathway Enrichment',
            'Variant Annotation',
            'Literature Search',
            'Protein Structure',
            'Single-cell Analysis'
          ].map((feature) => (
            <span
              key={feature}
              className="px-3 py-1 text-xs bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700 rounded-full"
            >
              {feature}
            </span>
          ))}
        </div>

        {/* Tip */}
        <p className="mt-8 text-sm text-gray-500 dark:text-gray-400">
          Select a previous chat from the sidebar or start a new conversation
        </p>
      </div>
    </div>
  )
}
