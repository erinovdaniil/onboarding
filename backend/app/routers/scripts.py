from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import os

router = APIRouter()

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None


class ScriptRequest(BaseModel):
    projectId: str
    transcript: Optional[str] = None


class TranslateRequest(BaseModel):
    text: str
    targetLanguage: str


@router.post("/generate")
async def generate_script(request: ScriptRequest):
    """
    Generate a polished script from video transcript or create one from scratch.
    """
    if not openai_client:
        raise HTTPException(
            status_code=500,
            detail="OpenAI API key not configured"
        )

    try:
        # In a real implementation, you would:
        # 1. Extract audio from video
        # 2. Transcribe using Whisper API
        # 3. Refine the transcript using GPT

        # For now, generate a sample script
        completion = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional video script writer. "
                        "Create a polished, engaging script based on screen recording content. "
                        "Remove filler words, improve clarity, and make it professional."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Generate a professional script for a screen recording video. "
                        "Make it clear, concise, and engaging. "
                        "Remove any filler words and improve the flow."
                    ),
                },
            ],
            max_tokens=1000,
        )

        script = completion.choices[0].message.content or ""

        return {"script": script, "projectId": request.projectId}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate script: {str(e)}"
        )


@router.post("/translate")
async def translate_script(request: TranslateRequest):
    """
    Translate script text to target language.
    """
    if not openai_client:
        raise HTTPException(
            status_code=500,
            detail="OpenAI API key not configured"
        )

    if not request.text:
        raise HTTPException(status_code=400, detail="No text provided")

    try:
        language_names = {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "ja": "Japanese",
            "ko": "Korean",
            "zh": "Chinese",
        }

        target_language_name = language_names.get(request.targetLanguage, "English")

        completion = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a professional translator. "
                        f"Translate the given text to {target_language_name} "
                        f"while maintaining the tone, style, and meaning."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Translate the following text to {target_language_name}:\n\n{request.text}",
                },
            ],
            max_tokens=2000,
        )

        translated_text = completion.choices[0].message.content or request.text

        return {"translatedText": translated_text}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to translate text: {str(e)}"
        )

