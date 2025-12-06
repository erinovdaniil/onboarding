'use client'

import { useRouter } from 'next/navigation'
import { ArrowLeft, LayoutGrid, Type, MoreVertical, Rocket } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

interface EditorTopBarProps {
  projectTitle: string
  onExport: () => void
  activeTab: 'video' | 'document'
  onTabChange: (tab: 'video' | 'document') => void
}

export default function EditorTopBar({ 
  projectTitle, 
  onExport, 
  activeTab,
  onTabChange 
}: EditorTopBarProps) {
  const router = useRouter()

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

      <div className="flex-1 text-center">
        <h1 className="text-lg font-semibold">{projectTitle}</h1>
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
          Export Video
        </Button>
      </div>
    </div>
  )
}

