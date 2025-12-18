from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import os
import io
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any

from app.storage import upload_file_to_storage, ensure_bucket_exists
from app.database import save_video_file, get_transcript, get_cleaned_transcript

router = APIRouter()

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

# Supabase Storage bucket name
STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "videos")

# Minimum pause duration to consider (in seconds)
MIN_PAUSE_DURATION = 0.3


class PauseConfig(BaseModel):
    enabled: bool
    startTime: float  # seconds into the video where pause should occur
    pauseDuration: float  # how long the silence should be


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class VoiceoverRequest(BaseModel):
    projectId: str
    script: str
    voice: str = "alloy"
    pauseConfigs: Optional[List[PauseConfig]] = None
    videoDuration: Optional[float] = None  # Total video duration for timing calculations
    transcriptSegments: Optional[List[TranscriptSegment]] = None  # For auto-sync
    autoSync: bool = True  # Enable auto-sync by default


def detect_natural_pauses(segments: List[Dict[str, Any]], min_pause: float = MIN_PAUSE_DURATION) -> List[PauseConfig]:
    """
    Detect natural pauses between transcript segments.

    Analyzes gaps between segments to find natural pauses in speech.
    These pauses should be preserved in the generated voiceover.
    """
    pauses = []

    if not segments or len(segments) < 2:
        return pauses

    # Sort segments by start time
    sorted_segments = sorted(segments, key=lambda s: s.get('start', 0))

    for i in range(len(sorted_segments) - 1):
        current_end = sorted_segments[i].get('end', 0)
        next_start = sorted_segments[i + 1].get('start', 0)

        # Calculate gap between segments
        gap = next_start - current_end

        # If gap is significant, it's a natural pause
        if gap >= min_pause:
            pauses.append(PauseConfig(
                enabled=True,
                startTime=current_end,  # Pause starts at end of current segment
                pauseDuration=gap
            ))
            print(f"Detected natural pause at {current_end}s for {gap}s")

    return pauses


def group_words_into_phrases(words: List[Dict[str, Any]], pause_threshold: float = 0.3) -> List[Dict[str, Any]]:
    """
    Group word-level timestamps into natural phrases based on pauses.

    When there's a gap > pause_threshold between words, we start a new phrase.
    This creates natural speech segments that match the original pacing.
    """
    if not words:
        return []

    phrases = []
    current_phrase = {
        "text": "",
        "start": words[0].get("start", 0),
        "end": words[0].get("end", 0),
        "words": []
    }

    for i, word in enumerate(words):
        word_text = word.get("word", "").strip()
        word_start = word.get("start", 0)
        word_end = word.get("end", 0)

        if not word_text:
            continue

        # Check if there's a significant gap from previous word
        if i > 0 and current_phrase["words"]:
            gap = word_start - current_phrase["end"]
            if gap >= pause_threshold:
                # Save current phrase and start new one
                current_phrase["text"] = " ".join(w.get("word", "") for w in current_phrase["words"]).strip()
                if current_phrase["text"]:
                    phrases.append(current_phrase)
                # Start new phrase
                current_phrase = {
                    "text": "",
                    "start": word_start,
                    "end": word_end,
                    "words": []
                }

        # Add word to current phrase
        current_phrase["words"].append(word)
        current_phrase["end"] = word_end

    # Don't forget the last phrase
    if current_phrase["words"]:
        current_phrase["text"] = " ".join(w.get("word", "") for w in current_phrase["words"]).strip()
        if current_phrase["text"]:
            phrases.append(current_phrase)

    return phrases


def generate_segment_based_audio(
    segments: List[Dict[str, Any]],
    voice: str,
    video_duration: float,
    words: List[Dict[str, Any]] = None
) -> bytes:
    """
    Generate voiceover by creating TTS for each phrase and placing
    them at the EXACT timestamps from the original video.

    Priority:
    1. If word-level timestamps available, group into natural phrases
    2. Fall back to segment-level timestamps

    This approach ensures natural pacing by:
    1. Generating audio for each phrase's text
    2. Placing each audio clip at the phrase's start time
    3. Filling gaps with silence (natural pauses from original speech)
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        print("pydub not installed, falling back to simple generation")
        return None

    # Use word-level timestamps if available (more precise)
    if words and len(words) > 1:
        print(f"\n=== Using word-level timestamps ({len(words)} words) ===")
        phrases = group_words_into_phrases(words, pause_threshold=0.25)
        print(f"Grouped into {len(phrases)} natural phrases")
        working_segments = phrases
    elif segments and len(segments) > 1:
        print(f"\n=== Using segment-level timestamps ({len(segments)} segments) ===")
        working_segments = segments
    else:
        print("Not enough segments for timing-based generation")
        return None

    # Sort by start time
    sorted_segments = sorted(working_segments, key=lambda s: s.get('start', 0))

    print(f"Video duration: {video_duration}s")

    # Start with silence from 0 to first segment
    first_start = sorted_segments[0].get('start', 0) if sorted_segments else 0
    if first_start > 0:
        result = AudioSegment.silent(duration=int(first_start * 1000))
        print(f"Initial silence: {first_start:.2f}s")
    else:
        result = AudioSegment.empty()

    current_position_ms = int(first_start * 1000)

    for i, segment in enumerate(sorted_segments):
        seg_start = segment.get('start', 0)
        seg_end = segment.get('end', 0)
        seg_text = segment.get('text', '').strip()

        if not seg_text:
            continue

        seg_start_ms = int(seg_start * 1000)
        seg_duration_ms = int((seg_end - seg_start) * 1000)

        # Add silence gap if needed (natural pause between phrases)
        if seg_start_ms > current_position_ms:
            gap_ms = seg_start_ms - current_position_ms
            silence = AudioSegment.silent(duration=gap_ms)
            result += silence
            current_position_ms = seg_start_ms
            print(f"  [{i}] Gap: {gap_ms}ms silence")

        # Generate TTS audio for this phrase
        try:
            response = openai_client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=seg_text,
            )
            seg_audio = AudioSegment.from_mp3(io.BytesIO(response.content))
            generated_duration_ms = len(seg_audio)

            text_preview = seg_text[:50] + "..." if len(seg_text) > 50 else seg_text
            print(f"  [{i}] [{seg_start:.2f}s-{seg_end:.2f}s] \"{text_preview}\"")
            print(f"       Slot: {seg_duration_ms}ms, Generated: {generated_duration_ms}ms")

            # Handle timing mismatch
            if generated_duration_ms > seg_duration_ms * 1.2:
                # TTS is significantly longer than original - speed up to fit
                speed_factor = generated_duration_ms / seg_duration_ms
                if speed_factor <= 1.5:
                    seg_audio = seg_audio.speedup(playback_speed=speed_factor)
                    print(f"       Sped up {speed_factor:.2f}x to fit")

            result += seg_audio
            current_position_ms += len(seg_audio)

        except Exception as e:
            print(f"  [{i}] Failed: {e}")
            result += AudioSegment.silent(duration=seg_duration_ms)
            current_position_ms += seg_duration_ms

    # Add trailing silence
    final_duration_ms = len(result)
    target_duration_ms = int(video_duration * 1000)

    if target_duration_ms > final_duration_ms:
        trailing_ms = target_duration_ms - final_duration_ms
        result += AudioSegment.silent(duration=trailing_ms)
        print(f"Trailing silence: {trailing_ms}ms")

    print(f"=== Final audio: {len(result)/1000:.1f}s ===\n")

    output = io.BytesIO()
    result.export(output, format="mp3")
    return output.getvalue()


def insert_silences_into_audio(audio_content: bytes, pause_configs: List[PauseConfig], video_duration: float) -> bytes:
    """
    Insert silence gaps into the audio at specified timestamps.

    The approach:
    - The pause startTime represents when the pause should occur in the FINAL output
      (which should match the video timeline)
    - We need to calculate how much original audio plays before each pause point
    - As we insert silences, we track the cumulative offset

    Example:
    - Original audio: 20s
    - Video: 25s
    - Pause at 10s (video time) for 2s
    - The pause should occur at 10s in the final audio
    - So we play 10s of original audio, then 2s silence, then remaining 10s audio
    - Final audio: 22s (10 + 2 + 10)
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        print("pydub not installed, returning original audio")
        return audio_content

    # Load the audio
    audio = AudioSegment.from_mp3(io.BytesIO(audio_content))
    audio_duration_ms = len(audio)
    audio_duration_sec = audio_duration_ms / 1000.0

    print(f"Original audio duration: {audio_duration_sec}s, Video duration: {video_duration}s")

    # Sort pauses by start time
    sorted_pauses = sorted(
        [p for p in pause_configs if p.enabled],
        key=lambda p: p.startTime
    )

    if not sorted_pauses:
        return audio_content

    print(f"Processing {len(sorted_pauses)} pause(s)")

    # Build the new audio with silences inserted
    # The key insight: pause.startTime is where in the FINAL timeline the pause occurs
    # We need to track how much silence we've added to calculate original audio positions
    result = AudioSegment.empty()
    current_original_position_ms = 0  # Position in original audio
    total_silence_added_ms = 0  # Total silence added so far

    for pause in sorted_pauses:
        # pause.startTime is the position in the final output where pause should start
        pause_final_time_ms = int(pause.startTime * 1000)

        # Calculate how much original audio should play before this pause
        # final_time = original_audio_played + silence_added
        # So: original_audio_to_play = final_time - silence_added
        original_audio_end_ms = pause_final_time_ms - total_silence_added_ms

        print(f"Pause at {pause.startTime}s: final_pos={pause_final_time_ms}ms, "
              f"silence_so_far={total_silence_added_ms}ms, "
              f"original_audio_end={original_audio_end_ms}ms")

        # Make sure we don't go past the original audio end or backwards
        if original_audio_end_ms > audio_duration_ms:
            original_audio_end_ms = audio_duration_ms
        if original_audio_end_ms < current_original_position_ms:
            # Pause is before current position (overlapping pauses), skip
            print(f"  Skipping - position would go backwards")
            continue

        # Add audio from current position to pause point
        if original_audio_end_ms > current_original_position_ms:
            chunk = audio[current_original_position_ms:original_audio_end_ms]
            result += chunk
            print(f"  Added audio chunk: {current_original_position_ms}ms to {original_audio_end_ms}ms ({len(chunk)}ms)")

        # Add silence
        silence_duration_ms = int(pause.pauseDuration * 1000)
        silence = AudioSegment.silent(duration=silence_duration_ms)
        result += silence
        total_silence_added_ms += silence_duration_ms
        print(f"  Added silence: {silence_duration_ms}ms")

        # Move current position in original audio
        current_original_position_ms = original_audio_end_ms

    # Add remaining audio after the last pause
    if current_original_position_ms < audio_duration_ms:
        remaining = audio[current_original_position_ms:]
        result += remaining
        print(f"Added remaining audio: {current_original_position_ms}ms to end ({len(remaining)}ms)")

    print(f"Final audio duration: {len(result)/1000}s")

    # Export to bytes
    output = io.BytesIO()
    result.export(output, format="mp3")
    return output.getvalue()


@router.post("/generate")
async def generate_voiceover(request: VoiceoverRequest):
    """
    Generate AI voiceover from script text.

    Features:
    - Auto-sync: Automatically detect natural pauses from transcript and preserve them
    - Manual pauses: Insert silence gaps at specified timestamps
    - Segment-based: Generate audio per transcript segment for better timing
    """
    if not openai_client:
        raise HTTPException(
            status_code=500,
            detail="OpenAI API key not configured"
        )

    if not request.script:
        raise HTTPException(status_code=400, detail="No script provided")

    try:
        audio_content = None

        # Try auto-sync approach first if enabled
        if request.autoSync and request.videoDuration:
            import json
            from app.pipeline import generate_segmented_voiceover

            # First, check for CLEANED transcript (preferred - has improved text)
            cleaned_record = await get_cleaned_transcript(request.projectId)

            if cleaned_record:
                # Use cleaned transcript segments for voiceover
                cleaned_segments = cleaned_record.get("segments", [])
                if isinstance(cleaned_segments, str):
                    try:
                        cleaned_segments = json.loads(cleaned_segments)
                    except json.JSONDecodeError:
                        cleaned_segments = []

                if cleaned_segments:
                    print(f"Using CLEANED transcript ({len(cleaned_segments)} segments) for voiceover")

                    # Use the pipeline's time-synced voiceover generation
                    audio_url = await generate_segmented_voiceover(
                        request.projectId,
                        cleaned_segments,
                        request.voice or "alloy"
                    )

                    if audio_url:
                        return {
                            "success": True,
                            "audioUrl": audio_url,
                        }

            # Fallback: Try to get original transcript segments
            segments = None
            if request.transcriptSegments:
                segments = [s.dict() for s in request.transcriptSegments]
            else:
                # Fetch transcript from database
                words = None
                transcript_record = await get_transcript(request.projectId)

                if transcript_record:
                    # Try to get word-level timestamps first (most precise)
                    if transcript_record.get('words'):
                        words_data = transcript_record['words']
                        if isinstance(words_data, str):
                            try:
                                words = json.loads(words_data)
                            except json.JSONDecodeError:
                                words = []
                        else:
                            words = words_data
                        if words:
                            print(f"Loaded {len(words)} word-level timestamps from database")

                    # Also get segments as fallback
                    if transcript_record.get('segments'):
                        segments_data = transcript_record['segments']
                        if isinstance(segments_data, str):
                            try:
                                segments = json.loads(segments_data)
                            except json.JSONDecodeError:
                                segments = []
                        else:
                            segments = segments_data
                        if segments:
                            print(f"Loaded {len(segments)} segments from database")

            # Generate audio using word-level or segment-level timestamps
            if words or (segments and len(segments) > 1):
                print(f"Using timing-based generation (original transcript)")

                # Generate TTS for each phrase and place at original timestamps
                audio_content = generate_segment_based_audio(
                    segments,
                    request.voice or "alloy",
                    request.videoDuration,
                    words=words
                )

        # Fallback: Simple generation without auto-sync
        if audio_content is None:
            response = openai_client.audio.speech.create(
                model="tts-1",
                voice=request.voice or "alloy",
                input=request.script,
            )
            audio_content = response.content

            # Apply manual pauses only
            if request.pauseConfigs and request.videoDuration:
                enabled_pauses = [p for p in request.pauseConfigs if p.enabled]
                if enabled_pauses:
                    print(f"Inserting {len(enabled_pauses)} manual pause(s)")
                    audio_content = insert_silences_into_audio(
                        audio_content,
                        request.pauseConfigs,
                        request.videoDuration
                    )

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
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate voiceover: {str(e)}"
        )

