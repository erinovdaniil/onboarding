from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import os
import json
from typing import List, Dict, Optional

from app.database import get_transcript as db_get_transcript

router = APIRouter()


class SegmentTranscriptRequest(BaseModel):
    projectId: str
    segmentDuration: float = 7.0  # Default segment duration in seconds


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


@router.post("/segment")
async def segment_transcript(request: SegmentTranscriptRequest):
    """
    Segment transcript into time-based chunks for step creation.
    Reads from Supabase database.
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

        # If transcript has segments from Whisper, use them
        if transcript_segments and len(transcript_segments) > 0:
            segments = []
            for i, seg in enumerate(transcript_segments):
                segments.append({
                    "id": f"segment-{i}",
                    "startTime": seg.get("start", 0),
                    "endTime": seg.get("end", seg.get("start", 0) + request.segmentDuration),
                    "text": seg.get("text", ""),
                    "transcript": seg.get("text", "")
                })
            return {"segments": segments}

        # Otherwise, segment by duration using full text
        full_text = transcript_record.get("text", "")
        if not full_text:
            return {"segments": []}

        # Simple segmentation by duration (split text roughly by time)
        words = full_text.split()
        words_per_segment = max(10, int(len(words) / (60 / request.segmentDuration)))  # Rough estimate

        segments = []
        current_segment = []
        segment_start = 0.0

        for i, word in enumerate(words):
            current_segment.append(word)

            # Create segment when we reach the word count or at natural breaks
            if len(current_segment) >= words_per_segment or i == len(words) - 1:
                segment_text = " ".join(current_segment)
                segment_end = segment_start + request.segmentDuration

                segments.append({
                    "id": f"segment-{len(segments)}",
                    "startTime": segment_start,
                    "endTime": segment_end,
                    "text": segment_text,
                    "transcript": segment_text
                })

                segment_start = segment_end
                current_segment = []

        return {"segments": segments}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to segment transcript: {str(e)}"
        )
