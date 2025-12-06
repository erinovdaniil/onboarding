'use client'

import { useState, useRef, useCallback } from 'react'
import { Play, Square, Download, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'

interface ScreenRecorderProps {
  onRecordingComplete: (project: any) => void
}

export default function ScreenRecorder({ onRecordingComplete }: ScreenRecorderProps) {
  const [isRecording, setIsRecording] = useState(false)
  const [recordedChunks, setRecordedChunks] = useState<Blob[]>([])
  const [recordingTime, setRecordingTime] = useState(0)
  const [isUploading, setIsUploading] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const timerRef = useRef<NodeJS.Timeout | null>(null)

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop()
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
      }
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
      setIsRecording(false)
    }
  }, [])

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        } as MediaTrackConstraints,
        audio: true,
      })

      streamRef.current = stream
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'video/webm;codecs=vp9',
      })

      const chunks: Blob[] = []
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data)
        }
      }

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunks, { type: 'video/webm' })
        setRecordedChunks([blob])
        stream.getTracks().forEach(track => track.stop())
      }

      mediaRecorderRef.current = mediaRecorder
      mediaRecorder.start(1000)
      setIsRecording(true)
      setRecordingTime(0)

      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1)
      }, 1000)

      stream.getVideoTracks()[0].addEventListener('ended', () => {
        stopRecording()
      })
    } catch (error) {
      console.error('Error starting recording:', error)
      alert('Failed to start recording. Please grant screen sharing permissions.')
    }
  }, [stopRecording])

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  const handleUpload = async () => {
    if (recordedChunks.length === 0) {
      console.error('Upload failed: No recorded chunks available')
      alert('No recording available to upload')
      return
    }

    const blob = recordedChunks[0]
    console.log('Starting upload process:', {
      blobSize: blob.size,
      blobType: blob.type,
      recordingDuration: recordingTime
    })

    if (blob.size === 0) {
      console.error('Upload failed: Blob is empty')
      alert('Recording is empty. Please try recording again.')
      return
    }

    setIsUploading(true)
    const formData = new FormData()
    formData.append('video', blob, 'recording.webm')

    try {
      console.log('Sending upload request to /api/upload')
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      })

      console.log('Upload response status:', response.status, response.statusText)

      if (!response.ok) {
        const errorText = await response.text()
        console.error('Upload failed with status:', response.status, errorText)
        throw new Error(`Upload failed: ${response.status} ${response.statusText}`)
      }

      const project = await response.json()
      console.log('Upload successful, received project:', project)

      onRecordingComplete(project)
    } catch (error) {
      console.error('Error uploading video:', error)
      alert(`Failed to upload video: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <CardTitle className="text-2xl mb-2">Screen Recording</CardTitle>
        <CardDescription>
          Record your screen to create professional videos with AI-powered enhancements
        </CardDescription>
      </div>

      <Card className="border-2 border-dashed">
        <CardContent className="p-12">
          {!isRecording && recordedChunks.length === 0 && (
            <div className="space-y-4 text-center">
              <div className="mx-auto w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center">
                <Play className="w-8 h-8 text-primary" />
              </div>
              <div>
                <h3 className="text-lg font-semibold mb-2">Ready to Record</h3>
                <p className="text-muted-foreground mb-4">
                  Click the button below to start recording your screen
                </p>
                <Button
                  onClick={startRecording}
                  size="lg"
                  className="gap-2"
                >
                  <Play className="w-5 h-5" />
                  Start Recording
                </Button>
              </div>
            </div>
          )}

          {isRecording && (
            <div className="space-y-4 text-center">
              <div className="mx-auto w-16 h-16 bg-destructive/10 rounded-full flex items-center justify-center animate-pulse">
                <div className="w-8 h-8 bg-destructive rounded-full" />
              </div>
              <div>
                <h3 className="text-lg font-semibold mb-2">Recording in Progress</h3>
                <Badge variant="destructive" className="text-2xl font-mono mb-4 px-4 py-2">
                  {formatTime(recordingTime)}
                </Badge>
                <div>
                  <Button
                    onClick={stopRecording}
                    variant="destructive"
                    size="lg"
                    className="gap-2"
                  >
                    <Square className="w-5 h-5" />
                    Stop Recording
                  </Button>
                </div>
              </div>
            </div>
          )}

          {!isRecording && recordedChunks.length > 0 && (
            <div className="space-y-4 text-center">
              <div className="mx-auto w-16 h-16 bg-green-500/10 rounded-full flex items-center justify-center">
                {isUploading ? (
                  <Loader2 className="w-8 h-8 text-green-600 animate-spin" />
                ) : (
                  <Download className="w-8 h-8 text-green-600" />
                )}
              </div>
              <div>
                <h3 className="text-lg font-semibold mb-2">
                  {isUploading ? 'Uploading...' : 'Recording Complete'}
                </h3>
                <p className="text-muted-foreground mb-4">
                  Duration: <Badge variant="secondary">{formatTime(recordingTime)}</Badge>
                </p>
                <div className="flex gap-4 justify-center">
                  <Button
                    onClick={handleUpload}
                    size="lg"
                    className="gap-2"
                    disabled={isUploading}
                  >
                    {isUploading ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        Uploading...
                      </>
                    ) : (
                      <>
                        <Download className="w-5 h-5" />
                        Process Video
                      </>
                    )}
                  </Button>
                  <Button
                    onClick={() => {
                      setRecordedChunks([])
                      setRecordingTime(0)
                    }}
                    variant="outline"
                    size="lg"
                    disabled={isUploading}
                  >
                    Record Again
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Alert>
        <AlertDescription>
          <strong>Tip:</strong> Make sure to grant screen sharing permissions when prompted. 
          You can record your entire screen, a specific window, or a browser tab.
        </AlertDescription>
      </Alert>
    </div>
  )
}
