'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { apiClient } from '@/lib/api-client'
import { StoragePreferences, StoragePreferencesUpdate, FolderStructurePreview } from '@/lib/types'

export default function SettingsPage() {
  // Local UI settings (stored in localStorage)
  const [uiSettings, setUiSettings] = useState({
    darkMode: false,
    notifications: true,
    streamingEnabled: true,
    defaultModel: 'claude-opus-4-6',
    maxTokens: 4096,
    temperature: 0.7,
  })

  // Storage preferences (stored in backend)
  const [storagePrefs, setStoragePrefs] = useState<StoragePreferences | null>(null)
  const [storageForm, setStorageForm] = useState<StoragePreferencesUpdate>({
    create_subfolders: true,
    subfolder_by_date: true,
    subfolder_by_type: true,
  })
  const [folderPreview, setFolderPreview] = useState<FolderStructurePreview | null>(null)

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'general' | 'storage'>('general')

  // Load settings on mount
  useEffect(() => {
    const loadSettings = async () => {
      try {
        // Load UI settings from localStorage
        const savedUiSettings = localStorage.getItem('bioagent-settings')
        if (savedUiSettings) {
          setUiSettings(JSON.parse(savedUiSettings))
        }

        // Load storage preferences from backend
        const prefs = await apiClient.settings.getStoragePreferences()
        setStoragePrefs(prefs)
        setStorageForm({
          create_subfolders: prefs.create_subfolders,
          subfolder_by_date: prefs.subfolder_by_date,
          subfolder_by_type: prefs.subfolder_by_type,
        })

        // Load folder preview
        await loadFolderPreview({
          create_subfolders: prefs.create_subfolders,
          subfolder_by_date: prefs.subfolder_by_date,
          subfolder_by_type: prefs.subfolder_by_type,
        })
      } catch (err) {
        console.error('Failed to load settings:', err)
        setError('Failed to load settings')
      } finally {
        setLoading(false)
      }
    }

    loadSettings()
  }, [])

  // Load folder preview when storage form changes
  const loadFolderPreview = async (prefs: StoragePreferencesUpdate) => {
    try {
      const preview = await apiClient.settings.previewFolderStructure(prefs)
      setFolderPreview(preview)
    } catch (err) {
      console.error('Failed to load folder preview:', err)
    }
  }

  // Handle storage form change
  const handleStorageChange = async (updates: Partial<StoragePreferencesUpdate>) => {
    const newForm = { ...storageForm, ...updates }
    setStorageForm(newForm)

    // Update preview
    await loadFolderPreview(newForm)
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)

    try {
      // Save UI settings to localStorage
      localStorage.setItem('bioagent-settings', JSON.stringify(uiSettings))

      // Save storage preferences to backend
      const updatedPrefs = await apiClient.settings.updateStoragePreferences(storageForm)
      setStoragePrefs(updatedPrefs)

      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      console.error('Failed to save settings:', err)
      setError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-bio-dna-500"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </Link>
            <div>
              <h1 className="font-semibold text-gray-900 dark:text-white">Settings</h1>
              <p className="text-xs text-gray-500 dark:text-gray-400">Configure BioAgent preferences</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        {/* Success/Error messages */}
        {saved && (
          <div className="mb-6 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-green-700 dark:text-green-300">
            Settings saved successfully!
          </div>
        )}
        {error && (
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        {/* Tabs */}
        <div className="flex space-x-1 mb-6 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg">
          <button
            onClick={() => setActiveTab('general')}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'general'
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
            }`}
          >
            General
          </button>
          <button
            onClick={() => setActiveTab('storage')}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'storage'
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
            }`}
          >
            Storage
          </button>
        </div>

        {activeTab === 'general' && (
          <>
            {/* Appearance */}
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 mb-6">
              <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <h2 className="font-semibold text-gray-900 dark:text-white">Appearance</h2>
              </div>
              <div className="p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">Dark Mode</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Use dark theme for the interface</p>
                  </div>
                  <button
                    onClick={() => setUiSettings(s => ({ ...s, darkMode: !s.darkMode }))}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      uiSettings.darkMode ? 'bg-bio-dna-500' : 'bg-gray-200 dark:bg-gray-700'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        uiSettings.darkMode ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
              </div>
            </div>

            {/* AI Settings */}
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 mb-6">
              <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <h2 className="font-semibold text-gray-900 dark:text-white">AI Configuration</h2>
              </div>
              <div className="p-6 space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">Streaming Responses</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Show responses as they&apos;re generated</p>
                  </div>
                  <button
                    onClick={() => setUiSettings(s => ({ ...s, streamingEnabled: !s.streamingEnabled }))}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      uiSettings.streamingEnabled ? 'bg-bio-dna-500' : 'bg-gray-200 dark:bg-gray-700'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        uiSettings.streamingEnabled ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>

                <div>
                  <label className="block font-medium text-gray-900 dark:text-white mb-2">
                    Default Model
                  </label>
                  <select
                    value={uiSettings.defaultModel}
                    onChange={(e) => setUiSettings(s => ({ ...s, defaultModel: e.target.value }))}
                    className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-bio-dna-500 text-gray-900 dark:text-white"
                  >
                    <option value="claude-opus-4-6">Claude Opus 4.6 (Most capable, agentic)</option>
                    <option value="claude-sonnet-4-5">Claude Sonnet 4.5 (Balanced)</option>
                    <option value="claude-haiku-4-5">Claude Haiku 4.5 (Fast)</option>
                  </select>
                </div>
              </div>
            </div>

            {/* About */}
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 mb-6">
              <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <h2 className="font-semibold text-gray-900 dark:text-white">About BioAgent</h2>
              </div>
              <div className="p-6">
                <div className="space-y-2 text-sm text-gray-600 dark:text-gray-300">
                  <p><span className="font-medium">Version:</span> 1.0.0</p>
                  <p><span className="font-medium">Tools Available:</span> 72</p>
                  <p><span className="font-medium">Specialists:</span> 6 (Pipeline Engineer, Statistician, Literature Agent, QC Reviewer, Domain Expert, Research Agent)</p>
                  <p><span className="font-medium">Supported Formats:</span> 34 bioinformatics file formats</p>
                </div>
              </div>
            </div>
          </>
        )}

        {activeTab === 'storage' && (
          <>
            {/* Storage Location Info */}
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 mb-6">
              <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <h2 className="font-semibold text-gray-900 dark:text-white">Workspace Location</h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  All files are stored in a single consolidated workspace
                </p>
              </div>
              <div className="p-6">
                {storagePrefs && (
                  <div className="space-y-3">
                    <div className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-900 rounded-lg">
                      <svg className="w-5 h-5 text-bio-dna-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                      </svg>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 dark:text-white">Workspace</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 font-mono truncate">{storagePrefs.workspace_path}</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 bg-gray-50 dark:bg-gray-900 rounded-lg">
                        <p className="text-xs font-medium text-gray-700 dark:text-gray-300">Uploads</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 font-mono truncate">{storagePrefs.uploads_path}</p>
                      </div>
                      <div className="p-3 bg-gray-50 dark:bg-gray-900 rounded-lg">
                        <p className="text-xs font-medium text-gray-700 dark:text-gray-300">Outputs</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 font-mono truncate">{storagePrefs.outputs_path}</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Folder Organization */}
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 mb-6">
              <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <h2 className="font-semibold text-gray-900 dark:text-white">Folder Organization</h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  Automatically organize output files into subfolders
                </p>
              </div>
              <div className="p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">Create Subfolders</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Automatically organize files into folders</p>
                  </div>
                  <button
                    onClick={() => handleStorageChange({ create_subfolders: !storageForm.create_subfolders })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      storageForm.create_subfolders ? 'bg-bio-dna-500' : 'bg-gray-200 dark:bg-gray-700'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        storageForm.create_subfolders ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>

                {storageForm.create_subfolders && (
                  <>
                    <div className="flex items-center justify-between pl-4 border-l-2 border-gray-200 dark:border-gray-600">
                      <div>
                        <p className="font-medium text-gray-900 dark:text-white">Organize by Date</p>
                        <p className="text-sm text-gray-500 dark:text-gray-400">Create folders like 2026-02-06</p>
                      </div>
                      <button
                        onClick={() => handleStorageChange({ subfolder_by_date: !storageForm.subfolder_by_date })}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                          storageForm.subfolder_by_date ? 'bg-bio-dna-500' : 'bg-gray-200 dark:bg-gray-700'
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                            storageForm.subfolder_by_date ? 'translate-x-6' : 'translate-x-1'
                          }`}
                        />
                      </button>
                    </div>

                    <div className="flex items-center justify-between pl-4 border-l-2 border-gray-200 dark:border-gray-600">
                      <div>
                        <p className="font-medium text-gray-900 dark:text-white">Organize by Type</p>
                        <p className="text-sm text-gray-500 dark:text-gray-400">Separate results, reports, figures, etc.</p>
                      </div>
                      <button
                        onClick={() => handleStorageChange({ subfolder_by_type: !storageForm.subfolder_by_type })}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                          storageForm.subfolder_by_type ? 'bg-bio-dna-500' : 'bg-gray-200 dark:bg-gray-700'
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                            storageForm.subfolder_by_type ? 'translate-x-6' : 'translate-x-1'
                          }`}
                        />
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Folder Structure Preview */}
            {folderPreview && (
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 mb-6">
                <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                  <h2 className="font-semibold text-gray-900 dark:text-white">Preview</h2>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    How your files will be organized
                  </p>
                </div>
                <div className="p-6">
                  <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 font-mono text-sm">
                    <div className="text-gray-600 dark:text-gray-400">
                      <div className="flex items-center gap-2">
                        <svg className="w-4 h-4 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
                        </svg>
                        <span className="text-gray-900 dark:text-white">outputs/</span>
                      </div>
                      {folderPreview.subfolders.map((folder, index) => (
                        <div key={index} className="ml-6 mt-2">
                          <div className="flex items-center gap-2">
                            <svg className="w-4 h-4 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
                            </svg>
                            <span>{folder.example || folder.name}</span>
                          </div>
                          {folder.categories && (
                            <div className="ml-6 mt-1 text-xs text-gray-500">
                              {folder.categories.join(' | ')}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                    <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                      <p className="text-xs text-gray-500 dark:text-gray-400">Example output path:</p>
                      <p className="text-gray-900 dark:text-white break-all text-xs">{folderPreview.example_path}</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* Save Button */}
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2 bg-gradient-to-r from-bio-dna-500 to-bio-rna-500 text-white font-medium rounded-lg hover:from-bio-dna-600 hover:to-bio-rna-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {saving ? (
              <>
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Saving...
              </>
            ) : (
              'Save Settings'
            )}
          </button>
        </div>
      </main>
    </div>
  )
}
