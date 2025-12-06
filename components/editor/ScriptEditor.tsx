'use client'

import { useState } from 'react'
import { Plus, FileText, Pencil, Sparkles, Languages, Mic, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Label } from '@/components/ui/label'

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
  isProcessing?: boolean
  selectedLanguage?: string
  onLanguageChange?: (lang: string) => void
  selectedVoice?: string
  onVoiceChange?: (voice: string) => void
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
  isProcessing = false,
  selectedLanguage = 'en',
  onLanguageChange,
  selectedVoice = 'alloy',
  onVoiceChange,
}: ScriptEditorProps) {
  const [activeTab, setActiveTab] = useState('script')

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
          <TabsList className="grid w-full grid-cols-7">
            <TabsTrigger value="script" className="text-xs">Script</TabsTrigger>
            <TabsTrigger value="ai-voice" className="text-xs">AI Voice</TabsTrigger>
            <TabsTrigger value="music" className="text-xs">Music</TabsTrigger>
            <TabsTrigger value="visuals" className="text-xs">Visuals</TabsTrigger>
            <TabsTrigger value="zooms" className="text-xs">Zooms</TabsTrigger>
            <TabsTrigger value="ai-avatar" className="text-xs">AI Avatar</TabsTrigger>
            <TabsTrigger value="elements" className="text-xs">Elements</TabsTrigger>
          </TabsList>
        </div>

        {/* Script Tab */}
        <TabsContent value="script" className="flex-1 flex flex-col m-0 p-0">
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

          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {scriptLines.length > 0 ? (
              scriptLines.map((line) => (
                <div key={line.id} className="text-sm py-1">
                  {line.time && (
                    <span className="text-muted-foreground font-mono mr-2">
                      {line.time}
                    </span>
                  )}
                  <span>{line.text}</span>
                </div>
              ))
            ) : (
              <div className="text-sm text-muted-foreground text-center py-8">
                No script content yet. Generate a script to get started.
              </div>
            )}
          </div>

          <div className="p-4 border-t space-y-2">
            <Textarea
              placeholder="Enter script text..."
              value={script}
              onChange={(e) => onScriptChange(e.target.value)}
              className="min-h-[80px] resize-none"
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

        {/* Placeholder tabs */}
        <TabsContent value="music" className="flex-1 p-4">
          <p className="text-sm text-muted-foreground">Music library coming soon...</p>
        </TabsContent>
        <TabsContent value="visuals" className="flex-1 p-4">
          <p className="text-sm text-muted-foreground">Visual effects coming soon...</p>
        </TabsContent>
        <TabsContent value="zooms" className="flex-1 p-4">
          <p className="text-sm text-muted-foreground">Zoom controls coming soon...</p>
        </TabsContent>
        <TabsContent value="ai-avatar" className="flex-1 p-4">
          <p className="text-sm text-muted-foreground">AI Avatar settings coming soon...</p>
        </TabsContent>
        <TabsContent value="elements" className="flex-1 p-4">
          <p className="text-sm text-muted-foreground">Elements library coming soon...</p>
        </TabsContent>
      </Tabs>
    </div>
  )
}
