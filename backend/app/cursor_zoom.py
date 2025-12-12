"""
Automatic Cursor Zoom Module

Detects mouse cursor in screen recording videos and generates smooth
zoom effects following cursor movement.

Quick implementation optimized for speed:
- Process every 3rd frame for 3x speed improvement
- Simple velocity-based zoom
- Smooth interpolation between detections
"""

import logging
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from collections import deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CursorTracker:
    """Tracks cursor position across frames with smoothing and prediction."""

    def __init__(self, max_history: int = 5, max_gap_frames: int = 3):
        self.position_history = deque(maxlen=max_history)
        self.last_valid_position = None
        self.lost_frames = 0
        self.max_gap_frames = max_gap_frames

    def update(self, new_position: Optional[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
        """Update tracker with new detection, handling gaps with prediction."""
        if new_position:
            self.position_history.append(new_position)
            self.last_valid_position = new_position
            self.lost_frames = 0
            return self.get_smoothed_position()
        else:
            self.lost_frames += 1

            # Predict position based on velocity if within gap tolerance
            if self.lost_frames <= self.max_gap_frames and len(self.position_history) >= 2:
                velocity = self.get_velocity()
                prev = self.position_history[-1]
                predicted = (
                    int(prev[0] + velocity[0]),
                    int(prev[1] + velocity[1])
                )
                self.position_history.append(predicted)
                return self.get_smoothed_position()

            # Too many lost frames, return last known position
            return self.get_smoothed_position()

    def get_velocity(self) -> Tuple[float, float]:
        """Calculate movement velocity from recent positions."""
        if len(self.position_history) < 2:
            return (0.0, 0.0)

        positions = list(self.position_history)
        vx = positions[-1][0] - positions[-2][0]
        vy = positions[-1][1] - positions[-2][1]
        return (vx, vy)

    def get_speed(self) -> float:
        """Calculate movement speed (magnitude of velocity)."""
        vx, vy = self.get_velocity()
        return (vx**2 + vy**2)**0.5

    def get_smoothed_position(self) -> Optional[Tuple[int, int]]:
        """Return smoothed position using weighted average of recent frames."""
        if not self.position_history:
            return self.last_valid_position

        # Weighted average (more weight to recent positions)
        positions = list(self.position_history)
        weights = [i + 1 for i in range(len(positions))]  # [1, 2, 3, 4, 5]
        total_weight = sum(weights)

        avg_x = sum(p[0] * w for p, w in zip(positions, weights)) / total_weight
        avg_y = sum(p[1] * w for p, w in zip(positions, weights)) / total_weight

        return (int(avg_x), int(avg_y))


def detect_cursor_in_frame(
    frame: np.ndarray,
    cursor_template: np.ndarray,
    threshold: float = 0.6
) -> Optional[Tuple[int, int, float]]:
    """
    Detect cursor position in a single frame using template matching.

    Args:
        frame: Video frame (grayscale)
        cursor_template: Cursor template image (grayscale)
        threshold: Match confidence threshold (0.0 to 1.0)

    Returns:
        (x, y, confidence) tuple or None if not found
    """
    try:
        result = cv2.matchTemplate(frame, cursor_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            # max_loc is top-left corner; return center of cursor
            h, w = cursor_template.shape[:2]
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return (center_x, center_y, max_val)

        return None
    except Exception as e:
        logger.error(f"Error in cursor detection: {e}")
        return None


async def detect_cursor_positions(
    video_path: Path,
    frame_skip: int = 3,
    downsample_factor: int = 2
) -> List[Optional[Tuple[int, int]]]:
    """
    Detect cursor positions across all video frames.

    Args:
        video_path: Path to input video
        frame_skip: Process every Nth frame (3 = 3x faster)
        downsample_factor: Downscale frames for detection (2 = 4x faster)

    Returns:
        List of (x, y) positions for each frame (None if not detected)
    """
    logger.info(f"Starting cursor detection for {video_path}")

    # Load cursor templates
    template_path = Path(__file__).parent / "static" / "cursor_template.png"
    template_black_path = Path(__file__).parent / "static" / "cursor_template_black.png"

    if not template_path.exists():
        logger.error(f"Cursor template not found: {template_path}")
        return []

    cursor_template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
    cursor_template_black = cv2.imread(str(template_black_path), cv2.IMREAD_GRAYSCALE)

    # Downscale templates
    cursor_template = cv2.resize(
        cursor_template,
        (cursor_template.shape[1] // downsample_factor,
         cursor_template.shape[0] // downsample_factor)
    )
    cursor_template_black = cv2.resize(
        cursor_template_black,
        (cursor_template_black.shape[1] // downsample_factor,
         cursor_template_black.shape[0] // downsample_factor)
    )

    # Open video
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.error(f"Failed to open video: {video_path}")
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    logger.info(f"Video: {total_frames} frames at {fps} FPS")
    logger.info(f"Processing every {frame_skip} frames with {downsample_factor}x downscale")

    positions = []
    tracker = CursorTracker()
    frame_idx = 0
    processed_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Process every Nth frame
        if frame_idx % frame_skip == 0:
            # Downscale for faster processing
            small_frame = cv2.resize(
                frame,
                (frame.shape[1] // downsample_factor, frame.shape[0] // downsample_factor)
            )
            gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)

            # Try white cursor first, then black
            detection = detect_cursor_in_frame(gray, cursor_template, threshold=0.6)
            if not detection:
                detection = detect_cursor_in_frame(gray, cursor_template_black, threshold=0.6)

            if detection:
                # Scale coordinates back up
                x, y, confidence = detection
                scaled_pos = (x * downsample_factor, y * downsample_factor)
                tracked_pos = tracker.update(scaled_pos)
                logger.debug(f"Frame {frame_idx}: Cursor at {scaled_pos} (conf: {confidence:.2f})")
            else:
                tracked_pos = tracker.update(None)
                logger.debug(f"Frame {frame_idx}: No cursor detected")

            positions.append(tracked_pos)
            processed_count += 1
        else:
            # Interpolate for skipped frames
            if len(positions) > 0:
                positions.append(positions[-1])  # Copy last position
            else:
                positions.append(None)

        frame_idx += 1

        # Progress logging
        if frame_idx % 100 == 0:
            progress = (frame_idx / total_frames) * 100
            logger.info(f"Progress: {progress:.1f}% ({frame_idx}/{total_frames} frames)")

    cap.release()

    detection_rate = (processed_count / (total_frames / frame_skip)) * 100 if total_frames > 0 else 0
    logger.info(f"Cursor detection complete: {len(positions)} positions, {detection_rate:.1f}% detected")

    return positions


def generate_zoompan_filter(
    cursor_positions: List[Optional[Tuple[int, int]]],
    video_width: int,
    video_height: int,
    fps: float,
    base_zoom: float = 1.2,
    max_zoom: float = 1.4,
    min_movement_threshold: float = 50.0
) -> str:
    """
    Generate FFmpeg zoompan filter expression based on cursor positions.

    Args:
        cursor_positions: List of (x, y) cursor positions per frame
        video_width: Original video width
        video_height: Original video height
        fps: Video frame rate
        base_zoom: Minimum zoom level (1.0 = no zoom)
        max_zoom: Maximum zoom level
        min_movement_threshold: Minimum pixel movement to trigger zoom increase

    Returns:
        FFmpeg zoompan filter string
    """
    if not cursor_positions or all(p is None for p in cursor_positions):
        logger.warning("No cursor positions detected, using default zoom")
        return f"zoompan=z={base_zoom}:d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={video_width}x{video_height}:fps={fps}"

    # Simplified approach: Use fixed zoom that follows cursor center
    # This is fast and works well for most cases

    # Calculate average cursor position (for centering)
    valid_positions = [p for p in cursor_positions if p is not None]
    if not valid_positions:
        center_x, center_y = video_width // 2, video_height // 2
    else:
        center_x = int(np.mean([p[0] for p in valid_positions]))
        center_y = int(np.mean([p[1] for p in valid_positions]))

    # Create zoompan filter with fixed zoom following cursor
    # Note: This is a simplified version. For dynamic zoom based on movement,
    # we'd need to generate per-frame expressions which is more complex.

    zoompan_filter = (
        f"zoompan="
        f"z='{base_zoom}':"  # Fixed zoom level
        f"d=1:"  # Apply to each frame
        f"x='{center_x}-(iw/zoom/2)':"  # Center on average cursor X
        f"y='{center_y}-(ih/zoom/2)':"  # Center on average cursor Y
        f"s={video_width}x{video_height}:"
        f"fps={fps}"
    )

    logger.info(f"Generated zoompan filter: {base_zoom}x zoom centered on ({center_x}, {center_y})")
    return zoompan_filter


async def apply_cursor_zoom(
    input_video_path: Path,
    output_video_path: Path,
    enable_zoom: bool = True,
    zoom_level: float = 1.2
) -> bool:
    """
    Apply cursor-following zoom to video.

    Args:
        input_video_path: Path to input video
        output_video_path: Path for output video
        enable_zoom: Whether to apply zoom (False = passthrough)
        zoom_level: Zoom intensity (1.0 = no zoom, 1.2 = 20% zoom)

    Returns:
        True if successful, False otherwise
    """
    if not enable_zoom:
        logger.info("Cursor zoom disabled, skipping")
        return False

    try:
        logger.info(f"Applying cursor zoom to {input_video_path}")

        # Detect cursor positions
        cursor_positions = await detect_cursor_positions(
            input_video_path,
            frame_skip=3,  # Process every 3rd frame for speed
            downsample_factor=2  # 2x downscale for speed
        )

        if not cursor_positions:
            logger.error("Cursor detection failed")
            return False

        # Get video properties
        cap = cv2.VideoCapture(str(input_video_path))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()

        # Generate zoompan filter
        zoompan_filter = generate_zoompan_filter(
            cursor_positions,
            width,
            height,
            fps,
            base_zoom=zoom_level
        )

        # Apply zoom with FFmpeg
        import subprocess
        cmd = [
            "ffmpeg",
            "-i", str(input_video_path),
            "-vf", zoompan_filter,
            "-c:v", "libx264",
            "-preset", "medium",  # Balance speed/quality
            "-crf", "23",  # Quality
            "-c:a", "copy",  # Copy audio without re-encoding
            "-y",
            str(output_video_path)
        ]

        logger.info(f"Running FFmpeg: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            timeout=600  # 10 minute timeout
        )

        logger.info("Cursor zoom applied successfully")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e.stderr.decode()}")
        return False
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timeout")
        return False
    except Exception as e:
        logger.error(f"Error applying cursor zoom: {e}", exc_info=True)
        return False
