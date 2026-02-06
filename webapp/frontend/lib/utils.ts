import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Merge Tailwind CSS classes with clsx
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format file size to human readable string
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes'

  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

/**
 * Format date to relative time string
 */
export function formatRelativeTime(date: string | Date): string {
  const now = new Date()
  const then = new Date(date)
  const diffMs = now.getTime() - then.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  if (diffSec < 60) return 'just now'
  if (diffMin < 60) return `${diffMin} min ago`
  if (diffHour < 24) return `${diffHour} hour${diffHour > 1 ? 's' : ''} ago`
  if (diffDay < 7) return `${diffDay} day${diffDay > 1 ? 's' : ''} ago`

  return then.toLocaleDateString()
}

/**
 * Format duration in seconds to human readable string
 */
export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
}

/**
 * Truncate string with ellipsis
 */
export function truncate(str: string, length: number): string {
  if (str.length <= length) return str
  return str.slice(0, length - 3) + '...'
}

/**
 * Generate a random ID
 */
export function generateId(): string {
  return Math.random().toString(36).substring(2, 15)
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: NodeJS.Timeout

  return function (this: any, ...args: Parameters<T>) {
    clearTimeout(timeoutId)
    timeoutId = setTimeout(() => fn.apply(this, args), delay)
  }
}

/**
 * Get file extension
 */
export function getFileExtension(filename: string): string {
  const parts = filename.split('.')
  return parts.length > 1 ? parts.pop()!.toLowerCase() : ''
}

/**
 * Get file type category
 */
export function getFileTypeCategory(filename: string): string {
  const ext = getFileExtension(filename)

  const categories: Record<string, string[]> = {
    sequence: ['fastq', 'fq', 'fasta', 'fa', 'fna', 'ffn', 'faa'],
    alignment: ['bam', 'sam', 'cram'],
    variant: ['vcf', 'bcf', 'gvcf'],
    annotation: ['bed', 'gff', 'gff3', 'gtf'],
    singlecell: ['h5ad', 'h5', 'hdf5', 'mtx', 'loom'],
    structure: ['pdb', 'cif', 'mmcif'],
    tabular: ['csv', 'tsv', 'txt', 'xlsx', 'xls'],
    compressed: ['gz', 'zip', 'tar', 'bz2'],
  }

  for (const [category, extensions] of Object.entries(categories)) {
    if (extensions.includes(ext)) return category
  }

  return 'other'
}

/**
 * Get color for file type
 */
export function getFileTypeColor(filename: string): string {
  const category = getFileTypeCategory(filename)

  const colors: Record<string, string> = {
    sequence: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    alignment: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    variant: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
    annotation: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    singlecell: 'bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-400',
    structure: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-400',
    tabular: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-400',
    compressed: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
    other: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-400',
  }

  return colors[category] || colors.other
}

/**
 * Parse SSE stream
 */
export async function* parseSSEStream(
  stream: ReadableStream
): AsyncGenerator<{ event: string; data: any }> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()

  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()

      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      let currentEvent = ''
      let currentData = ''

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7)
        } else if (line.startsWith('data: ')) {
          currentData = line.slice(6)
          if (currentEvent && currentData) {
            try {
              yield { event: currentEvent, data: JSON.parse(currentData) }
            } catch {
              yield { event: currentEvent, data: currentData }
            }
            currentEvent = ''
            currentData = ''
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/**
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

/**
 * Download blob as file
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
