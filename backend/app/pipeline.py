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

            # Use GPT-4 to ONLY remove filler words - absolutely no other changes
            # CRITICAL: Do not change any actual words the user said
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a transcript cleaner. Your ONLY job is to remove filler words.\n\n"
                            "REMOVE ONLY these exact filler words/phrases:\n"
                            "- um, uh, er, ah, hmm\n"
                            "- repeated words like 'I I' or 'the the'\n\n"
                            "RULES:\n"
                            "- Do NOT change ANY other words\n"
                            "- Do NOT fix grammar\n"
                            "- Do NOT rephrase anything\n"
                            "- Do NOT add words\n"
                            "- Do NOT correct what seems like mistakes\n"
                            "- Keep the EXACT same meaning and wording\n\n"
                            "If the input has no filler words, return it EXACTLY as-is.\n"
                            "Output ONLY the text, nothing else."
                        )
                    },
                    {
                        "role": "user",
                        "content": segment.get("text", "")
                    }
                ],
                max_tokens=500,
                temperature=0.0  # Zero temperature for deterministic output
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
    Generate voiceover audio segment by segment, matching original timing.

    This ensures the voiceover matches the original video duration by:
    1. Generating TTS for each segment individually
    2. Adding silence padding after each segment to match original duration
    3. Concatenating all segments into one audio file

    Args:
        project_id: UUID of the project
        segments: List of cleaned segments with start/end timestamps
        voice: OpenAI TTS voice name

    Returns:
        URL of the generated voiceover audio, or None if failed
    """
    import subprocess
    import tempfile
    from pathlib import Path

    try:
        logger.info(f"Generating segmented voiceover for project {project_id} with {len(segments)} segments")

        if not openai_client:
            raise Exception("OpenAI API key not configured")

        from app.storage import upload_file_to_storage, ensure_bucket_exists
        from app.database import save_video_file

        STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "videos")
        ensure_bucket_exists(STORAGE_BUCKET, public=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            segment_files = []

            for i, seg in enumerate(segments):
                cleaned_text = seg.get("cleaned_text", seg.get("text", ""))
                if not cleaned_text.strip():
                    logger.warning(f"Segment {i} has no text, skipping")
                    continue

                # Calculate target duration from original timestamps
                start_time = seg.get("start", 0)
                end_time = seg.get("end", 0)
                target_duration = end_time - start_time

                logger.info(f"Segment {i+1}/{len(segments)}: {target_duration:.2f}s target, text: '{cleaned_text[:50]}...'")

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
                logger.info(f"Segment {i+1}: TTS duration = {tts_duration:.2f}s, target = {target_duration:.2f}s")

                # If TTS is shorter than target, pad with silence
                final_file = temp_path / f"seg_{i}_final.mp3"
                if target_duration > 0 and tts_duration < target_duration:
                    pad_duration = target_duration - tts_duration
                    logger.info(f"Segment {i+1}: Adding {pad_duration:.2f}s silence padding")

                    # Use ffmpeg to add silence padding at the end
                    subprocess.run([
                        "ffmpeg", "-i", str(raw_file),
                        "-af", f"apad=pad_dur={pad_duration}",
                        "-y", str(final_file)
                    ], capture_output=True, timeout=30)

                    if final_file.exists():
                        segment_files.append(str(final_file))
                    else:
                        # Fallback to raw file
                        segment_files.append(str(raw_file))
                else:
                    # TTS is already long enough, use as-is
                    segment_files.append(str(raw_file))

            if not segment_files:
                raise Exception("No audio segments generated")

            # Concatenate all segments using ffmpeg concat demuxer
            concat_list_file = temp_path / "concat_list.txt"
            with open(concat_list_file, "w") as f:
                for path in segment_files:
                    f.write(f"file '{path}'\n")

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

            # Read final audio
            with open(output_file, "rb") as f:
                audio_content = f.read()

            final_duration = get_audio_duration(str(output_file))
            logger.info(f"Final voiceover duration: {final_duration:.2f}s")

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

            logger.info(f"Segmented voiceover generated successfully: {audio_url}")
            return audio_url

    except Exception as e:
        logger.error(f"Error generating segmented voiceover: {e}", exc_info=True)
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
