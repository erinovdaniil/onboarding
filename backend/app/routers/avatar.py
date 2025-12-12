from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import os
import json

from app.database import get_project, update_project
from app.storage import upload_file_to_storage, ensure_bucket_exists, get_file_url
from app.database import save_video_file

router = APIRouter()

# Supabase Storage bucket name
STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "videos")


class AvatarRequest(BaseModel):
    projectId: str
    script: str
    avatarId: Optional[str] = "default"
    position: Optional[str] = "bottom-right"  # bottom-right, bottom-left, top-right, top-left
    size: Optional[str] = "medium"  # small, medium, large


@router.post("/generate")
async def generate_avatar(request: AvatarRequest):
    """
    Generate AI avatar video using Synthesia API.
    
    Note: This is a placeholder implementation. In production, you would:
    1. Call Synthesia API to generate avatar video from script
    2. Download the generated video
    3. Upload to Supabase Storage
    4. Store metadata in database
    5. Return the video URL
    
    For now, this stores configuration in the database.
    """
    try:
        # Verify project exists
        project = await get_project(request.projectId)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Store avatar configuration in project metadata
        avatar_config = {
            "avatarId": request.avatarId,
            "position": request.position,
            "size": request.size,
            "script": request.script,
        }
        
        # Update project with avatar config (stored as JSON in a metadata field)
        # Note: This assumes you have a metadata JSONB column in projects table
        # If not, you might want to create a separate avatar_configs table
        await update_project(request.projectId, {
            "avatar_config": json.dumps(avatar_config)
        })
        
        # TODO: In production, integrate with Synthesia API:
        # 1. Initialize Synthesia client with API key
        # 2. Create video request with script and avatar ID
        # 3. Poll for video completion
        # 4. Download video file
        # 5. Upload to Supabase Storage
        # 6. Save metadata with save_video_file()
        
        # Placeholder response
        return {
            "success": True,
            "message": "Avatar configuration saved. Synthesia integration pending.",
            "avatarUrl": None,  # Will be set when Synthesia integration is complete
            "config": avatar_config,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate avatar: {str(e)}"
        )


@router.get("/config/{project_id}")
async def get_avatar_config(project_id: str):
    """
    Get avatar configuration for a project.
    """
    try:
        project = await get_project(project_id)
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get avatar config from project metadata
        avatar_config_json = project.get("avatar_config")
        if not avatar_config_json:
            return {"config": None}
        
        # Parse JSON string
        if isinstance(avatar_config_json, str):
            config = json.loads(avatar_config_json)
        else:
            config = avatar_config_json
        
        return {"config": config}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch avatar config: {str(e)}"
        )

