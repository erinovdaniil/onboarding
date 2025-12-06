'use client'

import { useState, useEffect, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import EditorTopBar from '@/components/editor/EditorTopBar'
import ScriptEditor from '@/components/editor/ScriptEditor'
import VideoPreview from '@/components/editor/VideoPreview'
import VideoTimeline from '@/components/editor/VideoTimeline'
import DocumentView from '@/components/editor/DocumentView'
import { Loader2 } from 'lucide-react'
import EditorLayout from '@/components/layouts/EditorLayout'

export default function EditorPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.projectId as string
  const videoRef = useRef<HTMLVideoElement>(null)

  const [project, setProject] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'video' | 'document'>('video')
  const [script, setScript] = useState('')
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [isMuted, setIsMuted] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isProcessing, setIsProcessing] = useState(false)
  const [selectedLanguage, setSelectedLanguage] = useState('en')
  const [selectedVoice, setSelectedVoice] = useState('alloy')

  useEffect(() => {
    fetchProject()
  }, [projectId])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const updateTime = () => setCurrentTime(video.currentTime)
    const updateDuration = () => setDuration(video.duration)
    const handlePlay = () => setIsPlaying(true)
    const handlePause = () => setIsPlaying(false)

    video.addEventListener('timeupdate', updateTime)
    video.addEventListener('loadedmetadata', updateDuration)
    video.addEventListener('play', handlePlay)
    video.addEventListener('pause', handlePause)

    return () => {
      video.removeEventListener('timeupdate', updateTime)
      video.removeEventListener('loadedmetadata', updateDuration)
      video.removeEventListener('play', handlePlay)
      video.removeEventListener('pause', handlePause)
    }
  }, [videoUrl])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    video.currentTime = currentTime
  }, [currentTime])

  const fetchProject = async () => {
    try {
      const response = await fetch(`/api/projects/${projectId}`)
      if (response.ok) {
        const data = await response.json()
        setProject(data)
        setVideoUrl(data.videoUrl || null)
        setScript(data.script || '')
      } else {
        // Fallback: try to get from projects list
        const projectsResponse = await fetch('/api/projects')
        const projectsData = await projectsResponse.json()
        const foundProject = projectsData.projects?.find((p: any) => p.id === projectId)
        if (foundProject) {
          setProject(foundProject)
          setVideoUrl(foundProject.videoUrl || null)
          setScript(foundProject.script || '')
        }
      }
    } catch (error) {
      console.error('Error fetching project:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async () => {
    if (!projectId) return
    setIsProcessing(true)
    try {
      const response = await fetch(`/api/export/${projectId}`)
      if (!response.ok) throw new Error('Export failed')
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `video-${projectId}.mp4`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Error exporting video:', error)
      alert('Failed to export video')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleGenerateScript = async () => {
    if (!projectId) {
      alert('Project ID is missing')
      return
    }
    setIsProcessing(true)
    try {
      const response = await fetch('/api/generate-script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projectId }),
      })
      if (!response.ok) throw new Error('Failed to generate script')
      const data = await response.json()
      setScript(data.script || '')
    } catch (error) {
      console.error('Error generating script:', error)
      alert('Failed to generate script')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleTranslateScript = async () => {
    if (!script) {
      alert('Please generate a script first')
      return
    }
    setIsProcessing(true)
    try {
      const response = await fetch('/api/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: script, targetLanguage: selectedLanguage }),
      })
      if (!response.ok) throw new Error('Failed to translate')
      const data = await response.json()
      setScript(data.translatedText || script)
    } catch (error) {
      console.error('Error translating script:', error)
      alert('Failed to translate script')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleGenerateVoiceover = async () => {
    if (!script || !projectId) {
      alert('Please generate a script first')
      return
    }
    setIsProcessing(true)
    try {
      const response = await fetch('/api/generate-voiceover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectId,
          script,
          voice: selectedVoice,
        }),
      })
      if (!response.ok) throw new Error('Failed to generate voiceover')
      alert('Voiceover generated successfully!')
    } catch (error) {
      console.error('Error generating voiceover:', error)
      alert('Failed to generate voiceover')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleProcessVideo = async () => {
    if (!projectId) {
      alert('Project ID is missing')
      return
    }
    setIsProcessing(true)
    try {
      const response = await fetch('/api/process-video', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectId,
          script,
          voice: selectedVoice,
          language: selectedLanguage,
          brandSettings: {
            primaryColor: '#8B5CF6',
            secondaryColor: '#7C3AED',
          },
        }),
      })
      if (!response.ok) throw new Error('Failed to process video')
      const data = await response.json()
      if (data.processedVideoUrl) {
        setVideoUrl(data.processedVideoUrl)
      }
      alert('Video processed successfully!')
    } catch (error) {
      console.error('Error processing video:', error)
      alert('Failed to process video')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleRefreshVoiceover = () => {
    handleGenerateVoiceover()
  }

  const handlePlayPause = () => {
    const video = videoRef.current
    if (!video) return
    if (isPlaying) {
      video.pause()
    } else {
      video.play()
    }
  }

  const handleTimeChange = (time: number) => {
    setCurrentTime(time)
    const video = videoRef.current
    if (video) {
      video.currentTime = time
    }
  }

  const handleAddChapter = () => {
    const time = formatTime(currentTime)
    setScript(prev => `${prev}\n${time} [Chapter]\n`)
  }

  const handleAddClip = () => {
    const time = formatTime(currentTime)
    setScript(prev => `${prev}\n${time} [Clip]\n`)
  }

  const handleAddPause = () => {
    const time = formatTime(currentTime)
    setScript(prev => `${prev}\n${time} [Pause]\n`)
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="flex items-center gap-2">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading project...</p>
        </div>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <p className="text-muted-foreground mb-4">Project not found</p>
          <button
            onClick={() => router.push('/library')}
            className="text-primary hover:underline"
          >
            Go back to Library
          </button>
        </div>
      </div>
    )
  }

  return (
    <EditorLayout>
      <div className="h-screen flex flex-col bg-background">
        <EditorTopBar
          projectTitle={project.name || `Project ${projectId.slice(0, 8)}`}
          onExport={handleExport}
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />

      {activeTab === 'video' ? (
        <div className="flex-1 flex overflow-hidden">
          {/* Left Panel - Script Editor */}
          <div className="w-80 flex-shrink-0">
            <ScriptEditor
              script={script}
              onScriptChange={setScript}
              onAddChapter={handleAddChapter}
              onAddClip={handleAddClip}
              onAddPause={handleAddPause}
              onGenerateScript={handleGenerateScript}
              onTranslate={handleTranslateScript}
              onGenerateVoiceover={handleGenerateVoiceover}
              onProcessVideo={handleProcessVideo}
              isProcessing={isProcessing}
              selectedLanguage={selectedLanguage}
              onLanguageChange={setSelectedLanguage}
              selectedVoice={selectedVoice}
              onVoiceChange={setSelectedVoice}
            />
          </div>

          {/* Center Panel - Video Preview */}
          <div className="flex-1 flex flex-col">
            <VideoPreview
              videoUrl={videoUrl}
              isMuted={isMuted}
              onMuteToggle={() => setIsMuted(!isMuted)}
              onRefreshVoiceover={handleRefreshVoiceover}
              videoRef={videoRef}
            />
          </div>
        </div>
      ) : (
        <DocumentView
          content={script || 'No document content yet. Generate a script to get started.'}
          title={project.name || `Project ${projectId.slice(0, 8)}`}
        />
      )}

      {/* Bottom Panel - Timeline (only for video tab) */}
      {activeTab === 'video' && (
        <VideoTimeline
          duration={duration || 15}
          currentTime={currentTime}
          onTimeChange={handleTimeChange}
          onPlayPause={handlePlayPause}
          isPlaying={isPlaying}
        />
      )}
      </div>
    </EditorLayout>
  )
}
