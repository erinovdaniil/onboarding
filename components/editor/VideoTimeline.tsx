'use client'

import { useState, useRef, useEffect } from 'react'
import { Play, Pause, Maximize, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface VideoTimelineProps {
  duration: number // in seconds
  currentTime: number // in seconds
  onTimeChange: (time: number) => void
  onPlayPause: () => void
  isPlaying: boolean
}

export default function VideoTimeline({
  duration,
  currentTime,
  onTimeChange,
  onPlayPause,
  isPlaying,
}: VideoTimelineProps) {
  const [isDragging, setIsDragging] = useState(false)
  const timelineRef = useRef<HTMLDivElement>(null)

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!timelineRef.current) return
    const rect = timelineRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const percentage = x / rect.width
    const newTime = percentage * duration
    onTimeChange(Math.max(0, Math.min(duration, newTime)))
  }

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0

  // Generate time markers
  const markers = []
  const interval = duration > 15 ? 3 : 1
  for (let i = 0; i <= duration; i += interval) {
    markers.push(i)
  }

  return (
    <div className="border-t bg-card p-4 space-y-3">
      {/* Playback Controls */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={onPlayPause}
          className="h-8 w-8"
        >
          {isPlaying ? (
            <Pause className="w-4 h-4" />
          ) : (
            <Play className="w-4 h-4" />
          )}
        </Button>
        <span className="text-sm font-mono text-muted-foreground">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>
      </div>

      {/* Timeline Slider */}
      <div className="space-y-2">
        <div
          ref={timelineRef}
          className="relative h-12 bg-muted rounded cursor-pointer"
          onClick={handleTimelineClick}
        >
          {/* Time markers */}
          <div className="absolute inset-0 flex items-center">
            {markers.map((marker) => {
              const position = (marker / duration) * 100
              return (
                <div
                  key={marker}
                  className="absolute h-full border-l border-muted-foreground/30"
                  style={{ left: `${position}%` }}
                >
                  <span className="absolute -top-5 left-0 transform -translate-x-1/2 text-xs text-muted-foreground">
                    {marker}s
                  </span>
                </div>
              )
            })}
          </div>

          {/* Active clip segment (blue) */}
          <div
            className="absolute h-full bg-primary rounded-l"
            style={{ width: `${progress}%` }}
          />

          {/* Playhead */}
          <div
            className="absolute top-0 h-full w-0.5 bg-primary z-10"
            style={{ left: `${progress}%` }}
          >
            <div className="absolute -top-1 -left-1.5 w-3 h-3 bg-primary rounded-full" />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <Button variant="outline" size="sm" className="gap-2">
            <Plus className="w-4 h-4" />
            Add Clips from Script tab
          </Button>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <Maximize className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <Plus className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

