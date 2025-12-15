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
import logging
import traceback

from app.storage import upload_file_to_storage, ensure_bucket_exists
from app.database import create_project, save_transcript, save_video_file, update_project
from app.auth import optional_auth
from app.pipeline import run_automatic_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()

# Get upload directory from environment or use default (for temporary processing)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "../public/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Supabase Storage bucket name
STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "videos")

# Initialize OpenAI client for transcription
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None


async def convert_to_mp4(input_path: Path, output_path: Path) -> bool:
    """
    Convert video to MP4 format for better compatibility and reliable duration metadata.
    WebM files often have missing/unreliable duration metadata.
    """
    try:
        logger.info(f"Converting {input_path} to MP4...")
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", str(input_path),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",  # Enable fast start for streaming
                "-y",
                str(output_path)
            ],
            capture_output=True,
            timeout=600  # 10 min timeout for longer videos
        )
        if result.returncode == 0 and output_path.exists():
            logger.info(f"MP4 conversion successful: {output_path}")
            return True
        else:
            logger.error(f"MP4 conversion failed: {result.stderr.decode()}")
            return False
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error(f"MP4 conversion error: {e}")
        return False


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

        # Create project in database FIRST (before saving video file due to foreign key)
        project = await create_project(
            project_id=project_id,
            user_id=user_id,
            name=f"Project {project_id[:8]}",
            status="uploading"
        )

        # Save video file metadata (after project exists)
        await save_video_file(project_id, "original", storage_path, file_size)

        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            file_path = temp_path / f"original{file_extension}"

            # Write to temp file for processing
            with open(file_path, "wb") as f:
                f.write(file_content)

            # Convert WebM to MP4 for reliable duration metadata and faster processing
            # MP4 has proper duration metadata, WebM often doesn't
            mp4_path = temp_path / "original.mp4"
            mp4_storage_path = f"{project_id}/original.mp4"
            mp4_video_url = None

            if file_extension.lower() in [".webm", ".mkv", ".avi", ".mov"]:
                logger.info(f"Converting {file_extension} to MP4 for reliable processing...")
                if await convert_to_mp4(file_path, mp4_path):
                    # Upload MP4 version to storage
                    with open(mp4_path, "rb") as f:
                        mp4_content = f.read()

                    mp4_video_url = await upload_file_to_storage(
                        bucket_name=STORAGE_BUCKET,
                        file_path=mp4_storage_path,
                        file_content=mp4_content,
                        content_type="video/mp4"
                    )

                    # Save MP4 as the "original" for processing (pipeline will use this)
                    await save_video_file(project_id, "original", mp4_storage_path, len(mp4_content))
                    logger.info(f"MP4 version uploaded: {mp4_video_url}")

                    # Use MP4 path for transcription
                    file_path = mp4_path
                else:
                    logger.warning("MP4 conversion failed, using original format")

            # Extract audio and transcribe
            transcript = None

            if openai_client:
                audio_path = temp_path / "audio.mp3"
                if await extract_audio(file_path, audio_path):
                    transcript = await transcribe_audio(audio_path)
                    if transcript:
                        # Save transcript to database
                        await save_transcript(project_id, transcript)

            # Update project with video URL (prefer MP4 if available)
            await update_project(project_id, {
                "video_url": mp4_video_url or video_url,
                "status": "uploaded"
            })

            # Trigger automatic pipeline if transcript exists
            # Pass transcript directly to avoid DB read issues on network timeouts
            if transcript:
                background_tasks.add_task(run_automatic_pipeline, project_id, user_id, transcript)

            # Return project with transcript
            response_data = {
                **project,
                "videoUrl": video_url,
                "transcript": transcript,
            }

            return JSONResponse(content=response_data)

    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

