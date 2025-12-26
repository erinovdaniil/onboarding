'use client'

import { useState, useEffect } from 'react'
import { Play, Clock, RefreshCw, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

export interface TranscriptPhrase {
  id: string
  start: number
  end: number
  text: string
}

interface TranscriptEditorProps {
  phrases: TranscriptPhrase[]
  onPhrasesChange: (phrases: TranscriptPhrase[]) => void
  currentTime: number
  onSeekToTime: (time: number) => void
  disabled?: boolean
  projectId?: string
  onRetranscribe?: () => Promise<void>
  hasTranscriptText?: boolean
  onTranscriptEdited?: () => void  // Called when transcript is saved after edit
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  const ms = Math.floor((seconds % 1) * 10)
  return `${mins}:${secs.toString().padStart(2, '0')}.${ms}`
}

export default function TranscriptEditor({
  phrases,
  onPhrasesChange,
  currentTime,
  onSeekToTime,
  disabled = false,
  projectId,
  onRetranscribe,
  hasTranscriptText = false,
  onTranscriptEdited,
}: TranscriptEditorProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [isRetranscribing, setIsRetranscribing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)

  // Find the currently active phrase based on video time
  const activePhrase = phrases.find(
    (p) => currentTime >= p.start && currentTime <= p.end
  )

  const handlePhraseClick = (phrase: TranscriptPhrase) => {
    onSeekToTime(phrase.start)
  }

  const handleEditStart = (phrase: TranscriptPhrase) => {
    setEditingId(phrase.id)
    setEditText(phrase.text)
  }

  const saveTranscriptToBackend = async (updatedPhrases: TranscriptPhrase[]) => {
    if (!projectId) return

    setIsSaving(true)
    try {
      const response = await fetch('/api/transcripts/update', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectId,
          segments: updatedPhrases.map(p => ({
            id: p.id,
            start: p.start,
            end: p.end,
            text: p.text,
          })),
        }),
      })

      if (response.ok) {
        setHasUnsavedChanges(false)
        onTranscriptEdited?.()
      } else {
        console.error('Failed to save transcript')
      }
    } catch (error) {
      console.error('Error saving transcript:', error)
    } finally {
      setIsSaving(false)
    }
  }

  const handleEditSave = (id: string) => {
    const updatedPhrases = phrases.map((p) =>
      p.id === id ? { ...p, text: editText } : p
    )
    onPhrasesChange(updatedPhrases)
    setEditingId(null)
    setEditText('')
    setHasUnsavedChanges(true)

    // Auto-save to backend
    saveTranscriptToBackend(updatedPhrases)
  }

  const handleEditCancel = () => {
    setEditingId(null)
    setEditText('')
  }

  const handleKeyDown = (e: React.KeyboardEvent, id: string) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleEditSave(id)
    } else if (e.key === 'Escape') {
      handleEditCancel()
    }
  }

  const handleRetranscribe = async () => {
    if (!onRetranscribe || isRetranscribing) return
    setIsRetranscribing(true)
    try {
      await onRetranscribe()
    } finally {
      setIsRetranscribing(false)
    }
  }

  if (phrases.length === 0) {
    // Show different message if we have transcript text but no word-level timestamps
    if (hasTranscriptText && onRetranscribe) {
      return (
        <div className="p-4 text-center text-muted-foreground text-sm">
          <p>Word-level timestamps not available.</p>
          <p className="mt-1 text-xs mb-3">Re-transcribe to enable timestamp editing.</p>
          <Button
            size="sm"
            variant="outline"
            onClick={handleRetranscribe}
            disabled={isRetranscribing || disabled}
            className="gap-2"
          >
            {isRetranscribing ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                Re-transcribing...
              </>
            ) : (
              <>
                <RefreshCw className="w-3 h-3" />
                Re-transcribe Video
              </>
            )}
          </Button>
        </div>
      )
    }
    return (
      <div className="p-4 text-center text-muted-foreground text-sm">
        <p>No transcript available.</p>
        <p className="mt-1 text-xs">Upload a video to generate transcript.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b bg-muted/30">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <Clock className="w-3 h-3" />
            <span>{phrases.length} phrases</span>
          </div>
          {onRetranscribe && (
            <Button
              size="sm"
              variant="ghost"
              onClick={handleRetranscribe}
              disabled={isRetranscribing || disabled}
              className="h-6 px-2 text-xs gap-1"
              title="Re-transcribe with improved AI (gpt-4o-transcribe)"
            >
              {isRetranscribing ? (
                <>
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Re-transcribing...
                </>
              ) : (
                <>
                  <RefreshCw className="w-3 h-3" />
                  Re-transcribe
                </>
              )}
            </Button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {phrases.map((phrase, index) => {
          const isActive = activePhrase?.id === phrase.id
          const isEditing = editingId === phrase.id

          return (
            <div
              key={phrase.id}
              className={cn(
                'group border-b border-border/50 transition-colors',
                isActive && 'bg-primary/10',
                !isEditing && 'hover:bg-muted/50 cursor-pointer'
              )}
            >
              {/* Timestamp header */}
              <div
                className="flex items-center gap-2 px-3 py-1.5 text-xs"
                onClick={() => !isEditing && handlePhraseClick(phrase)}
              >
                <button
                  className={cn(
                    'flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono',
                    isActive
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground hover:bg-muted/80'
                  )}
                  onClick={(e) => {
                    e.stopPropagation()
                    handlePhraseClick(phrase)
                  }}
                >
                  <Play className="w-2.5 h-2.5" />
                  {formatTime(phrase.start)}
                </button>
                <span className="text-muted-foreground">→</span>
                <span className="text-[10px] font-mono text-muted-foreground">
                  {formatTime(phrase.end)}
                </span>
              </div>

              {/* Text content */}
              <div className="px-3 pb-2">
                {isEditing ? (
                  <textarea
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    onKeyDown={(e) => handleKeyDown(e, phrase.id)}
                    onBlur={() => handleEditSave(phrase.id)}
                    className="w-full p-2 text-sm bg-background border rounded resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                    rows={2}
                    autoFocus
                    disabled={disabled}
                  />
                ) : (
                  <p
                    className={cn(
                      'text-sm leading-relaxed',
                      isActive ? 'text-foreground font-medium' : 'text-foreground/80'
                    )}
                    onDoubleClick={() => !disabled && handleEditStart(phrase)}
                  >
                    {phrase.text}
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>

      <div className="px-3 py-2 border-t bg-muted/30 text-[10px] text-muted-foreground flex items-center justify-between">
        <span>Double-click text to edit • Click timestamp to seek</span>
        {isSaving && (
          <span className="flex items-center gap-1 text-primary">
            <Loader2 className="w-3 h-3 animate-spin" />
            Saving...
          </span>
        )}
        {!isSaving && hasUnsavedChanges && (
          <span className="text-yellow-600">Unsaved changes</span>
        )}
      </div>
    </div>
  )
}
