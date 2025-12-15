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

    # Get frame count - note: CAP_PROP_FRAME_COUNT is unreliable for WebM/VP9
    # May return 0 or negative values
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    # Handle invalid fps (WebM can report 1000 fps or 0)
    if fps <= 0 or fps > 120:
        fps = 30.0  # Default to 30 fps
        logger.warning(f"Invalid fps detected, defaulting to {fps}")

    # Handle invalid frame count - will count manually if needed
    if total_frames <= 0:
        total_frames = 0  # Will be counted during processing
        logger.warning("Frame count unavailable, will count during processing")

    logger.info(f"Video: {total_frames if total_frames > 0 else 'unknown'} frames at {fps} FPS")
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
            if total_frames > 0:
                progress = (frame_idx / total_frames) * 100
                logger.info(f"Progress: {progress:.1f}% ({frame_idx}/{total_frames} frames)")
            else:
                logger.info(f"Processed {frame_idx} frames...")

    cap.release()

    detection_rate = (processed_count / (total_frames / frame_skip)) * 100 if total_frames > 0 else 0
    logger.info(f"Cursor detection complete: {len(positions)} positions, {detection_rate:.1f}% detected")

    return positions


def detect_zoom_moments(
    cursor_positions: List[Optional[Tuple[int, int]]],
    fps: float,
    stillness_threshold: float = 15.0,
    stillness_duration_frames: int = 10,
    min_gap_frames: int = 30
) -> List[dict]:
    """
    Detect moments when cursor is relatively still (user pointing at something).

    Args:
        cursor_positions: List of (x, y) cursor positions per frame
        fps: Video frame rate
        stillness_threshold: Max movement (pixels) to consider "still"
        stillness_duration_frames: Min frames of stillness to trigger zoom
        min_gap_frames: Minimum frames between zoom events

    Returns:
        List of zoom events: {start_frame, end_frame, center_x, center_y}
    """
    zoom_events = []
    valid_positions = [(i, p) for i, p in enumerate(cursor_positions) if p is not None]

    if len(valid_positions) < stillness_duration_frames:
        return zoom_events

    i = 0
    last_zoom_end = -min_gap_frames

    while i < len(valid_positions) - stillness_duration_frames:
        frame_idx, pos = valid_positions[i]

        # Skip if too close to last zoom event
        if frame_idx < last_zoom_end + min_gap_frames:
            i += 1
            continue

        # Check if cursor stays relatively still for the required duration
        still_frames = 1
        positions_in_window = [pos]

        for j in range(i + 1, min(i + stillness_duration_frames * 2, len(valid_positions))):
            next_frame_idx, next_pos = valid_positions[j]

            # Calculate distance from first position
            dist = ((next_pos[0] - pos[0])**2 + (next_pos[1] - pos[1])**2)**0.5

            if dist <= stillness_threshold:
                still_frames += 1
                positions_in_window.append(next_pos)
            else:
                break

        # If we found enough still frames, create a zoom event
        if still_frames >= stillness_duration_frames:
            center_x = int(np.mean([p[0] for p in positions_in_window]))
            center_y = int(np.mean([p[1] for p in positions_in_window]))

            # Extend the zoom event a bit for smoother effect
            start_frame = max(0, frame_idx - int(fps * 0.3))  # Start 0.3s before
            end_frame = min(len(cursor_positions) - 1, frame_idx + still_frames + int(fps * 0.5))  # End 0.5s after

            zoom_events.append({
                'start_frame': start_frame,
                'end_frame': end_frame,
                'center_x': center_x,
                'center_y': center_y
            })

            last_zoom_end = end_frame
            i += still_frames
        else:
            i += 1

    logger.info(f"Detected {len(zoom_events)} zoom moments")
    return zoom_events


def generate_zoompan_filter(
    cursor_positions: List[Optional[Tuple[int, int]]],
    video_width: int,
    video_height: int,
    fps: float,
    base_zoom: float = 1.0,
    max_zoom: float = 1.5,
    min_movement_threshold: float = 50.0
) -> str:
    """
    Generate FFmpeg filter for dynamic zoom that follows cursor and zooms
    in when cursor pauses (pointing at something).

    Args:
        cursor_positions: List of (x, y) cursor positions per frame
        video_width: Original video width
        video_height: Original video height
        fps: Video frame rate
        base_zoom: Default zoom level (1.0 = no zoom)
        max_zoom: Zoom level when cursor is pointing at something
        min_movement_threshold: Not used in new implementation

    Returns:
        FFmpeg filter string
    """
    if not cursor_positions or all(p is None for p in cursor_positions):
        logger.warning("No cursor positions detected, returning no zoom")
        return None

    # Detect moments when user is pointing at something
    zoom_events = detect_zoom_moments(
        cursor_positions,
        fps,
        stillness_threshold=20.0,
        stillness_duration_frames=int(fps * 0.4),  # 0.4 seconds of stillness
        min_gap_frames=int(fps * 1.5)  # At least 1.5 seconds between zooms
    )

    if not zoom_events:
        logger.info("No zoom moments detected, using smooth cursor follow")
        # Fall back to smooth cursor following without zoom
        return generate_smooth_follow_filter(cursor_positions, video_width, video_height, fps)

    # Generate keyframes for smooth zoom transitions
    total_frames = len(cursor_positions)
    zoom_transition_frames = int(fps * 0.4)  # 0.4 second transition

    # Build per-frame zoom and position data
    frame_data = []
    for frame_idx in range(total_frames):
        # Find if we're in a zoom event
        in_zoom = False
        zoom_progress = 0.0
        target_x, target_y = video_width // 2, video_height // 2

        for event in zoom_events:
            start = event['start_frame']
            end = event['end_frame']

            if start <= frame_idx <= end:
                in_zoom = True
                event_duration = end - start
                event_progress = (frame_idx - start) / max(event_duration, 1)

                # Smooth ease-in-out for zoom
                if event_progress < 0.3:
                    # Zoom in phase
                    zoom_progress = (event_progress / 0.3) * 1.0
                    zoom_progress = ease_in_out(zoom_progress)
                elif event_progress > 0.7:
                    # Zoom out phase
                    zoom_progress = ((1.0 - event_progress) / 0.3) * 1.0
                    zoom_progress = ease_in_out(zoom_progress)
                else:
                    # Hold zoom
                    zoom_progress = 1.0

                target_x = event['center_x']
                target_y = event['center_y']
                break

        # Get current cursor position for smooth following
        cursor_pos = cursor_positions[frame_idx] if frame_idx < len(cursor_positions) else None
        if cursor_pos:
            # Blend between cursor position and zoom target
            if in_zoom:
                blend = zoom_progress * 0.8  # Keep some cursor following even when zoomed
                current_x = int(cursor_pos[0] * (1 - blend) + target_x * blend)
                current_y = int(cursor_pos[1] * (1 - blend) + target_y * blend)
            else:
                current_x, current_y = cursor_pos
        else:
            current_x, current_y = target_x, target_y

        # Calculate zoom level
        zoom_level = base_zoom + (max_zoom - base_zoom) * zoom_progress

        frame_data.append({
            'frame': frame_idx,
            'zoom': zoom_level,
            'x': current_x,
            'y': current_y
        })

    # Smooth the data
    frame_data = smooth_frame_data(frame_data, window_size=int(fps * 0.2))

    # Generate FFmpeg expression using sendcmd or complex expressions
    # Since zoompan with dynamic expressions is limited, we'll use a different approach:
    # Scale + crop with expressions that change per frame

    logger.info(f"Generated dynamic zoom filter with {len(zoom_events)} zoom events")

    # Use FFmpeg's zoompan with expression-based zoom and position
    # We'll create a filter that interpolates between keyframes
    return generate_keyframe_filter(frame_data, video_width, video_height, fps, zoom_events)


def ease_in_out(t: float) -> float:
    """Smooth ease-in-out function (cubic)."""
    if t < 0.5:
        return 4 * t * t * t
    else:
        return 1 - pow(-2 * t + 2, 3) / 2


def smooth_frame_data(frame_data: List[dict], window_size: int = 5) -> List[dict]:
    """Apply moving average smoothing to frame data."""
    if window_size < 2 or len(frame_data) < window_size:
        return frame_data

    smoothed = []
    half_window = window_size // 2

    for i, data in enumerate(frame_data):
        start = max(0, i - half_window)
        end = min(len(frame_data), i + half_window + 1)
        window = frame_data[start:end]

        smoothed.append({
            'frame': data['frame'],
            'zoom': np.mean([d['zoom'] for d in window]),
            'x': int(np.mean([d['x'] for d in window])),
            'y': int(np.mean([d['y'] for d in window]))
        })

    return smoothed


def generate_smooth_follow_filter(
    cursor_positions: List[Optional[Tuple[int, int]]],
    video_width: int,
    video_height: int,
    fps: float
) -> str:
    """Generate a filter that smoothly follows cursor without zooming."""
    # No zoom events detected - return None to skip zoom filter entirely
    # This avoids any unwanted default zoom and preserves original video
    logger.info("No zoom events detected, skipping zoom filter to preserve original video")
    return None


def generate_keyframe_filter(
    frame_data: List[dict],
    video_width: int,
    video_height: int,
    fps: float,
    zoom_events: List[dict]
) -> str:
    """
    Generate FFmpeg filter using keyframe-based zoom expressions.

    For dynamic zoom, we need to use expressions that vary with frame number.
    FFmpeg's zoompan supports expressions with 'on' (output frame number).
    """
    if not zoom_events:
        # No zoom events - return None to preserve original video without any zoom
        logger.info("No zoom events in keyframe filter, returning None")
        return None

    # Build zoom expression based on frame ranges
    # Format: if(between(on,start,end), zoom_value, else_value)
    zoom_expr_parts = []
    x_expr_parts = []
    y_expr_parts = []

    for event in zoom_events:
        start = event['start_frame']
        end = event['end_frame']
        cx = event['center_x']
        cy = event['center_y']
        duration = end - start

        # Zoom in for first 30%, hold for 40%, zoom out for 30%
        zoom_in_end = start + int(duration * 0.3)
        zoom_out_start = start + int(duration * 0.7)

        # Create smooth zoom expression for this event
        # Zoom in phase: linear interpolation from 1.0 to 1.5
        zoom_expr_parts.append(
            f"if(between(on,{start},{zoom_in_end}),"
            f"1.0+0.5*(on-{start})/{max(zoom_in_end-start, 1)},"
        )
        # Hold phase
        zoom_expr_parts.append(
            f"if(between(on,{zoom_in_end},{zoom_out_start}),1.5,"
        )
        # Zoom out phase
        zoom_expr_parts.append(
            f"if(between(on,{zoom_out_start},{end}),"
            f"1.5-0.5*(on-{zoom_out_start})/{max(end-zoom_out_start, 1)},"
        )

        # Position expressions - center on the zoom target during event
        x_expr_parts.append(
            f"if(between(on,{start},{end}),{cx}-(iw/zoom/2),"
        )
        y_expr_parts.append(
            f"if(between(on,{start},{end}),{cy}-(ih/zoom/2),"
        )

    # Build the nested if expressions
    # Default values (no zoom)
    default_zoom = "1.0"
    default_x = f"{video_width//2}-(iw/zoom/2)"
    default_y = f"{video_height//2}-(ih/zoom/2)"

    # Close all the if statements
    closing_parens = ")" * (len(zoom_expr_parts))

    zoom_expr = "".join(zoom_expr_parts) + default_zoom + closing_parens

    # For position, we need to handle outside-of-zoom-event frames
    # Use smoothed cursor following for those
    valid_data = [d for d in frame_data if d['x'] and d['y']]
    if valid_data:
        avg_x = int(np.mean([d['x'] for d in valid_data]))
        avg_y = int(np.mean([d['y'] for d in valid_data]))
    else:
        avg_x, avg_y = video_width // 2, video_height // 2

    default_x = f"{avg_x}-(iw/zoom/2)"
    default_y = f"{avg_y}-(ih/zoom/2)"

    x_closing = ")" * len(x_expr_parts)
    y_closing = ")" * len(y_expr_parts)

    x_expr = "".join(x_expr_parts) + default_x + x_closing
    y_expr = "".join(y_expr_parts) + default_y + y_closing

    # Build the complete filter
    zoompan_filter = (
        f"zoompan="
        f"z='{zoom_expr}':"
        f"d=1:"
        f"x='{x_expr}':"
        f"y='{y_expr}':"
        f"s={video_width}x{video_height}:"
        f"fps={fps}"
    )

    logger.info(f"Generated keyframe zoom filter with {len(zoom_events)} zoom events")
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
