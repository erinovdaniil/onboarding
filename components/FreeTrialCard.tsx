'use client'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

export default function FreeTrialCard() {
  // Mock data
  const daysRemaining = 10
  const aiMinutes = '9m 45s'
  const videoExports = 3

  return (
    <Card className="relative overflow-hidden bg-gradient-to-br from-purple-500/10 via-purple-600/10 to-blue-600/10 border-purple-200/50">
      <div className="p-4 space-y-4">
        {/* Mountain graphic placeholder - using CSS gradient */}
        <div className="absolute top-0 right-0 w-24 h-24 opacity-20">
          <div className="w-full h-full bg-gradient-to-br from-purple-400/30 to-blue-400/30 rounded-bl-full" />
        </div>
        
        <div className="relative z-10">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold text-foreground">Free Trial</span>
          </div>
          <p className="text-xs text-muted-foreground mb-4">
            Expires in {daysRemaining} days
          </p>
          
          <div className="space-y-3 mb-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">AI Minutes</span>
              <span className="text-sm font-medium">{aiMinutes}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Video Exports</span>
              <span className="text-sm font-medium">{videoExports}</span>
            </div>
          </div>
          
          <Button 
            className="w-full bg-primary hover:bg-primary/90 text-primary-foreground"
            size="sm"
          >
            Upgrade Plan
          </Button>
        </div>
      </div>
    </Card>
  )
}

