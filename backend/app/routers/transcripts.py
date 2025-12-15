from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import os
import json
import re
from typing import List, Dict, Optional

from app.database import get_transcript as db_get_transcript

router = APIRouter()


class SegmentTranscriptRequest(BaseModel):
    projectId: str
    segmentDuration: float = 10.0  # Target segment duration (flexible)
    minDuration: float = 5.0  # Minimum segment duration
    maxDuration: float = 20.0  # Maximum segment duration


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
    """
    try:
        # Get transcript from database
        transcript_record = await db_get_transcript(project_id)

        if not transcript_record:
            return {"transcript": None, "message": "No transcript available"}

        # Parse segments if stored as JSON string
        segments = transcript_record.get("segments", [])
        if isinstance(segments, str):
            try:
                segments = json.loads(segments)
            except json.JSONDecodeError:
                segments = []

        transcript = {
            "text": transcript_record.get("text", ""),
            "language": transcript_record.get("language", "en"),
            "segments": segments
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


