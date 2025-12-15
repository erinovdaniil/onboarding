from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import os
import json
import subprocess
import tempfile
import logging

from app.storage import (
    download_file_from_storage,
    upload_file_to_storage,
    get_file_url
)
from app.database import (
    get_video_files,
    save_video_file,
    update_project,
    get_project
)

logger = logging.getLogger(__name__)
router = APIRouter()

STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "videos")


class BrandSettings(BaseModel):
    logo: Optional[str] = None
    primaryColor: str = "#0ea5e9"
    secondaryColor: str = "#0284c7"


class ProcessVideoRequest(BaseModel):
    projectId: str
    script: Optional[str] = None
    voice: Optional[str] = None
    language: Optional[str] = None
    brandSettings: Optional[BrandSettings] = None


# -------------------------
# ZOOM FILTER (FIXED)
# -------------------------
def generate_custom_zoom_filter(
    zoom_config: dict,
    width: int,
    height: int,
    fps: float,
    duration: float
) -> Optional[str]:

    if not zoom_config or not zoom_config.get("enabled"):
        return None

    start_time = zoom_config.get("startTime", 0)
    end_time = zoom_config.get("endTime", start_time + 3)
    zoom_level = max(1.0, min(3.0, zoom_config.get("zoomLevel", 1.5)))
    center_x = zoom_config.get("centerX", 50) / 100.0
    center_y = zoom_config.get("centerY", 50) / 100.0

    start_time = max(0, min(duration, start_time))
    end_time = max(start_time + 0.1, min(duration, end_time))

    start_frame = int(start_time * fps)
    end_frame = int(end_time * fps)
    transition_frames = int(fps * 0.3)

    zoom_expr = (
        f"if(lt(on,{start_frame}),1,"
        f"if(lt(on,{start_frame + transition_frames}),"
        f"1+(({zoom_level}-1)*(on-{start_frame})/{transition_frames}),"
        f"if(lt(on,{end_frame - transition_frames}),"
        f"{zoom_level},"
        f"if(lt(on,{end_frame}),"
        f"{zoom_level}-(({zoom_level}-1)*(on-{end_frame - transition_frames})/{transition_frames}),"
        f"1))))"
    )

    pan_x_expr = (
        f"if(lt(on,{start_frame}),0,"
        f"if(gt(on,{end_frame}),0,"
        f"max(0,min(iw-iw/zoom,(iw-iw/zoom)*{center_x}))))"
    )

    pan_y_expr = (
        f"if(lt(on,{start_frame}),0,"
        f"if(gt(on,{end_frame}),0,"
        f"max(0,min(ih-ih/zoom,(ih-ih/zoom)*{center_y}))))"
    )

    return (
        f"zoompan="
        f"z='{zoom_expr}':"
        f"x='{pan_x_expr}':"
        f"y='{pan_y_expr}':"
        f"d=1:"                       # ✅ FIXED
        f"s={width}x{height}:"
        f"fps={fps}"
    )


# -------------------------
# PROCESS VIDEO
# -------------------------
@router.post("/process")
async def process_video(request: ProcessVideoRequest):
    logger.info(f"Processing video for project: {request.projectId}")
    try:
        video_files = await get_video_files(request.projectId)
        original_file = next(f for f in video_files if f["file_type"] == "original")

        project = await get_project(request.projectId)

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)

            original_path = tmp / "original.webm"
            original_path.write_bytes(
                await download_file_from_storage(
                    STORAGE_BUCKET, original_file["storage_path"]
                )
            )

            import cv2
            cap = cv2.VideoCapture(str(original_path))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()

            logger.info(f"Video info: {width}x{height}, {fps} fps, {frame_count} frames")

            # Try multiple methods to get duration
            duration = None

            # Method 1: Try format duration from ffprobe
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(original_path)],
                capture_output=True, text=True
            )
            duration_str = probe.stdout.strip()
            logger.info(f"ffprobe format duration: {duration_str}")

            if duration_str and duration_str != 'N/A':
                try:
                    duration = float(duration_str)
                    logger.info(f"Duration from ffprobe format: {duration}s")
                except ValueError:
                    pass

            # Method 2: Try stream duration from ffprobe
            if duration is None:
                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(original_path)],
                    capture_output=True, text=True
                )
                stream_duration = probe.stdout.strip()
                logger.info(f"ffprobe stream duration: {stream_duration}")

                if stream_duration and stream_duration != 'N/A':
                    try:
                        duration = float(stream_duration)
                        logger.info(f"Duration from ffprobe stream: {duration}s")
                    except ValueError:
                        pass

            # Method 3: Calculate from frame count (only if frame_count is valid/positive)
            if duration is None and frame_count > 0 and frame_count < 1e9 and fps > 0:
                duration = frame_count / fps
                logger.info(f"Duration calculated from frames: {duration}s ({frame_count} frames @ {fps} fps)")

            # Method 4: Use ffmpeg to decode and get actual duration
            if duration is None or duration <= 0:
                logger.info("Attempting to get duration via ffmpeg decode...")
                try:
                    import re
                    # First try just reading the header info
                    ffmpeg_result = subprocess.run(
                        ["ffmpeg", "-i", str(original_path)],
                        capture_output=True, text=True, timeout=10
                    )
                    # Parse duration from ffmpeg stderr output
                    duration_match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})", ffmpeg_result.stderr)
                    if duration_match:
                        hours, minutes, seconds = duration_match.groups()
                        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                        logger.info(f"Duration from ffmpeg header: {duration}s")
                except Exception as e:
                    logger.warning(f"Failed to get duration via ffmpeg header: {e}")

            # Method 5: Decode entire file if still no duration (for WebM without duration header)
            if duration is None or duration <= 0:
                logger.info("Attempting full decode to get duration...")
                try:
                    import re
                    ffmpeg_result = subprocess.run(
                        ["ffmpeg", "-i", str(original_path), "-f", "null", "-"],
                        capture_output=True, text=True, timeout=120
                    )
                    # Look for "time=" in the output which shows progress
                    time_matches = re.findall(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})", ffmpeg_result.stderr)
                    if time_matches:
                        # Get the last time value (final duration)
                        hours, minutes, seconds = time_matches[-1]
                        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                        logger.info(f"Duration from full decode: {duration}s")
                except Exception as e:
                    logger.warning(f"Failed to get duration via full decode: {e}")

            if duration is None or duration <= 0:
                logger.error("Unable to determine video duration using any method")
                raise ValueError("Unable to determine video duration. The video file may be corrupted or in an unsupported format.")

            zoom_filter = None
            if project and project.get("zoom_config"):
                zoom_config = project["zoom_config"]
                logger.info(f"Zoom config type: {type(zoom_config)}, value: {zoom_config}")
                # Handle both string and dict formats
                if isinstance(zoom_config, str):
                    zoom_config = json.loads(zoom_config)
                logger.info(f"Parsed zoom config: {zoom_config}")
                zoom_filter = generate_custom_zoom_filter(
                    zoom_config,
                    width, height, fps, duration
                )
                logger.info(f"Generated zoom filter: {zoom_filter}")

            output_path = tmp / "processed.mp4"

            ffmpeg_cmd = ["ffmpeg", "-y", "-i", str(original_path)]

            filters = []
            if zoom_filter:
                filters.append(f"[0:v]{zoom_filter}[v]")

            if filters:
                ffmpeg_cmd += ["-filter_complex", ";".join(filters), "-map", "[v]"]
            else:
                ffmpeg_cmd += ["-map", "0:v:0"]

            ffmpeg_cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(output_path)]

            logger.info(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")
            try:
                subprocess.run(
                    ffmpeg_cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                logger.info("FFmpeg processing completed successfully")
            except subprocess.CalledProcessError as e:
                logger.error("FFmpeg failed:\n%s", e.stderr)
                raise HTTPException(
                    status_code=500,
                    detail=f"FFmpeg error: {e.stderr}"
                )
            except subprocess.TimeoutExpired as e:
                logger.error("FFmpeg timed out after 300 seconds")
                raise HTTPException(
                    status_code=500,
                    detail="Video processing timed out. The video may be too long or complex."
                )

            content = output_path.read_bytes()

            storage_path = f"{request.projectId}/processed.mp4"
            url = await upload_file_to_storage(
                STORAGE_BUCKET, storage_path, content, "video/mp4"
            )

            await save_video_file(
                request.projectId, "processed", storage_path, len(content)
            )
            await update_project(request.projectId, {"status": "processed"})

            return {"success": True, "processedVideoUrl": url}

    except Exception as e:
        logger.error(f"Error processing video: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# EXPORT
# -------------------------
@router.get("/export/{project_id}")
async def export_video(project_id: str):

    files = await get_video_files(project_id)
    file = next((f for f in files if f["file_type"] == "processed"), None)
    if not file:
        raise HTTPException(status_code=404, detail="Video not found")

    url = await get_file_url(STORAGE_BUCKET, file["storage_path"], public=True)
    return {"url": url}
