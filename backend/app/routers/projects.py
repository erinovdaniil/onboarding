from fastapi import APIRouter, HTTPException
from pathlib import Path
import os
from typing import List, Dict, Any

router = APIRouter()

# Get upload directory
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "../public/uploads"))


@router.get("/")
async def list_projects():
    """
    List all video projects.
    """
    try:
        if not UPLOAD_DIR.exists():
            return {"projects": []}

        projects: List[Dict[str, Any]] = []

        # Iterate through project directories
        for project_dir in UPLOAD_DIR.iterdir():
            if project_dir.is_dir():
                project_id = project_dir.name
                original_video_path = project_dir / "original.webm"
                processed_video_path = project_dir / "processed.mp4"

                # Get creation time
                from datetime import datetime
                stat = original_video_path.stat() if original_video_path.exists() else project_dir.stat()
                created_at = datetime.fromtimestamp(stat.st_mtime).isoformat()

                projects.append({
                    "id": project_id,
                    "name": f"Project {project_id[:8]}",
                    "videoUrl": (
                        f"/uploads/{project_id}/original.webm"
                        if original_video_path.exists()
                        else None
                    ),
                    "processedVideoUrl": (
                        f"/uploads/{project_id}/processed.mp4"
                        if processed_video_path.exists()
                        else None
                    ),
                    "status": "processed" if processed_video_path.exists() else "uploaded",
                    "createdAt": created_at,
                })

        # Sort by creation date, newest first
        projects.sort(key=lambda x: x["createdAt"], reverse=True)

        return {"projects": projects}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch projects: {str(e)}"
        )


@router.get("/{project_id}")
async def get_project(project_id: str):
    """
    Get a single project by ID.
    """
    try:
        project_dir = UPLOAD_DIR / project_id
        
        if not project_dir.exists() or not project_dir.is_dir():
            raise HTTPException(status_code=404, detail="Project not found")
        
        original_video_path = project_dir / "original.webm"
        processed_video_path = project_dir / "processed.mp4"
        
        # Get creation time
        from datetime import datetime
        stat = original_video_path.stat() if original_video_path.exists() else project_dir.stat()
        created_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
        
        project = {
            "id": project_id,
            "name": f"Project {project_id[:8]}",
            "videoUrl": (
                f"/uploads/{project_id}/original.webm"
                if original_video_path.exists()
                else None
            ),
            "processedVideoUrl": (
                f"/uploads/{project_id}/processed.mp4"
                if processed_video_path.exists()
                else None
            ),
            "status": "processed" if processed_video_path.exists() else "uploaded",
            "createdAt": created_at,
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
async def delete_project(project_id: str):
    """
    Delete a project and all its files.
    """
    try:
        project_dir = UPLOAD_DIR / project_id

        if not project_dir.exists():
            raise HTTPException(status_code=404, detail="Project not found")

        # Delete the entire project directory
        import shutil
        shutil.rmtree(project_dir)

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete project: {str(e)}"
        )

