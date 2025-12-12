'use client'

import { useState, RefObject } from 'react'
import { ChevronUp, ChevronDown, Crop, Volume2, VolumeX, Subtitles, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface VideoPreviewProps {
  videoUrl: string | null
  isMuted: boolean
  onMuteToggle: () => void
  onRefreshVoiceover: () => void
  videoRef?: RefObject<HTMLVideoElement>
  isProcessedVideo?: boolean
}

export default function VideoPreview({
  videoUrl,
  isMuted,
  onMuteToggle,
  onRefreshVoiceover,
  videoRef,
  isProcessedVideo = false,
}: VideoPreviewProps) {
  const [aspectRatio, setAspectRatio] = useState('wide')

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
              muted={isMuted}
              className="max-w-full max-h-full"
            />
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
