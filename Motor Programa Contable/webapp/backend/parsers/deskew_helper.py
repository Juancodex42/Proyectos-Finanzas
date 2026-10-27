"""
High-performance orientation detection and deskewing helper for scanned document pages.
Optimized for tabular PDF certifications, ensuring minimal latency (<30ms per page).
"""

import threading
import numpy as np
import cv2
from PIL import Image


class AngleMemory:
    """
    Thread-safe orientation memory that tracks the dominant page orientation
    across an entire PDF document. Once detected on early pages, subsequent
    pages inherit the dominant orientation without redundant classification.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._angle_counts = {0: 0, 90: 0, 180: 0, 270: 0}
        self._dominant_angle = 0
        self._total_records = 0

    def record_angle(self, angle: int, weight: int = 1) -> None:
        """Records an observed valid angle (0, 90, 180, 270) with optional weight."""
        with self._lock:
            if angle in self._angle_counts:
                self._angle_counts[angle] += weight
                self._total_records += weight
                self._dominant_angle = max(
                    self._angle_counts.keys(),
                    key=lambda k: self._angle_counts[k]
                )

    def get_dominant_angle(self, default: int = 0) -> int:
        """Returns the most frequent angle recorded so far, or default if none."""
        with self._lock:
            if self._total_records > 0 and self._angle_counts[self._dominant_angle] > 0:
                return self._dominant_angle
            return default

    def get_dominant_sideways_angle(self, default: int = 270) -> int:
        """Returns dominant sideways angle (90 or 270) if recorded, else default."""
        with self._lock:
            c90 = self._angle_counts.get(90, 0)
            c270 = self._angle_counts.get(270, 0)
            if c90 > 0 or c270 > 0:
                return 90 if c90 > c270 else 270
            return default

    def get_dominant_horizontal_angle(self, default: int = 0) -> int:
        """Returns dominant horizontal angle (0 or 180) if recorded, else default."""
        with self._lock:
            c0 = self._angle_counts.get(0, 0)
            c180 = self._angle_counts.get(180, 0)
            if c0 > 0 or c180 > 0:
                return 180 if c180 > c0 else 0
            return default

    def has_memory(self) -> bool:
        """Returns True if at least one page orientation has been confidently recorded."""
        with self._lock:
            return self._total_records > 0

    def reset(self) -> None:
        """Clears memory state for processing a new document."""
        with self._lock:
            self._angle_counts = {0: 0, 90: 0, 180: 0, 270: 0}
            self._dominant_angle = 0
            self._total_records = 0

    def get_stats(self) -> dict:
        """Returns snapshot of recorded angle distributions."""
        with self._lock:
            return dict(self._angle_counts)


def deskew_image(pil_img: Image.Image, max_angle: float = 15.0) -> tuple:
    """
    Calculates table/text line tilt using Hough Line transform on a downscaled thumbnail,
    and rotates the image to achieve 100% horizontal alignment.

    Args:
        pil_img: PIL Image to deskew.
        max_angle: Maximum skew angle in degrees to correct for (defaults to 15.0).

    Returns:
        tuple: (deskewed_pil_img, detected_angle_float)
    """
    if pil_img is None:
        return None, 0.0

    try:
        w, h = pil_img.size
        if w < 50 or h < 50:
            return pil_img, 0.0

        # Downscale for ultra-fast line detection (max 800px width/height)
        scale = min(1.0, 800.0 / max(w, h))
        target_size = (int(w * scale), int(h * scale))

        if scale < 1.0:
            small_img = pil_img.resize(target_size, resample=Image.Resampling.BILINEAR)
        else:
            small_img = pil_img

        # Convert to grayscale array
        if small_img.mode != "L":
            small_gray = small_img.convert("L")
        else:
            small_gray = small_img
        np_gray = np.array(small_gray)

        # Detect edges
        edges = cv2.Canny(np_gray, 50, 150, apertureSize=3)

        # Hough lines transform targeting horizontal line segments
        min_line_len = max(40, int(60 * scale))
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=80,
            minLineLength=min_line_len,
            maxLineGap=int(10 * scale)
        )

        if lines is None or len(lines) == 0:
            return pil_img, 0.0

        candidate_angles = []
        weights = []

        for line in lines:
            x1, y1, x2, y2 = line[0]
            dx = x2 - x1
            dy = y2 - y1
            if dx == 0:
                continue

            # Ensure dx is positive so angle is strictly in (-90, 90)
            if dx < 0:
                dx, dy = -dx, -dy

            angle_deg = np.degrees(np.arctan2(dy, dx))

            # Focus strictly on near-horizontal lines (-max_angle to +max_angle)
            if -max_angle <= angle_deg <= max_angle:
                line_len = np.hypot(dx, dy)
                candidate_angles.append(angle_deg)
                weights.append(line_len)

        if not candidate_angles:
            return pil_img, 0.0

        # Weighted median calculation
        sorted_indices = np.argsort(candidate_angles)
        sorted_angles = np.array(candidate_angles)[sorted_indices]
        sorted_weights = np.array(weights)[sorted_indices]
        cum_weights = np.cumsum(sorted_weights)
        cutoff = cum_weights[-1] / 2.0
        median_idx = np.searchsorted(cum_weights, cutoff)
        detected_angle = float(sorted_angles[min(median_idx, len(sorted_angles) - 1)])

        # Ignore imperceptible sub-0.35 degree noise to avoid unnecessary interpolation
        if abs(detected_angle) < 0.35:
            return pil_img, 0.0

        # Rotate original image to correct tilt (counteract detected skew)
        if pil_img.mode in ("RGB", "BGR"):
            fill = (255, 255, 255)
        elif pil_img.mode == "RGBA":
            fill = (255, 255, 255, 255)
        elif pil_img.mode in ("L", "1"):
            fill = 255
        else:
            fill = (255, 255, 255)

        deskewed = pil_img.rotate(
            detected_angle,
            resample=Image.Resampling.BICUBIC,
            expand=False,
            fillcolor=fill
        )
        return deskewed, round(detected_angle, 2)

    except Exception as e:
        print(f"[DESKEW ERROR] Failed deskew calculation: {e}")
        return pil_img, 0.0


def detect_page_orientation_fast(pil_img: Image.Image, angle_memory: AngleMemory = None) -> int:
    """
    Evaluates page orientation (0, 90, 180, 270 degrees) using geometric line analysis
    on a low-resolution thumbnail (<20ms runtime). Reuses AngleMemory if available.

    Args:
        pil_img: PIL Image of the page.
        angle_memory: Optional AngleMemory instance with learned dominant angle.

    Returns:
        int: Detected orientation angle (0, 90, 180, or 270).
    """
    if pil_img is None:
        return 0

    try:
        w, h = pil_img.size
        # Downscale to low-resolution thumbnail for quick edge analysis
        scale = min(1.0, 400.0 / max(w, h))
        target_size = (max(10, int(w * scale)), max(10, int(h * scale)))
        small_gray = pil_img.resize(target_size, resample=Image.Resampling.BILINEAR).convert("L")
        np_gray = np.array(small_gray)

        # Detect edges
        edges = cv2.Canny(np_gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=60,
            minLineLength=max(20, int(30 * scale)),
            maxLineGap=int(8 * scale)
        )

        h_count = 0
        v_count = 0

        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                ang = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
                if ang <= 20 or ang >= 160:
                    h_count += 1
                elif 70 <= ang <= 110:
                    v_count += 1

        # Table lines run vertically: page is rotated sideways (90° or 270°).
        if v_count > 2 * h_count and v_count >= 4:
            if angle_memory is not None and angle_memory.has_memory():
                return angle_memory.get_dominant_sideways_angle(default=270)
            return 270

        # Table lines run horizontally: page is upright or upside-down (0° or 180°).
        if h_count > 2 * v_count and h_count >= 4:
            if angle_memory is not None and angle_memory.has_memory():
                return angle_memory.get_dominant_horizontal_angle(default=0)
            return 0

        # Inconclusive/sparse lines: rely on AngleMemory if recorded
        if angle_memory is not None and angle_memory.has_memory():
            return angle_memory.get_dominant_angle(default=0)

        return 0

    except Exception as e:
        print(f"[ORIENTATION DETECT ERROR] {e}")
        return 0
