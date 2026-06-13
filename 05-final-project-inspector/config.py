"""Constants for the Inspector mission. Every tunable parameter lives
here so the planner code stays focused on logic.

Numbers were measured during bench calibration with `calibrate.py` and
verified during the approved flight on 2026-06-03.
"""
import os


# Tello SDK link (UDP)
TELLO_IP    = '192.168.10.1'
CMD_PORT    = 8889   # commands and their text responses
STATE_PORT  = 8890   # telemetry push stream
VIDEO_URL   = 'udp://@0.0.0.0:11111?overrun_nonfatal=1&fifo_size=50000000'
CMD_TIMEOUT = 7.0

# Frame and control loop
FRAME_W   = 480
FRAME_H   = 360
CENTER_X  = FRAME_W // 2
CENTER_Y  = FRAME_H // 2
RC_HZ     = 20
VIDEO_FPS = 20

# HSV segmentation for the orange cone. Hue 0..8 covers the red/orange
# end of the spectrum, the very high saturation lower bound rejects any
# pastel surface so only the cone fires.
OBSTACLE_HSV_LOWER = (0, 226, 130)
OBSTACLE_HSV_UPPER = (8, 255, 255)
MIN_CONTOUR_AREA   = 800
MORPH_KERNEL       = 5
GAUSS_KERNEL       = 11

# Distance estimation.
#
# Reference pinhole model (kept for didactic value):
#     d = f * W_real / w_px
#
# What the mission actually uses (no focal calibration needed):
#     d = DIST_REF_CM * sqrt(AREA_REF / area)
#
# DIST_REF_CM and AREA_REF were measured on the bench: the cone
# projects to roughly AREA_REF px^2 at DIST_REF_CM cm.
FOCAL_PX               = 460.0
OBSTACLE_REAL_WIDTH_CM = 10.0
DIST_REF_CM            = 150.0
AREA_REF               = 17500.0

# Motion and safety
DEFAULT_SPEED = 30    # cm/s for the SDK `speed` command
BATTERY_MIN   = 20    # below this: do not take off
BATTERY_SAFE  = 30    # recommended threshold for a stable flight

# Output paths
_BASE        = os.path.dirname(os.path.abspath(__file__))
EVIDENCE_DIR = os.path.join(_BASE, 'evidence')
FIGURES_DIR  = os.path.join(_BASE, 'figures')
