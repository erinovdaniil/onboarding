'use client'

import { useState, useEffect, useRef, RefObject } from 'react'
import { ChevronUp, ChevronDown, Crop, Volume2, VolumeX, Subtitles, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface ZoomConfig {
  enabled: boolean
  startTime: number
  endTime: number
  zoomLevel: number
  centerX?: number
  centerY?: number
}

interface VideoPreviewProps {
  videoUrl: string | null
  voiceoverUrl?: string | null
  isMuted: boolean
  onMuteToggle: () => void
  onRefreshVoiceover: () => void
  videoRef?: RefObject<HTMLVideoElement>
  isProcessedVideo?: boolean
  zoomConfig?: ZoomConfig | null
}

export default function VideoPreview({
  videoUrl,
  voiceoverUrl,
  isMuted,
  onMuteToggle,
  onRefreshVoiceover,
  videoRef,
  isProcessedVideo = false,
  zoomConfig,
}: VideoPreviewProps) {
  const [aspectRatio, setAspectRatio] = useState('wide')
  const [currentZoom, setCurrentZoom] = useState(1)
  const [zoomOrigin, setZoomOrigin] = useState({ x: 50, y: 50 })
  const audioRef = useRef<HTMLAudioElement>(null)

  // Keep video element muted when voiceover exists (prevent native controls from unmuting)
  useEffect(() => {
    if (!videoRef?.current) return
    const video = videoRef.current

    // Only force mute if voiceover exists
    if (!voiceoverUrl) return

    // Force mute on any volume change attempt when voiceover is active
    const forceMute = () => {
      if (!video.muted) {
        video.muted = true
      }
    }

    video.addEventListener('volumechange', forceMute)
    return () => video.removeEventListener('volumechange', forceMute)
  }, [videoRef, voiceoverUrl])

  // Sync voiceover audio with video playback
  // Pause effects are now baked into the voiceover audio file itself
  useEffect(() => {
    if (!videoRef?.current || !audioRef.current || !voiceoverUrl) return

    const video = videoRef.current
    const audio = audioRef.current

    const syncAudio = () => {
      // Keep audio in sync with video
      if (!video.paused) {
        // Only sync if audio is not playing or drifted too much
        if (audio.paused) {
          audio.currentTime = video.currentTime
          audio.play().catch(() => {})
        } else if (Math.abs(video.currentTime - audio.currentTime) > 0.5) {
          audio.currentTime = video.currentTime
        }
      }
    }

    const handlePlay = () => {
      audio.currentTime = video.currentTime
      audio.play().catch(() => {})
    }

    const handlePause = () => {
      audio.pause()
    }

    const handleSeeked = () => {
      audio.currentTime = video.currentTime
    }

    video.addEventListener('play', handlePlay)
    video.addEventListener('pause', handlePause)
    video.addEventListener('seeked', handleSeeked)
    video.addEventListener('timeupdate', syncAudio)

    return () => {
      video.removeEventListener('play', handlePlay)
      video.removeEventListener('pause', handlePause)
      video.removeEventListener('seeked', handleSeeked)
      video.removeEventListener('timeupdate', syncAudio)
    }
  }, [videoRef, voiceoverUrl])

  // Apply real-time zoom effect based on video currentTime
  useEffect(() => {
    if (!videoRef?.current || !zoomConfig?.enabled) {
      setCurrentZoom(1)
      return
    }

    const video = videoRef.current
    const transitionDuration = 0.3 // seconds for smooth transition

    const updateZoom = () => {
      const time = video.currentTime
      const { startTime, endTime, zoomLevel, centerX = 50, centerY = 50 } = zoomConfig

      let zoom = 1
      if (time >= startTime && time <= endTime) {
        // Calculate zoom with smooth transitions
        const zoomInEnd = startTime + transitionDuration
        const zoomOutStart = endTime - transitionDuration

        if (time < zoomInEnd) {
          // Zooming in
          const progress = (time - startTime) / transitionDuration
          zoom = 1 + (zoomLevel - 1) * Math.min(progress, 1)
        } else if (time > zoomOutStart) {
          // Zooming out
          const progress = (time - zoomOutStart) / transitionDuration
          zoom = zoomLevel - (zoomLevel - 1) * Math.min(progress, 1)
        } else {
          // Fully zoomed
          zoom = zoomLevel
        }

        setZoomOrigin({ x: centerX, y: centerY })
      }

      setCurrentZoom(zoom)
    }

    video.addEventListener('timeupdate', updateZoom)
    video.addEventListener('seeked', updateZoom)

    return () => {
      video.removeEventListener('timeupdate', updateZoom)
      video.removeEventListener('seeked', updateZoom)
    }
  }, [videoRef, zoomConfig])

  return (
    <div className="flex-1 flex flex-col bg-card">
      {/* Controls */}
      <div className="border-b p-3 flex items-center justify-between gap-2 bg-background">
        <div className="flex items-center gap-2">
          <Select value={aspectRatio} onValueChange={setAspectRatio}>
            <SelectTrigger className="w-24 h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="wide">Wide</SelectItem>
              <SelectItem value="square">Square</SelectItem>
              <SelectItem value="vertical">Vertical</SelectItem>
            </SelectContent>
          </Select>
          
          <Button variant="ghost" size="icon" className="h-8 w-8" title="Move up">
            <ChevronUp className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8" title="Move down">
            <ChevronDown className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8" title="Crop">
            <Crop className="w-4 h-4" />
          </Button>
          <Button 
            variant="ghost" 
            size="icon" 
            className="h-8 w-8"
            onClick={onMuteToggle}
            title={isMuted ? 'Unmute' : 'Mute'}
          >
            {isMuted ? (
              <VolumeX className="w-4 h-4" />
            ) : (
              <Volume2 className="w-4 h-4" />
            )}
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8" title="Closed captions">
            <Subtitles className="w-4 h-4" />
          </Button>
        </div>
        
        <Button 
          variant="outline" 
          size="sm"
          onClick={onRefreshVoiceover}
          className="gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh voiceover
        </Button>
      </div>

      {/* Video Player */}
      <div className="flex-1 relative bg-black flex items-center justify-center overflow-hidden">
        {videoUrl ? (
          <>
            <video
              ref={videoRef}
              src={videoUrl}
              controls
              muted={!!voiceoverUrl || isMuted}
              crossOrigin="anonymous"
              className="w-full h-full object-contain"
              style={{
                transform: `scale(${currentZoom})`,
                transformOrigin: `${zoomOrigin.x}% ${zoomOrigin.y}%`,
                transition: 'transform 0.1s ease-out',
              }}
            />
            {/* Audio element for voiceover only */}
            {voiceoverUrl && (
              <audio
                ref={audioRef}
                src={voiceoverUrl}
                muted={isMuted}
                crossOrigin="anonymous"
              />
            )}
            {/* Watermark */}
            <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 text-white/50 text-xs pointer-events-none">
              Made with Trupeer.ai
            </div>
            {/* AI Avatar placeholder - only show for original video (not processed) */}
            {!isProcessedVideo && (
              <div className="absolute bottom-4 right-4 w-24 h-32 bg-white/10 rounded-lg border border-white/20 flex items-center justify-center pointer-events-none">
                <span className="text-white/50 text-xs">AI Avatar</span>
              </div>
            )}
          </>
        ) : (
          <div className="text-muted-foreground text-center p-8">
            <p className="mb-2">Video preview will appear here</p>
            <p className="text-sm">Upload or record a video to get started</p>
          </div>
        )}
      </div>
    </div>
  )
}
