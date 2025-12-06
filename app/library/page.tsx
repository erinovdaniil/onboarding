'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Search, Plus, ArrowUpDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import ProjectList from '@/components/ProjectList'

export default function LibraryPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const router = useRouter()

  return (
    <div className="p-8 space-y-6">
      {/* Header with Search and Actions */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1 max-w-md">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
            <Input
              placeholder="Search content"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>
        <Button className="bg-primary hover:bg-primary/90 text-primary-foreground gap-2">
          <Plus className="w-4 h-4" />
          Create new
        </Button>
      </div>

      {/* Content Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Your Content</h1>
        <Button variant="outline" size="sm" className="gap-2">
          <ArrowUpDown className="w-4 h-4" />
          Newest
        </Button>
      </div>

      {/* Project List */}
      <ProjectList 
        onSelectProject={(project) => {
          router.push(`/editor/${project.id}`)
        }}
        searchQuery={searchQuery}
      />
    </div>
  )
}

