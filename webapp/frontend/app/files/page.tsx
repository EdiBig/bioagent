'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

interface FileInfo {
  id: number
  filename: string
  original_filename: string
  file_type: string
  file_size: number
  description?: string
  is_profiled: boolean
  profile_data?: any
  created_at: string
}

export default function FilesPage() {
  const router = useRouter()
  const [files, setFiles] = useState<FileInfo[]>([])
  const [selectedFiles, setSelectedFiles] = useState<Set<number>>(new Set())
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [dragActive, setDragActive] = useState(false)
  const [startingAnalysis, setStartingAnalysis] = useState(false)

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api'

  // Load files
  const loadFiles = useCallback(async () => {
    try {
      setIsLoading(true)
      const response = await fetch(`${API_URL}/files/list`)
      if (response.ok) {
        const data = await response.json()
        setFiles(data)
      } else {
        setError('Failed to load files')
      }
    } catch (err) {
      setError('Failed to connect to server')
    } finally {
      setIsLoading(false)
    }
  }, [API_URL])

  useEffect(() => {
    loadFiles()
  }, [loadFiles])

  // Format file size
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  // Get file type color
  const getFileTypeColor = (type: string | undefined | null) => {
    if (!type) return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
    const colors: Record<string, string> = {
      fastq: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
      fasta: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
      vcf: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
      bam: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
      csv: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200',
      tsv: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200',
      bed: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
      gff: 'bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200',
      h5ad: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
    }
    return colors[type.toLowerCase()] || 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
  }

  // Handle file upload
  const handleUpload = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return

    setUploading(true)
    setUploadProgress(0)
    setError(null)

    const formData = new FormData()
    for (let i = 0; i < fileList.length; i++) {
      formData.append('files', fileList[i])
    }

    try {
      const xhr = new XMLHttpRequest()

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          setUploadProgress(Math.round((event.loaded / event.total) * 100))
        }
      })

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          loadFiles()
        } else {
          setError('Upload failed')
        }
        setUploading(false)
        setUploadProgress(0)
      })

      xhr.addEventListener('error', () => {
        setError('Upload failed')
        setUploading(false)
        setUploadProgress(0)
      })

      xhr.open('POST', `${API_URL}/files/upload-multiple`)
      xhr.send(formData)
    } catch (err) {
      setError('Upload failed')
      setUploading(false)
    }
  }

  // Handle drag and drop
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    handleUpload(e.dataTransfer.files)
  }

  // Handle file selection
  const toggleFileSelection = (fileId: number) => {
    setSelectedFiles(prev => {
      const newSet = new Set(prev)
      if (newSet.has(fileId)) {
        newSet.delete(fileId)
      } else {
        newSet.add(fileId)
      }
      return newSet
    })
  }

  const selectAllFiles = () => {
    if (selectedFiles.size === files.length) {
      setSelectedFiles(new Set())
    } else {
      setSelectedFiles(new Set(files.map(f => f.id)))
    }
  }

  // Start analysis with selected files
  const startAnalysis = async () => {
    if (selectedFiles.size === 0) {
      setError('Please select at least one file')
      return
    }

    setStartingAnalysis(true)
    setError(null)

    try {
      const response = await fetch(`${API_URL}/analyses/start-with-files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_ids: Array.from(selectedFiles),
          analysis_type: 'general',
        })
      })

      if (response.ok) {
        const data = await response.json()
        // Redirect to chat page with the analysis
        router.push(data.data.redirect_url)
      } else {
        const errorData = await response.json()
        setError(errorData.detail || 'Failed to start analysis')
      }
    } catch (err) {
      setError('Failed to start analysis')
    } finally {
      setStartingAnalysis(false)
    }
  }

  // Handle delete
  const handleDelete = async (fileId: number) => {
    if (!confirm('Are you sure you want to delete this file?')) return

    try {
      const response = await fetch(`${API_URL}/files/delete/${fileId}`, {
        method: 'DELETE'
      })
      if (response.ok) {
        // Remove from selection if selected
        setSelectedFiles(prev => {
          const newSet = new Set(prev)
          newSet.delete(fileId)
          return newSet
        })
        loadFiles()
      } else {
        setError('Failed to delete file')
      }
    } catch (err) {
      setError('Failed to delete file')
    }
  }

  const selectedFilesList = files.filter(f => selectedFiles.has(f.id))

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
              <h1 className="font-semibold text-gray-900 dark:text-white">File Manager</h1>
              <p className="text-xs text-gray-500 dark:text-gray-400">Upload and manage bioinformatics files</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="px-2 py-1 text-xs font-medium bg-bio-dna-100 text-bio-dna-800 dark:bg-bio-dna-900 dark:text-bio-dna-200 rounded-full">
              34 Formats Supported
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Upload Area */}
        <div
          className={`border-2 border-dashed rounded-xl p-8 mb-8 text-center transition-colors ${
            dragActive
              ? 'border-bio-dna-500 bg-bio-dna-50 dark:bg-bio-dna-900/20'
              : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            type="file"
            multiple
            onChange={(e) => handleUpload(e.target.files)}
            className="hidden"
            id="file-upload"
            accept=".fastq,.fq,.fasta,.fa,.vcf,.bam,.sam,.bed,.gff,.gtf,.csv,.tsv,.h5ad,.mtx,.pdb,.cif,.gz"
          />
          <label htmlFor="file-upload" className="cursor-pointer">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gray-100 dark:bg-gray-800 mb-4">
              <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <p className="text-gray-600 dark:text-gray-300 mb-2">
              <span className="font-medium text-bio-dna-600 dark:text-bio-dna-400">Click to upload</span> or drag and drop
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              FASTQ, FASTA, VCF, BAM, BED, GFF, CSV, TSV, h5ad, PDB, and more
            </p>
          </label>

          {uploading && (
            <div className="mt-4">
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div
                  className="bg-bio-dna-500 h-2 rounded-full transition-all"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <p className="text-sm text-gray-500 mt-2">Uploading... {uploadProgress}%</p>
            </div>
          )}
        </div>

        {/* Selected Files Action Bar */}
        {selectedFiles.size > 0 && (
          <div className="bg-bio-dna-50 dark:bg-bio-dna-900/20 border border-bio-dna-200 dark:border-bio-dna-800 rounded-xl p-4 mb-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-bio-dna-700 dark:text-bio-dna-300 font-medium">
                  {selectedFiles.size} file{selectedFiles.size > 1 ? 's' : ''} selected
                </span>
                <button
                  onClick={() => setSelectedFiles(new Set())}
                  className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  Clear selection
                </button>
              </div>
              <button
                onClick={startAnalysis}
                disabled={startingAnalysis}
                className="px-4 py-2 bg-gradient-to-r from-bio-dna-500 to-bio-rna-500 text-white rounded-lg hover:from-bio-dna-600 hover:to-bio-rna-600 transition-all font-medium flex items-center gap-2 disabled:opacity-50"
              >
                {startingAnalysis ? (
                  <>
                    <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                    Starting...
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Analyze Selected Files
                  </>
                )}
              </button>
            </div>
            {/* Show selected file names */}
            <div className="mt-3 flex flex-wrap gap-2">
              {selectedFilesList.slice(0, 5).map(file => (
                <span key={file.id} className="px-2 py-1 bg-white dark:bg-gray-800 rounded text-xs text-gray-700 dark:text-gray-300">
                  {file.original_filename}
                </span>
              ))}
              {selectedFilesList.length > 5 && (
                <span className="px-2 py-1 text-xs text-gray-500">
                  +{selectedFilesList.length - 5} more
                </span>
              )}
            </div>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6 text-red-700 dark:text-red-300 flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Files List */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
          <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900 dark:text-white">Your Files</h2>
            {files.length > 0 && (
              <button
                onClick={selectAllFiles}
                className="text-sm text-bio-dna-600 hover:text-bio-dna-700 dark:text-bio-dna-400"
              >
                {selectedFiles.size === files.length ? 'Deselect All' : 'Select All'}
              </button>
            )}
          </div>

          {isLoading ? (
            <div className="p-8 text-center">
              <div className="animate-spin h-8 w-8 border-2 border-bio-dna-500 border-t-transparent rounded-full mx-auto" />
              <p className="mt-2 text-gray-500">Loading files...</p>
            </div>
          ) : files.length === 0 ? (
            <div className="p-8 text-center text-gray-500 dark:text-gray-400">
              <svg className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z" />
              </svg>
              <p>No files uploaded yet</p>
              <p className="text-sm">Upload some files to get started with analysis</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200 dark:divide-gray-700">
              {files.map((file) => (
                <div
                  key={file.id}
                  className={`px-6 py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer transition-colors ${
                    selectedFiles.has(file.id) ? 'bg-bio-dna-50 dark:bg-bio-dna-900/20' : ''
                  }`}
                  onClick={() => toggleFileSelection(file.id)}
                >
                  <div className="flex items-center gap-4">
                    {/* Checkbox */}
                    <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                      selectedFiles.has(file.id)
                        ? 'bg-bio-dna-500 border-bio-dna-500'
                        : 'border-gray-300 dark:border-gray-600'
                    }`}>
                      {selectedFiles.has(file.id) && (
                        <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </div>

                    {/* File icon */}
                    <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-gray-700 flex items-center justify-center">
                      <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </div>

                    {/* File info */}
                    <div>
                      <p className="font-medium text-gray-900 dark:text-white">{file.original_filename}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded ${getFileTypeColor(file.file_type)}`}>
                          {(file.file_type || 'UNKNOWN').toUpperCase()}
                        </span>
                        <span className="text-xs text-gray-500">{formatFileSize(file.file_size)}</span>
                        <span className="text-xs text-gray-500">
                          {new Date(file.created_at).toLocaleDateString()}
                        </span>
                        {file.is_profiled && (
                          <span className="px-1.5 py-0.5 text-xs bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 rounded">
                            Profiled
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => handleDelete(file.id)}
                      className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                      title="Delete file"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
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
