"""Colour detection and distance estimation for the orange cone.

Areas are reported in px^2 over the canonical FRAME_W x FRAME_H frame,
so callers must resize the frame to that size before detecting.
"""
from dataclasses import dataclass

import cv2
import numpy as np

import config as C


_GUI = None


def gui_available():
    """Return True if this OpenCV build can open windows.

    The headless wheel cannot; the mp4 still gets written. Cached so the
    probe runs at most once per process.
    """
    global _GUI
    if _GUI is None:
        try:
            cv2.namedWindow('__probe__')
            cv2.destroyWindow('__probe__')
            _GUI = True
        except cv2.error:
            _GUI = False
    return _GUI


@dataclass
class Detection:
    found: bool = False
    cx: int = 0
    cy: int = 0
    area: float = 0.0
    bbox: tuple = (0, 0, 0, 0)
    dist_cm: float = float('inf')

    @property
    def offset_x(self):
        return self.cx - C.CENTER_X

    @property
    def offset_y(self):
        return self.cy - C.CENTER_Y


def estimate_distance(w_px, real_w_cm=C.OBSTACLE_REAL_WIDTH_CM,
                      focal_px=C.FOCAL_PX):
    """Pinhole distance: d = f * W_real / w_px. Requires focal calibration."""
    if w_px <= 0:
        return float('inf')
    return focal_px * real_w_cm / w_px


def distance_from_area(area):
    """Distance from apparent area, calibrated on the bench.

    d = DIST_REF_CM * sqrt(AREA_REF / area)

    Does not need a calibrated focal length, which makes it more robust
    than the pinhole model for this particular setup.
    """
    if area <= 0:
        return float('inf')
    return C.DIST_REF_CM * (C.AREA_REF / area) ** 0.5


class ColorDetector:
    """Detect a single colour blob in HSV space."""

    def __init__(self, lower, upper, name='object',
                 min_area=C.MIN_CONTOUR_AREA,
                 real_w_cm=C.OBSTACLE_REAL_WIDTH_CM):
        self.lower = np.array(lower, dtype=np.uint8)
        self.upper = np.array(upper, dtype=np.uint8)
        self.name = name
        self.min_area = min_area
        self.real_w_cm = real_w_cm
        self.kernel = np.ones((C.MORPH_KERNEL, C.MORPH_KERNEL), np.uint8)

    def mask(self, frame):
        blurred = cv2.GaussianBlur(frame, (C.GAUSS_KERNEL, C.GAUSS_KERNEL), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        m = cv2.inRange(hsv, self.lower, self.upper)
        m = cv2.erode(m, self.kernel, iterations=2)
        m = cv2.dilate(m, self.kernel, iterations=2)
        return m

    def detect(self, frame):
        """Return the Detection for the largest blob above min_area."""
        m = self.mask(frame)
        contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return Detection()
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        if area < self.min_area:
            return Detection()
        x, y, w, h = cv2.boundingRect(largest)
        return Detection(
            found=True,
            cx=x + w // 2,
            cy=y + h // 2,
            area=area,
            bbox=(x, y, w, h),
            dist_cm=distance_from_area(area),
        )

    def draw(self, frame, det, color=(0, 255, 0)):
        if not det.found:
            return frame
        x, y, w, h = det.bbox
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.circle(frame, (det.cx, det.cy), 4, color, -1)
        cv2.putText(frame, f"{self.name} d~{det.dist_cm:.0f}cm",
                    (x, max(y - 8, 12)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, color, 2)
        return frame


def obstacle_detector():
    return ColorDetector(
        C.OBSTACLE_HSV_LOWER, C.OBSTACLE_HSV_UPPER,
        name='OBSTACLE', real_w_cm=C.OBSTACLE_REAL_WIDTH_CM,
    )
