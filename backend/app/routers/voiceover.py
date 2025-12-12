from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import os
from pathlib import Path

from app.storage import upload_file_to_storage, ensure_bucket_exists
from app.database import save_video_file

router = APIRouter()

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

# Supabase Storage bucket name
STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "videos")


class VoiceoverRequest(BaseModel):
    projectId: str
    script: str
    voice: str = "alloy"


@router.post("/generate")
async def generate_voiceover(request: VoiceoverRequest):
    """
    Generate AI voiceover from script text.
    """
    if not openai_client:
        raise HTTPException(
            status_code=500,
            detail="OpenAI API key not configured"
        )

    if not request.script:
        raise HTTPException(status_code=400, detail="No script provided")

    try:
        # Generate voiceover using OpenAI TTS
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice=request.voice or "alloy",
            input=request.script,
        )

        # Get audio content
        audio_content = response.content
        
        # Ensure storage bucket exists
        ensure_bucket_exists(STORAGE_BUCKET, public=True)
        
        # Upload to Supabase Storage
        storage_path = f"{request.projectId}/voiceover.mp3"
        audio_url = await upload_file_to_storage(
            bucket_name=STORAGE_BUCKET,
            file_path=storage_path,
            file_content=audio_content,
            content_type="audio/mpeg"
        )
        
        # Save video file metadata
        await save_video_file(
            project_id=request.projectId,
            file_type="audio",
            storage_path=storage_path,
            file_size=len(audio_content)
        )

        return {
            "success": True,
            "audioUrl": audio_url,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate voiceover: {str(e)}"
        )

