'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, Upload, ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import ScreenRecorder from '@/components/ScreenRecorder'
import RecentContent from '@/components/RecentContent'
import Link from 'next/link'

export default function Home() {
  const [showRecorder, setShowRecorder] = useState(false)
  const [showUpload, setShowUpload] = useState(false)
  const router = useRouter()

  const handleRecordingComplete = (project: any) => {
    setShowRecorder(false)
    router.push(`/editor/${project.id}`)
  }

  const handleUploadClick = () => {
    // For now, just open file input
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'video/*'
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (!file) return

      const formData = new FormData()
      formData.append('video', file)

      try {
        const response = await fetch('/api/upload', {
          method: 'POST',
          body: formData,
        })
        const project = await response.json()
        router.push(`/editor/${project.id}`)
      } catch (error) {
        console.error('Error uploading video:', error)
        alert('Failed to upload video')
      }
    }
    input.click()
  }

  return (
    <div className="p-8 space-y-8">
      {/* Welcome Section */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold">Welcome back, Daniil!</h1>
        <p className="text-lg text-muted-foreground">What's on your mind today?</p>
      </div>

      {/* Primary Action Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-2xl">
        <Card 
          className="border-2 border-dashed cursor-pointer hover:border-primary hover:bg-primary/5 transition-colors"
          onClick={() => setShowRecorder(true)}
        >
          <CardContent className="p-8 flex flex-col items-center justify-center text-center space-y-4 min-h-[200px]">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
              <Plus className="w-8 h-8 text-primary" />
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-semibold">Start Recording</h3>
              <p className="text-sm text-muted-foreground">
                Record your screen to create professional videos
              </p>
            </div>
          </CardContent>
        </Card>

        <Card 
          className="border-2 border-dashed cursor-pointer hover:border-primary hover:bg-primary/5 transition-colors"
          onClick={handleUploadClick}
        >
          <CardContent className="p-8 flex flex-col items-center justify-center text-center space-y-4 min-h-[200px]">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
              <Upload className="w-8 h-8 text-primary" />
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-semibold">Upload a Video</h3>
              <p className="text-sm text-muted-foreground">
                Upload an existing video to edit and enhance
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Content Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold">Recent Content</h2>
          <Link 
            href="/library" 
            className="text-sm text-primary hover:underline flex items-center gap-1"
          >
            See all
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
        <RecentContent />
      </div>

      {/* Screen Recorder Dialog */}
      <Dialog open={showRecorder} onOpenChange={setShowRecorder}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <ScreenRecorder onRecordingComplete={handleRecordingComplete} />
        </DialogContent>
      </Dialog>
    </div>
  )
}
