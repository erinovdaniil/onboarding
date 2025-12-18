from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import os
import json
import re
from pathlib import Path
from typing import Optional

from app.database import get_cleaned_transcript, get_transcript as db_get_transcript

router = APIRouter()

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

# Get upload directory
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "../public/uploads"))

# Filler words to remove (keeps timing sync with video)
FILLER_WORDS = [
    r'\bum\b', r'\bumm\b', r'\bummm\b',
    r'\buh\b', r'\buhh\b', r'\buhhh\b',
    r'\bhmm\b', r'\bhm\b', r'\bhmm+\b',
    r'\bah\b', r'\bahh\b',
    r'\ber\b', r'\berr\b',
    r'\blike\b(?=,|\s+,)',  # "like," filler usage
    r'\byou know\b(?=,|\s+,)',  # "you know," filler usage
    r'^so,?\s+',  # "so" at start of sentence
    r'\bso,\s+',  # "so," as filler mid-sentence
]


def remove_filler_words(text: str) -> str:
    """
    Remove only filler words from transcript while keeping the rest identical.
    This preserves timing sync with the video.
    """
    result = text

    for pattern in FILLER_WORDS:
        # Case insensitive removal
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)

    # Clean up extra whitespace and punctuation artifacts
    result = re.sub(r'\s+', ' ', result)  # Multiple spaces to single
    result = re.sub(r'\s+,', ',', result)  # Space before comma
    result = re.sub(r',\s*,', ',', result)  # Double commas
    result = re.sub(r'^\s*,\s*', '', result)  # Leading comma
    result = re.sub(r'\s+\.', '.', result)  # Space before period
    result = result.strip()

    return result


class ScriptRequest(BaseModel):
    projectId: str
    transcript: Optional[str] = None
    useAI: bool = False  # If true, use AI to rewrite (may break sync). Default: only remove fillers


class TranslateRequest(BaseModel):
    text: str
    targetLanguage: str


@router.post("/generate")
async def generate_script(request: ScriptRequest):
    """
    Generate a cleaned script from video transcript.

    Priority:
    1. Return cleaned transcript from database (already AI-improved)
    2. Fall back to original transcript with filler word removal
    3. Use AI rewriting only if explicitly requested
    """
    try:
        # First, check for cleaned transcript (preferred - already AI-improved)
        cleaned_record = await get_cleaned_transcript(request.projectId)

        if cleaned_record:
            # Use the full cleaned text from the cleaned_transcripts table
            full_cleaned = cleaned_record.get("full_cleaned_text", "")
            if full_cleaned:
                print(f"Using cleaned transcript for script generation")
                return {"script": full_cleaned, "projectId": request.projectId}

            # Fallback: construct from segments
            segments = cleaned_record.get("segments", [])
            if isinstance(segments, str):
                try:
                    segments = json.loads(segments)
                except json.JSONDecodeError:
                    segments = []

            if segments:
                cleaned_text = " ".join(seg.get("cleaned_text", "") for seg in segments)
                if cleaned_text.strip():
                    print(f"Constructed script from {len(segments)} cleaned segments")
                    return {"script": cleaned_text.strip(), "projectId": request.projectId}

        # Try to get transcript from database
        transcript_text = request.transcript
        if not transcript_text:
            transcript_record = await db_get_transcript(request.projectId)
            if transcript_record:
                transcript_text = transcript_record.get("text", "")
                print(f"Using original transcript from database")
            else:
                # Legacy: try local file
                project_dir = UPLOAD_DIR / request.projectId
                transcript_path = project_dir / "transcript.json"

                if transcript_path.exists():
                    with open(transcript_path, "r") as f:
                        transcript_data = json.load(f)
                        transcript_text = transcript_data.get("text", "")

        # If we have a transcript, clean it
        if transcript_text:
            # Default: Just remove filler words to preserve video sync
            script = remove_filler_words(transcript_text)

            # Only use AI rewriting if explicitly requested AND OpenAI is configured
            if request.useAI and openai_client:
                # AI rewriting - note: this may break video sync!
                try:
                    completion = openai_client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "You are a professional video script writer. "
                                    "Create a polished, engaging script based on the provided transcript. "
                                    "Remove filler words, improve clarity, and make it professional. "
                                    "Keep the original meaning and flow, but enhance the language."
                                ),
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"Refine and polish the following transcript into a professional script:\n\n{transcript_text}"
                                ),
                            },
                        ],
                        max_tokens=2000,
                    )
                    script = completion.choices[0].message.content or script
                except Exception as ai_error:
                    # Fall back to simple cleaning if AI fails
                    print(f"AI script generation failed, using simple cleaning: {ai_error}")
        else:
            # No transcript - return empty or generate sample
            if openai_client and request.useAI:
                completion = openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a professional video script writer. "
                                "Create a polished, engaging script for a screen recording tutorial."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                "Generate a short professional script for a screen recording video tutorial. "
                                "Make it clear and concise."
                            ),
                        },
                    ],
                    max_tokens=1000,
                )
                script = completion.choices[0].message.content or ""
            else:
                script = ""

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

