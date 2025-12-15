'use client'

import { useState, useRef, useEffect } from 'react'
import { ZoomIn, X, GripVertical } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export interface ZoomConfig {
  enabled: boolean
  startTime: number  // seconds
  endTime: number    // seconds
  zoomLevel: number  // 1.0 - 3.0
  centerX?: number   // 0-100 percentage (optional, auto-detect if not set)
  centerY?: number   // 0-100 percentage
}

interface ZoomBlockProps {
  zoom: ZoomConfig
  duration: number
  onZoomChange: (zoom: ZoomConfig) => void
  onDelete: () => void
}

export default function ZoomBlock({
  zoom,
  duration,
  onZoomChange,
  onDelete,
}: ZoomBlockProps) {
  const blockRef = useRef<HTMLDivElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isResizingLeft, setIsResizingLeft] = useState(false)
  const [isResizingRight, setIsResizingRight] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const dragStartX = useRef(0)
  const dragStartTime = useRef(0)

  const safeDuration = duration > 0 ? duration : 1
  const leftPercent = (zoom.startTime / safeDuration) * 100
  const widthPercent = ((zoom.endTime - zoom.startTime) / safeDuration) * 100

  const handleMouseDown = (e: React.MouseEvent, type: 'drag' | 'left' | 'right') => {
    e.preventDefault()
    e.stopPropagation()
    dragStartX.current = e.clientX
    dragStartTime.current = type === 'left' ? zoom.startTime : type === 'right' ? zoom.endTime : zoom.startTime

    if (type === 'drag') setIsDragging(true)
    else if (type === 'left') setIsResizingLeft(true)
    else if (type === 'right') setIsResizingRight(true)
  }

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging && !isResizingLeft && !isResizingRight) return
      if (!blockRef.current?.parentElement) return

      const parent = blockRef.current.parentElement
      const rect = parent.getBoundingClientRect()
      const deltaX = e.clientX - dragStartX.current
      const deltaTime = (deltaX / rect.width) * safeDuration

      if (isDragging) {
        // Move the entire block
        const zoomDuration = zoom.endTime - zoom.startTime
        let newStart = dragStartTime.current + deltaTime
        newStart = Math.max(0, Math.min(safeDuration - zoomDuration, newStart))
        onZoomChange({
          ...zoom,
          startTime: newStart,
          endTime: newStart + zoomDuration,
        })
      } else if (isResizingLeft) {
        // Resize from left edge
        let newStart = dragStartTime.current + deltaTime
        newStart = Math.max(0, Math.min(zoom.endTime - 0.5, newStart)) // Min 0.5s duration
        onZoomChange({ ...zoom, startTime: newStart })
      } else if (isResizingRight) {
        // Resize from right edge
        let newEnd = dragStartTime.current + deltaTime
        newEnd = Math.max(zoom.startTime + 0.5, Math.min(safeDuration, newEnd)) // Min 0.5s duration
        onZoomChange({ ...zoom, endTime: newEnd })
      }
    }

    const handleMouseUp = () => {
      setIsDragging(false)
      setIsResizingLeft(false)
      setIsResizingRight(false)
    }

    if (isDragging || isResizingLeft || isResizingRight) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, isResizingLeft, isResizingRight, zoom, safeDuration, onZoomChange])

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <>
      {/* Zoom block on timeline */}
      <div
        ref={blockRef}
        className="absolute top-1 bottom-1 bg-blue-500/80 rounded cursor-move group hover:bg-blue-500 transition-colors"
        style={{
          left: `${leftPercent}%`,
          width: `${widthPercent}%`,
          minWidth: '40px',
        }}
        onMouseDown={(e) => handleMouseDown(e, 'drag')}
        onClick={(e) => {
          e.stopPropagation()
          setShowSettings(!showSettings)
        }}
      >
        {/* Left resize handle */}
        <div
          className="absolute left-0 top-0 bottom-0 w-2 cursor-ew-resize hover:bg-blue-300/50 rounded-l"
          onMouseDown={(e) => handleMouseDown(e, 'left')}
        />

        {/* Content */}
        <div className="flex items-center justify-center h-full px-2 text-white text-xs font-medium select-none overflow-hidden">
          <ZoomIn className="w-3 h-3 mr-1 flex-shrink-0" />
          <span className="truncate">{zoom.zoomLevel}x</span>
        </div>

        {/* Right resize handle */}
        <div
          className="absolute right-0 top-0 bottom-0 w-2 cursor-ew-resize hover:bg-blue-300/50 rounded-r"
          onMouseDown={(e) => handleMouseDown(e, 'right')}
        />

        {/* Delete button (visible on hover) */}
        <button
          className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 rounded-full opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
          onClick={(e) => {
            e.stopPropagation()
            onDelete()
          }}
        >
          <X className="w-3 h-3 text-white" />
        </button>
      </div>

      {/* Settings popover */}
      {showSettings && (
        <div
          className="absolute z-50 bg-popover border rounded-lg shadow-lg p-3 space-y-3"
          style={{
            left: `${leftPercent}%`,
            bottom: '100%',
            marginBottom: '8px',
            minWidth: '200px',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Zoom Settings</span>
            <button
              className="text-muted-foreground hover:text-foreground"
              onClick={() => setShowSettings(false)}
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="space-y-2">
            <label className="text-xs text-muted-foreground">Zoom Level</label>
            <Select
              value={zoom.zoomLevel.toString()}
              onValueChange={(value) =>
                onZoomChange({ ...zoom, zoomLevel: parseFloat(value) })
              }
            >
              <SelectTrigger className="h-8">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1.25">1.25x</SelectItem>
                <SelectItem value="1.5">1.5x</SelectItem>
                <SelectItem value="1.75">1.75x</SelectItem>
                <SelectItem value="2">2x</SelectItem>
                <SelectItem value="2.5">2.5x</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Zoom Position Selector */}
          <div className="space-y-2">
            <label className="text-xs text-muted-foreground">Zoom Position</label>
            <div className="grid grid-cols-3 gap-1 w-24 mx-auto">
              {[
                { x: 0, y: 0, label: 'TL' },
                { x: 50, y: 0, label: 'TC' },
                { x: 100, y: 0, label: 'TR' },
                { x: 0, y: 50, label: 'ML' },
                { x: 50, y: 50, label: 'C' },
                { x: 100, y: 50, label: 'MR' },
                { x: 0, y: 100, label: 'BL' },
                { x: 50, y: 100, label: 'BC' },
                { x: 100, y: 100, label: 'BR' },
              ].map((pos) => {
                const isSelected =
                  (zoom.centerX ?? 50) === pos.x && (zoom.centerY ?? 50) === pos.y
                return (
                  <button
                    key={pos.label}
                    className={`w-7 h-7 rounded text-[10px] font-medium transition-colors ${
                      isSelected
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted hover:bg-muted/80 text-muted-foreground'
                    }`}
                    onClick={() =>
                      onZoomChange({ ...zoom, centerX: pos.x, centerY: pos.y })
                    }
                  >
                    {pos.label}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="text-xs text-muted-foreground">
            {formatTime(zoom.startTime)} - {formatTime(zoom.endTime)}
            <span className="ml-2">
              ({(zoom.endTime - zoom.startTime).toFixed(1)}s)
            </span>
          </div>
        </div>
      )}
    </>
  )
}
