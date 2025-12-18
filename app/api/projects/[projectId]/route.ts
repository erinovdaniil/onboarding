import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'

export async function GET(
  request: NextRequest,
  { params }: { params: { projectId: string } }
) {
  try {
    const { projectId } = params
    const authorization = request.headers.get('authorization')

    // Forward the request to Python backend
    const response = await fetch(`${BACKEND_URL}/api/projects/${projectId}`, {
      method: 'GET',
      headers: authorization ? { 'Authorization': authorization } : {},
    })

    if (!response.ok) {
      // If project not found, try to get from projects list
      const projectsResponse = await fetch(`${BACKEND_URL}/api/projects/`)
      const projectsData = await projectsResponse.json()
      const project = projectsData.projects?.find((p: any) => p.id === projectId)
      
      if (project) {
        return NextResponse.json(project)
      }
      
      return NextResponse.json(
        { error: 'Project not found' },
        { status: 404 }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching project:', error)
    // Fallback: try to get from projects list
    try {
      const projectsResponse = await fetch(`${BACKEND_URL}/api/projects/`)
      const projectsData = await projectsResponse.json()
      const project = projectsData.projects?.find((p: any) => p.id === params.projectId)
      
      if (project) {
        return NextResponse.json(project)
      }
    } catch (fallbackError) {
      console.error('Fallback error:', fallbackError)
    }
    
    return NextResponse.json(
      { error: 'Failed to fetch project' },
      { status: 500 }
    )
  }
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: { projectId: string } }
) {
  try {
    const { projectId } = params
    const authorization = request.headers.get('authorization')
    const body = await request.json()

    // Forward the request to Python backend
    const response = await fetch(`${BACKEND_URL}/api/projects/${projectId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...(authorization ? { 'Authorization': authorization } : {}),
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      const error = await response.json()
      return NextResponse.json(
        { error: error.detail || 'Failed to update project' },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error updating project:', error)
    return NextResponse.json(
      { error: 'Failed to update project' },
      { status: 500 }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { projectId: string } }
) {
  try {
    const { projectId } = params
    const authorization = request.headers.get('authorization')

    // Forward the request to Python backend
    const response = await fetch(`${BACKEND_URL}/api/projects/${projectId}`, {
      method: 'DELETE',
      headers: authorization ? { 'Authorization': authorization } : {},
    })

    if (!response.ok) {
      const error = await response.json()
      return NextResponse.json(
        { error: error.detail || 'Failed to delete project' },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error deleting project:', error)
    return NextResponse.json(
      { error: 'Failed to delete project' },
      { status: 500 }
    )
  }
}
