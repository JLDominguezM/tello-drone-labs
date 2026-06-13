# Lab 04: Visual Tracking

The first lab where perception and control run in the same loop. The
drone segments a colour blob with OpenCV and uses a PD controller to
keep the blob centred while hovering. The same building blocks return
in the final project.

[![Demo](https://img.shields.io/badge/Demo_video-YouTube-red?logo=youtube)](https://youtu.be/FGLN-wSKNz8)

## Scripts

| File | What it does |
|---|---|
| `01_color_detection.py` | Read the live stream, run an HSV based detection, draw the bounding box, save an mp4. No flight. |
| `02_visual_tracking.py` | Same detection while in the air. PD on yaw + throttle keeps the blob centred. Press `q` to land. |
| `reset_tello.py` | Push `command` / `streamoff` / `rc 0 0 0 0`. Use it if a previous script aborted with the drone still in SDK mode. |

## Vision pipeline

The pipeline below is identical in both scripts. Tune the bounds with a
sample frame and a colour picker; the defaults are aimed at green.

```
frame -> resize 480x360 -> GaussianBlur 11x11 -> BGR2HSV
      -> inRange(LOWER, UPPER)
      -> erode(2) -> dilate(2)
      -> findContours(RETR_EXTERNAL)
      -> largest area > MIN_AREA -> boundingRect
```

## Control law

For the tracking script, `(cx, cy)` is the centroid of the bounding
box. The control is plain PD with a deadband and a clamp on each
channel:

```
error_yaw = cx - FRAME_WIDTH/2
error_z   = FRAME_HEIGHT/2 - cy

if |error| < deadband: error = 0

yaw     = clip(Kp_yaw * error_yaw + Kd_yaw * (error_yaw - prev_error_yaw),
               -clamp_yaw, +clamp_yaw)
throttle = clip(Kp_z   * error_z   + Kd_z   * (error_z - prev_error_z),
                -clamp_z, +clamp_z)

rc 0 0 throttle yaw
```

Roll and pitch are left at zero. The drone only rotates and changes
altitude to follow the target.

## Threading

The `TelloStream` helper reads the video stream in a daemon thread, so
the main loop is never blocked by a slow `cap.read()` call. A second
timer in the main loop sends an `rc` every 100 ms and a third one
sends a `battery?` heartbeat every 5 s to keep the SDK mode alive.

## Run

```
# Calibrate the colour first:
python3 01_color_detection.py

# Then fly the tracker (make sure you have at least 1.5 m of clearance
# in each direction, the controller is reactive but the drone can drift):
python3 02_visual_tracking.py

# Recovery if a script left the link in a bad state:
python3 reset_tello.py
```
