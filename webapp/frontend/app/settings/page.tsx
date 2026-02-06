'use client'

import { useState } from 'react'
import Link from 'next/link'

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    darkMode: false,
    notifications: true,
    streamingEnabled: true,
    defaultModel: 'claude-3-opus',
    maxTokens: 4096,
    temperature: 0.7,
  })

  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    // In a real app, this would save to backend/localStorage
    localStorage.setItem('bioagent-settings', JSON.stringify(settings))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
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
        {/* Success message */}
        {saved && (
          <div className="mb-6 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-green-700 dark:text-green-300">
            Settings saved successfully!
          </div>
        )}

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
                onClick={() => setSettings(s => ({ ...s, darkMode: !s.darkMode }))}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  settings.darkMode ? 'bg-bio-dna-500' : 'bg-gray-200 dark:bg-gray-700'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    settings.darkMode ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </div>
        </div>

        {/* Notifications */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 mb-6">
          <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="font-semibold text-gray-900 dark:text-white">Notifications</h2>
          </div>
          <div className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900 dark:text-white">Enable Notifications</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">Get notified when analyses complete</p>
              </div>
              <button
                onClick={() => setSettings(s => ({ ...s, notifications: !s.notifications }))}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  settings.notifications ? 'bg-bio-dna-500' : 'bg-gray-200 dark:bg-gray-700'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    settings.notifications ? 'translate-x-6' : 'translate-x-1'
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
                onClick={() => setSettings(s => ({ ...s, streamingEnabled: !s.streamingEnabled }))}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  settings.streamingEnabled ? 'bg-bio-dna-500' : 'bg-gray-200 dark:bg-gray-700'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    settings.streamingEnabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            <div>
              <label className="block font-medium text-gray-900 dark:text-white mb-2">
                Default Model
              </label>
              <select
                value={settings.defaultModel}
                onChange={(e) => setSettings(s => ({ ...s, defaultModel: e.target.value }))}
                className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-bio-dna-500"
              >
                <option value="claude-3-opus">Claude 3 Opus (Most capable)</option>
                <option value="claude-3-sonnet">Claude 3 Sonnet (Balanced)</option>
                <option value="claude-3-haiku">Claude 3 Haiku (Fast)</option>
              </select>
            </div>

            <div>
              <label className="block font-medium text-gray-900 dark:text-white mb-2">
                Max Tokens: {settings.maxTokens}
              </label>
              <input
                type="range"
                min="1024"
                max="8192"
                step="1024"
                value={settings.maxTokens}
                onChange={(e) => setSettings(s => ({ ...s, maxTokens: parseInt(e.target.value) }))}
                className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>1024</span>
                <span>8192</span>
              </div>
            </div>

            <div>
              <label className="block font-medium text-gray-900 dark:text-white mb-2">
                Temperature: {settings.temperature}
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={settings.temperature}
                onChange={(e) => setSettings(s => ({ ...s, temperature: parseFloat(e.target.value) }))}
                className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>0 (Precise)</span>
                <span>1 (Creative)</span>
              </div>
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

        {/* Save Button */}
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            className="px-6 py-2 bg-gradient-to-r from-bio-dna-500 to-bio-rna-500 text-white font-medium rounded-lg hover:from-bio-dna-600 hover:to-bio-rna-600 transition-all"
          >
            Save Settings
          </button>
        </div>
      </main>
    </div>
  )
}
