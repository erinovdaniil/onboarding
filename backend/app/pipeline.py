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

            # Use GPT-4 to clean this segment's text
            response = await openai_client.chat.completions.acreate(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional transcript editor. "
                            "Remove filler words (um, uh, like, you know), fix grammar and punctuation, "
                            "and improve clarity while keeping the exact meaning unchanged. "
                            "Output ONLY the cleaned text, nothing else."
                        )
                    },
                    {
                        "role": "user",
                        "content": segment.get("text", "")
                    }
                ],
                max_tokens=500,
                temperature=0.3  # Lower temperature for more consistent results
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


async def generate_voiceover_internal(
    project_id: str,
    script: str,
    voice: str = "alloy"
) -> Optional[str]:
    """
    Generate voiceover audio using OpenAI TTS.
    This is an internal function called by the pipeline.

    Args:
        project_id: UUID of the project
        script: Cleaned script text
        voice: OpenAI TTS voice name

    Returns:
        URL of the generated voiceover audio, or None if failed
    """
    try:
        logger.info(f"Generating voiceover for project {project_id} with voice '{voice}'")

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

            # Download original video
            original_video_content = await download_file_from_storage(STORAGE_BUCKET, original_storage_path)
            original_video_path = temp_path / "original.webm"
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
                            base_zoom=1.2  # 20% zoom
                        )
                        logger.info("Cursor zoom filter generated successfully")
                except Exception as e:
                    logger.warning(f"Cursor zoom detection failed, proceeding without zoom: {e}")
                    enable_cursor_zoom = False

            # Build FFmpeg command
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
                if zoom_filter and enable_cursor_zoom:
                    # Zoom video first, then add avatar
                    filter_complex = (
                        f"[0:v]{zoom_filter}[zoomed];"
                        f"[2:v]scale=iw*{scale}:ih*{scale}[avatar];"
                        f"[zoomed][avatar]overlay={overlay_pos}[v]"
                    )
                else:
                    # No zoom, just avatar overlay
                    filter_complex = (
                        f"[2:v]scale=iw*{scale}:ih*{scale}[avatar];"
                        f"[0:v][avatar]overlay={overlay_pos}[v]"
                    )

                # Loop static image for video duration and overlay
                ffmpeg_cmd.extend([
                    "-loop", "1",  # Loop static image
                    "-i", str(avatar_path),
                    "-filter_complex",
                    filter_complex,
                    "-map", "[v]",
                    "-map", "1:a:0",  # Audio from voiceover only
                    "-shortest",  # Match output to shortest input (voiceover length)
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-y",
                    str(processed_video_path)
                ])
            else:
                # No avatar - apply zoom if available, otherwise just combine
                if zoom_filter and enable_cursor_zoom:
                    ffmpeg_cmd.extend([
                        "-filter_complex",
                        f"[0:v]{zoom_filter}[v]",
                        "-map", "[v]",
                        "-map", "1:a:0",  # Audio from voiceover
                        "-shortest",  # Match output to voiceover length
                        "-c:v", "libx264",
                        "-c:a", "aac",
                        "-y",
                        str(processed_video_path)
                    ])
                else:
                    # No zoom, no avatar - just combine video and voiceover
                    ffmpeg_cmd.extend([
                        "-map", "0:v:0",  # Video from original
                        "-map", "1:a:0",  # Audio from voiceover
                        "-shortest",  # Match output to voiceover length
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


async def run_automatic_pipeline(project_id: str, user_id: Optional[str] = None):
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
    """
    try:
        logger.info(f"Starting automatic pipeline for project {project_id}")

        # Get project and transcript
        project = await get_project(project_id, user_id=user_id)
        if not project:
            logger.error(f"Project {project_id} not found")
            return

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
        segments = transcript_record.get("segments", [])
        if isinstance(segments, str):
            segments = json.loads(segments)

        if not segments:
            logger.warning(f"No segments in transcript for project {project_id}")
            # Use full text as single segment
            segments = [{
                "id": 0,
                "start": 0.0,
                "end": 0.0,
                "text": transcript_record.get("text", "")
            }]

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
        # STAGE 2: Generate Voiceover
        # ============================================================
        logger.info("Stage 2: Generating voiceover")
        await update_project_status(project_id, "generating_voiceover", processing_step="Generating AI voiceover")

        try:
            voice = project.get("voiceover_voice", "alloy")
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
            processed_video_url = await process_video_internal(project_id)

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
