"""
Automatic Video Processing Pipeline

This module orchestrates the complete video processing pipeline:
1. Clean transcript segments with AI (GPT-4)
2. Generate voiceover from cleaned script (OpenAI TTS)
3. Process video with voiceover and avatar overlay (FFmpeg)

Status tracking via database, error handling with graceful degradation.
"""

import logging
import os
from typing import List, Dict, Any, Optional
from openai import OpenAI

from app.database import (
    get_transcript,
    get_project,
    save_cleaned_transcript,
    update_project_status
)

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None


def merge_segments_into_sentences(whisper_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge Whisper's arbitrary segments into natural sentence groups.

    Whisper often breaks text mid-sentence. This function groups segments
    together until we hit a sentence boundary (. ! ?) or a long pause (>0.5s).

    This ensures each segment contains complete thoughts/sentences.
    """
    import re

    if not whisper_segments:
        return []

    merged_segments = []
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

        combined_text = " ".join(current_text_parts)

        # Check if we should end this segment group
        should_end = False

        # 1. Check for sentence ending (. ! ?)
        ends_with_sentence = bool(re.search(r'[.!?]$', seg_text))

        # 2. Check for long pause before next segment (> 0.5s)
        has_long_pause = False
        if i + 1 < len(whisper_segments):
            next_start = whisper_segments[i + 1].get("start", seg_end)
            pause_duration = next_start - seg_end
            has_long_pause = pause_duration > 0.5

        # End group if we hit a sentence boundary or long pause
        if ends_with_sentence or has_long_pause:
            should_end = True

        # Last segment - always end
        if i == len(whisper_segments) - 1:
            should_end = True

        if should_end and current_group:
            merged_segments.append({
                "id": len(merged_segments),
                "start": current_start,
                "end": seg_end,
                "text": combined_text
            })
            current_group = []
            current_text_parts = []
            current_start = None

    return merged_segments


async def clean_transcript_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Clean each transcript segment individually using GPT-4.
    Preserves start/end timestamps while improving text quality.

    Args:
        segments: List of {id, start, end, text} from Whisper API

    Returns:
        List of {id, start, end, original_text, cleaned_text}
    """
    if not openai_client:
        logger.warning("OpenAI API key not configured, skipping text cleaning")
        # Return segments with cleaned_text = original text
        return [
            {
                "id": seg.get("id"),
                "start": seg.get("start"),
                "end": seg.get("end"),
                "original_text": seg.get("text"),
                "cleaned_text": seg.get("text")
            }
            for seg in segments
        ]

    cleaned_segments = []

    for i, segment in enumerate(segments):
        try:
            logger.info(f"Cleaning segment {i+1}/{len(segments)}")

            # Use GPT-4 to clean text while preserving meaning and natural speech
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a transcript cleaner. Your ONLY job is to remove filler words while keeping everything else exactly the same.\n\n"
                            "REMOVE these filler words:\n"
                            "- um, uh, er, ah, hmm, mm\n"
                            "- like (when used as filler, not comparison)\n"
                            "- you know, I mean, sort of, kind of (when used as fillers)\n"
                            "- so (at the start of sentences when used as filler)\n"
                            "- basically, actually, literally (when not adding meaning)\n\n"
                            "RULES:\n"
                            "- Keep the EXACT same meaning - do not rephrase or rewrite\n"
                            "- Keep plain, simple English - do not make it sound formal or professional\n"
                            "- Keep the natural conversational tone\n"
                            "- Only fix obvious grammar mistakes, not style\n"
                            "- Do NOT add words or elaborate\n"
                            "- Do NOT change technical terms\n\n"
                            "Output ONLY the cleaned text, nothing else."
                        )
                    },
                    {
                        "role": "user",
                        "content": segment.get("text", "")
                    }
                ],
                max_tokens=500,
                temperature=0.1  # Very low creativity - just clean, don't rewrite
            )

            cleaned_text = response.choices[0].message.content.strip()

            cleaned_segments.append({
                "id": segment.get("id"),
                "start": segment.get("start"),
                "end": segment.get("end"),
                "original_text": segment.get("text"),
                "cleaned_text": cleaned_text
            })

        except Exception as e:
            logger.error(f"Error cleaning segment {i}: {e}")
            # Fallback: use original text
            cleaned_segments.append({
                "id": segment.get("id"),
                "start": segment.get("start"),
                "end": segment.get("end"),
                "original_text": segment.get("text"),
                "cleaned_text": segment.get("text")  # Fallback to original
            })

    return cleaned_segments


def get_audio_duration(audio_path: str) -> float:
    """Get duration of an audio file using ffprobe."""
    import subprocess
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ], capture_output=True, timeout=30)
        if result.returncode == 0:
            return float(result.stdout.decode().strip())
    except Exception as e:
        logger.warning(f"Could not get audio duration: {e}")
    return 0.0


async def generate_segmented_voiceover(
    project_id: str,
    segments: List[Dict[str, Any]],
    voice: str = "alloy"
) -> Optional[str]:
    """
    Generate voiceover audio that matches original video timing exactly.

    Workflow for each segment:
    1. Original audio 00:00 - 00:03 (3 seconds)
    2. Transcribe: "Um, so like, click here"
    3. Clean with AI: "Click here"
    4. Generate TTS (maybe 1.5s naturally)
    5. Adjust to EXACTLY match original duration (3 seconds)
       - If TTS shorter: add silence padding at the end
       - If TTS longer: speed up (max 1.5x) then pad if needed

    This ensures voiceover syncs perfectly with the original video.

    Args:
        project_id: UUID of the project
        segments: List of cleaned segments with original start/end timestamps
        voice: OpenAI TTS voice name

    Returns:
        URL of the generated voiceover audio, or None if failed
    """
    import subprocess
    import tempfile
    from pathlib import Path

    try:
        logger.info(f"Generating time-synced voiceover for project {project_id} with {len(segments)} segments")

        if not openai_client:
            raise Exception("OpenAI API key not configured")

        from app.storage import upload_file_to_storage, ensure_bucket_exists
        from app.database import save_video_file

        STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "videos")
        ensure_bucket_exists(STORAGE_BUCKET, public=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            segment_files = []
            processed_segments = []  # Track segments we actually process

            for i, seg in enumerate(segments):
                cleaned_text = seg.get("cleaned_text", seg.get("text", ""))
                if not cleaned_text.strip():
                    logger.warning(f"Segment {i} has no text, skipping")
                    continue

                # Get original timing - this is what we must match
                original_start = seg.get("start", 0)
                original_end = seg.get("end", 0)
                target_duration = original_end - original_start

                if target_duration <= 0:
                    logger.warning(f"Segment {i} has invalid duration ({target_duration}s), skipping")
                    continue

                logger.info(f"Segment {i+1}/{len(segments)}: {original_start:.2f}s - {original_end:.2f}s ({target_duration:.2f}s)")
                logger.info(f"  Text: '{cleaned_text[:60]}...'")

                # Generate TTS for this segment
                try:
                    response = openai_client.audio.speech.create(
                        model="tts-1",
                        voice=voice,
                        input=cleaned_text
                    )
                except Exception as e:
                    logger.error(f"TTS failed for segment {i}: {e}")
                    continue

                # Save raw TTS to temp file
                raw_file = temp_path / f"seg_{i}_raw.mp3"
                with open(raw_file, "wb") as f:
                    f.write(response.content)

                # Get actual TTS duration
                tts_duration = get_audio_duration(str(raw_file))
                logger.info(f"  TTS duration: {tts_duration:.2f}s, target: {target_duration:.2f}s")

                # Adjust audio to EXACTLY match target duration
                final_file = temp_path / f"seg_{i}_final.mp3"

                if abs(tts_duration - target_duration) < 0.1:
                    # Close enough (within 100ms), use as-is
                    logger.info(f"  Duration close enough, using as-is")
                    final_file = raw_file

                elif tts_duration < target_duration:
                    # TTS is shorter - add silence padding at the end
                    pad_duration = target_duration - tts_duration
                    logger.info(f"  Adding {pad_duration:.2f}s silence padding")

                    result = subprocess.run([
                        "ffmpeg", "-i", str(raw_file),
                        "-af", f"apad=pad_dur={pad_duration}",
                        "-y", str(final_file)
                    ], capture_output=True, timeout=30)

                    if result.returncode != 0 or not final_file.exists():
                        logger.warning(f"  Padding failed, using raw file")
                        final_file = raw_file

                else:
                    # TTS is longer - need to speed up
                    speed_factor = tts_duration / target_duration

                    if speed_factor <= 1.5:
                        # Speed up is acceptable (max 1.5x)
                        logger.info(f"  Speeding up by {speed_factor:.2f}x")

                        result = subprocess.run([
                            "ffmpeg", "-i", str(raw_file),
                            "-af", f"atempo={speed_factor}",
                            "-y", str(final_file)
                        ], capture_output=True, timeout=30)

                        if result.returncode == 0 and final_file.exists():
                            # Check if we need additional padding after speedup
                            new_duration = get_audio_duration(str(final_file))
                            if new_duration < target_duration - 0.1:
                                pad_duration = target_duration - new_duration
                                padded_file = temp_path / f"seg_{i}_padded.mp3"
                                subprocess.run([
                                    "ffmpeg", "-i", str(final_file),
                                    "-af", f"apad=pad_dur={pad_duration}",
                                    "-y", str(padded_file)
                                ], capture_output=True, timeout=30)
                                if padded_file.exists():
                                    final_file = padded_file
                        else:
                            logger.warning(f"  Speedup failed, using raw file")
                            final_file = raw_file
                    else:
                        # Speed factor too high - speed up to 1.5x max, then truncate
                        logger.info(f"  Speed factor {speed_factor:.2f}x too high, using 1.5x and truncating")

                        sped_file = temp_path / f"seg_{i}_sped.mp3"
                        subprocess.run([
                            "ffmpeg", "-i", str(raw_file),
                            "-af", "atempo=1.5",
                            "-y", str(sped_file)
                        ], capture_output=True, timeout=30)

                        # Truncate to target duration
                        if sped_file.exists():
                            subprocess.run([
                                "ffmpeg", "-i", str(sped_file),
                                "-t", str(target_duration),
                                "-y", str(final_file)
                            ], capture_output=True, timeout=30)

                        if not final_file.exists():
                            final_file = raw_file

                # Verify final duration
                final_duration = get_audio_duration(str(final_file))
                logger.info(f"  Final segment duration: {final_duration:.2f}s")

                segment_files.append(str(final_file))
                processed_segments.append({
                    **seg,
                    "voiceover_start": original_start,  # Same as original!
                    "voiceover_end": original_end,
                })

            if not segment_files:
                raise Exception("No audio segments generated")

            # Now we need to create the final audio file with correct timing
            # Add silence between segments if there are gaps in the original timestamps

            # Sort segments by start time
            processed_segments.sort(key=lambda x: x.get("start", 0))

            # Build final audio with gaps preserved
            final_audio_parts = []
            current_time = 0.0

            for i, seg in enumerate(processed_segments):
                seg_start = seg.get("start", 0)
                seg_end = seg.get("end", 0)

                # Add silence for gap before this segment
                gap_before = seg_start - current_time
                if gap_before > 0.05:  # Only add silence if gap > 50ms
                    silence_file = temp_path / f"silence_{i}.mp3"
                    subprocess.run([
                        "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-t", str(gap_before),
                        "-c:a", "libmp3lame", "-q:a", "2",
                        "-y", str(silence_file)
                    ], capture_output=True, timeout=30)
                    if silence_file.exists():
                        final_audio_parts.append(str(silence_file))
                        logger.info(f"Added {gap_before:.2f}s silence before segment {i+1}")

                # Add the segment audio
                final_audio_parts.append(segment_files[i])
                current_time = seg_end

            # Create concat list
            concat_list_file = temp_path / "concat_list.txt"
            with open(concat_list_file, "w") as f:
                for path in final_audio_parts:
                    f.write(f"file '{path}'\n")

            # Concatenate all parts
            output_file = temp_path / "voiceover.mp3"
            concat_result = subprocess.run([
                "ffmpeg", "-f", "concat", "-safe", "0",
                "-i", str(concat_list_file),
                "-c:a", "libmp3lame", "-q:a", "2",
                "-y", str(output_file)
            ], capture_output=True, timeout=120)

            if concat_result.returncode != 0:
                logger.error(f"FFmpeg concat failed: {concat_result.stderr.decode()}")
                raise Exception("Failed to concatenate audio segments")

            # Save cleaned transcript with timestamps (same as original since we're synced)
            try:
                full_cleaned_text = " ".join([seg["cleaned_text"] for seg in processed_segments])
                await save_cleaned_transcript(project_id, processed_segments, full_cleaned_text)
                logger.info(f"Saved cleaned_transcripts with synced timestamps")
            except Exception as e:
                logger.warning(f"Could not save cleaned_transcripts: {e}")

            # Read final audio
            with open(output_file, "rb") as f:
                audio_content = f.read()

            total_duration = get_audio_duration(str(output_file))
            logger.info(f"Final voiceover duration: {total_duration:.2f}s")

            # Upload to Supabase Storage
            storage_path = f"{project_id}/voiceover.mp3"
            audio_url = await upload_file_to_storage(
                bucket_name=STORAGE_BUCKET,
                file_path=storage_path,
                file_content=audio_content,
                content_type="audio/mpeg"
            )

            # Save metadata
            await save_video_file(project_id, "audio", storage_path, len(audio_content))

            logger.info(f"Time-synced voiceover generated successfully: {audio_url}")
            return audio_url

    except Exception as e:
        logger.error(f"Error generating voiceover: {e}", exc_info=True)
        return None


async def generate_voiceover_internal(
    project_id: str,
    script: str,
    voice: str = "alloy"
) -> Optional[str]:
    """
    Generate voiceover audio using OpenAI TTS (simple version).
    This is a fallback when segments aren't available.

    Args:
        project_id: UUID of the project
        script: Cleaned script text
        voice: OpenAI TTS voice name

    Returns:
        URL of the generated voiceover audio, or None if failed
    """
    try:
        logger.info(f"Generating simple voiceover for project {project_id} with voice '{voice}'")

        if not openai_client:
            raise Exception("OpenAI API key not configured")

        from app.storage import upload_file_to_storage, ensure_bucket_exists
        from app.database import save_video_file

        # Ensure bucket exists
        STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "videos")
        ensure_bucket_exists(STORAGE_BUCKET, public=True)

        # Generate audio with OpenAI TTS
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=script
        )

        # Read audio content
        audio_content = response.content

        # Upload to Supabase Storage
        storage_path = f"{project_id}/voiceover.mp3"
        audio_url = await upload_file_to_storage(
            bucket_name=STORAGE_BUCKET,
            file_path=storage_path,
            file_content=audio_content,
            content_type="audio/mpeg"
        )

        # Save metadata
        await save_video_file(project_id, "audio", storage_path, len(audio_content))

        logger.info(f"Voiceover generated successfully: {audio_url}")
        return audio_url

    except Exception as e:
        logger.error(f"Error generating voiceover: {e}")
        return None


async def process_video_internal(project_id: str, enable_cursor_zoom: bool = True) -> Optional[str]:
    """
    Process video with voiceover, avatar overlay, and optional cursor zoom using FFmpeg.
    This is an internal function called by the pipeline.

    Args:
        project_id: UUID of the project
        enable_cursor_zoom: Whether to apply cursor-following zoom effect

    Returns:
        URL of the processed video, or None if failed
    """
    try:
        logger.info(f"Processing video for project {project_id} (cursor_zoom={enable_cursor_zoom})")

        from app.storage import download_file_from_storage, upload_file_to_storage
        from app.database import get_video_files, save_video_file, get_project
        from pathlib import Path
        import tempfile
        import subprocess

        STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "videos")

        # Get video files from database
        video_files = await get_video_files(project_id)

        # Find original video
        original_file = next((f for f in video_files if f.get("file_type") == "original"), None)
        if not original_file:
            logger.error(f"Original video not found for project {project_id}")
            return None

        original_storage_path = original_file.get("storage_path")
        if not original_storage_path:
            logger.error("Original video storage path not found")
            return None

        # Find voiceover file (required)
        voiceover_file = next((f for f in video_files if f.get("file_type") == "audio"), None)
        if not voiceover_file:
            logger.error("Voiceover file not found - required for processing")
            return None

        # Get avatar config from project metadata
        project = await get_project(project_id)
        avatar_config = {"position": "bottom-right", "size": "medium"}  # Default
        if project:
            avatar_config_json = project.get("avatar_config")
            if avatar_config_json:
                import json
                if isinstance(avatar_config_json, str):
                    avatar_config = json.loads(avatar_config_json)
                else:
                    avatar_config = avatar_config_json

        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Download original video (may be MP4 if converted during upload)
            original_video_content = await download_file_from_storage(STORAGE_BUCKET, original_storage_path)
            # Use the correct extension from storage path
            original_ext = Path(original_storage_path).suffix or ".mp4"
            original_video_path = temp_path / f"original{original_ext}"
            with open(original_video_path, "wb") as f:
                f.write(original_video_content)

            # Download voiceover
            voiceover_storage_path = voiceover_file.get("storage_path")
            voiceover_content = await download_file_from_storage(STORAGE_BUCKET, voiceover_storage_path)
            voiceover_path = temp_path / "voiceover.mp3"
            with open(voiceover_path, "wb") as f:
                f.write(voiceover_content)

            # Use default static avatar
            default_avatar_path = Path(__file__).parent / "static" / "default_avatar.png"
            if not default_avatar_path.exists():
                logger.warning(f"Default avatar not found at {default_avatar_path}")
                avatar_path = None
            else:
                avatar_path = default_avatar_path

            # Detect cursor positions if cursor zoom is enabled
            cursor_positions = None
            zoom_filter = None
            if enable_cursor_zoom:
                try:
                    from app.cursor_zoom import detect_cursor_positions as detect_cursor, generate_zoompan_filter
                    import cv2

                    logger.info("Detecting cursor positions for zoom effect...")
                    cursor_positions = await detect_cursor(
                        original_video_path,
                        frame_skip=3,  # Process every 3rd frame for speed
                        downsample_factor=2  # Downscale for speed
                    )

                    if cursor_positions:
                        # Get video properties for zoom filter
                        cap = cv2.VideoCapture(str(original_video_path))
                        vid_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        vid_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        vid_fps = cap.get(cv2.CAP_PROP_FPS)
                        cap.release()

                        zoom_filter = generate_zoompan_filter(
                            cursor_positions,
                            vid_width,
                            vid_height,
                            vid_fps,
                            base_zoom=1.0,  # No zoom by default
                            max_zoom=1.5    # Zoom in to 1.5x when pointing
                        )
                        if zoom_filter:
                            logger.info("Cursor zoom filter generated successfully")
                        else:
                            logger.info("No zoom events detected")
                except Exception as e:
                    logger.warning(f"Cursor zoom detection failed, proceeding without zoom: {e}")
                    enable_cursor_zoom = False

            # Get video duration using FFprobe (reliable for WebM/VP9)
            # OpenCV's CAP_PROP_FRAME_COUNT is unreliable for WebM files
            video_duration = 0.0
            video_fps = 30.0
            try:
                # Strategy 1: Get duration from format and stream info
                probe_cmd = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-show_entries", "stream=duration,r_frame_rate,nb_frames",
                    "-of", "json",
                    str(original_video_path)
                ]
                probe_result = subprocess.run(probe_cmd, capture_output=True, timeout=30)
                if probe_result.returncode == 0:
                    import json as json_module
                    probe_data = json_module.loads(probe_result.stdout.decode())

                    # Try to get duration from format first
                    if "format" in probe_data and "duration" in probe_data["format"]:
                        try:
                            video_duration = float(probe_data["format"]["duration"])
                        except (ValueError, TypeError):
                            pass

                    # If format duration is 0 or missing, try stream duration
                    if video_duration <= 0 and "streams" in probe_data:
                        for stream in probe_data["streams"]:
                            if "duration" in stream:
                                try:
                                    stream_dur = float(stream["duration"])
                                    if stream_dur > 0:
                                        video_duration = stream_dur
                                        break
                                except (ValueError, TypeError):
                                    pass

                    # Get fps from stream
                    if "streams" in probe_data and len(probe_data["streams"]) > 0:
                        fps_str = probe_data["streams"][0].get("r_frame_rate", "30/1")
                        if "/" in fps_str:
                            num, den = fps_str.split("/")
                            video_fps = float(num) / float(den) if float(den) > 0 else 30.0
                        else:
                            video_fps = float(fps_str)

                        # If still no duration, calculate from nb_frames and fps
                        if video_duration <= 0:
                            nb_frames = probe_data["streams"][0].get("nb_frames")
                            if nb_frames and video_fps > 0:
                                try:
                                    video_duration = int(nb_frames) / video_fps
                                except (ValueError, TypeError):
                                    pass

                    logger.info(f"FFprobe result: duration={video_duration:.2f}s, fps={video_fps:.2f}")

                # Strategy 2: If still no duration, use ffprobe with -count_frames (slower but reliable)
                if video_duration <= 0:
                    logger.info("Format/stream duration not available, counting frames...")
                    probe_cmd2 = [
                        "ffprobe", "-v", "error",
                        "-select_streams", "v:0",
                        "-count_frames",
                        "-show_entries", "stream=nb_read_frames,r_frame_rate",
                        "-of", "json",
                        str(original_video_path)
                    ]
                    probe_result2 = subprocess.run(probe_cmd2, capture_output=True, timeout=120)
                    if probe_result2.returncode == 0:
                        probe_data2 = json_module.loads(probe_result2.stdout.decode())
                        if "streams" in probe_data2 and len(probe_data2["streams"]) > 0:
                            nb_read_frames = probe_data2["streams"][0].get("nb_read_frames")
                            fps_str = probe_data2["streams"][0].get("r_frame_rate", "30/1")
                            if "/" in fps_str:
                                num, den = fps_str.split("/")
                                video_fps = float(num) / float(den) if float(den) > 0 else 30.0
                            if nb_read_frames and video_fps > 0:
                                video_duration = int(nb_read_frames) / video_fps
                                logger.info(f"Counted {nb_read_frames} frames, duration={video_duration:.2f}s")

                logger.info(f"Original video duration: {video_duration:.2f}s at {video_fps:.2f} fps (via ffprobe)")
            except Exception as e:
                logger.warning(f"FFprobe failed, falling back to OpenCV: {e}")
                # Fallback to OpenCV (may not be accurate for WebM)
                import cv2
                cap = cv2.VideoCapture(str(original_video_path))
                video_fps = cap.get(cv2.CAP_PROP_FPS)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if video_fps > 0 and video_fps <= 120 and total_frames > 0:
                    video_duration = total_frames / video_fps
                cap.release()
                logger.info(f"Original video duration: {video_duration:.2f}s (via OpenCV fallback)")

            # If duration is still invalid, skip apad filter
            if video_duration <= 0:
                logger.warning("Could not determine video duration, will skip audio padding")
                video_duration = 0

            # Build FFmpeg command - preserve full video duration
            processed_video_path = temp_path / "processed.mp4"
            ffmpeg_cmd = [
                "ffmpeg",
                "-i", str(original_video_path),
                "-i", str(voiceover_path)
            ]

            # Add avatar overlay if available
            if avatar_path and avatar_path.exists():
                position = avatar_config.get("position", "bottom-right")
                size = avatar_config.get("size", "medium")

                # Scale avatar based on size
                scale_map = {
                    "small": "0.15",
                    "medium": "0.2",
                    "large": "0.25",
                }
                scale = scale_map.get(size, scale_map["medium"])

                # Position overlay
                position_map = {
                    "bottom-right": "W-w-20:H-h-20",
                    "bottom-left": "20:H-h-20",
                    "top-right": "W-w-20:20",
                    "top-left": "20:20",
                }
                overlay_pos = position_map.get(position, position_map["bottom-right"])

                # Build filter_complex with optional zoom
                # Audio filter: pad voiceover with silence to match video duration (if known)
                use_apad = video_duration > 0

                if zoom_filter and enable_cursor_zoom:
                    # Zoom video first, then add avatar
                    if use_apad:
                        filter_complex = (
                            f"[0:v]{zoom_filter}[zoomed];"
                            f"[2:v]scale=iw*{scale}:ih*{scale}[avatar];"
                            f"[zoomed][avatar]overlay={overlay_pos}:shortest=1[v];"
                            f"[1:a]apad=whole_dur={video_duration}[a]"
                        )
                    else:
                        filter_complex = (
                            f"[0:v]{zoom_filter}[zoomed];"
                            f"[2:v]scale=iw*{scale}:ih*{scale}[avatar];"
                            f"[zoomed][avatar]overlay={overlay_pos}:shortest=1[v]"
                        )
                else:
                    # No zoom, just avatar overlay
                    if use_apad:
                        filter_complex = (
                            f"[2:v]scale=iw*{scale}:ih*{scale}[avatar];"
                            f"[0:v][avatar]overlay={overlay_pos}:shortest=1[v];"
                            f"[1:a]apad=whole_dur={video_duration}[a]"
                        )
                    else:
                        filter_complex = (
                            f"[2:v]scale=iw*{scale}:ih*{scale}[avatar];"
                            f"[0:v][avatar]overlay={overlay_pos}:shortest=1[v]"
                        )

                # Loop static image for video duration and overlay
                ffmpeg_cmd.extend([
                    "-loop", "1",  # Loop static image
                    "-i", str(avatar_path),
                    "-filter_complex",
                    filter_complex,
                    "-map", "[v]",
                ])

                if use_apad:
                    ffmpeg_cmd.extend(["-map", "[a]"])  # Use padded audio
                else:
                    ffmpeg_cmd.extend(["-map", "1:a:0", "-shortest"])  # Use voiceover directly with -shortest

                ffmpeg_cmd.extend([
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-y",
                    str(processed_video_path)
                ])
            else:
                # No avatar - apply zoom if available, otherwise just combine
                use_apad = video_duration > 0

                if zoom_filter and enable_cursor_zoom:
                    if use_apad:
                        # Pad audio to match video duration
                        filter_complex = (
                            f"[0:v]{zoom_filter}[v];"
                            f"[1:a]apad=whole_dur={video_duration}[a]"
                        )
                        ffmpeg_cmd.extend([
                            "-filter_complex",
                            filter_complex,
                            "-map", "[v]",
                            "-map", "[a]",  # Use padded audio
                            "-c:v", "libx264",
                            "-c:a", "aac",
                            "-y",
                            str(processed_video_path)
                        ])
                    else:
                        # No duration known, use -shortest
                        filter_complex = f"[0:v]{zoom_filter}[v]"
                        ffmpeg_cmd.extend([
                            "-filter_complex",
                            filter_complex,
                            "-map", "[v]",
                            "-map", "1:a:0",
                            "-shortest",
                            "-c:v", "libx264",
                            "-c:a", "aac",
                            "-y",
                            str(processed_video_path)
                        ])
                else:
                    # No zoom, no avatar - just combine video and voiceover
                    if use_apad:
                        filter_complex = f"[1:a]apad=whole_dur={video_duration}[a]"
                        ffmpeg_cmd.extend([
                            "-filter_complex",
                            filter_complex,
                            "-map", "0:v:0",  # Video from original
                            "-map", "[a]",  # Use padded audio
                            "-c:v", "libx264",
                            "-c:a", "aac",
                            "-y",
                            str(processed_video_path)
                        ])
                    else:
                        # No duration known, use -shortest
                        ffmpeg_cmd.extend([
                            "-map", "0:v:0",
                            "-map", "1:a:0",
                            "-shortest",
                            "-c:v", "libx264",
                            "-c:a", "aac",
                            "-y",
                            str(processed_video_path)
                        ])

            # Execute FFmpeg
            try:
                logger.info(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")
                result = subprocess.run(
                    ffmpeg_cmd,
                    check=True,
                    capture_output=True,
                    timeout=300
                )
                logger.info("FFmpeg processing completed successfully")

            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg error: {e.stderr.decode()}")
                return None
            except subprocess.TimeoutExpired:
                logger.error("FFmpeg processing timed out")
                return None
            except FileNotFoundError:
                logger.error("FFmpeg not found. Please install: brew install ffmpeg")
                return None

            # Upload processed video to Supabase Storage
            if processed_video_path.exists():
                with open(processed_video_path, "rb") as f:
                    processed_video_content = f.read()

                processed_storage_path = f"{project_id}/processed.mp4"
                processed_video_url = await upload_file_to_storage(
                    bucket_name=STORAGE_BUCKET,
                    file_path=processed_storage_path,
                    file_content=processed_video_content,
                    content_type="video/mp4"
                )

                # Save processed video file metadata
                await save_video_file(
                    project_id=project_id,
                    file_type="processed",
                    storage_path=processed_storage_path,
                    file_size=len(processed_video_content)
                )

                logger.info(f"Video processed successfully: {processed_video_url}")
                return processed_video_url
            else:
                logger.error("Processed video file not found")
                return None

    except Exception as e:
        logger.error(f"Error processing video: {e}", exc_info=True)
        return None


async def run_automatic_pipeline(project_id: str, user_id: Optional[str] = None, transcript_data: Optional[Dict[str, Any]] = None):
    """
    Main pipeline orchestration function.
    Runs all stages of video processing automatically after upload.

    Pipeline stages:
    1. Clean transcript segments (preserve timestamps)
    2. Generate voiceover from cleaned script
    3. Process video with voiceover + avatar overlay

    Updates project status at each stage for frontend progress display.
    Handles errors gracefully with fallbacks where possible.

    Args:
        project_id: UUID of the project to process
        user_id: Optional user ID for logging/tracking
        transcript_data: Optional transcript data passed directly (avoids DB read issues)
    """
    try:
        logger.info(f"Starting automatic pipeline for project {project_id}")

        # Get project and transcript
        project = await get_project(project_id, user_id=user_id)
        if not project:
            logger.error(f"Project {project_id} not found")
            return

        # Use passed transcript_data if available, otherwise fetch from DB
        transcript_record = transcript_data
        if not transcript_record:
            transcript_record = await get_transcript(project_id)

        if not transcript_record:
            logger.error(f"No transcript found for project {project_id}")
            await update_project_status(
                project_id,
                "error",
                error_message="No transcript available for processing"
            )
            return

        # Parse segments from transcript
        import json
        raw_segments = transcript_record.get("segments", [])
        if isinstance(raw_segments, str):
            raw_segments = json.loads(raw_segments)

        if not raw_segments:
            logger.warning(f"No segments in transcript for project {project_id}")
            # Use full text as single segment
            raw_segments = [{
                "id": 0,
                "start": 0.0,
                "end": 0.0,
                "text": transcript_record.get("text", "")
            }]

        # Merge Whisper segments into natural sentence groups
        # This prevents breaking sentences in the middle
        segments = merge_segments_into_sentences(raw_segments)
        logger.info(f"Merged {len(raw_segments)} raw segments into {len(segments)} sentence groups")

        # ============================================================
        # STAGE 1: Clean Transcript
        # ============================================================
        logger.info("Stage 1: Cleaning transcript segments")
        await update_project_status(project_id, "cleaning", processing_step="Cleaning transcript with AI")

        try:
            cleaned_segments = await clean_transcript_segments(segments)

            # Combine cleaned segments into full script
            full_cleaned_text = " ".join([seg["cleaned_text"] for seg in cleaned_segments])

            # Save cleaned transcript
            await save_cleaned_transcript(project_id, cleaned_segments, full_cleaned_text)

            # Update project with cleaned script
            from app.database import update_project
            await update_project(project_id, {"cleaned_script": full_cleaned_text})

            logger.info(f"Transcript cleaned successfully: {len(cleaned_segments)} segments")
            await update_project_status(project_id, "cleaned")

        except Exception as e:
            logger.error(f"Transcript cleaning failed: {e}")
            # Fallback: use original transcript
            full_cleaned_text = transcript_record.get("text", "")
            logger.warning("Using original transcript as fallback")

        # ============================================================
        # STAGE 2: Generate Voiceover (Segment-Based for Timing)
        # ============================================================
        logger.info("Stage 2: Generating voiceover with segment timing")
        await update_project_status(project_id, "generating_voiceover", processing_step="Generating AI voiceover")

        try:
            voice = project.get("voiceover_voice", "alloy")

            # Use segmented voiceover generation to match original timing
            # This adds silence padding between segments to preserve video duration
            if cleaned_segments and len(cleaned_segments) > 0:
                logger.info(f"Using segmented voiceover with {len(cleaned_segments)} segments")
                voiceover_url = await generate_segmented_voiceover(project_id, cleaned_segments, voice)
            else:
                # Fallback to simple voiceover if no segments
                logger.info("No segments available, using simple voiceover generation")
                voiceover_url = await generate_voiceover_internal(project_id, full_cleaned_text, voice)

            if not voiceover_url:
                raise Exception("Voiceover generation returned None")

            logger.info(f"Voiceover generated successfully")
            await update_project_status(project_id, "generated_voiceover")

        except Exception as e:
            logger.error(f"Voiceover generation failed: {e}")
            await update_project_status(
                project_id,
                "error",
                error_message=f"Voiceover generation failed: {str(e)}"
            )
            return  # CRITICAL: Can't proceed without voiceover

        # ============================================================
        # STAGE 3: Process Video
        # ============================================================
        logger.info("Stage 3: Processing video with voiceover and avatar")
        await update_project_status(project_id, "processing_video", processing_step="Processing video with avatar")

        try:
            # Disable automatic cursor zoom in pipeline - users control zoom via timeline editor
            processed_video_url = await process_video_internal(project_id, enable_cursor_zoom=False)

            if processed_video_url:
                # Update project with processed video URL
                from app.database import update_project
                await update_project(project_id, {"processed_video_url": processed_video_url})
                logger.info(f"Video processed successfully")
            else:
                logger.warning("Video processing returned None, keeping original video")
                # Not critical - user still has voiceover
                await update_project_status(
                    project_id,
                    "complete",
                    error_message="Video processing skipped, voiceover available separately"
                )
                return

        except Exception as e:
            logger.error(f"Video processing failed: {e}")
            # Not critical - user still has voiceover
            await update_project_status(
                project_id,
                "complete",
                error_message=f"Video processing failed: {str(e)}, but voiceover is available"
            )
            return

        # ============================================================
        # PIPELINE COMPLETE
        # ============================================================
        logger.info(f"Pipeline completed successfully for project {project_id}")
        await update_project_status(project_id, "complete", processing_step="Processing complete")

    except Exception as e:
        logger.error(f"Pipeline failed for project {project_id}: {e}", exc_info=True)
        await update_project_status(
            project_id,
            "error",
            error_message=f"Pipeline error: {str(e)}"
        )
