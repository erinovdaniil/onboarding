"""
Database utilities for Supabase PostgreSQL.
This module provides helper functions for database operations.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.supabase_client import supabase
from fastapi import HTTPException


async def create_project(
    project_id: str,
    user_id: Optional[str] = None,
    name: Optional[str] = None,
    status: str = "uploaded"
) -> Dict[str, Any]:
    """
    Create a new project in the database.
    """
    try:
        project_data = {
            "id": project_id,
            "name": name or f"Project {project_id[:8]}",
            "status": status,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
        }
        
        result = supabase.table("projects").insert(project_data).execute()
        
        if result.data:
            return result.data[0]
        raise HTTPException(status_code=500, detail="Failed to create project")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


async def get_project(project_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get a project by ID, optionally filtered by user_id.
    """
    try:
        query = supabase.table("projects").select("*").eq("id", project_id)
        
        if user_id:
            query = query.eq("user_id", user_id)
        
        result = query.execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        print(f"Error fetching project: {e}")
        return None


async def list_projects(user_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    List all projects, optionally filtered by user_id.
    """
    try:
        query = supabase.table("projects").select("*").order("created_at", desc=True).limit(limit)
        
        if user_id:
            query = query.eq("user_id", user_id)
        
        result = query.execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error listing projects: {e}")
        return []


async def update_project(project_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Update a project with new data.
    """
    try:
        result = supabase.table("projects").update(updates).eq("id", project_id).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        print(f"Error updating project: {e}")
        return None


async def delete_project(project_id: str, user_id: Optional[str] = None) -> bool:
    """
    Delete a project by ID.
    """
    try:
        query = supabase.table("projects").delete().eq("id", project_id)
        
        if user_id:
            query = query.eq("user_id", user_id)
        
        result = query.execute()
        return True
    except Exception as e:
        print(f"Error deleting project: {e}")
        return False


async def save_transcript(project_id: str, transcript_data: Dict[str, Any]) -> bool:
    """
    Save transcript data for a project.
    Includes word-level timestamps for precise voiceover sync.
    """
    try:
        import json
        transcript_record = {
            "project_id": project_id,
            "text": transcript_data.get("text", ""),
            "language": transcript_data.get("language", "en"),
            "segments": json.dumps(transcript_data.get("segments", [])),  # Store as JSON string for JSONB
            "created_at": datetime.utcnow().isoformat(),
        }

        # Add word-level timestamps if available
        if transcript_data.get("words"):
            transcript_record["words"] = json.dumps(transcript_data.get("words", []))

        # Check if transcript already exists
        existing = supabase.table("transcripts").select("*").eq("project_id", project_id).execute()

        if existing.data and len(existing.data) > 0:
            # Update existing
            supabase.table("transcripts").update(transcript_record).eq("project_id", project_id).execute()
        else:
            # Insert new
            supabase.table("transcripts").insert(transcript_record).execute()

        return True
    except Exception as e:
        print(f"Error saving transcript: {e}")
        return False


async def get_transcript(project_id: str) -> Optional[Dict[str, Any]]:
    """
    Get transcript for a project.
    """
    try:
        result = supabase.table("transcripts").select("*").eq("project_id", project_id).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        print(f"Error fetching transcript: {e}")
        return None


async def save_video_file(
    project_id: str,
    file_type: str,
    storage_path: str,
    file_size: Optional[int] = None
) -> bool:
    """
    Save video file metadata.
    """
    try:
        file_record = {
            "project_id": project_id,
            "file_type": file_type,  # 'original', 'processed', 'audio', 'avatar'
            "storage_path": storage_path,
            "file_size": file_size,
            "created_at": datetime.utcnow().isoformat(),
        }
        
        supabase.table("video_files").insert(file_record).execute()
        return True
    except Exception as e:
        print(f"Error saving video file: {e}")
        return False


async def get_video_files(project_id: str) -> List[Dict[str, Any]]:
    """
    Get all video files for a project.
    """
    try:
        result = supabase.table("video_files").select("*").eq("project_id", project_id).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error fetching video files: {e}")
        return []


async def save_cleaned_transcript(
    project_id: str,
    cleaned_segments: List[Dict[str, Any]],
    full_text: str
) -> bool:
    """
    Save cleaned transcript segments with preserved timestamps.
    """
    try:
        import json
        cleaned_record = {
            "project_id": project_id,
            "segments": json.dumps(cleaned_segments),  # Store as JSON string for JSONB
            "full_cleaned_text": full_text,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Check if cleaned transcript already exists
        existing = supabase.table("cleaned_transcripts").select("*").eq("project_id", project_id).execute()

        if existing.data and len(existing.data) > 0:
            # Update existing
            supabase.table("cleaned_transcripts").update(cleaned_record).eq("project_id", project_id).execute()
        else:
            # Insert new
            supabase.table("cleaned_transcripts").insert(cleaned_record).execute()

        return True
    except Exception as e:
        print(f"Error saving cleaned transcript: {e}")
        return False


async def get_cleaned_transcript(project_id: str) -> Optional[Dict[str, Any]]:
    """
    Get cleaned transcript for a project.
    """
    try:
        result = supabase.table("cleaned_transcripts").select("*").eq("project_id", project_id).execute()

        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        print(f"Error fetching cleaned transcript: {e}")
        return None


async def update_project_status(
    project_id: str,
    status: str,
    error_message: Optional[str] = None,
    processing_step: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Update project status and processing information.
    """
    try:
        updates = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }

        if error_message is not None:
            updates["error_message"] = error_message

        if processing_step is not None:
            updates["processing_step"] = processing_step

        result = supabase.table("projects").update(updates).eq("id", project_id).execute()

        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        print(f"Error updating project status: {e}")
        return None

