'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

interface Analysis {
  id: number
  analysis_id: string
  title: string
  analysis_type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  input_files: Array<{ id: number; filename: string; file_type: string }>
  chat_session_id?: number
  created_at: string
  started_at?: string
  completed_at?: string
}

interface AnalysisStats {
  total_analyses: number
  completed_analyses: number
  running_analyses: number
  failed_analyses: number
  total_compute_hours: number
}

export default function AnalysesPage() {
  const router = useRouter()
  const [analyses, setAnalyses] = useState<Analysis[]>([])
  const [stats, setStats] = useState<AnalysisStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterType, setFilterType] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('all')

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api'

  // Load analyses
  const loadAnalyses = useCallback(async () => {
    try {
      setIsLoading(true)
      const params = new URLSearchParams()
      if (filterType !== 'all') params.append('analysis_type', filterType)
      if (filterStatus !== 'all') params.append('status', filterStatus)

      const response = await fetch(`${API_URL}/analyses?${params}`)
      if (response.ok) {
        const data = await response.json()
        setAnalyses(data.items || [])
      } else {
        setError('Failed to load analyses')
      }
    } catch (err) {
      setError('Failed to connect to server')
    } finally {
      setIsLoading(false)
    }
  }, [API_URL, filterType, filterStatus])

  // Load stats
  const loadStats = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/analyses/stats/summary`)
      if (response.ok) {
        const data = await response.json()
        setStats(data.data)
      }
    } catch (err) {
      // Stats are optional
    }
  }, [API_URL])

  useEffect(() => {
    loadAnalyses()
    loadStats()
  }, [loadAnalyses, loadStats])

  // Get status color
  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
      running: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
      completed: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
      failed: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    }
    return colors[status] || 'bg-gray-100 text-gray-800'
  }

  // Get analysis type icon
  const getTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      differential_expression: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
      pathway_enrichment: 'M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1',
      variant_annotation: 'M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z',
      literature_search: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
      general: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
    }
    return icons[type] || icons['general']
  }

  const analysisTypes = [
    'all',
    'general',
    'differential_expression',
    'pathway_enrichment',
    'variant_annotation',
    'literature_search',
    'structure_prediction',
    'single_cell'
  ]

  // Navigate to analysis chat
  const openAnalysis = (analysis: Analysis) => {
    if (analysis.chat_session_id) {
      router.push(`/chat/${analysis.chat_session_id}`)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </Link>
            <div>
              <h1 className="font-semibold text-gray-900 dark:text-white">Analysis History</h1>
              <p className="text-xs text-gray-500 dark:text-gray-400">Track and manage your bioinformatics analyses</p>
            </div>
          </div>
          <Link
            href="/files"
            className="px-4 py-2 text-sm font-medium bg-gradient-to-r from-bio-dna-500 to-bio-rna-500 text-white rounded-lg hover:from-bio-dna-600 hover:to-bio-rna-600 transition-all flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Analysis
          </Link>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Workflow Info */}
        <div className="bg-gradient-to-r from-bio-dna-50 to-bio-rna-50 dark:from-bio-dna-900/20 dark:to-bio-rna-900/20 border border-bio-dna-200 dark:border-bio-dna-800 rounded-xl p-4 mb-8">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-bio-dna-100 dark:bg-bio-dna-900 flex items-center justify-center flex-shrink-0">
              <svg className="w-5 h-5 text-bio-dna-600 dark:text-bio-dna-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <h3 className="font-medium text-gray-900 dark:text-white">How to Start an Analysis</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                1. Go to <Link href="/files" className="text-bio-dna-600 dark:text-bio-dna-400 hover:underline">File Manager</Link> and upload your data files
                <br />
                2. Select the files you want to analyze
                <br />
                3. Click "Analyze Selected Files" to start a new analysis session
              </p>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-500 dark:text-gray-400">Total Analyses</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.total_analyses}</p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-500 dark:text-gray-400">Completed</p>
              <p className="text-2xl font-bold text-green-600">{stats.completed_analyses}</p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-500 dark:text-gray-400">Running</p>
              <p className="text-2xl font-bold text-blue-600">{stats.running_analyses}</p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-500 dark:text-gray-400">Failed</p>
              <p className="text-2xl font-bold text-red-600">{stats.failed_analyses}</p>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-wrap gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Analysis Type
            </label>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-bio-dna-500"
            >
              {analysisTypes.map((type) => (
                <option key={type} value={type}>
                  {type === 'all' ? 'All Types' : type.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Status
            </label>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-bio-dna-500"
            >
              <option value="all">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6 text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        {/* Analyses List */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
          {isLoading ? (
            <div className="p-8 text-center">
              <div className="animate-spin h-8 w-8 border-2 border-bio-dna-500 border-t-transparent rounded-full mx-auto" />
              <p className="mt-2 text-gray-500">Loading analyses...</p>
            </div>
          ) : analyses.length === 0 ? (
            <div className="p-8 text-center text-gray-500 dark:text-gray-400">
              <svg className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <p>No analyses found</p>
              <p className="text-sm mt-1">Upload files and start your first analysis</p>
              <Link
                href="/files"
                className="inline-flex items-center gap-2 mt-4 px-4 py-2 text-sm font-medium bg-bio-dna-500 text-white rounded-lg hover:bg-bio-dna-600 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                Upload Files
              </Link>
            </div>
          ) : (
            <div className="divide-y divide-gray-200 dark:divide-gray-700">
              {analyses.map((analysis) => (
                <div
                  key={analysis.id}
                  className="px-6 py-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer transition-colors"
                  onClick={() => openAnalysis(analysis)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 rounded-lg bg-bio-dna-100 dark:bg-bio-dna-900 flex items-center justify-center">
                        <svg className="w-5 h-5 text-bio-dna-600 dark:text-bio-dna-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={getTypeIcon(analysis.analysis_type)} />
                        </svg>
                      </div>
                      <div>
                        <p className="font-medium text-gray-900 dark:text-white">{analysis.title}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs text-bio-dna-600 dark:text-bio-dna-400 font-mono bg-bio-dna-50 dark:bg-bio-dna-900/30 px-1.5 py-0.5 rounded">
                            {analysis.analysis_id}
                          </span>
                          <span className="text-xs text-gray-500">{(analysis.analysis_type || 'general').replace(/_/g, ' ')}</span>
                        </div>
                        {/* Input files */}
                        {analysis.input_files && analysis.input_files.length > 0 && (
                          <div className="flex items-center gap-1 mt-2">
                            <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            <span className="text-xs text-gray-500">
                              {analysis.input_files.slice(0, 2).map(f => f.filename).join(', ')}
                              {analysis.input_files.length > 2 && ` +${analysis.input_files.length - 2} more`}
                            </span>
                          </div>
                        )}
                        <p className="text-xs text-gray-400 mt-1">
                          Created {new Date(analysis.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(analysis.status)}`}>
                        {analysis.status}
                      </span>
                      {analysis.status === 'running' && (
                        <div className="animate-spin h-4 w-4 border-2 border-bio-dna-500 border-t-transparent rounded-full" />
                      )}
                      {analysis.chat_session_id && (
                        <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
