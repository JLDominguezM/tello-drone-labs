"""Visual tracking with a PD controller on yaw and throttle.

While flying, the drone reads the same colour mask as script 01 and
drives two control channels:

  yaw      = Kp * error_yaw + Kd * (error_yaw - prev_error_yaw)
  throttle = Kp * error_z   + Kd * (error_z   - prev_error_z)

`error_yaw` is the horizontal pixel offset between the centroid of the
detection and the centre of the frame. `error_z` is the vertical
offset. Both are clamped before being sent over `rc` so the drone never
crosses an aggressive setpoint.

Two background timers run concurrently with the vision loop:

  * a heartbeat to port 8889 every 5 s, otherwise the firmware drops
    out of SDK mode and the next `rc` is ignored;
  * the `rc` itself at 10 Hz, faster than the perception loop, so that
    the firmware always has a fresh setpoint.

Press `q` to land cleanly.
"""
import socket
import threading
import time

import cv2
import numpy as np


TELLO_IP = '192.168.10.1'
TELLO_PORT = 8889
VIDEO_URL = 'udp://@0.0.0.0:11111'
OUTPUT_FILE = 'visual_tracking_evidence.mp4'

LOWER = np.array([35, 60, 60])
UPPER = np.array([85, 255, 255])
MIN_AREA = 1000

KP_YAW, KD_YAW = 0.25, 0.15
KP_Z, KD_Z = 0.2, 0.1
DEADBAND_YAW = 40
DEADBAND_Z = 30
CLAMP_YAW = 60
CLAMP_Z = 25


class TelloStream:
    def __init__(self, url):
        self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        self.ret = False
        self.frame = None
        self.stopped = False

    def start(self):
        threading.Thread(target=self._update, daemon=True).start()
        return self

    def _update(self):
        while not self.stopped:
            self.ret, self.frame = self.cap.read()

    def read(self):
        return self.ret, self.frame

    def stop(self):
        self.stopped = True
        if self.cap.isOpened():
            self.cap.release()


def send_command(sock, command, tello_addr, expect_response=True):
    try:
        sock.sendto(command.encode('utf-8'), tello_addr)
        if not expect_response:
            return None
        response, _ = sock.recvfrom(1024)
        return response.decode('utf-8').strip()
    except Exception:
        return None


def main():
    tello_addr = (TELLO_IP, TELLO_PORT)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', TELLO_PORT))
    sock.settimeout(1.0)

    print("Initialising Tello (keep-alive active)")
    send_command(sock, 'command', tello_addr)
    battery = send_command(sock, 'battery?', tello_addr)
    print(f"Battery: {battery}%")

    send_command(sock, 'streamon', tello_addr)
    time.sleep(2)

    stream = TelloStream(VIDEO_URL).start()

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(OUTPUT_FILE, fourcc, 20.0, (480, 360))

    prev_error_yaw = 0
    prev_error_z = 0
    kernel = np.ones((5, 5), np.uint8)

    global_throttle = 0
    global_yaw = 0

    print("Taking off")
    send_command(sock, 'takeoff', tello_addr)
    time.sleep(5)

    print("Tracking enabled. Press q to land.")
    last_rc_time = time.time()
    last_heartbeat = time.time()

    try:
        while True:
            ret, frame = stream.read()
            if ret and frame is not None:
                frame = cv2.resize(frame, (480, 360))
                blurred = cv2.GaussianBlur(frame, (11, 11), 0)
                hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv, LOWER, UPPER)
                mask = cv2.erode(mask, kernel, iterations=2)
                mask = cv2.dilate(mask, kernel, iterations=2)

                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                               cv2.CHAIN_APPROX_SIMPLE)
                found = False
                if contours:
                    largest = max(contours, key=cv2.contourArea)
                    if cv2.contourArea(largest) > MIN_AREA:
                        found = True
                        x, y, w, h = cv2.boundingRect(largest)
                        cx, cy = x + w // 2, y + h // 2

                        error_yaw = cx - 240
                        error_z = 180 - cy
                        if abs(error_yaw) < DEADBAND_YAW:
                            error_yaw = 0
                        if abs(error_z) < DEADBAND_Z:
                            error_z = 0

                        global_yaw = int(KP_YAW * error_yaw
                                         + KD_YAW * (error_yaw - prev_error_yaw))
                        global_yaw = int(np.clip(global_yaw, -CLAMP_YAW, CLAMP_YAW))

                        global_throttle = int(KP_Z * error_z
                                              + KD_Z * (error_z - prev_error_z))
                        global_throttle = int(np.clip(global_throttle, -CLAMP_Z, CLAMP_Z))

                        prev_error_yaw, prev_error_z = error_yaw, error_z
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                if not found:
                    global_throttle, global_yaw = 0, 0
                    cv2.putText(frame, "SEARCHING", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                else:
                    cv2.putText(frame, "TRACKING", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                out.write(frame)
                cv2.imshow("Tracking", frame)

            now = time.time()
            if now - last_heartbeat > 5.0:
                sock.sendto(b'battery?', tello_addr)
                last_heartbeat = now
            if now - last_rc_time > 0.1:
                send_command(sock, f"rc 0 0 {global_throttle} {global_yaw}",
                             tello_addr, expect_response=False)
                last_rc_time = now

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        print("\nLanding")
        send_command(sock, "rc 0 0 0 0", tello_addr, expect_response=False)
        time.sleep(0.5)
        send_command(sock, "land", tello_addr)
        stream.stop()
        out.release()
        send_command(sock, 'streamoff', tello_addr)
        cv2.destroyAllWindows()
        sock.close()


if __name__ == '__main__':
    main()
