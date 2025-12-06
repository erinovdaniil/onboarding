import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'

export async function GET(
  request: NextRequest,
  { params }: { params: { projectId: string } }
) {
  try {
    const { projectId } = params
    
    // Forward the request to Python backend
    const response = await fetch(`${BACKEND_URL}/api/video/export/${projectId}`, {
      method: 'GET',
    })

    if (!response.ok) {
      const error = await response.json()
      return NextResponse.json(
        { error: error.detail || 'Failed to export video' },
        { status: response.status }
      )
    }

    // Get the video blob from Python backend
    const blob = await response.blob()
    const contentType = response.headers.get('content-type') || 'video/mp4'
    const contentDisposition = response.headers.get('content-disposition') || `attachment; filename="video-${projectId}.mp4"`

    return new NextResponse(blob, {
      headers: {
        'Content-Type': contentType,
        'Content-Disposition': contentDisposition,
      },
    })
  } catch (error) {
    console.error('Error exporting video:', error)
    return NextResponse.json(
      { error: 'Failed to export video' },
      { status: 500 }
    )
  }
}
