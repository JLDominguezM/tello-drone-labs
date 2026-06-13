"""HSV based colour detection on the live Tello video stream, without
flying.

Pipeline per frame:
  1. Read from the threaded `TelloStream` (so OpenCV reads do not block
     the keep-alive sender).
  2. Resize to 480x360 to bound the work per frame.
  3. Gaussian blur, then HSV threshold for the target colour.
  4. Morphological erode + dilate to clean speckle.
  5. Largest contour. If its area is above a minimum it is treated as
     the detection; a bounding box and label are drawn on the frame.

The annotated frames are saved to an mp4 as evidence and also shown in
a live window. Press `q` to exit.

Calibrate the HSV range before relying on the result: the defaults
below were measured for a green target under indoor lighting.
"""
import socket
import threading
import time

import cv2
import numpy as np


TELLO_IP = '192.168.10.1'
TELLO_PORT = 8889
VIDEO_URL = 'udp://@0.0.0.0:11111'
OUTPUT_FILE = 'color_detection_evidence.mp4'

LOWER = np.array([35, 60, 60])
UPPER = np.array([85, 255, 255])
MIN_AREA = 800


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
        self.cap.release()


def send_command(sock, command, tello_addr):
    sock.sendto(command.encode('utf-8'), tello_addr)


def main():
    tello_addr = (TELLO_IP, TELLO_PORT)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', TELLO_PORT))

    print("Detection mode, no flight")
    send_command(sock, 'command', tello_addr)
    send_command(sock, 'streamon', tello_addr)
    time.sleep(2)

    stream = TelloStream(VIDEO_URL).start()

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(OUTPUT_FILE, fourcc, 20.0, (480, 360))

    kernel = np.ones((5, 5), np.uint8)

    try:
        while True:
            ret, frame = stream.read()
            if not ret or frame is None:
                continue

            frame = cv2.resize(frame, (480, 360))
            blurred = cv2.GaussianBlur(frame, (11, 11), 0)
            hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, LOWER, UPPER)
            mask = cv2.erode(mask, kernel, iterations=2)
            mask = cv2.dilate(mask, kernel, iterations=2)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                           cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest = max(contours, key=cv2.contourArea)
                if cv2.contourArea(largest) > MIN_AREA:
                    x, y, w, h = cv2.boundingRect(largest)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, "DETECTION OK", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            out.write(frame)
            cv2.imshow("Color Detection", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        out.release()
        stream.stop()
        send_command(sock, 'streamoff', tello_addr)
        cv2.destroyAllWindows()
        sock.close()
        print(f"Saved: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
