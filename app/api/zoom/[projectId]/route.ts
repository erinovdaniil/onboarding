import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ projectId: string }> }
) {
  try {
    const { projectId } = await params
    const authorization = request.headers.get('authorization')

    const response = await fetch(`${BACKEND_URL}/api/zoom/${projectId}`, {
      method: 'GET',
      headers: authorization ? { 'Authorization': authorization } : {},
    })

    if (!response.ok) {
      return NextResponse.json(
        { zoomConfig: null },
        { status: 200 }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching zoom config:', error)
    return NextResponse.json(
      { zoomConfig: null },
      { status: 200 }
    )
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ projectId: string }> }
) {
  try {
    const { projectId } = await params
    const authorization = request.headers.get('authorization')
    const body = await request.json()

    const response = await fetch(`${BACKEND_URL}/api/zoom/${projectId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(authorization ? { 'Authorization': authorization } : {}),
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      const error = await response.json()
      return NextResponse.json(
        { error: error.detail || 'Failed to save zoom config' },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error saving zoom config:', error)
    return NextResponse.json(
      { error: 'Failed to save zoom config' },
      { status: 500 }
    )
  }
}
