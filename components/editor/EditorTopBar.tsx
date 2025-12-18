'use client'

import { useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowLeft, LayoutGrid, Type, MoreVertical, Rocket } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

interface EditorTopBarProps {
  projectTitle: string
  onExport: () => void
  activeTab: 'video' | 'document'
  onTabChange: (tab: 'video' | 'document') => void
  onTitleChange?: (newTitle: string) => void
}

export default function EditorTopBar({
  projectTitle,
  onExport,
  activeTab,
  onTabChange,
  onTitleChange
}: EditorTopBarProps) {
  const router = useRouter()
  const [isEditing, setIsEditing] = useState(false)
  const [editedTitle, setEditedTitle] = useState(projectTitle)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSave = () => {
    if (editedTitle.trim() && editedTitle !== projectTitle && onTitleChange) {
      onTitleChange(editedTitle.trim())
    } else {
      setEditedTitle(projectTitle)
    }
    setIsEditing(false)
  }

  const handleClickTitle = () => {
    setEditedTitle(projectTitle)
    setIsEditing(true)
    setTimeout(() => inputRef.current?.focus(), 0)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSave()
    } else if (e.key === 'Escape') {
      setEditedTitle(projectTitle)
      setIsEditing(false)
    }
  }

  return (
    <div className="h-16 border-b bg-card flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.push('/library')}
          className="h-8 w-8"
        >
          <ArrowLeft className="w-4 h-4" />
        </Button>

        <Tabs value={activeTab} onValueChange={(v) => onTabChange(v as 'video' | 'document')}>
          <TabsList>
            <TabsTrigger value="video">Video</TabsTrigger>
            <TabsTrigger value="document">Document</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <div className="flex-1 flex items-center justify-center">
        {isEditing ? (
          <Input
            ref={inputRef}
            value={editedTitle}
            onChange={(e) => setEditedTitle(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={handleSave}
            className="max-w-2xl text-center text-lg font-semibold h-9"
            autoFocus
          />
        ) : (
          <TooltipProvider>
            <Tooltip delayDuration={200}>
              <TooltipTrigger asChild>
                <h1
                  className="text-lg font-semibold cursor-text px-3 py-2 rounded-md transition-all hover:bg-muted/50 active:bg-muted"
                  onClick={handleClickTitle}
                >
                  {projectTitle}
                </h1>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="text-xs font-normal">
                Edit project name
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>

      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <LayoutGrid className="w-4 h-4" />
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <Type className="w-4 h-4" />
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <MoreVertical className="w-4 h-4" />
        </Button>
        <Button
          className="bg-primary hover:bg-primary/90 text-primary-foreground gap-2"
          onClick={onExport}
        >
          <Rocket className="w-4 h-4" />
          {activeTab === 'document' ? 'Export Document' : 'Export Video'}
        </Button>
      </div>
    </div>
  )
}

