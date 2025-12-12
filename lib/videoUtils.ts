/**
 * Utility functions for video frame capture and processing
 */

/**
 * Captures a video frame at a specific timestamp and returns it as a data URL
 * @param video - The HTMLVideoElement to capture from
 * @param timestamp - The timestamp in seconds to capture at
 * @returns Promise that resolves to a data URL of the captured frame
 */
export async function captureVideoFrame(
  video: HTMLVideoElement,
  timestamp: number
): Promise<string> {
  return new Promise((resolve, reject) => {
    // Check if video is loaded
    if (!video || video.readyState < 2) {
      reject(new Error('Video not ready'))
      return
    }

    // Create canvas to draw video frame
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')

    if (!ctx) {
      reject(new Error('Could not get canvas context'))
      return
    }

    // Store current time to restore later
    const originalTime = video.currentTime

    // Handler for when video seeks to the target timestamp
    const onSeeked = () => {
      try {
        // Draw the current video frame to canvas
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

        // Convert canvas to data URL
        const dataUrl = canvas.toDataURL('image/jpeg', 0.8)

        // Restore original video time
        video.currentTime = originalTime

        // Clean up
        video.removeEventListener('seeked', onSeeked)
        video.removeEventListener('error', onError)

        resolve(dataUrl)
      } catch (error) {
        video.removeEventListener('seeked', onSeeked)
        video.removeEventListener('error', onError)
        reject(error)
      }
    }

    // Handler for seeking errors
    const onError = (error: Event) => {
      video.removeEventListener('seeked', onSeeked)
      video.removeEventListener('error', onError)
      reject(new Error('Failed to seek video'))
    }

    // Set up event listeners
    video.addEventListener('seeked', onSeeked, { once: true })
    video.addEventListener('error', onError, { once: true })

    // Seek to the target timestamp
    video.currentTime = timestamp
  })
}

/**
 * Generates mock video steps based on video duration
 * @param duration - Total video duration in seconds
 * @param intervalSeconds - Interval between steps (default: 7 seconds)
 * @returns Array of step objects without screenshots
 */
export function generateMockSteps(
  duration: number,
  intervalSeconds: number = 7
): Array<{
  id: string
  startTime: number
  endTime: number
  transcript: string
  title?: string
}> {
  const steps = []
  let currentTime = 0
  let stepNumber = 1

  while (currentTime < duration) {
    const endTime = Math.min(currentTime + intervalSeconds, duration)

    steps.push({
      id: `step-${stepNumber}`,
      startTime: currentTime,
      endTime: endTime,
      transcript: `This is step ${stepNumber}. Add your description of what happens in this part of the video.`,
      title: `Step ${stepNumber}`,
    })

    currentTime = endTime
    stepNumber++
  }

  return steps
}

/**
 * Formats seconds to MM:SS format
 * @param seconds - Time in seconds
 * @returns Formatted time string
 */
export function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}
