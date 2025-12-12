'use client'

import { useState } from 'react'
import { Pencil, Trash2, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'

export interface VideoStep {
  id: string
  startTime: number
  endTime: number
  transcript: string
  screenshot?: string
  title?: string
}

interface StepEditorProps {
  step: VideoStep
  stepNumber: number
  onUpdate: (id: string, updates: Partial<VideoStep>) => void
  onDelete: (id: string) => void
  onRecapture: (id: string) => void
  onScreenshotClick: (timestamp: number) => void
  isCapturing?: boolean
}

export default function StepEditor({
  step,
  stepNumber,
  onUpdate,
  onDelete,
  onRecapture,
  onScreenshotClick,
  isCapturing = false,
}: StepEditorProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editedTitle, setEditedTitle] = useState(step.title || '')
  const [editedTranscript, setEditedTranscript] = useState(step.transcript)

  const handleSave = () => {
    onUpdate(step.id, {
      title: editedTitle,
      transcript: editedTranscript,
    })
    setIsEditing(false)
  }

  const handleCancel = () => {
    setEditedTitle(step.title || '')
    setEditedTranscript(step.transcript)
    setIsEditing(false)
  }

  return (
    <div className="group">
      <div className="flex gap-6">
        {/* Step Content */}
        <div className="flex-1 space-y-4">
            {/* Header with title and actions */}
            <div className="flex items-start justify-between gap-2">
              <div className="space-y-1 flex-1">
                {isEditing ? (
                  <Input
                    value={editedTitle}
                    onChange={(e) => setEditedTitle(e.target.value)}
                    placeholder="Step title (optional)"
                    className="text-xl font-medium"
                  />
                ) : (
                  <h2 className="text-2xl font-medium text-gray-900">
                    {stepNumber}. {step.title || `Step ${stepNumber}`}
                  </h2>
                )}
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                {isEditing ? (
                  <>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleCancel}
                      className="h-7 px-2"
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      onClick={handleSave}
                      className="h-7 px-2"
                    >
                      Save
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => setIsEditing(true)}
                      className="h-8 w-8"
                      title="Edit step"
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => onDelete(step.id)}
                      className="h-8 w-8 text-destructive hover:text-destructive"
                      title="Delete step"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </>
                )}
              </div>
            </div>

            {/* Screenshot */}
            <div className="relative aspect-video bg-muted rounded-md overflow-hidden border">
              {isCapturing ? (
                <div className="absolute inset-0 flex items-center justify-center">
                  <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                </div>
              ) : step.screenshot ? (
                <>
                  <img
                    src={step.screenshot}
                    alt={`Step ${stepNumber} screenshot`}
                    className="w-full h-full object-cover"
                  />
                </>
              ) : (
                <div className="absolute inset-0 flex items-center justify-center">
                  <p className="text-sm text-muted-foreground">No screenshot</p>
                </div>
              )}
            </div>

            {/* Transcript */}
            <div>
              {isEditing ? (
                <Textarea
                  value={editedTranscript}
                  onChange={(e) => setEditedTranscript(e.target.value)}
                  placeholder="Enter step description..."
                  className="min-h-[100px] resize-none text-base"
                />
              ) : (
                <p className="text-base text-gray-700 leading-relaxed">
                  {step.transcript}
                </p>
              )}
            </div>
        </div>
      </div>
    </div>
  )
}
