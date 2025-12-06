from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import os
from pathlib import Path
import aiofiles

router = APIRouter()

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

# Get upload directory
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "../public/uploads"))


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

        # Save the audio file
        project_dir = UPLOAD_DIR / request.projectId
        project_dir.mkdir(parents=True, exist_ok=True)

        audio_path = project_dir / "voiceover.mp3"
        
        # Write audio content to file
        audio_content = response.content
        async with aiofiles.open(audio_path, "wb") as f:
            await f.write(audio_content)

        return {
            "success": True,
            "audioUrl": f"/uploads/{request.projectId}/voiceover.mp3",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate voiceover: {str(e)}"
        )

