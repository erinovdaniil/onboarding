'use client'

import { useState, useEffect } from 'react'
import { Play, Pause, Download, Settings, Languages, Mic, Sparkles, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'

interface VideoEditorProps {
  project: any
}

export default function VideoEditor({ project }: VideoEditorProps) {
  const [isProcessing, setIsProcessing] = useState(false)
  const [script, setScript] = useState('')
  const [generatedScript, setGeneratedScript] = useState('')
  const [selectedLanguage, setSelectedLanguage] = useState('en')
  const [selectedVoice, setSelectedVoice] = useState('alloy')
  const [brandSettings, setBrandSettings] = useState({
    logo: '',
    primaryColor: '#0ea5e9',
    secondaryColor: '#0284c7',
  })
  const [videoUrl, setVideoUrl] = useState<string | null>(null)

  const languages = [
    { code: 'en', name: 'English' },
    { code: 'es', name: 'Spanish' },
    { code: 'fr', name: 'French' },
    { code: 'de', name: 'German' },
    { code: 'it', name: 'Italian' },
    { code: 'pt', name: 'Portuguese' },
    { code: 'ja', name: 'Japanese' },
    { code: 'ko', name: 'Korean' },
    { code: 'zh', name: 'Chinese' },
  ]

  const voices = [
    { id: 'alloy', name: 'Alloy' },
    { id: 'echo', name: 'Echo' },
    { id: 'fable', name: 'Fable' },
    { id: 'onyx', name: 'Onyx' },
    { id: 'nova', name: 'Nova' },
    { id: 'shimmer', name: 'Shimmer' },
  ]

  useEffect(() => {
    if (project?.videoUrl) {
      setVideoUrl(project.videoUrl)
    }
  }, [project])

  const generateScript = async () => {
    if (!project?.id) {
      alert('Please upload a video first')
      return
    }

    setIsProcessing(true)
    try {
      const response = await fetch('/api/generate-script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projectId: project.id }),
      })

      const data = await response.json()
      setGeneratedScript(data.script)
      setScript(data.script)
    } catch (error) {
      console.error('Error generating script:', error)
      alert('Failed to generate script')
    } finally {
      setIsProcessing(false)
    }
  }

  const translateScript = async () => {
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

      const data = await response.json()
      setScript(data.translatedText)
    } catch (error) {
      console.error('Error translating script:', error)
      alert('Failed to translate script')
    } finally {
      setIsProcessing(false)
    }
  }

  const generateVoiceover = async () => {
    if (!script) {
      alert('Please generate a script first')
      return
    }

    setIsProcessing(true)
    try {
      const response = await fetch('/api/generate-voiceover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectId: project.id,
          script,
          voice: selectedVoice,
        }),
      })

      const data = await response.json()
      alert('Voiceover generated successfully!')
    } catch (error) {
      console.error('Error generating voiceover:', error)
      alert('Failed to generate voiceover')
    } finally {
      setIsProcessing(false)
    }
  }

  const processVideo = async () => {
    if (!project?.id) {
      alert('Please upload a video first')
      return
    }

    setIsProcessing(true)
    try {
      const response = await fetch('/api/process-video', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectId: project.id,
          script,
          voice: selectedVoice,
          language: selectedLanguage,
          brandSettings,
        }),
      })

      const data = await response.json()
      setVideoUrl(data.processedVideoUrl)
      alert('Video processed successfully!')
    } catch (error) {
      console.error('Error processing video:', error)
      alert('Failed to process video')
    } finally {
      setIsProcessing(false)
    }
  }

  const exportVideo = async () => {
    if (!videoUrl) {
      alert('No video to export')
      return
    }

    try {
      const response = await fetch(`/api/export/${project.id}`)
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `video-${project.id}.mp4`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Error exporting video:', error)
      alert('Failed to export video')
    }
  }

  if (!project) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">No project selected. Please record a video first.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <CardTitle className="text-2xl mb-2">Video Editor</CardTitle>
        <CardDescription>
          Enhance your video with AI-generated scripts, voiceovers, and effects
        </CardDescription>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Video Preview */}
        <Card>
          <CardHeader>
            <CardTitle>Video Preview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="bg-black rounded-lg overflow-hidden aspect-video flex items-center justify-center">
              {videoUrl ? (
                <video
                  src={videoUrl}
                  controls
                  className="w-full h-full"
                />
              ) : (
                <p className="text-muted-foreground">Video preview will appear here</p>
              )}
            </div>
            <div className="flex gap-2">
              <Button
                onClick={processVideo}
                disabled={isProcessing}
                className="flex-1 gap-2"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Process Video
                  </>
                )}
              </Button>
              <Button
                onClick={exportVideo}
                disabled={!videoUrl || isProcessing}
                variant="secondary"
                className="gap-2"
              >
                <Download className="w-4 h-4" />
                Export
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Editor Controls */}
        <div className="space-y-4">
          {/* AI Script Generation */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-primary" />
                  <CardTitle className="text-lg">AI Script Generation</CardTitle>
                </div>
                <Button
                  onClick={generateScript}
                  disabled={isProcessing}
                  size="sm"
                  variant="outline"
                >
                  Generate
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <Textarea
                value={script}
                onChange={(e) => setScript(e.target.value)}
                placeholder="AI-generated script will appear here..."
                className="min-h-[120px]"
              />
            </CardContent>
          </Card>

          {/* Voiceover Settings */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Mic className="w-5 h-5 text-primary" />
                <CardTitle className="text-lg">Voiceover Settings</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Voice</Label>
                <Select value={selectedVoice} onValueChange={setSelectedVoice}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {voices.map((voice) => (
                      <SelectItem key={voice.id} value={voice.id}>
                        {voice.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button
                onClick={generateVoiceover}
                disabled={!script || isProcessing}
                className="w-full gap-2"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Mic className="w-4 h-4" />
                    Generate Voiceover
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Translation */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Languages className="w-5 h-5 text-primary" />
                <CardTitle className="text-lg">Translation</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Target Language</Label>
                <Select value={selectedLanguage} onValueChange={setSelectedLanguage}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {languages.map((lang) => (
                      <SelectItem key={lang.code} value={lang.code}>
                        {lang.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button
                onClick={translateScript}
                disabled={!script || isProcessing}
                className="w-full gap-2"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Translating...
                  </>
                ) : (
                  <>
                    <Languages className="w-4 h-4" />
                    Translate Script
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Brand Settings */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Settings className="w-5 h-5 text-primary" />
                <CardTitle className="text-lg">Brand Customization</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Primary Color</Label>
                <Input
                  type="color"
                  value={brandSettings.primaryColor}
                  onChange={(e) => setBrandSettings({ ...brandSettings, primaryColor: e.target.value })}
                  className="h-10 w-full cursor-pointer"
                />
              </div>
              <div className="space-y-2">
                <Label>Secondary Color</Label>
                <Input
                  type="color"
                  value={brandSettings.secondaryColor}
                  onChange={(e) => setBrandSettings({ ...brandSettings, secondaryColor: e.target.value })}
                  className="h-10 w-full cursor-pointer"
                />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
