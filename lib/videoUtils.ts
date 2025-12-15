/**
 * Utility functions for video frame capture and processing
 */

/**
 * Captures a video frame at a specific timestamp using a fresh video element
 * This avoids CORS issues with already-loaded videos
 * @param videoUrl - The URL of the video to capture from
 * @param timestamp - The timestamp in seconds to capture at
 * @returns Promise that resolves to a data URL of the captured frame
 */
export async function captureFrameFromUrl(
  videoUrl: string,
  timestamp: number
): Promise<string> {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video')
    video.crossOrigin = 'anonymous'
    video.muted = true
    video.preload = 'metadata'

    const cleanup = () => {
      video.removeEventListener('loadeddata', onLoaded)
      video.removeEventListener('seeked', onSeeked)
      video.removeEventListener('error', onError)
      video.src = ''
      video.load()
    }

    const timeout = setTimeout(() => {
      cleanup()
      reject(new Error('Video capture timed out'))
    }, 15000)

    const onError = () => {
      clearTimeout(timeout)
      cleanup()
      reject(new Error('Failed to load video for capture'))
    }

    const onSeeked = () => {
      clearTimeout(timeout)
      try {
        const canvas = document.createElement('canvas')
        canvas.width = video.videoWidth || 640
        canvas.height = video.videoHeight || 360
        const ctx = canvas.getContext('2d')

        if (!ctx) {
          cleanup()
          reject(new Error('Could not get canvas context'))
          return
        }

        ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
        const dataUrl = canvas.toDataURL('image/jpeg', 0.8)
        cleanup()
        resolve(dataUrl)
      } catch (error) {
        cleanup()
        reject(new Error(`Canvas capture failed: ${error}`))
      }
    }

    const onLoaded = () => {
      // Clamp timestamp to video duration
      const clampedTimestamp = Math.min(timestamp, video.duration || timestamp)
      video.addEventListener('seeked', onSeeked, { once: true })
      video.currentTime = clampedTimestamp
    }

    video.addEventListener('loadeddata', onLoaded, { once: true })
    video.addEventListener('error', onError, { once: true })
    video.src = videoUrl
    video.load()
  })
}

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
  // Wait for video to be ready if not already
  if (video.readyState < 2) {
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        video.removeEventListener('loadeddata', onLoaded)
        reject(new Error('Video load timed out'))
      }, 10000)

      const onLoaded = () => {
        clearTimeout(timeout)
        resolve()
      }

      video.addEventListener('loadeddata', onLoaded, { once: true })
    })
  }

  return new Promise((resolve, reject) => {
    // Validate timestamp
    if (!Number.isFinite(timestamp) || timestamp < 0) {
      reject(new Error('Invalid timestamp'))
      return
    }

    // Clamp timestamp to video duration
    const clampedTimestamp = Math.min(timestamp, video.duration || timestamp)

    // Create canvas to draw video frame
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth || 640
    canvas.height = video.videoHeight || 360
    const ctx = canvas.getContext('2d')

    if (!ctx) {
      reject(new Error('Could not get canvas context'))
      return
    }

    // Store current time to restore later
    const originalTime = video.currentTime

    // Timeout to prevent hanging
    const timeout = setTimeout(() => {
      video.removeEventListener('seeked', onSeeked)
      video.removeEventListener('error', onError)
      reject(new Error('Screenshot capture timed out'))
    }, 5000)

    // Handler for when video seeks to the target timestamp
    const onSeeked = () => {
      clearTimeout(timeout)
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
        // CORS error - canvas is tainted
        reject(new Error(`Canvas error: ${error}`))
      }
    }

    // Handler for seeking errors
    const onError = (error: Event) => {
      clearTimeout(timeout)
      video.removeEventListener('seeked', onSeeked)
      video.removeEventListener('error', onError)
      reject(new Error('Failed to seek video'))
    }

    // Set up event listeners
    video.addEventListener('seeked', onSeeked, { once: true })
    video.addEventListener('error', onError, { once: true })

    // Seek to the target timestamp
    video.currentTime = clampedTimestamp
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
  // Validate duration to prevent infinite loops
  if (!Number.isFinite(duration) || duration <= 0 || duration > 3600) {
    // Return empty array for invalid durations or videos longer than 1 hour
    return []
  }

  const steps = []
  let currentTime = 0
  let stepNumber = 1
  const maxSteps = 100 // Safety limit

  while (currentTime < duration && stepNumber <= maxSteps) {
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
