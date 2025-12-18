'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import EditorTopBar from '@/components/editor/EditorTopBar'
import ScriptEditor from '@/components/editor/ScriptEditor'
import VideoPreview from '@/components/editor/VideoPreview'
import VideoTimeline from '@/components/editor/VideoTimeline'
import DocumentView from '@/components/editor/DocumentView'
import { VideoStep } from '@/components/editor/StepEditor'
import { ZoomConfig } from '@/components/editor/ZoomBlock'
import { TranscriptPhrase } from '@/components/editor/TranscriptEditor'
import { Loader2 } from 'lucide-react'
import EditorLayout from '@/components/layouts/EditorLayout'
import { captureVideoFrame, captureFrameFromUrl, generateMockSteps } from '@/lib/videoUtils'
import { authenticatedFetch } from '@/lib/api'

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
  const [voiceoverUrl, setVoiceoverUrl] = useState<string | null>(null)
  const [isProcessedVideo, setIsProcessedVideo] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isProcessing, setIsProcessing] = useState(false)
  const [selectedLanguage, setSelectedLanguage] = useState('en')
  const [selectedVoice, setSelectedVoice] = useState('alloy')
  const [steps, setSteps] = useState<VideoStep[]>([])
  const [capturingStepIds, setCapturingStepIds] = useState<string[]>([])
  const [transcript, setTranscript] = useState<any>(null)
  const [zoomConfig, setZoomConfig] = useState<ZoomConfig | null>(null)
  const [isApplyingZoom, setIsApplyingZoom] = useState(false)
  const [transcriptPhrases, setTranscriptPhrases] = useState<TranscriptPhrase[]>([])
  const stepsCreatedFromTranscriptRef = useRef(false)
  const isSeekingRef = useRef(false) // Track if user is manually seeking

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

  // Removed: This effect was causing play/pause glitching because it would
  // seek the video on every timeupdate, creating a feedback loop.
  // Instead, we only seek in handleTimeChange when user explicitly changes time.

  // Generate mock steps when video duration is available (only if no transcript phrases available)
  useEffect(() => {
    const generateSteps = async () => {
      const video = videoRef.current
      if (!video || !duration || duration === 0) return
      // Don't generate mock steps if transcript phrases exist or steps already created
      if (transcriptPhrases.length > 0 || steps.length > 0 || stepsCreatedFromTranscriptRef.current) return

      // Generate mock steps based on video duration
      const mockSteps = generateMockSteps(duration)

      // Set steps without screenshots first
      setSteps(mockSteps.map(step => ({ ...step, screenshot: undefined })))

      // Capture screenshots for each step asynchronously
      for (const step of mockSteps) {
        try {
          setCapturingStepIds(prev => [...prev, step.id])
          const screenshot = await captureVideoFrame(video, step.startTime)

          setSteps(prevSteps =>
            prevSteps.map(s =>
              s.id === step.id ? { ...s, screenshot } : s
            )
          )
        } catch (error) {
          console.error(`Failed to capture screenshot for ${step.id}:`, error)
        } finally {
          setCapturingStepIds(prev => prev.filter(id => id !== step.id))
        }
      }
    }

    generateSteps()
  }, [duration, transcriptPhrases.length, steps.length])

  const resolveVideoUrl = (url: string | null) => {
    if (!url) return null
    if (url.startsWith('http')) return url
    const backendUrl =
      process.env.NEXT_PUBLIC_BACKEND_URL ||
      process.env.BACKEND_URL ||
      'http://localhost:8000'
    return `${backendUrl}${url}`
  }

  const fetchProject = async () => {
    try {
      // Check if this is a placeholder project
      if (projectId.startsWith('placeholder-')) {
        // Create mock project for placeholder
        const mockProject = {
          id: projectId,
          name: 'Sample Video',
          createdAt: new Date().toISOString(),
          thumbnailUrl: null,
          videoUrl: null,
          language: 'English',
          script: '',
        }
        setProject(mockProject)
        setVideoUrl(null)
        setScript('')

        // Add demo steps for placeholder project
        const demoSteps: VideoStep[] = [
          {
            id: 'demo-step-1',
            startTime: 0,
            endTime: 5,
            title: 'Introduction',
            transcript: 'Welcome to our video editor! This is a demo step showing how the step-by-step timeline works.',
            screenshot: 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="400" height="225"%3E%3Crect width="400" height="225" fill="%238B5CF6"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" fill="white" font-size="24" font-family="Arial"%3EStep 1%3C/text%3E%3C/svg%3E'
          },
          {
            id: 'demo-step-2',
            startTime: 5,
            endTime: 12,
            title: 'Feature Overview',
            transcript: 'Click on any screenshot to jump to that point in the video. You can also edit the title and transcript of each step.',
            screenshot: 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="400" height="225"%3E%3Crect width="400" height="225" fill="%237C3AED"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" fill="white" font-size="24" font-family="Arial"%3EStep 2%3C/text%3E%3C/svg%3E'
          },
          {
            id: 'demo-step-3',
            startTime: 12,
            endTime: 20,
            title: 'Editing Steps',
            transcript: 'Use the edit icon to modify step details. You can re-capture screenshots by clicking the refresh icon that appears when you hover over the image.',
            screenshot: 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="400" height="225"%3E%3Crect width="400" height="225" fill="%236D28D9"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" fill="white" font-size="24" font-family="Arial"%3EStep 3%3C/text%3E%3C/svg%3E'
          },
          {
            id: 'demo-step-4',
            startTime: 20,
            endTime: 28,
            title: 'Adding New Steps',
            transcript: 'Click the "Add Step" button at the top to create a new step at the current video position. This is useful for breaking down your content into digestible sections.',
            screenshot: 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="400" height="225"%3E%3Crect width="400" height="225" fill="%235B21B6"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" fill="white" font-size="24" font-family="Arial"%3EStep 4%3C/text%3E%3C/svg%3E'
          }
        ]
        setSteps(demoSteps)

        setLoading(false)
        return
      }

      // Normal project fetching logic - use authenticated fetch
      const response = await authenticatedFetch(`/api/projects/${projectId}`)
      if (response.ok) {
        const data = await response.json()
        setProject(data)
        const hasProcessedVideo = !!data.processedVideoUrl
        setVideoUrl(resolveVideoUrl(data.processedVideoUrl || data.videoUrl || null))
        setVoiceoverUrl(data.voiceoverUrl ? resolveVideoUrl(data.voiceoverUrl) : null)
        setIsProcessedVideo(hasProcessedVideo)
        setScript(data.script || '')

        // Always fetch transcript from API to get cleaned version if available
        // The transcript API returns cleaned text with original timestamps when processing is complete
        loadTranscript()

        // Load zoom config if available
        if (data.zoom_config) {
          setZoomConfig(data.zoom_config)
        } else {
          loadZoomConfig()
        }
      } else {
        // Fallback: try to get from projects list
        const projectsResponse = await authenticatedFetch('/api/projects')
        const projectsData = await projectsResponse.json()
        const foundProject = projectsData.projects?.find((p: any) => p.id === projectId)
        if (foundProject) {
          setProject(foundProject)
          const hasProcessedVideo = !!foundProject.processedVideoUrl
          setVideoUrl(resolveVideoUrl(foundProject.processedVideoUrl || foundProject.videoUrl || null))
          setIsProcessedVideo(hasProcessedVideo)
          setScript(foundProject.script || '')
          loadTranscript()
        }
      }
    } catch (error) {
      console.error('Error fetching project:', error)
    } finally {
      setLoading(false)
    }
  }

  // Group words into phrases based on pauses (matching backend logic)
  // Also handles cleaned transcript format where each "word" is actually a full segment
  const groupWordsIntoPhrases = (words: any[], pauseThreshold = 0.25): TranscriptPhrase[] => {
    if (!words || words.length === 0) return []

    // Check if this is cleaned transcript format (segments, not individual words)
    const isCleanedFormat = words.some(w => w.is_cleaned_segment)

    if (isCleanedFormat) {
      // Cleaned transcript: each entry is a full segment with improved text
      return words.map((seg, index) => ({
        id: seg.id || `phrase-${index}`,
        text: seg.word || '',  // In cleaned format, 'word' contains the full segment text
        start: seg.start || 0,
        end: seg.end || 0
      })).filter(p => p.text.trim())
    }

    // Original word-level format: group into phrases based on pauses
    const phrases: TranscriptPhrase[] = []
    let currentPhrase = {
      id: 'phrase-0',
      text: '',
      start: words[0]?.start || 0,
      end: words[0]?.end || 0,
      words: [] as string[]
    }

    for (let i = 0; i < words.length; i++) {
      const word = words[i]
      const wordText = (word.word || '').trim()
      const wordStart = word.start || 0
      const wordEnd = word.end || 0

      if (!wordText) continue

      // Check for gap from previous word
      if (i > 0 && currentPhrase.words.length > 0) {
        const gap = wordStart - currentPhrase.end
        if (gap >= pauseThreshold) {
          // Save current phrase and start new one
          currentPhrase.text = currentPhrase.words.join(' ').trim()
          if (currentPhrase.text) {
            phrases.push({ ...currentPhrase })
          }
          currentPhrase = {
            id: `phrase-${phrases.length}`,
            text: '',
            start: wordStart,
            end: wordEnd,
            words: []
          }
        }
      }

      currentPhrase.words.push(wordText)
      currentPhrase.end = wordEnd
    }

    // Don't forget last phrase
    if (currentPhrase.words.length > 0) {
      currentPhrase.text = currentPhrase.words.join(' ').trim()
      if (currentPhrase.text) {
        phrases.push({ ...currentPhrase })
      }
    }

    return phrases
  }

  const loadTranscript = async () => {
    try {
      const response = await fetch(`/api/transcripts/${projectId}`)
      if (response.ok) {
        const data = await response.json()
        if (data.transcript) {
          setTranscript(data.transcript)
          if (data.transcript.text && !script) {
            setScript(data.transcript.text)
          }

          // Load word-level timestamps and convert to phrases
          if (data.transcript.words && data.transcript.words.length > 0) {
            const words = typeof data.transcript.words === 'string'
              ? JSON.parse(data.transcript.words)
              : data.transcript.words
            const phrases = groupWordsIntoPhrases(words)
            setTranscriptPhrases(phrases)
          }
        }
      }
    } catch (error) {
      console.error('Error loading transcript:', error)
    }
  }

  const loadZoomConfig = async () => {
    try {
      const response = await fetch(`/api/zoom/${projectId}`)
      if (response.ok) {
        const data = await response.json()
        if (data.zoomConfig) {
          setZoomConfig(data.zoomConfig)
        }
      }
    } catch (error) {
      console.error('Error loading zoom config:', error)
    }
  }

  // Create steps from transcript phrases (word-level timestamps)
  useEffect(() => {
    const createStepsFromPhrases = async () => {
      if (!transcriptPhrases || transcriptPhrases.length === 0) return
      if (!duration || duration === 0) return
      if (!videoRef.current) return

      // Check if steps already created from transcript
      if (stepsCreatedFromTranscriptRef.current) return

      // Mark as created
      stepsCreatedFromTranscriptRef.current = true

      // Create steps directly from transcript phrases
      const newSteps: VideoStep[] = transcriptPhrases.map((phrase, index) => ({
        id: phrase.id || `step-${index}`,
        startTime: phrase.start,
        endTime: phrase.end,
        title: `Step ${index + 1}`,
        transcript: phrase.text,
        screenshot: undefined,
      }))

      // Set steps without screenshots first
      setSteps(newSteps)

      // Capture screenshots for each step asynchronously
      const currentVideoUrl = videoRef.current?.src
      if (!currentVideoUrl) return

      for (const step of newSteps) {
        try {
          setCapturingStepIds(prev => [...prev, step.id])
          // Capture at the start of the phrase for better context
          const captureTime = step.startTime

          // Try URL-based capture first (handles CORS better)
          let screenshot: string
          try {
            screenshot = await captureFrameFromUrl(currentVideoUrl, captureTime)
          } catch (urlError) {
            console.warn('URL capture failed, trying video ref:', urlError)
            screenshot = await captureVideoFrame(videoRef.current!, captureTime)
          }

          setSteps(prevSteps =>
            prevSteps.map(s =>
              s.id === step.id ? { ...s, screenshot } : s
            )
          )
        } catch (error) {
          console.error(`Failed to capture screenshot for ${step.id}:`, error)
        } finally {
          setCapturingStepIds(prev => prev.filter(id => id !== step.id))
        }
      }
    }

    createStepsFromPhrases()
  }, [transcriptPhrases, duration])

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
      // Step 1: Generate cleaned script from transcript
      const transcriptText = typeof transcript === 'string' ? transcript : transcript?.text || ''
      const response = await fetch('/api/generate-script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projectId, transcript: transcriptText }),
      })
      if (!response.ok) throw new Error('Failed to generate script')
      const data = await response.json()
      const newScript = data.script || ''
      setScript(newScript)

      // Step 2: Regenerate voiceover with the new script (including pause effects)
      if (newScript) {
        const voiceoverResponse = await fetch('/api/generate-voiceover', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            projectId,
            script: newScript,
            voice: selectedVoice,
            videoDuration: duration > 0 ? duration : undefined,
          }),
        })
        if (voiceoverResponse.ok) {
          const voiceoverData = await voiceoverResponse.json()
          if (voiceoverData.audioUrl) {
            // Add cache-busting to force reload
            setVoiceoverUrl(voiceoverData.audioUrl + '?t=' + Date.now())
          }
        } else {
          console.warn('Failed to regenerate voiceover')
        }
      }
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
          videoDuration: duration > 0 ? duration : undefined,
        }),
      })
      if (!response.ok) throw new Error('Failed to generate voiceover')
      const data = await response.json()
      if (data.audioUrl) {
        setVoiceoverUrl(data.audioUrl + '?t=' + Date.now())
      }
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
        setIsProcessedVideo(true)
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

  const handleRetranscribe = async () => {
    if (!projectId || projectId.startsWith('placeholder-')) return
    try {
      const response = await fetch('/api/transcripts/retranscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projectId }),
      })
      if (!response.ok) throw new Error('Failed to retranscribe')
      const data = await response.json()
      if (data.transcript) {
        setTranscript(data.transcript)
        // Load the new word-level timestamps
        if (data.transcript.words && data.transcript.words.length > 0) {
          const phrases = groupWordsIntoPhrases(data.transcript.words)
          setTranscriptPhrases(phrases)
        }
      }
    } catch (error) {
      console.error('Error retranscribing:', error)
      alert('Failed to retranscribe video')
    }
  }

  const handleGenerateAvatar = async (config: { avatarId: string; position: string; size: string }) => {
    if (!script || !projectId) {
      alert('Please generate a script first')
      return
    }
    setIsProcessing(true)
    try {
      const response = await fetch('/api/avatar/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectId,
          script,
          ...config,
        }),
      })
      if (!response.ok) throw new Error('Failed to generate avatar')
      const data = await response.json()
      alert('Avatar configuration saved! It will be included when you process the video.')
    } catch (error) {
      console.error('Error generating avatar:', error)
      alert('Failed to generate avatar')
    } finally {
      setIsProcessing(false)
    }
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

  // Step handlers
  const handleStepUpdate = useCallback((id: string, updates: Partial<VideoStep>) => {
    setSteps(prevSteps =>
      prevSteps.map(step =>
        step.id === id ? { ...step, ...updates } : step
      )
    )
  }, [])

  const handleStepDelete = useCallback((id: string) => {
    setSteps(prevSteps => prevSteps.filter(step => step.id !== id))
  }, [])

  const handleStepRecapture = useCallback(async (id: string) => {
    const video = videoRef.current
    if (!video) return

    const step = steps.find(s => s.id === id)
    if (!step) return

    try {
      setCapturingStepIds(prev => [...prev, id])
      const screenshot = await captureVideoFrame(video, step.startTime)

      setSteps(prevSteps =>
        prevSteps.map(s =>
          s.id === id ? { ...s, screenshot } : s
        )
      )
    } catch (error) {
      console.error(`Failed to recapture screenshot for ${id}:`, error)
    } finally {
      setCapturingStepIds(prev => prev.filter(stepId => stepId !== id))
    }
  }, [steps])

  const handleScreenshotClick = useCallback((timestamp: number) => {
    const video = videoRef.current
    if (video) {
      video.currentTime = timestamp
      setCurrentTime(timestamp)
      // Switch to video tab if not already there
      setActiveTab('video')
    }
  }, [])

  const handleAddStep = useCallback(async () => {
    const video = videoRef.current
    if (!video) return

    const newStepId = `step-${Date.now()}`
    const newStep: VideoStep = {
      id: newStepId,
      startTime: currentTime,
      endTime: Math.min(currentTime + 7, duration),
      transcript: 'Enter step description here...',
      title: `New Step`,
    }

    // Add step without screenshot first
    setSteps(prevSteps => [...prevSteps, newStep])

    // Capture screenshot
    try {
      setCapturingStepIds(prev => [...prev, newStepId])
      const screenshot = await captureVideoFrame(video, currentTime)

      setSteps(prevSteps =>
        prevSteps.map(s =>
          s.id === newStepId ? { ...s, screenshot } : s
        )
      )
    } catch (error) {
      console.error('Failed to capture screenshot for new step:', error)
    } finally {
      setCapturingStepIds(prev => prev.filter(id => id !== newStepId))
    }
  }, [currentTime, duration])

  const handleZoomChange = useCallback(async (zoom: ZoomConfig | null) => {
    setZoomConfig(zoom)

    // Save zoom config to backend
    if (projectId && !projectId.startsWith('placeholder-')) {
      try {
        await fetch(`/api/zoom/${projectId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ zoomConfig: zoom }),
        })
      } catch (error) {
        console.error('Failed to save zoom config:', error)
      }
    }
  }, [projectId])

  const handleApplyZoom = useCallback(async () => {
    if (!projectId || projectId.startsWith('placeholder-')) return

    setIsApplyingZoom(true)
    try {
      // Save zoom config - preview effect is applied instantly via CSS transform
      if (zoomConfig) {
        await fetch(`/api/zoom/${projectId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ zoomConfig }),
        })
      }
      // The zoom effect is now shown in real-time via CSS transform in VideoPreview
      // FFmpeg processing will happen only on final export
    } catch (error) {
      console.error('Error saving zoom config:', error)
      alert('Failed to save zoom effect')
    } finally {
      setIsApplyingZoom(false)
    }
  }, [projectId, zoomConfig])

  const handleTitleChange = useCallback(async (newTitle: string) => {
    if (!projectId || projectId.startsWith('placeholder-')) return

    try {
      const response = await authenticatedFetch(`/api/projects/${projectId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newTitle }),
      })

      if (response.ok) {
        const updatedProject = await response.json()
        setProject((prev: any) => ({ ...prev, name: newTitle }))
      } else {
        alert('Failed to update project name')
      }
    } catch (error) {
      console.error('Error updating project name:', error)
      alert('Failed to update project name')
    }
  }, [projectId])

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
      <div className="h-full flex flex-col bg-background">
        <EditorTopBar
          projectTitle={project.name || `Project ${projectId.slice(0, 8)}`}
          onExport={handleExport}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onTitleChange={handleTitleChange}
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
              onGenerateAvatar={handleGenerateAvatar}
              isProcessing={isProcessing}
              selectedLanguage={selectedLanguage}
              onLanguageChange={setSelectedLanguage}
              selectedVoice={selectedVoice}
              onVoiceChange={setSelectedVoice}
              projectId={projectId}
              transcriptPhrases={transcriptPhrases}
              onTranscriptPhrasesChange={setTranscriptPhrases}
              currentTime={currentTime}
              onSeekToTime={handleTimeChange}
              onRetranscribe={handleRetranscribe}
              hasTranscriptText={!!transcript?.text}
            />
          </div>

          {/* Center Panel - Video Preview */}
          <div className="flex-1 flex flex-col">
            <VideoPreview
              videoUrl={videoUrl}
              voiceoverUrl={voiceoverUrl}
              isMuted={isMuted}
              onMuteToggle={() => setIsMuted(!isMuted)}
              onRefreshVoiceover={handleRefreshVoiceover}
              videoRef={videoRef}
              isProcessedVideo={isProcessedVideo}
              zoomConfig={zoomConfig}
            />
          </div>
        </div>
      ) : (
        <DocumentView
          content={script || 'No document content yet. Generate a script to get started.'}
          title={project.name || `Project ${projectId.slice(0, 8)}`}
          steps={steps}
          onStepUpdate={handleStepUpdate}
          onStepDelete={handleStepDelete}
          onStepRecapture={handleStepRecapture}
          onScreenshotClick={handleScreenshotClick}
          onAddStep={handleAddStep}
          capturingStepIds={capturingStepIds}
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
          zoomConfig={zoomConfig}
          onZoomChange={handleZoomChange}
          onApplyZoom={handleApplyZoom}
          isApplyingZoom={isApplyingZoom}
        />
      )}
      </div>
    </EditorLayout>
  )
}
