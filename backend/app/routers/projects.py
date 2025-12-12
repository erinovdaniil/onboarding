from fastapi import APIRouter, HTTPException, Header
from pathlib import Path
import os
import json
from typing import List, Dict, Any, Optional

from app.database import (
    list_projects as db_list_projects,
    get_project as db_get_project,
    delete_project as db_delete_project,
    get_transcript,
    get_video_files
)
from app.storage import delete_file_from_storage
from app.auth import optional_auth

router = APIRouter()

# Supabase Storage bucket name
STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "videos")


@router.get("/")
async def list_projects(authorization: Optional[str] = Header(None)):
    """
    List all video projects.
    Optionally filtered by user if authorization header is provided.
    """
    try:
        # Extract user_id from JWT token if provided
        user_id = optional_auth(authorization)

        # Get projects from database
        projects = await db_list_projects(user_id=user_id)

        # Get video files for each project to populate URLs
        from app.storage import get_file_url
        for project in projects:
            video_files = await get_video_files(project["id"])
            
            # Find original and processed video URLs
            for video_file in video_files:
                storage_path = video_file.get("storage_path")
                if storage_path:
                    file_url = await get_file_url(STORAGE_BUCKET, storage_path, public=True)
                    if video_file["file_type"] == "original":
                        project["videoUrl"] = file_url or project.get("video_url")
                    elif video_file["file_type"] == "processed":
                        project["processedVideoUrl"] = file_url

        return {"projects": projects}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch projects: {str(e)}"
        )


@router.get("/{project_id}")
async def get_project(project_id: str, authorization: Optional[str] = Header(None)):
    """
    Get a single project by ID.
    """
    try:
        # Extract user_id from JWT token if provided
        user_id = optional_auth(authorization)

        # Get project from database
        project = await db_get_project(project_id, user_id=user_id)
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get video files
        video_files = await get_video_files(project_id)
        
        # Populate video URLs from storage
        from app.storage import get_file_url
        for video_file in video_files:
            storage_path = video_file.get("storage_path")
            if storage_path:
                file_url = await get_file_url(STORAGE_BUCKET, storage_path, public=True)
                if video_file["file_type"] == "original":
                    project["videoUrl"] = file_url or project.get("video_url")
                elif video_file["file_type"] == "processed":
                    project["processedVideoUrl"] = file_url

        # Get transcript
        transcript_record = await get_transcript(project_id)
        if transcript_record:
            project["transcript"] = {
                "text": transcript_record.get("text", ""),
                "language": transcript_record.get("language", "en"),
                "segments": transcript_record.get("segments", [])
            }
        
        return project
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch project: {str(e)}"
        )


@router.delete("/{project_id}")
async def delete_project(project_id: str, authorization: Optional[str] = Header(None)):
    """
    Delete a project and all its files from database and storage.
    """
    try:
        # Extract user_id from JWT token if provided
        user_id = optional_auth(authorization)

        # Get project to verify it exists
        project = await db_get_project(project_id, user_id=user_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get all video files for this project
        video_files = await get_video_files(project_id)
        
        # Delete files from Supabase Storage
        for video_file in video_files:
            storage_path = video_file.get("storage_path")
            if storage_path:
                await delete_file_from_storage(STORAGE_BUCKET, storage_path)

        # Delete project from database (cascades to transcripts and video_files)
        success = await db_delete_project(project_id, user_id=user_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete project")

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete project: {str(e)}"
        )

