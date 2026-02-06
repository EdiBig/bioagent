import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import '../styles/globals.css'

const inter = Inter({ subsets: ['latin'] })

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
}

export const metadata: Metadata = {
  title: 'BioAgent - AI-Powered Bioinformatics',
  description: 'Advanced bioinformatics analysis with AI assistance. 72+ specialized tools for genomics, proteomics, and systems biology.',
  keywords: ['bioinformatics', 'AI', 'genomics', 'analysis', 'research', 'RNA-seq', 'variant calling'],
  authors: [{ name: 'BioAgent Team' }],
  icons: {
    icon: '/favicon.ico',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} antialiased`}>
        <div className="min-h-screen bg-gradient-to-br from-gray-50 to-white dark:from-gray-900 dark:to-gray-800">
          {children}
        </div>
      </body>
    </html>
  )
}
