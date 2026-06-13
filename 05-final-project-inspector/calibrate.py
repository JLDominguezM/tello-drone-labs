"""Headless calibration utility.

Two modes:

  --mode hsv    Place the target so it fills the central patch of the
                frame; the script averages the HSV samples and prints
                the lower/upper bounds you can paste into `config.py`.

  --mode focal  Place the target at a known distance; the script
                detects it with the current HSV bounds and computes the
                focal length in pixels from
                    f = w_px * d / W_real.

Sources accepted via --source:
    tello   the live Tello stream (default)
    cam     a local webcam (--cam <index>)
    video   a recorded mp4 (--video <path>)
"""
import argparse
import os
import time

import cv2
import numpy as np

import config as C
import vision
from tello_driver import Tello, TelloStream


def open_source(args):
    """Return (read_fn, close_fn) for the chosen source."""
    if args.source == 'tello':
        drone = Tello()
        if drone.connect() != 'ok':
            print("No response from the Tello. Are you on the right WiFi?")
        drone.streamon()
        time.sleep(2.0)
        stream = TelloStream().start()

        def close():
            stream.stop()
            drone.streamoff()
            drone.close()

        return stream.read, close

    cap = cv2.VideoCapture(args.video if args.source == 'video' else args.cam)
    return cap.read, cap.release


def grab_frames(read_fn, n, budget=20.0):
    """Collect up to `n` valid frames within `budget` seconds."""
    frames, t0 = [], time.time()
    while len(frames) < n and time.time() - t0 < budget:
        ret, raw = read_fn()
        if ret and raw is not None:
            frames.append(cv2.resize(raw, (C.FRAME_W, C.FRAME_H)))
        else:
            time.sleep(0.03)
    return frames


def calib_hsv(args, read_fn):
    r = args.roi
    cx, cy = C.CENTER_X, C.CENTER_Y
    print(f"Place the target so it fills the centre of the frame...")
    time.sleep(1.0)
    frames = grab_frames(read_fn, args.frames)
    if not frames:
        print("Could not capture any frame.")
        return
    patches = [cv2.cvtColor(f[cy - r:cy + r, cx - r:cx + r],
                            cv2.COLOR_BGR2HSV) for f in frames]
    px = np.concatenate([p.reshape(-1, 3) for p in patches], axis=0)
    h, s, v = px[:, 0], px[:, 1], px[:, 2]
    lower = (int(max(0, np.percentile(h, 10) - 5)),
             int(max(40, np.percentile(s, 10) - 25)),
             int(max(40, np.percentile(v, 10) - 25)))
    upper = (int(min(179, np.percentile(h, 90) + 5)), 255, 255)
    print("\n--- Paste into config.py ---")
    print(f"OBSTACLE_HSV_LOWER = {lower}")
    print(f"OBSTACLE_HSV_UPPER = {upper}")
    print("----------------------------")
    if abs(np.percentile(h, 90) - np.percentile(h, 10)) > 90:
        print("Note: hue spreads across the wrap point (red), tune by hand.")

    f = frames[-1].copy()
    cv2.rectangle(f, (cx - r, cy - r), (cx + r, cy + r), (0, 255, 0), 2)
    mask = cv2.inRange(cv2.cvtColor(f, cv2.COLOR_BGR2HSV),
                       np.array(lower), np.array(upper))
    cv2.imwrite(os.path.join(C.EVIDENCE_DIR, 'calib_hsv.png'), f)
    cv2.imwrite(os.path.join(C.EVIDENCE_DIR, 'calib_mask.png'), mask)
    print(f"Wrote {C.EVIDENCE_DIR}/calib_hsv.png and calib_mask.png")


def calib_focal(args, read_fn):
    det = vision.obstacle_detector()
    print(f"Place the target at {args.dist} cm and hold it still...")
    time.sleep(1.0)
    widths = []
    last = None
    for f in grab_frames(read_fn, args.frames):
        d = det.detect(f)
        if d.found:
            widths.append(d.bbox[2])
            last = (f, d)
    if not widths:
        print("No detection. Calibrate HSV first with --mode hsv.")
        return
    w_px = float(np.median(widths))
    focal = w_px * args.dist / C.OBSTACLE_REAL_WIDTH_CM
    print("\n--- Paste into config.py ---")
    print(f"FOCAL_PX = {focal:.1f}    "
          f"# W_real={C.OBSTACLE_REAL_WIDTH_CM}cm, d={args.dist}cm, "
          f"w_px~{w_px:.0f}")
    print("----------------------------")
    if last:
        f, d = last
        det.draw(f, d)
        cv2.imwrite(os.path.join(C.EVIDENCE_DIR, 'calib_focal.png'), f)


def main():
    ap = argparse.ArgumentParser(description="Headless HSV / focal calibration.")
    ap.add_argument('--mode', choices=['hsv', 'focal'], default='hsv')
    ap.add_argument('--source', choices=['tello', 'cam', 'video'], default='tello')
    ap.add_argument('--video', type=str, help='path to mp4 when --source video')
    ap.add_argument('--cam', type=int, default=0, help='webcam index when --source cam')
    ap.add_argument('--dist', type=float, default=100.0,
                    help='known distance in cm when --mode focal')
    ap.add_argument('--roi', type=int, default=40,
                    help='half side of the central HSV sampling patch (px)')
    ap.add_argument('--frames', type=int, default=60,
                    help='number of frames to average')
    args = ap.parse_args()

    os.makedirs(C.EVIDENCE_DIR, exist_ok=True)
    read_fn, close_fn = open_source(args)
    try:
        if args.mode == 'hsv':
            calib_hsv(args, read_fn)
        else:
            calib_focal(args, read_fn)
    finally:
        close_fn()


if __name__ == '__main__':
    main()
