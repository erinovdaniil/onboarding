'use client'

import { useState } from 'react'
import { Plus, FileText, Pencil, Sparkles, Languages, Mic, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import TranscriptEditor, { TranscriptPhrase } from './TranscriptEditor'

interface ScriptEditorProps {
  script: string
  onScriptChange: (script: string) => void
  onAddChapter: () => void
  onAddClip: () => void
  onAddPause: () => void
  onGenerateScript?: () => void
  onTranslate?: () => void
  onGenerateVoiceover?: () => void
  onProcessVideo?: () => void
  onGenerateAvatar?: (config: { avatarId: string; position: string; size: string }) => void
  isProcessing?: boolean
  selectedLanguage?: string
  onLanguageChange?: (lang: string) => void
  selectedVoice?: string
  onVoiceChange?: (voice: string) => void
  projectId?: string
  transcriptPhrases?: TranscriptPhrase[]
  onTranscriptPhrasesChange?: (phrases: TranscriptPhrase[]) => void
  currentTime?: number
  onSeekToTime?: (time: number) => void
  onRetranscribe?: () => Promise<void>
  hasTranscriptText?: boolean
}

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

const avatarOptions = [
  { id: 'default', name: 'Default Avatar' },
  { id: 'female-1', name: 'Female Avatar 1' },
  { id: 'female-2', name: 'Female Avatar 2' },
  { id: 'male-1', name: 'Male Avatar 1' },
  { id: 'male-2', name: 'Male Avatar 2' },
]

const positionOptions = [
  { id: 'bottom-right', name: 'Bottom Right' },
  { id: 'bottom-left', name: 'Bottom Left' },
  { id: 'top-right', name: 'Top Right' },
  { id: 'top-left', name: 'Top Left' },
]

const sizeOptions = [
  { id: 'small', name: 'Small' },
  { id: 'medium', name: 'Medium' },
  { id: 'large', name: 'Large' },
]

export default function ScriptEditor({
  script,
  onScriptChange,
  onAddChapter,
  onAddClip,
  onAddPause,
  onGenerateScript,
  onTranslate,
  onGenerateVoiceover,
  onProcessVideo,
  onGenerateAvatar,
  isProcessing = false,
  selectedLanguage = 'en',
  onLanguageChange,
  selectedVoice = 'alloy',
  onVoiceChange,
  projectId,
  transcriptPhrases = [],
  onTranscriptPhrasesChange,
  currentTime = 0,
  onSeekToTime,
  onRetranscribe,
  hasTranscriptText = false,
}: ScriptEditorProps) {
  const [activeTab, setActiveTab] = useState('transcript')
  const [avatarId, setAvatarId] = useState('default')
  const [avatarPosition, setAvatarPosition] = useState('bottom-right')
  const [avatarSize, setAvatarSize] = useState('medium')

  // Parse script with timestamps (format: "0:00 Text here")
  const scriptLines = script
    .split('\n')
    .filter(line => line.trim())
    .map((line, index) => {
      const match = line.match(/^(\d+:\d+)\s+(.+)$/)
      if (match) {
        return { time: match[1], text: match[2], id: index }
      }
      return { time: null, text: line, id: index }
    })

  return (
    <div className="h-full flex flex-col border-r bg-card">
      {/* Tab Navigation */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
        <div className="border-b px-4">
          <TabsList className="w-full justify-start">
            <TabsTrigger value="transcript" className="text-xs">Transcript</TabsTrigger>
            <TabsTrigger value="script" className="text-xs">Script</TabsTrigger>
            <TabsTrigger value="ai-voice" className="text-xs">AI Voice</TabsTrigger>
            <TabsTrigger value="ai-avatar" className="text-xs">AI Avatar</TabsTrigger>
          </TabsList>
        </div>

        {/* Transcript Tab */}
        <TabsContent value="transcript" className="m-0 p-0">
          <div className="h-[calc(100vh-16rem)]">
            <TranscriptEditor
              phrases={transcriptPhrases}
              onPhrasesChange={onTranscriptPhrasesChange || (() => {})}
              currentTime={currentTime}
              onSeekToTime={onSeekToTime || (() => {})}
              disabled={isProcessing}
              projectId={projectId}
              onRetranscribe={onRetranscribe}
              hasTranscriptText={hasTranscriptText}
            />
          </div>
        </TabsContent>

        {/* Script Tab */}
        <TabsContent value="script" className="m-0 p-0">
          <div className="h-[calc(100vh-16rem)] overflow-y-auto">
            <div className="p-4 border-b space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
              <Button 
                size="sm" 
                variant="outline" 
                onClick={onAddChapter}
                disabled={isProcessing}
              >
                Add Chapters
              </Button>
              <Button 
                size="sm" 
                variant="outline" 
                onClick={onAddClip}
                disabled={isProcessing}
              >
                Add Clip
              </Button>
              <Button 
                size="sm" 
                variant="outline" 
                onClick={onAddPause}
                disabled={isProcessing}
              >
                Add Pause
              </Button>
            </div>
            <div className="flex items-center gap-2">
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-8 w-8"
                title="Document actions"
              >
                <FileText className="w-4 h-4" />
              </Button>
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-8 w-8"
                title="Edit script"
              >
                <Pencil className="w-4 h-4" />
              </Button>
              {onGenerateScript && (
                <Button
                  size="sm"
                  variant="default"
                  onClick={onGenerateScript}
                  disabled={isProcessing}
                  className="ml-auto gap-2"
                >
                  {isProcessing ? (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3 h-3" />
                      Generate Script
                    </>
                  )}
                </Button>
              )}
            </div>
          </div>

          <div className="p-4 space-y-2">
            <Textarea
              placeholder="Enter script text..."
              value={script}
              onChange={(e) => onScriptChange(e.target.value)}
              className="h-[200px] resize-none"
              disabled={isProcessing}
            />
            {onTranslate && (
              <div className="flex items-center gap-2">
                <Select value={selectedLanguage} onValueChange={onLanguageChange}>
                  <SelectTrigger className="h-8 text-xs">
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
                <Button
                  size="sm"
                  variant="outline"
                  onClick={onTranslate}
                  disabled={!script || isProcessing}
                  className="gap-2"
                >
                  <Languages className="w-3 h-3" />
                  Translate
                </Button>
              </div>
            )}
            </div>
          </div>
        </TabsContent>

        {/* AI Voice Tab */}
        <TabsContent value="ai-voice" className="flex-1 p-4 space-y-4">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Voice</Label>
              <Select value={selectedVoice} onValueChange={onVoiceChange}>
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
            {onGenerateVoiceover && (
              <Button
                onClick={onGenerateVoiceover}
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
            )}
            {onProcessVideo && (
              <Button
                onClick={onProcessVideo}
                disabled={!script || isProcessing}
                className="w-full gap-2 bg-primary"
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
            )}
          </div>
        </TabsContent>

        {/* AI Avatar Tab */}
        <TabsContent value="ai-avatar" className="flex-1 p-4 space-y-4 overflow-y-auto">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Enable AI Avatar</Label>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  defaultChecked
                  className="h-4 w-4 rounded border-gray-300"
                />
                <span className="text-sm text-muted-foreground">
                  Enable AI avatar in video
                </span>
              </div>
            </div>
            
            <div className="space-y-2">
              <Label>Select Avatar</Label>
              <Select value={avatarId} onValueChange={setAvatarId}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {avatarOptions.map((avatar) => (
                    <SelectItem key={avatar.id} value={avatar.id}>
                      {avatar.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Position</Label>
              <Select value={avatarPosition} onValueChange={setAvatarPosition}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {positionOptions.map((pos) => (
                    <SelectItem key={pos.id} value={pos.id}>
                      {pos.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Size</Label>
              <Select value={avatarSize} onValueChange={setAvatarSize}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {sizeOptions.map((size) => (
                    <SelectItem key={size.id} value={size.id}>
                      {size.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {onGenerateAvatar && (
              <Button
                onClick={() => onGenerateAvatar({
                  avatarId,
                  position: avatarPosition,
                  size: avatarSize,
                })}
                disabled={!script || isProcessing}
                className="w-full gap-2"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Generating Avatar...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Generate Avatar
                  </>
                )}
              </Button>
            )}

            <div className="text-xs text-muted-foreground p-3 bg-muted rounded-lg">
              <p className="font-semibold mb-1">Note:</p>
              <p>Avatar will be composited onto your video during processing. Make sure you have a script generated before creating the avatar.</p>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
