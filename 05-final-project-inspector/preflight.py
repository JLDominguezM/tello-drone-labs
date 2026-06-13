"""Pre-flight check. Does NOT take off. Verifies, in order:

  1. SDK link on port 8889.
  2. Battery state of charge.
  3. Telemetry push on port 8890.
  4. H.264 video stream on port 11111.
  5. Cone detection in the current frame.

If the SDK check fails the rest is skipped instead of hanging on
timeouts. Anything written to `evidence/` is useful as visual proof that
the calibration is still valid.
"""
import os
import time

import cv2

import config as C
import vision
from tello_driver import Tello, TelloStream


OK = "[  OK  ]"
FAIL = "[ FAIL ]"
WARN = "[ WARN ]"


def main():
    os.makedirs(C.EVIDENCE_DIR, exist_ok=True)
    results = []
    print("=== Preflight (no takeoff) ===\n")

    drone = Tello()

    # 1) SDK
    resp = drone.connect()
    ok_conn = (resp == 'ok')
    print(f"{OK if ok_conn else FAIL} 1. SDK link ('command' -> {resp!r})")
    results.append(('SDK link', ok_conn))

    if not ok_conn:
        print(f"\n{FAIL} No response from the drone. Check:")
        print("   - You are on the Tello WiFi network (not the internet).")
        print("   - Firewall is not blocking UDP 8889 (sudo ufw allow 8889/udp).")
        print("   - Another script did not leave the socket open.")
        drone.close()
        _summary(results)
        return

    # 2) Battery
    time.sleep(1.0)
    bat = drone.get_battery()
    ok_bat = bat is not None and bat >= C.BATTERY_MIN
    tag = OK if (bat is not None and bat >= C.BATTERY_SAFE) else (WARN if ok_bat else FAIL)
    print(f"{tag} 2. Battery: {bat}% "
          f"(min {C.BATTERY_MIN}, recommended {C.BATTERY_SAFE})")
    results.append(('Battery', ok_bat))

    # 3) Telemetry push
    t0 = time.time()
    telem = {}
    while time.time() - t0 < 4.0:
        telem = drone.telemetry()
        if telem.get('tof') is not None or telem.get('bat') is not None:
            break
        time.sleep(0.2)
    ok_telem = telem.get('tof') is not None
    print(f"{OK if ok_telem else FAIL} 3. Telemetry (8890): "
          f"tof={telem.get('tof')}cm h={telem.get('h')}cm "
          f"yaw={telem.get('yaw')} bat={telem.get('bat')}%")
    results.append(('Telemetry 8890', ok_telem))

    # 4) Video
    drone.streamon()
    time.sleep(2.0)
    stream = TelloStream().start()
    t0, frame = time.time(), None
    while time.time() - t0 < 10.0:
        ret, raw = stream.read()
        if ret and raw is not None:
            frame = raw
            break
        time.sleep(0.05)
    ok_video = frame is not None
    if ok_video:
        h, w = frame.shape[:2]
        print(f"{OK} 4. Video (11111): first frame {w}x{h}")
        frame = cv2.resize(frame, (C.FRAME_W, C.FRAME_H))
        cv2.imwrite(os.path.join(C.EVIDENCE_DIR, 'preflight_frame.png'), frame)
    else:
        print(f"{FAIL} 4. Video (11111): no frame in 10 s")
        print("        Wait a couple of seconds after streamon and retry.")
    results.append(('Video 11111', ok_video))

    # 5) Cone detection
    if ok_video:
        obs = vision.obstacle_detector()
        d = obs.detect(frame)
        print(f"{OK if d.found else WARN} 5. Orange cone: "
              + (f"area={d.area:.0f} d~{d.dist_cm:.0f}cm"
                 if d.found else "not visible right now"))
        cv2.imwrite(os.path.join(C.EVIDENCE_DIR, 'preflight_obstacle_mask.png'),
                    obs.mask(frame))
        print(f"        HSV mask written to "
              f"{C.EVIDENCE_DIR}/preflight_obstacle_mask.png")

    stream.stop()
    drone.streamoff()
    drone.close()
    _summary(results)


def _summary(results):
    print("\n=== Summary ===")
    for name, ok in results:
        print(f"  {OK if ok else FAIL} {name}")
    if results and all(ok for _, ok in results):
        print("\nReady. Next: python3 inspector_mission.py")
    else:
        print("\nFix the failures above before taking off.")


if __name__ == '__main__':
    main()
