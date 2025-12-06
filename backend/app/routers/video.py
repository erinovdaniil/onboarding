from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import os

router = APIRouter()

# Get upload directory
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "../public/uploads"))


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


@router.post("/process")
async def process_video(request: ProcessVideoRequest):
    """
    Process video with AI enhancements, voiceover, and branding.
    """
    try:
        project_dir = UPLOAD_DIR / request.projectId
        original_video_path = project_dir / "original.webm"

        if not original_video_path.exists():
            raise HTTPException(status_code=404, detail="Original video not found")

        # In a real implementation, you would:
        # 1. Load the original video
        # 2. Load the generated voiceover audio
        # 3. Combine video and audio using FFmpeg
        # 4. Apply zoom effects, transitions, and branding
        # 5. Export the final video

        # For now, we'll simulate the processing
        # In production, use ffmpeg-python or subprocess to call FFmpeg

        # Simulate processing delay
        import asyncio
        await asyncio.sleep(2)

        # For demo purposes, return the original video
        # In production, return the processed video URL
        processed_video_url = f"/uploads/{request.projectId}/original.webm"

        return {
            "success": True,
            "processedVideoUrl": processed_video_url,
            "message": "Video processed successfully (demo mode - using original video)",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process video: {str(e)}"
        )


@router.get("/export/{project_id}")
async def export_video(project_id: str):
    """
    Export processed video file.
    """
    try:
        project_dir = UPLOAD_DIR / project_id
        processed_video_path = project_dir / "processed.mp4"
        original_video_path = project_dir / "original.webm"

        # Try to get processed video first, fallback to original
        video_path = processed_video_path if processed_video_path.exists() else original_video_path

        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Video not found")

        from fastapi.responses import FileResponse
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4" if video_path.suffix == ".mp4" else "video/webm",
            filename=f"video-{project_id}{video_path.suffix}",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export video: {str(e)}"
        )

