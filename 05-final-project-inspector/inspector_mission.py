"""Inspector mission entry point. Dynamic image based visual servoing.

State machine:

    SEARCH -> APPROACH -> ORBIT_STATIC -> ORBIT_DYNAMIC -> CAPTURE -> LAND

Both orbit phases share the same control law. The split into a static
phase (target fixed) and a dynamic phase (operator moves the target)
makes the experiment a controlled comparison: the planner reacts to a
perturbation only in the second phase, but the same gains are in use
throughout.

Run with the live OpenCV window:
    python3 inspector_mission.py

Or headless (only writes the mp4):
    python3 inspector_mission.py --no-show
"""
import argparse
import csv
import os
import time
from dataclasses import dataclass
from enum import Enum

import cv2

import config as C
import vision
from tello_driver import Tello, TelloStream


# --- tunable parameters ------------------------------------------------
SEARCH_YAW = 30                  # constant rc yaw while searching
SEARCH_TIMEOUT = 25.0            # s without detection then LAND
APPROACH_KP_YAW = 0.30
APPROACH_YAW_CLAMP = 50
APPROACH_PITCH = 15
APPROACH_CENTER_DEADBAND = 60    # px
APPROACH_TIMEOUT = 18.0
LOST_FRAMES_TO_SEARCH = 12       # consecutive misses to go back to SEARCH
AREA_CLOSE = 35000               # area that triggers ORBIT
ORBIT_ROLL = 25                  # rc roll during orbit
ORBIT_KP_YAW = 0.30
ORBIT_YAW_CLAMP = 45
ORBIT_AREA_TARGET = AREA_CLOSE
ORBIT_KP_PITCH = 0.0008
ORBIT_PITCH_CLAMP = 12
ORBIT_LOST_YAW = -20

ORBIT_STATIC_DURATION = 25.0     # phase 1: target fixed
ORBIT_DYNAMIC_DURATION = 25.0    # phase 2: operator moves the target

CAPTURE_DURATION = 1.2
MAX_MISSION_TIME = 120.0
BATTERY_MIN = 25


class P(Enum):
    SEARCH = 'SEARCH'
    APPROACH = 'APPROACH'
    ORBIT_STATIC = 'ORBIT_STATIC'
    ORBIT_DYNAMIC = 'ORBIT_DYNAMIC'
    CAPTURE = 'CAPTURE'
    LAND = 'LAND'
    DONE = 'DONE'


WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (0, 0, 255)
BLUE = (255, 128, 0)
ORANGE = (0, 165, 255)
YELLOW = (0, 255, 255)


@dataclass
class Decision:
    phase: P
    action: str
    rc: tuple
    text: str
    color: tuple = WHITE


def clip(v, lo, hi):
    return max(lo, min(hi, v))


class InspectorPlanner:
    """Pure planner. Knows nothing about hardware; the executor below
    feeds it detections and applies its `Decision.rc` to the drone."""

    def __init__(self):
        self.phase = P.SEARCH
        self.t0_phase = time.time()
        self.lost_count = 0
        self.events = []

    def start(self, now=None):
        now = now or time.time()
        self.phase = P.SEARCH
        self.t0_phase = now
        self.lost_count = 0
        self._log(now, "starting search")

    def _enter(self, phase, now, msg=''):
        if phase != self.phase:
            self.phase = phase
            self.t0_phase = now
            self._log(now, msg or f"-> {phase.value}")

    def _log(self, now, msg):
        self.events.append((now, self.phase.value, msg))
        print(f"[FSM {self.phase.value:14s}] {msg}")

    def update(self, obstacle, now=None):
        now = now or time.time()
        e = now - self.t0_phase
        if self.phase == P.SEARCH:        return self._search(obstacle, now, e)
        if self.phase == P.APPROACH:      return self._approach(obstacle, now, e)
        if self.phase == P.ORBIT_STATIC:  return self._orbit_static(obstacle, now, e)
        if self.phase == P.ORBIT_DYNAMIC: return self._orbit_dynamic(obstacle, now, e)
        if self.phase == P.CAPTURE:       return self._capture(now, e)
        if self.phase == P.LAND:
            return Decision(P.LAND, 'LAND', (0, 0, 0, 0), "LANDING", GREEN)
        return Decision(P.DONE, 'DONE', (0, 0, 0, 0), "MISSION DONE", GREEN)

    def _search(self, obstacle, now, e):
        if obstacle.found:
            self.lost_count = 0
            self._enter(P.APPROACH, now,
                        f"target acquired (area={obstacle.area:.0f}) -> approach")
            return self._approach(obstacle, now, 0.0)
        if e > SEARCH_TIMEOUT:
            self._enter(P.LAND, now, "search timeout, landing")
            return Decision(P.LAND, 'LAND', (0, 0, 0, 0),
                            "NO TARGET -> LAND", YELLOW)
        return Decision(P.SEARCH, 'SEARCH', (0, 0, 0, SEARCH_YAW),
                        f"SEARCHING ({e:.1f}/{SEARCH_TIMEOUT:.0f}s)", BLUE)

    def _approach(self, obstacle, now, e):
        if not obstacle.found:
            self.lost_count += 1
            if self.lost_count >= LOST_FRAMES_TO_SEARCH:
                self._enter(P.SEARCH, now, "lost target, back to search")
                return Decision(P.SEARCH, 'SEARCH', (0, 0, 0, SEARCH_YAW),
                                "searching...", BLUE)
            return Decision(P.APPROACH, 'APPROACH', (0, 0, 0, 0),
                            f"APPROACHING (lost {self.lost_count}f)", ORANGE)
        self.lost_count = 0
        if e > APPROACH_TIMEOUT:
            self._enter(P.LAND, now, "approach timeout, landing")
            return Decision(P.LAND, 'LAND', (0, 0, 0, 0),
                            "TIMEOUT -> LAND", YELLOW)
        if obstacle.area >= AREA_CLOSE:
            self._enter(P.ORBIT_STATIC, now,
                        f"close (area={obstacle.area:.0f}/{AREA_CLOSE}) -> "
                        f"phase 1: static orbit ({ORBIT_STATIC_DURATION:.0f}s), "
                        f"do not move the target")
            return self._orbit_static(obstacle, now, 0.0)
        yaw = clip(int(APPROACH_KP_YAW * obstacle.offset_x),
                   -APPROACH_YAW_CLAMP, APPROACH_YAW_CLAMP)
        centered = abs(obstacle.offset_x) < APPROACH_CENTER_DEADBAND
        pitch = APPROACH_PITCH if centered else 0
        return Decision(
            P.APPROACH, 'APPROACH', (0, pitch, 0, yaw),
            f"APPROACH area={obstacle.area:.0f}/{AREA_CLOSE} "
            f"off={obstacle.offset_x} "
            f"{'centered->advance' if centered else 'centering'}",
            ORANGE,
        )

    def _orbit_static(self, obstacle, now, e):
        if e >= ORBIT_STATIC_DURATION:
            self._enter(P.ORBIT_DYNAMIC, now,
                        ">>> phase 2: NOW MOVE THE TARGET, drone will follow <<<")
            return self._orbit_dynamic(obstacle, now, 0.0)
        return self._orbit_control(
            obstacle, e, P.ORBIT_STATIC, ORBIT_STATIC_DURATION,
            "PHASE 1/2 STATIC: do not move the target",
        )

    def _orbit_dynamic(self, obstacle, now, e):
        if e >= ORBIT_DYNAMIC_DURATION:
            self._enter(P.CAPTURE, now, "orbit phases done, capture photo")
            return Decision(P.CAPTURE, 'CAPTURE', (0, 0, 0, 0),
                            "STABILISE -> PHOTO", GREEN)
        return self._orbit_control(
            obstacle, e, P.ORBIT_DYNAMIC, ORBIT_DYNAMIC_DURATION,
            "PHASE 2/2 DYNAMIC: move the target",
        )

    def _orbit_control(self, obstacle, e, phase, duration, label):
        """Yaw centres the target, pitch holds the distance using the
        area error, roll is a constant lateral push. If the target is
        not visible, stop the lateral motion and yaw to search for it."""
        if not obstacle.found:
            return Decision(
                phase, 'ORBIT_LOOK', (0, 0, 0, ORBIT_LOST_YAW),
                f"{label} | target lost, searching ({e:.1f}/{duration:.0f}s)",
                YELLOW,
            )
        yaw = clip(int(ORBIT_KP_YAW * obstacle.offset_x),
                   -ORBIT_YAW_CLAMP, ORBIT_YAW_CLAMP)
        area_err = ORBIT_AREA_TARGET - obstacle.area
        pitch = clip(int(ORBIT_KP_PITCH * area_err),
                     -ORBIT_PITCH_CLAMP, ORBIT_PITCH_CLAMP)
        return Decision(
            phase, 'ORBIT', (ORBIT_ROLL, pitch, 0, yaw),
            f"{label} ({e:.1f}/{duration:.0f}s) "
            f"area={obstacle.area:.0f}/{ORBIT_AREA_TARGET} "
            f"yaw={yaw} pitch={pitch}",
            ORANGE,
        )

    def _capture(self, now, e):
        if e >= CAPTURE_DURATION:
            self._enter(P.LAND, now, "photo taken, landing")
            return Decision(P.LAND, 'LAND', (0, 0, 0, 0), "LANDING", GREEN)
        return Decision(P.CAPTURE, 'CAPTURE', (0, 0, 0, 0),
                        f"CAPTURING ({e:.1f}/{CAPTURE_DURATION:.1f}s)", GREEN)


# --- HUD ---------------------------------------------------------------
def _put(frame, text, org, color=WHITE, scale=0.5, thick=1):
    cv2.putText(frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale,
                (0, 0, 0), thick + 2, cv2.LINE_AA)
    cv2.putText(frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale,
                color, thick, cv2.LINE_AA)


def draw_hud(frame, decision, obstacle, telem, elapsed):
    cv2.line(frame, (C.CENTER_X, 0), (C.CENTER_X, C.FRAME_H), (60, 60, 60), 1)
    cv2.line(frame, (0, C.CENTER_Y), (C.FRAME_W, C.CENTER_Y), (60, 60, 60), 1)
    cv2.line(frame,
             (C.CENTER_X - APPROACH_CENTER_DEADBAND, C.CENTER_Y),
             (C.CENTER_X + APPROACH_CENTER_DEADBAND, C.CENTER_Y),
             (100, 100, 100), 1)

    if obstacle.found:
        x, y, w, h = obstacle.bbox
        cv2.rectangle(frame, (x, y), (x + w, y + h), ORANGE, 2)
        cv2.circle(frame, (obstacle.cx, obstacle.cy), 4, ORANGE, -1)

    _put(frame, f"{decision.phase.value} | {decision.action}",
         (8, 22), decision.color, 0.6, 2)
    _put(frame, decision.text, (8, 44), decision.color, 0.5, 1)

    oa = f"{obstacle.area:.0f}" if obstacle.found else "-"
    od = f"{obstacle.dist_cm:.0f}cm" if obstacle.found else "-"
    ox = obstacle.offset_x if obstacle.found else '-'
    _put(frame,
         f"TARGET: {'YES' if obstacle.found else 'no'}  area={oa}/{AREA_CLOSE}  "
         f"d~{od}  off={ox}",
         (8, C.FRAME_H - 30),
         ORANGE if obstacle.found else (160, 160, 160))

    t = telem or {}
    _put(frame,
         f"bat:{t.get('bat','-')}%  tof:{t.get('tof','-')}cm  "
         f"h:{t.get('h','-')}cm  yaw:{t.get('yaw','-')}  t:{elapsed:.1f}s",
         (8, C.FRAME_H - 12), (200, 255, 200))


CSV_HEADER = ['t', 'phase', 'action', 'bat', 'tof', 'h', 'yaw',
              'obs_found', 'obs_area', 'obs_dist', 'obs_off_x',
              'rc_a', 'rc_b', 'rc_c', 'rc_d']


def csv_row(t, dec, obs, telem):
    return [
        round(t, 3), dec.phase.value, dec.action,
        telem.get('bat'), telem.get('tof'), telem.get('h'), telem.get('yaw'),
        int(obs.found), round(obs.area, 1),
        round(obs.dist_cm, 1) if obs.found else '',
        obs.offset_x if obs.found else '',
        *dec.rc,
    ]


# --- executor ----------------------------------------------------------
def run(show=True):
    os.makedirs(C.EVIDENCE_DIR, exist_ok=True)
    if show and not vision.gui_available():
        print("Note: OpenCV without GUI, running headless. The mp4 will still be written.")
        show = False

    ts = time.strftime('%Y%m%d_%H%M%S')
    video_out = os.path.join(C.EVIDENCE_DIR, f'inspector_mission_{ts}.mp4')
    csv_out = os.path.join(C.EVIDENCE_DIR, f'telemetry_inspector_{ts}.csv')
    photo_path = os.path.join(C.EVIDENCE_DIR, f'inspection_{ts}.png')
    print("Outputs for this run (timestamped, never overwritten):")
    print(f"  Video : {video_out}")
    print(f"  CSV   : {csv_out}")
    print(f"  Photo : {photo_path}")

    drone = Tello()
    print("Connecting (SDK mode)...")
    drone.connect()
    time.sleep(1.0)
    bat = drone.get_battery()
    print(f"Battery: {bat}%")
    if bat is None or bat < BATTERY_MIN:
        print(f"Battery too low ({bat}% < {BATTERY_MIN}%). Aborting.")
        drone.close()
        return

    drone.streamon()
    time.sleep(2.0)
    stream = TelloStream().start()
    detector = vision.obstacle_detector()
    planner = InspectorPlanner()

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(video_out, fourcc, C.VIDEO_FPS,
                             (C.FRAME_W, C.FRAME_H))
    csv_f = open(csv_out, 'w', newline='')
    log = csv.writer(csv_f)
    log.writerow(CSV_HEADER)

    photo_saved = False
    prev_phase = None
    t_start = time.time()
    period = 1.0 / C.RC_HZ

    try:
        print("Taking off")
        h0 = drone.takeoff()
        if h0 is not None:
            print(f"Takeoff confirmed (altitude {h0} cm)")
        else:
            print("Warning: no altitude confirmation after takeoff, continuing.")
        time.sleep(1.5)
        planner.start()

        while True:
            now = time.time()
            elapsed = now - t_start
            ret, raw = stream.read()
            if not ret or raw is None:
                time.sleep(0.05)
                continue
            frame = cv2.resize(raw, (C.FRAME_W, C.FRAME_H))
            obstacle = detector.detect(frame)
            telem = drone.telemetry()
            decision = planner.update(obstacle, now)
            draw_hud(frame, decision, obstacle, telem, elapsed)
            writer.write(frame)
            log.writerow(csv_row(elapsed, decision, obstacle, telem))

            if (decision.phase == P.CAPTURE
                    and prev_phase != P.CAPTURE
                    and not photo_saved):
                cv2.imwrite(photo_path, frame)
                photo_saved = True
                print(f"Inspection photo saved: {photo_path}")

            if show:
                cv2.imshow("Inspector (q=land, e=emergency)", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                if key == ord('e'):
                    drone.emergency()
                    break

            drone.send_rc(*decision.rc)
            if decision.phase in (P.LAND, P.DONE):
                break
            if elapsed > MAX_MISSION_TIME:
                print("MAX_MISSION_TIME reached, landing.")
                break

            prev_phase = decision.phase
            dt = time.time() - now
            if dt < period:
                time.sleep(period - dt)

    finally:
        print("\nFinishing: rc 0 + land")
        drone.send_rc(0, 0, 0, 0)
        time.sleep(0.3)
        if drone.is_flying:
            drone.land()
        writer.release()
        csv_f.close()
        stream.stop()
        drone.streamoff()
        drone.close()
        if show:
            try:
                cv2.destroyAllWindows()
            except cv2.error:
                pass
        status = "(saved)" if photo_saved else "(not taken, never reached CAPTURE)"
        print("\nEvidence for this run:")
        print(f"  Video : {video_out}")
        print(f"  CSV   : {csv_out}")
        print(f"  Photo : {photo_path} {status}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser(
        description="Inspector mission (IBVS + orbit + photo).")
    ap.add_argument('--no-show', action='store_true',
                    help='Headless mode: do not open the OpenCV window.')
    args = ap.parse_args()
    run(show=not args.no_show)
