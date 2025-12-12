from fastapi import APIRouter, UploadFile, File, HTTPException, Header, BackgroundTasks
from fastapi.responses import JSONResponse
import os
import uuid
import json
import subprocess
from pathlib import Path
from typing import Optional
from openai import OpenAI
import tempfile

from app.storage import upload_file_to_storage, ensure_bucket_exists
from app.database import create_project, save_transcript, save_video_file, update_project
from app.auth import optional_auth
from app.pipeline import run_automatic_pipeline

router = APIRouter()

# Get upload directory from environment or use default (for temporary processing)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "../public/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Supabase Storage bucket name
STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "videos")

# Initialize OpenAI client for transcription
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None


async def extract_audio(video_path: Path, audio_path: Path) -> bool:
    """
    Extract audio from video using FFmpeg.
    """
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i", str(video_path),
                "-vn",
                "-acodec", "libmp3lame",
                "-ar", "16000",
                "-ac", "1",
                "-y",
                str(audio_path)
            ],
            check=True,
            capture_output=True,
            timeout=300
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"FFmpeg error: {e}")
        return False


async def transcribe_audio(audio_path: Path) -> Optional[dict]:
    """
    Transcribe audio using OpenAI Whisper API.
    Returns transcript with segments and timestamps.
    """
    if not openai_client:
        return None
    
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )
        
        # Convert to dict format
        transcript_data = {
            "text": transcript.text,
            "language": getattr(transcript, "language", "en"),
            "segments": []
        }
        
        # Extract segments if available
        if hasattr(transcript, "segments") and transcript.segments:
            for segment in transcript.segments:
                transcript_data["segments"].append({
                    "id": segment.id,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text
                })
        
        return transcript_data
    except Exception as e:
        print(f"Transcription error: {e}")
        return None


@router.post("/")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None)
):
    """
    Upload a video file and create a new project.
    Automatically transcribes the video using Whisper API.
    Stores files in Supabase Storage and metadata in Supabase Database.
    """
    try:
        # Extract user_id from JWT token (optional - allows anonymous uploads for now)
        user_id = optional_auth(authorization)

        # Generate unique project ID
        project_id = str(uuid.uuid4())
        
        # Ensure storage bucket exists
        ensure_bucket_exists(STORAGE_BUCKET, public=True)

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Determine file extension
        file_extension = Path(file.filename or "video.webm").suffix or ".webm"
        storage_path = f"{project_id}/original{file_extension}"

        # Upload to Supabase Storage
        video_url = await upload_file_to_storage(
            bucket_name=STORAGE_BUCKET,
            file_path=storage_path,
            file_content=file_content,
            content_type=file.content_type or "video/webm"
        )

        # Save video file metadata
        await save_video_file(project_id, "original", storage_path, file_size)

        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            file_path = temp_path / f"original{file_extension}"
            
            # Write to temp file for processing
            with open(file_path, "wb") as f:
                f.write(file_content)

            # Extract audio and transcribe
            transcript = None
            
            if openai_client:
                audio_path = temp_path / "audio.mp3"
                if await extract_audio(file_path, audio_path):
                    transcript = await transcribe_audio(audio_path)
                    if transcript:
                        # Save transcript to database
                        await save_transcript(project_id, transcript)

            # Create project in database
            project = await create_project(
                project_id=project_id,
                user_id=user_id,
                name=f"Project {project_id[:8]}",
                status="uploaded"
            )

            # Update project with video URL
            await update_project(project_id, {
                "video_url": video_url,
                "status": "uploaded"
            })

            # Trigger automatic pipeline if transcript exists
            if transcript:
                background_tasks.add_task(run_automatic_pipeline, project_id, user_id)

            # Return project with transcript
            response_data = {
                **project,
                "videoUrl": video_url,
                "transcript": transcript,
            }

            return JSONResponse(content=response_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

