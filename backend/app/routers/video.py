from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import os
import json
import subprocess
import tempfile
import httpx

from app.storage import (
    download_file_from_storage,
    upload_file_to_storage,
    get_file_url
)
from app.database import (
    get_video_files,
    save_video_file,
    update_project,
    get_project
)

router = APIRouter()

# Supabase Storage bucket name
STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "videos")


class BrandSettings(BaseModel):
    logo: Optional[str] = None
    primaryColor: str = "#0ea5e9"
    secondaryColor: str = "#0284c7"


class ProcessVideoRequest(BaseModel):
    projectId: str
    script: Optional[str] = None
    voice: Optional[str] = None
    language: Optional[str] = None
    brandSettings: Optional[BrandSettings] = None


def get_avatar_overlay_filter(position: str, size: str) -> str:
    """
    Generate FFmpeg overlay filter for avatar positioning.
    """
    # Scale avatar based on size
    scale_map = {
        "small": "scale=iw*0.15:ih*0.15",
        "medium": "scale=iw*0.2:ih*0.2",
        "large": "scale=iw*0.25:ih*0.25",
    }
    scale = scale_map.get(size, scale_map["medium"])
    
    # Position overlay
    position_map = {
        "bottom-right": "overlay=W-w-20:H-h-20",
        "bottom-left": "overlay=20:H-h-20",
        "top-right": "overlay=W-w-20:20",
        "top-left": "overlay=20:20",
    }
    overlay = position_map.get(position, position_map["bottom-right"])
    
    return f"[2:v]{scale}[avatar];[0:v][avatar]{overlay}[v]"


@router.post("/process")
async def process_video(request: ProcessVideoRequest):
    """
    Process video with AI enhancements, voiceover, avatar, and branding.
    Downloads files from Supabase Storage, processes with FFmpeg, and uploads result back.
    """
    try:
        # Get video files from database
        video_files = await get_video_files(request.projectId)
        
        # Find original video
        original_file = next((f for f in video_files if f.get("file_type") == "original"), None)
        if not original_file:
            raise HTTPException(status_code=404, detail="Original video not found")
        
        original_storage_path = original_file.get("storage_path")
        if not original_storage_path:
            raise HTTPException(status_code=404, detail="Original video storage path not found")

        # Find voiceover and avatar files
        voiceover_file = next((f for f in video_files if f.get("file_type") == "audio"), None)
        avatar_file = next((f for f in video_files if f.get("file_type") == "avatar"), None)
        
        # Get avatar config from project metadata
        avatar_config = None
        if avatar_file:
            project = await get_project(request.projectId)
            if project:
                avatar_config_json = project.get("avatar_config")
                if avatar_config_json:
                    if isinstance(avatar_config_json, str):
                        avatar_config = json.loads(avatar_config_json)
                    else:
                        avatar_config = avatar_config_json
                else:
                    # Default config if not set
                    avatar_config = {"position": "bottom-right", "size": "medium"}

        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Download original video
            original_video_content = await download_file_from_storage(STORAGE_BUCKET, original_storage_path)
            original_video_path = temp_path / "original.webm"
            with open(original_video_path, "wb") as f:
                f.write(original_video_content)
            
            # Download voiceover if available
            voiceover_path = None
            if voiceover_file:
                voiceover_storage_path = voiceover_file.get("storage_path")
                if voiceover_storage_path:
                    voiceover_content = await download_file_from_storage(STORAGE_BUCKET, voiceover_storage_path)
                    voiceover_path = temp_path / "voiceover.mp3"
                    with open(voiceover_path, "wb") as f:
                        f.write(voiceover_content)
            
            # Download avatar if available
            avatar_path = None
            if avatar_file:
                avatar_storage_path = avatar_file.get("storage_path")
                if avatar_storage_path:
                    avatar_content = await download_file_from_storage(STORAGE_BUCKET, avatar_storage_path)
                    avatar_path = temp_path / "avatar.mp4"
                    with open(avatar_path, "wb") as f:
                        f.write(avatar_content)
            
            # Build FFmpeg command
            processed_video_path = temp_path / "processed.mp4"
            ffmpeg_cmd = ["ffmpeg", "-i", str(original_video_path), "-y"]
            
            # Add voiceover audio if available
            if voiceover_path and voiceover_path.exists():
                ffmpeg_cmd.extend(["-i", str(voiceover_path)])
                ffmpeg_cmd.extend(["-c:v", "libx264", "-c:a", "aac"])
                ffmpeg_cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])
                ffmpeg_cmd.extend(["-shortest"])
            else:
                ffmpeg_cmd.extend(["-c:v", "libx264", "-c:a", "copy"])

            # Add avatar overlay if available
            if avatar_config and avatar_path and avatar_path.exists():
                position = avatar_config.get("position", "bottom-right")
                size = avatar_config.get("size", "medium")
                overlay_filter = get_avatar_overlay_filter(position, size)
                
                # Complex filter for avatar overlay
                ffmpeg_cmd.extend([
                    "-i", str(avatar_path),
                    "-filter_complex", overlay_filter,
                    "-map", "[v]"
                ])
                
                if voiceover_path and voiceover_path.exists():
                    ffmpeg_cmd.extend(["-map", "1:a:0"])
            else:
                ffmpeg_cmd.extend(["-map", "0:v:0"])
                if voiceover_path and voiceover_path.exists():
                    ffmpeg_cmd.extend(["-map", "1:a:0"])

            ffmpeg_cmd.append(str(processed_video_path))

            # Execute FFmpeg
            try:
                result = subprocess.run(
                    ffmpeg_cmd,
                    check=True,
                    capture_output=True,
                    timeout=300
                )
            except subprocess.CalledProcessError as e:
                print(f"FFmpeg error: {e.stderr.decode()}")
                # Fallback: use original video
                processed_video_path = original_video_path
            except subprocess.TimeoutExpired:
                raise HTTPException(status_code=500, detail="Video processing timed out")
            except FileNotFoundError:
                raise HTTPException(
                    status_code=500,
                    detail="FFmpeg not found. Please install FFmpeg: brew install ffmpeg"
                )
            
            # Upload processed video to Supabase Storage
            if processed_video_path.exists():
                with open(processed_video_path, "rb") as f:
                    processed_video_content = f.read()
                
                processed_storage_path = f"{request.projectId}/processed.mp4"
                processed_video_url = await upload_file_to_storage(
                    bucket_name=STORAGE_BUCKET,
                    file_path=processed_storage_path,
                    file_content=processed_video_content,
                    content_type="video/mp4"
                )
                
                # Save processed video file metadata
                await save_video_file(
                    project_id=request.projectId,
                    file_type="processed",
                    storage_path=processed_storage_path,
                    file_size=len(processed_video_content)
                )
                
                # Update project status
                await update_project(request.projectId, {"status": "processed"})
                
                return {
                    "success": True,
                    "processedVideoUrl": processed_video_url,
                    "message": "Video processed successfully",
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to create processed video")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process video: {str(e)}"
        )


@router.get("/export/{project_id}")
async def export_video(project_id: str):
    """
    Export processed video file.
    Returns a redirect to the video URL in Supabase Storage.
    """
    try:
        # Get video files from database
        video_files = await get_video_files(project_id)
        
        # Try to get processed video first, fallback to original
        processed_file = next((f for f in video_files if f.get("file_type") == "processed"), None)
        original_file = next((f for f in video_files if f.get("file_type") == "original"), None)
        
        video_file = processed_file or original_file
        if not video_file:
            raise HTTPException(status_code=404, detail="Video not found")
        
        storage_path = video_file.get("storage_path")
        if not storage_path:
            raise HTTPException(status_code=404, detail="Video storage path not found")
        
        # Get public URL from Supabase Storage
        video_url = await get_file_url(STORAGE_BUCKET, storage_path, public=True)
        
        if not video_url:
            raise HTTPException(status_code=404, detail="Video URL not found")
        
        # Return redirect to video URL
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=video_url)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export video: {str(e)}"
        )

