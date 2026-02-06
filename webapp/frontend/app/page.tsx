'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import {
  BeakerIcon,
  ChatBubbleLeftRightIcon,
  DocumentDuplicateIcon,
  ChartBarIcon,
  CogIcon,
  PlusIcon,
  ClockIcon,
  ArrowRightIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'

interface DashboardStats {
  totalChats: number
  totalAnalyses: number
  completedAnalyses: number
  totalFiles: number
}

interface ActivityItem {
  id: number
  type: string
  title: string
  timestamp: string
  status: string
}

export default function HomePage() {
  const [stats, setStats] = useState<DashboardStats>({
    totalChats: 0,
    totalAnalyses: 0,
    completedAnalyses: 0,
    totalFiles: 0
  })

  const [recentActivity] = useState<ActivityItem[]>([
    {
      id: 1,
      type: 'analysis',
      title: 'RNA-seq Differential Expression',
      timestamp: '2 hours ago',
      status: 'completed'
    },
    {
      id: 2,
      type: 'chat',
      title: 'Variant calling pipeline discussion',
      timestamp: '5 hours ago',
      status: 'active'
    },
    {
      id: 3,
      type: 'file',
      title: 'sample_data.fastq uploaded',
      timestamp: '1 day ago',
      status: 'uploaded'
    }
  ])

  const quickActions = [
    {
      title: 'New Chat',
      description: 'Start analyzing your data',
      icon: ChatBubbleLeftRightIcon,
      href: '/chat',
      gradient: 'from-bio-dna-500 to-bio-rna-500'
    },
    {
      title: 'Upload Files',
      description: 'Add new datasets',
      icon: DocumentDuplicateIcon,
      href: '/files',
      gradient: 'from-bio-protein-500 to-bio-pathway-500'
    },
    {
      title: 'View Analyses',
      description: 'Check analysis results',
      icon: ChartBarIcon,
      href: '/analyses',
      gradient: 'from-bio-pathway-500 to-bio-expression-500'
    }
  ]

  const capabilities = [
    'Database queries (NCBI, Ensembl, UniProt, KEGG)',
    'Code execution (Python, R, Bash)',
    'File ingestion (34 bioinformatics formats)',
    'Publication-quality visualizations',
    'ML predictions (pathogenicity, drug response)',
    'Cloud execution (AWS, GCP, Azure, SLURM)',
  ]

  return (
    <div className="min-h-screen">
      {/* Navigation Header */}
      <nav className="border-b bg-white/80 backdrop-blur-sm dark:bg-gray-900/80 dark:border-gray-700 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-4">
              <BeakerIcon className="h-8 w-8 text-bio-dna-500" />
              <h1 className="text-xl font-bold gradient-text">
                BioAgent
              </h1>
            </div>

            <div className="flex items-center space-x-4">
              <Link href="/files">
                <Button variant="ghost" size="sm">
                  <DocumentDuplicateIcon className="h-4 w-4 mr-2" />
                  Files
                </Button>
              </Link>

              <Link href="/analyses">
                <Button variant="ghost" size="sm">
                  <ChartBarIcon className="h-4 w-4 mr-2" />
                  Analyses
                </Button>
              </Link>

              <Link href="/settings">
                <Button variant="ghost" size="sm">
                  <CogIcon className="h-4 w-4" />
                </Button>
              </Link>

              <Link href="/chat">
                <Button className="btn-primary">
                  <PlusIcon className="h-4 w-4 mr-2" />
                  New Chat
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Hero Section */}
        <div className="mb-12 text-center">
          <h2 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">
            AI-Powered Bioinformatics
          </h2>
          <p className="text-xl text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
            72+ specialized tools for genomics, proteomics, and systems biology.
            Start a conversation to analyze your data.
          </p>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          {quickActions.map((action) => {
            const IconComponent = action.icon
            return (
              <Link key={action.title} href={action.href}>
                <div className="group card hover:shadow-lg transition-all duration-200 cursor-pointer h-full">
                  <div className="flex items-center justify-between mb-4">
                    <div className={`p-3 rounded-lg bg-gradient-to-r ${action.gradient} bg-opacity-10`}>
                      <IconComponent className="h-6 w-6 text-gray-700 dark:text-gray-300" />
                    </div>
                    <ArrowRightIcon className="h-5 w-5 text-gray-400 group-hover:text-gray-600 group-hover:translate-x-1 transition-all" />
                  </div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                    {action.title}
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-300">
                    {action.description}
                  </p>
                </div>
              </Link>
            )
          })}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Capabilities */}
          <div className="lg:col-span-2">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center">
              <SparklesIcon className="h-5 w-5 mr-2 text-bio-dna-500" />
              Capabilities
            </h3>
            <div className="card">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {capabilities.map((cap, index) => (
                  <div key={index} className="flex items-start">
                    <div className="w-2 h-2 rounded-full bg-bio-dna-500 mt-2 mr-3 flex-shrink-0" />
                    <span className="text-gray-700 dark:text-gray-300">{cap}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Getting Started */}
            <div className="mt-6 bg-gradient-to-r from-bio-dna-50 to-bio-rna-50 dark:from-bio-dna-900/20 dark:to-bio-rna-900/20 p-6 rounded-xl border border-bio-dna-200 dark:border-bio-dna-700/30">
              <h4 className="font-semibold text-gray-900 dark:text-white mb-3">
                Getting Started
              </h4>
              <div className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
                <p>1. Upload your sequencing files (.fastq, .bam, .vcf)</p>
                <p>2. Start a chat to describe your analysis goals</p>
                <p>3. Let AI guide you through the bioinformatics workflow</p>
                <p>4. Review results and download processed data</p>
              </div>
            </div>
          </div>

          {/* Recent Activity */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Recent Activity
            </h3>
            <div className="space-y-3">
              {recentActivity.map((item) => (
                <div
                  key={item.id}
                  className="card p-4"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-1">
                        <div className={`w-2 h-2 rounded-full ${
                          item.status === 'completed' ? 'bg-green-500' :
                          item.status === 'active' ? 'bg-blue-500' :
                          'bg-gray-500'
                        }`} />
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                          {item.type}
                        </span>
                      </div>
                      <h4 className="font-medium text-gray-900 dark:text-white text-sm mb-1">
                        {item.title}
                      </h4>
                      <div className="flex items-center text-xs text-gray-500 dark:text-gray-400">
                        <ClockIcon className="h-3 w-3 mr-1" />
                        {item.timestamp}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Pro Tip */}
            <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-700/30">
              <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-2 text-sm">
                Pro Tip
              </h4>
              <p className="text-xs text-blue-700 dark:text-blue-300">
                Ask BioAgent to &quot;walk me through analyzing RNA-seq data&quot; for a complete guided workflow.
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 dark:border-gray-700 mt-12 py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-gray-500 dark:text-gray-400">
            BioAgent - AI-Powered Bioinformatics Platform
          </p>
        </div>
      </footer>
    </div>
  )
}
