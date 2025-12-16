'use client'

import { useState, useRef, useEffect } from 'react'
import { Play, Pause, Maximize, Plus, ZoomIn, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import ZoomBlock, { ZoomConfig } from './ZoomBlock'

interface VideoTimelineProps {
  duration: number // in seconds
  currentTime: number // in seconds
  onTimeChange: (time: number) => void
  onPlayPause: () => void
  isPlaying: boolean
  zoomConfig?: ZoomConfig | null
  onZoomChange?: (zoom: ZoomConfig | null) => void
  onApplyZoom?: () => void
  isApplyingZoom?: boolean
}

export default function VideoTimeline({
  duration,
  currentTime,
  onTimeChange,
  onPlayPause,
  isPlaying,
  zoomConfig,
  onZoomChange,
  onApplyZoom,
  isApplyingZoom,
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

  // Generate time markers (with validation to prevent infinite loops)
  const markers: number[] = []
  const safeDuration = Number.isFinite(duration) && duration > 0 ? duration : 0
  if (safeDuration > 0) {
    const interval = safeDuration > 15 ? 3 : 1
    for (let i = 0; i <= safeDuration; i += interval) {
      markers.push(i)
    }
  }

  // Ref for effects tracks (to sync click behavior)
  const zoomTrackRef = useRef<HTMLDivElement>(null)

  const handleEffectTrackClick = (e: React.MouseEvent<HTMLDivElement>, trackRef: React.RefObject<HTMLDivElement>) => {
    if (!trackRef.current) return
    const rect = trackRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const percentage = x / rect.width
    const newTime = percentage * duration
    onTimeChange(Math.max(0, Math.min(duration, newTime)))
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

      {/* Timeline Tracks */}
      <div className="space-y-1">
        {/* Time markers row */}
        <div className="relative h-5 ml-16">
          {markers.map((marker) => {
            const position = safeDuration > 0 ? (marker / safeDuration) * 100 : 0
            return (
              <span
                key={marker}
                className="absolute transform -translate-x-1/2 text-xs text-muted-foreground"
                style={{ left: `${position}%` }}
              >
                {marker}s
              </span>
            )
          })}
        </div>

        {/* Video Track */}
        <div className="flex items-center gap-2">
          <div className="w-14 text-xs text-muted-foreground font-medium text-right pr-2">Video</div>
          <div
            ref={timelineRef}
            className="relative flex-1 h-10 bg-muted rounded cursor-pointer"
            onClick={handleTimelineClick}
          >
            {/* Active clip segment (blue) */}
            <div
              className="absolute h-full bg-primary/30 rounded-l"
              style={{ width: `${progress}%` }}
            />

            {/* Playhead */}
            <div
              className="absolute top-0 h-full w-0.5 bg-primary z-20"
              style={{ left: `${progress}%` }}
            >
              <div className="absolute -top-1 -left-1.5 w-3 h-3 bg-primary rounded-full" />
            </div>
          </div>
        </div>

        {/* Zoom Track */}
        <div className="flex items-center gap-2">
          <div className="w-14 text-xs text-muted-foreground font-medium text-right pr-2 flex items-center justify-end gap-1">
            <ZoomIn className="w-3 h-3" />
            Zoom
          </div>
          <div
            ref={zoomTrackRef}
            className="relative flex-1 h-8 bg-blue-950/30 rounded cursor-pointer border border-blue-900/50"
            onClick={(e) => handleEffectTrackClick(e, zoomTrackRef)}
          >
            {/* Zoom block */}
            {zoomConfig && zoomConfig.enabled && onZoomChange && (
              <ZoomBlock
                zoom={zoomConfig}
                duration={safeDuration}
                onZoomChange={onZoomChange}
                onDelete={() => onZoomChange(null)}
              />
            )}

            {/* Playhead line */}
            <div
              className="absolute top-0 h-full w-0.5 bg-primary/50 z-10 pointer-events-none"
              style={{ left: `${progress}%` }}
            />
          </div>
        </div>

      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-between">
        <Button variant="outline" size="sm" className="gap-2">
          <Plus className="w-4 h-4" />
          Add Clips from Script tab
        </Button>
        <div className="flex items-center gap-2">
          {/* Add Zoom button */}
          {onZoomChange && (!zoomConfig || !zoomConfig.enabled) && (
            <Button
              variant="outline"
              size="sm"
              className="gap-2 border-blue-600 text-blue-500 hover:bg-blue-950/50"
              onClick={() => {
                const zoomDuration = Math.min(3, safeDuration - currentTime)
                onZoomChange({
                  enabled: true,
                  startTime: currentTime,
                  endTime: currentTime + zoomDuration,
                  zoomLevel: 1.5,
                  centerX: 50,
                  centerY: 50,
                })
              }}
            >
              <ZoomIn className="w-4 h-4" />
              Add Zoom
            </Button>
          )}
          {/* Apply Zoom button */}
          {zoomConfig && zoomConfig.enabled && onApplyZoom && (
            <Button
              variant="default"
              size="sm"
              className="gap-2"
              onClick={onApplyZoom}
              disabled={isApplyingZoom}
            >
              <RefreshCw className={`w-4 h-4 ${isApplyingZoom ? 'animate-spin' : ''}`} />
              {isApplyingZoom ? 'Applying...' : 'Apply Zoom'}
            </Button>
          )}
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <Maximize className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}

