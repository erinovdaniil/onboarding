'use client'

import { Share2, Download, Edit } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface DocumentViewProps {
  content: string
  title: string
}

export default function DocumentView({ content, title }: DocumentViewProps) {
  // Enhanced markdown-like rendering
  const renderContent = (text: string) => {
    if (!text.trim()) {
      return (
        <div className="text-center py-12 text-muted-foreground">
          <p>No document content yet.</p>
          <p className="text-sm mt-2">Generate a script to create document content.</p>
        </div>
      )
    }

    const lines = text.split('\n')
    const elements: JSX.Element[] = []
    let inCodeBlock = false
    let codeBlockContent: string[] = []
    let paragraphBuffer: string[] = []

    const flushParagraph = () => {
      if (paragraphBuffer.length > 0) {
        const paragraph = paragraphBuffer.join(' ')
        if (paragraph.trim()) {
          elements.push(
            <p key={`p-${elements.length}`} className="mb-4 text-foreground leading-relaxed">
              {paragraph}
            </p>
          )
        }
        paragraphBuffer = []
      }
    }

    lines.forEach((line, index) => {
      // Code blocks
      if (line.startsWith('```')) {
        if (inCodeBlock) {
          flushParagraph()
          elements.push(
            <pre key={`code-${elements.length}`} className="bg-muted p-4 rounded-lg my-4 overflow-x-auto">
              <code className="text-sm">{codeBlockContent.join('\n')}</code>
            </pre>
          )
          codeBlockContent = []
          inCodeBlock = false
        } else {
          flushParagraph()
          inCodeBlock = true
        }
        return
      }

      if (inCodeBlock) {
        codeBlockContent.push(line)
        return
      }

      // Headings
      if (line.startsWith('# ')) {
        flushParagraph()
        elements.push(
          <h1 key={`h1-${index}`} className="text-3xl font-bold mb-4 mt-8 first:mt-0">
            {line.substring(2).trim()}
          </h1>
        )
        return
      }
      if (line.startsWith('## ')) {
        flushParagraph()
        elements.push(
          <h2 key={`h2-${index}`} className="text-2xl font-semibold mb-3 mt-6">
            {line.substring(3).trim()}
          </h2>
        )
        return
      }
      if (line.startsWith('### ')) {
        flushParagraph()
        elements.push(
          <h3 key={`h3-${index}`} className="text-xl font-semibold mb-2 mt-4">
            {line.substring(4).trim()}
          </h3>
        )
        return
      }

      // Images
      if (line.startsWith('![')) {
        flushParagraph()
        const match = line.match(/!\[([^\]]*)\]\(([^)]+)\)/)
        if (match) {
          elements.push(
            <div key={`img-${index}`} className="my-6">
              <img
                src={match[2]}
                alt={match[1]}
                className="rounded-lg max-w-full border shadow-sm"
              />
            </div>
          )
        }
        return
      }

      // Lists
      if (line.match(/^[-*]\s/)) {
        flushParagraph()
        const listItem = line.substring(2).trim()
        elements.push(
          <li key={`li-${index}`} className="ml-6 mb-2 list-disc">
            {listItem}
          </li>
        )
        return
      }

      // Timestamps (for script format)
      if (line.match(/^\d+:\d+\s/)) {
        flushParagraph()
        const match = line.match(/^(\d+:\d+)\s+(.+)$/)
        if (match) {
          elements.push(
            <div key={`timestamp-${index}`} className="mb-3 py-2 border-l-2 border-primary pl-4">
              <span className="text-sm font-mono text-muted-foreground mr-3">{match[1]}</span>
              <span className="text-foreground">{match[2]}</span>
            </div>
          )
        }
        return
      }

      // Regular text
      if (line.trim()) {
        paragraphBuffer.push(line.trim())
      } else {
        flushParagraph()
      }
    })

    flushParagraph()

    return elements.length > 0 ? elements : (
      <p className="text-muted-foreground">No content to display.</p>
    )
  }

  const handleShare = () => {
    // TODO: Implement share functionality
    navigator.clipboard.writeText(window.location.href)
    alert('Link copied to clipboard!')
  }

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/plain' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${title.replace(/\s+/g, '-')}.txt`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  }

  return (
    <div className="flex-1 overflow-y-auto bg-background">
      <div className="max-w-4xl mx-auto p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8 pb-6 border-b">
          <h1 className="text-3xl font-bold">{title}</h1>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-2" onClick={handleDownload}>
              <Download className="w-4 h-4" />
              Download
            </Button>
            <Button variant="outline" size="sm" className="gap-2">
              <Edit className="w-4 h-4" />
              Edit
            </Button>
            <Button variant="default" size="sm" className="gap-2 bg-primary" onClick={handleShare}>
              <Share2 className="w-4 h-4" />
              Share
            </Button>
          </div>
        </div>

        {/* Content */}
        <div className="prose prose-slate max-w-none">
          {renderContent(content)}
        </div>
      </div>
    </div>
  )
}
