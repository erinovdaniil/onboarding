from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import os
import io
import json
import re
import tempfile
import subprocess
import logging
from typing import List, Dict, Optional
from openai import OpenAI

from app.database import get_transcript as db_get_transcript, save_transcript, get_project, get_cleaned_transcript as db_get_cleaned_transcript, save_cleaned_transcript
from app.storage import download_file_from_storage

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

# Storage bucket
STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "videos")


class SegmentTranscriptRequest(BaseModel):
    projectId: str
    segmentDuration: float = 10.0  # Target segment duration (flexible)
    minDuration: float = 5.0  # Minimum segment duration
    maxDuration: float = 20.0  # Maximum segment duration


class TranscriptSegmentUpdate(BaseModel):
    id: str
    start: float
    end: float
    text: str


class UpdateTranscriptRequest(BaseModel):
    projectId: str
    segments: List[TranscriptSegmentUpdate]


def find_sentence_boundaries(text: str) -> List[int]:
    """Find character positions of sentence endings."""
    # Match sentence-ending punctuation followed by space or end
    pattern = r'[.!?]+(?:\s|$)'
    boundaries = []
    for match in re.finditer(pattern, text):
        boundaries.append(match.end())
    return boundaries


def smart_segment_whisper_segments(
    whisper_segments: List[Dict],
    target_duration: float = 10.0,
    min_duration: float = 5.0,
    max_duration: float = 20.0
) -> List[Dict]:
    """
    Intelligently segment Whisper output into logical steps.
    Groups segments at natural boundaries (sentences, pauses) while respecting duration limits.
    """
    if not whisper_segments:
        return []

    result_segments = []
    current_group = []
    current_start = None
    current_text_parts = []

    for i, seg in enumerate(whisper_segments):
        seg_start = seg.get("start", 0)
        seg_end = seg.get("end", seg_start + 1)
        seg_text = seg.get("text", "").strip()

        if not seg_text:
            continue

        # Start new group if empty
        if current_start is None:
            current_start = seg_start

        current_group.append(seg)
        current_text_parts.append(seg_text)

        current_duration = seg_end - current_start
        combined_text = " ".join(current_text_parts)

        # Check if we should end this segment
        should_end = False

        # 1. Check for sentence ending
        ends_with_sentence = bool(re.search(r'[.!?]$', seg_text))

        # 2. Check for long pause before next segment (> 0.5s)
        has_long_pause = False
        if i + 1 < len(whisper_segments):
            next_start = whisper_segments[i + 1].get("start", seg_end)
            pause_duration = next_start - seg_end
            has_long_pause = pause_duration > 0.5

        # Decision logic
        if current_duration >= max_duration:
            # Force end if we hit max duration
            should_end = True
        elif current_duration >= min_duration:
            # Can end if we have a natural boundary
            if ends_with_sentence or has_long_pause:
                should_end = True
            elif current_duration >= target_duration:
                # Past target, end at next opportunity
                should_end = True

        # Last segment - always end
        if i == len(whisper_segments) - 1:
            should_end = True

        if should_end and current_group:
            result_segments.append({
                "id": f"segment-{len(result_segments)}",
                "startTime": current_start,
                "endTime": seg_end,
                "text": combined_text,
                "transcript": combined_text
            })
            current_group = []
            current_text_parts = []
            current_start = None

    return result_segments


@router.get("/{project_id}")
async def get_transcript(project_id: str):
    """
    Get transcript for a project from Supabase database.
    Returns cleaned transcript if available, otherwise original.
    """
    try:
        # First, try to get cleaned transcript (improved text with original timestamps)
        cleaned_record = await db_get_cleaned_transcript(project_id)
        logger.info(f"Cleaned transcript for {project_id}: {cleaned_record is not None}")

        # Get original transcript for metadata (language, original words)
        transcript_record = await db_get_transcript(project_id)
        logger.info(f"Original transcript for {project_id}: {transcript_record is not None}")

        if not transcript_record and not cleaned_record:
            return {"transcript": None, "message": "No transcript available"}

        # Parse original segments if stored as JSON string
        original_segments = []
        if transcript_record:
            original_segments = transcript_record.get("segments", [])
            if isinstance(original_segments, str):
                try:
                    original_segments = json.loads(original_segments)
                except json.JSONDecodeError:
                    original_segments = []

        # Parse original words if stored as JSON string
        original_words = []
        if transcript_record:
            original_words = transcript_record.get("words", [])
            if isinstance(original_words, str):
                try:
                    original_words = json.loads(original_words)
                except json.JSONDecodeError:
                    original_words = []

        # If cleaned transcript exists, convert to words format for display
        words_for_display = original_words
        if cleaned_record:
            cleaned_segments = cleaned_record.get("segments", [])
            if isinstance(cleaned_segments, str):
                try:
                    cleaned_segments = json.loads(cleaned_segments)
                except json.JSONDecodeError:
                    cleaned_segments = []

            # Convert cleaned segments to a format the frontend can display
            # Each segment has: id, start, end, original_text, cleaned_text, voiceover_start, voiceover_end
            if cleaned_segments:
                words_for_display = []
                for seg in cleaned_segments:
                    # Use voiceover timestamps if available, otherwise fall back to original
                    start_time = seg.get("voiceover_start", seg.get("start", 0))
                    end_time = seg.get("voiceover_end", seg.get("end", 0))

                    words_for_display.append({
                        "word": seg.get("cleaned_text", seg.get("original_text", "")),
                        "start": start_time,
                        "end": end_time,
                        "original_start": seg.get("start", 0),  # Keep original for reference
                        "original_end": seg.get("end", 0),
                        "is_cleaned_segment": True  # Flag to indicate this is a full segment
                    })

        transcript = {
            "text": cleaned_record.get("full_cleaned_text", "") if cleaned_record else (transcript_record.get("text", "") if transcript_record else ""),
            "language": transcript_record.get("language", "en") if transcript_record else "en",
            "segments": original_segments,
            "words": words_for_display,
            "has_cleaned_transcript": cleaned_record is not None
        }

        return {"transcript": transcript}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch transcript: {str(e)}"
        )


def generate_step_title(text: str, step_number: int) -> str:
    """
    Generate a concise step title from the transcript text.
    Uses simple heuristics - could be enhanced with AI later.
    """
    if not text:
        return f"Step {step_number}"

    # Clean up the text
    text = text.strip()

    # Try to extract the main action/instruction
    # Look for imperative verbs at the start
    imperative_patterns = [
        r'^(click|tap|select|choose|open|close|go to|navigate|enter|type|press|drag|scroll|find|look|check|enable|disable|turn|set|add|remove|delete|create|save|download|upload|install|run|start|stop|copy|paste|move|resize)\s',
    ]

    for pattern in imperative_patterns:
        match = re.search(pattern, text.lower())
        if match:
            # Found an action verb, extract a meaningful phrase
            words = text.split()
            # Take first 5-8 words for title
            title_words = words[:min(7, len(words))]
            title = " ".join(title_words)
            # Capitalize first letter
            title = title[0].upper() + title[1:] if title else f"Step {step_number}"
            # Remove trailing punctuation except for important ones
            title = re.sub(r'[,;:]$', '', title)
            return title

    # Fallback: Use first sentence or first N words
    sentences = re.split(r'[.!?]+', text)
    if sentences and sentences[0].strip():
        first_sentence = sentences[0].strip()
        words = first_sentence.split()
        if len(words) <= 8:
            title = first_sentence
        else:
            title = " ".join(words[:7]) + "..."
        title = title[0].upper() + title[1:] if title else f"Step {step_number}"
        return title

    return f"Step {step_number}"


class RetranscribeRequest(BaseModel):
    projectId: str


@router.post("/retranscribe")
async def retranscribe_video(request: RetranscribeRequest):
    """
    Re-transcribe a video with word-level timestamps.
    This is needed for existing videos that were transcribed without word timestamps.
    """
    if not openai_client:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    try:
        # Get project to find video URL
        project = await get_project(request.projectId)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        video_url = project.get("video_url")
        if not video_url:
            raise HTTPException(status_code=400, detail="No video found for this project")

        logger.info(f"Re-transcribing video for project {request.projectId}")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Download video from storage
            # Extract storage path from URL
            storage_path = f"{request.projectId}/original.mp4"
            video_content = await download_file_from_storage(STORAGE_BUCKET, storage_path)

            if not video_content:
                # Try webm
                storage_path = f"{request.projectId}/original.webm"
                video_content = await download_file_from_storage(STORAGE_BUCKET, storage_path)

            if not video_content:
                raise HTTPException(status_code=404, detail="Video file not found in storage")

            # Save video to temp file
            video_path = temp_path / "video.mp4"
            with open(video_path, "wb") as f:
                f.write(video_content)

            # Extract audio
            audio_path = temp_path / "audio.mp3"
            result = subprocess.run(
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
                capture_output=True,
                timeout=300
            )

            if result.returncode != 0:
                raise HTTPException(status_code=500, detail="Failed to extract audio")

            # Transcribe with word-level timestamps
            with open(audio_path, "rb") as audio_file:
                transcript = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["word", "segment"]
                )

            # Build transcript data
            transcript_data = {
                "text": transcript.text,
                "language": getattr(transcript, "language", "en"),
                "segments": [],
                "words": []
            }

            # Extract word-level timestamps
            if hasattr(transcript, "words") and transcript.words:
                for word in transcript.words:
                    transcript_data["words"].append({
                        "word": word.word,
                        "start": word.start,
                        "end": word.end
                    })
                logger.info(f"Got {len(transcript_data['words'])} word-level timestamps")

            # Extract segments
            if hasattr(transcript, "segments") and transcript.segments:
                for segment in transcript.segments:
                    transcript_data["segments"].append({
                        "id": segment.id,
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text
                    })
                logger.info(f"Got {len(transcript_data['segments'])} segments")

            # Save to database
            await save_transcript(request.projectId, transcript_data)

            return {
                "success": True,
                "transcript": transcript_data,
                "wordCount": len(transcript_data["words"]),
                "segmentCount": len(transcript_data["segments"])
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Re-transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Re-transcription failed: {str(e)}")


@router.post("/segment")
async def segment_transcript(request: SegmentTranscriptRequest):
    """
    Segment transcript into logical steps with smart boundaries.
    Uses sentence endings and natural pauses for better segmentation.
    """
    try:
        # Get transcript from database
        transcript_record = await db_get_transcript(request.projectId)

        if not transcript_record:
            raise HTTPException(status_code=404, detail="Transcript not found")

        # Parse segments if stored as JSON string
        transcript_segments = transcript_record.get("segments", [])
        if isinstance(transcript_segments, str):
            try:
                transcript_segments = json.loads(transcript_segments)
            except json.JSONDecodeError:
                transcript_segments = []

        # If transcript has segments from Whisper, use smart segmentation
        if transcript_segments and len(transcript_segments) > 0:
            segments = smart_segment_whisper_segments(
                transcript_segments,
                target_duration=request.segmentDuration,
                min_duration=request.minDuration,
                max_duration=request.maxDuration
            )

            # Generate titles for each segment
            for i, seg in enumerate(segments):
                seg["title"] = generate_step_title(seg["text"], i + 1)

            return {"segments": segments}

        # Fallback: segment by text if no Whisper segments
        full_text = transcript_record.get("text", "")
        if not full_text:
            return {"segments": []}

        # Smart text-based segmentation using sentences
        sentences = re.split(r'(?<=[.!?])\s+', full_text)
        segments = []
        current_text = []
        segment_start = 0.0
        estimated_wps = 2.5  # words per second estimate

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            current_text.append(sentence)
            combined = " ".join(current_text)
            word_count = len(combined.split())
            estimated_duration = word_count / estimated_wps

            # Check if we should end this segment
            if estimated_duration >= request.segmentDuration or sentence == sentences[-1]:
                segment_end = segment_start + estimated_duration

                seg = {
                    "id": f"segment-{len(segments)}",
                    "startTime": segment_start,
                    "endTime": segment_end,
                    "text": combined,
                    "transcript": combined
                }
                seg["title"] = generate_step_title(combined, len(segments) + 1)
                segments.append(seg)

                segment_start = segment_end
                current_text = []

        return {"segments": segments}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to segment transcript: {str(e)}"
        )


@router.put("/update")
async def update_transcript(request: UpdateTranscriptRequest):
    """
    Update cleaned transcript segments with user edits.
    This allows users to manually edit the transcript text before regenerating voiceover.
    """
    try:
        logger.info(f"Updating transcript for project {request.projectId} with {len(request.segments)} segments")

        # Get existing cleaned transcript to preserve original text
        existing = await db_get_cleaned_transcript(request.projectId)

        if existing:
            existing_segments = existing.get("segments", [])
            if isinstance(existing_segments, str):
                existing_segments = json.loads(existing_segments)

            # Create a map of existing segments by id for quick lookup
            existing_map = {str(seg.get("id", i)): seg for i, seg in enumerate(existing_segments)}
        else:
            existing_map = {}

        # Build updated segments
        updated_segments = []
        for seg in request.segments:
            # Get original text from existing segment if available
            existing_seg = existing_map.get(seg.id, {})
            original_text = existing_seg.get("original_text", seg.text)

            updated_segments.append({
                "id": seg.id,
                "start": seg.start,
                "end": seg.end,
                "original_text": original_text,
                "cleaned_text": seg.text,  # User edited text becomes the cleaned text
                "voiceover_start": seg.start,
                "voiceover_end": seg.end,
            })

        # Combine into full text
        full_cleaned_text = " ".join(seg["cleaned_text"] for seg in updated_segments)

        # Save to database
        await save_cleaned_transcript(request.projectId, updated_segments, full_cleaned_text)

        logger.info(f"Transcript updated successfully for project {request.projectId}")

        return {
            "success": True,
            "message": "Transcript updated successfully",
            "segmentCount": len(updated_segments)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update transcript: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update transcript: {str(e)}"
        )


