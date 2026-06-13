"""Tello driver over raw UDP sockets, without the `robomaster` library.

Three channels are used:

  * 8889  outbound commands and request/response queries; also `rc`.
  * 8890  inbound semicolon separated telemetry pushed by the firmware
          a few times per second. Parsed in its own thread so it does
          not race with the command socket.
  * 11111 inbound H.264 video stream. Read by `TelloStream` with
          OpenCV in a dedicated thread.

The two classes here are intentionally small and stateless beyond what
the firmware itself tracks. Higher level logic lives in
`inspector_mission.py`.
"""
import os
import socket
import threading
import time

import cv2

import config as C


class TelloStream:
    """Read the H.264 stream in a background thread.

    The OpenCV `cap.release()` call must happen on the same thread that
    runs `cap.read()`. Releasing from another thread while a read is in
    flight corrupts the ffmpeg state and segfaults the process, which
    was the original symptom that pinned this design.
    """

    def __init__(self, url=C.VIDEO_URL):
        # Silence the noisy H.264 decoder warm-up logs.
        os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")
        self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        self.ret = False
        self.frame = None
        self.stopped = False
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._update, daemon=True)
        self._thread.start()
        return self

    def _update(self):
        while not self.stopped:
            if self.cap.isOpened():
                self.ret, self.frame = self.cap.read()
            else:
                time.sleep(0.05)
        if self.cap.isOpened():
            self.cap.release()

    def read(self):
        return self.ret, self.frame

    def stop(self):
        self.stopped = True
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None


class Tello:
    """Lightweight wrapper around the SDK 3.0 surface used by the
    Inspector mission.
    """

    def __init__(self, ip=C.TELLO_IP):
        self.addr = (ip, C.CMD_PORT)

        self.cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cmd_sock.bind(('', C.CMD_PORT))
        self.cmd_sock.settimeout(C.CMD_TIMEOUT)

        self.state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.state_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.state_sock.bind(('', C.STATE_PORT))
        self.state_sock.settimeout(1.0)

        self._state = {}
        self._state_lock = threading.Lock()
        self._stopped = False
        self.is_flying = False

    # ---- connection ---------------------------------------------------
    def connect(self):
        """Enter SDK mode and start the telemetry reader thread."""
        threading.Thread(target=self._state_loop, daemon=True).start()
        resp = self.send_command('command')
        self.send_command(f'speed {C.DEFAULT_SPEED}', wait=True)
        return resp

    # ---- commands -----------------------------------------------------
    def send_command(self, cmd, wait=True):
        """Send a command. If `wait` is True, return the text response."""
        try:
            self.cmd_sock.sendto(cmd.encode('utf-8'), self.addr)
        except OSError as e:
            print(f"[tello] error sending '{cmd}': {e}")
            return None
        if not wait:
            return None
        try:
            data, _ = self.cmd_sock.recvfrom(1024)
            return data.decode('utf-8').strip()
        except socket.timeout:
            print(f"[tello] no response (timeout) to '{cmd}'")
            return None

    def send_rc(self, a, b, c, d):
        """Continuous RC control. a=roll b=pitch c=throttle d=yaw."""
        self.send_command(f'rc {int(a)} {int(b)} {int(c)} {int(d)}', wait=False)

    def query(self, cmd):
        """One shot query (battery?, tof?, ...). Returns string or None."""
        return self.send_command(cmd, wait=True)

    # ---- flight helpers ----------------------------------------------
    def _drain(self):
        """Discard any datagram still queued on 8889.

        Useful after `takeoff`: the firmware sometimes acknowledges
        late, and the late `ok` would otherwise be parsed as the
        response to the next command.
        """
        self.cmd_sock.setblocking(False)
        try:
            while True:
                self.cmd_sock.recvfrom(1024)
        except (BlockingIOError, OSError):
            pass
        finally:
            self.cmd_sock.settimeout(C.CMD_TIMEOUT)

    def takeoff(self, confirm_timeout=8.0, min_height=30):
        """Send `takeoff` and confirm by reading the altitude on 8890.

        The synchronous `ok` reply to `takeoff` is unreliable: it can
        arrive late or be dropped. Confirming the manoeuvre by reading
        `h` from the telemetry stream is more robust.
        """
        self.send_command('takeoff', wait=False)
        self.is_flying = True
        t0 = time.time()
        while time.time() - t0 < confirm_timeout:
            h = self.get_state().get('h')
            if h is not None and h >= min_height:
                self._drain()
                return h
            time.sleep(0.2)
        self._drain()
        return None

    def land(self):
        self.send_rc(0, 0, 0, 0)
        r = self.send_command('land')
        self.is_flying = False
        return r

    def emergency(self):
        # `emergency` does not respond reliably, so it is sent a few
        # times to maximise the chance one datagram lands.
        for _ in range(3):
            self.send_command('emergency', wait=False)
        self.is_flying = False

    def streamon(self):
        return self.send_command('streamon')

    def streamoff(self):
        return self.send_command('streamoff')

    # ---- telemetry (port 8890) ---------------------------------------
    def _state_loop(self):
        while not self._stopped:
            try:
                data, _ = self.state_sock.recvfrom(1024)
            except (socket.timeout, OSError):
                continue
            parsed = {}
            for pair in data.decode('utf-8', 'ignore').strip().split(';'):
                if ':' not in pair:
                    continue
                k, v = pair.split(':', 1)
                try:
                    parsed[k] = float(v) if ('.' in v) else int(v)
                except ValueError:
                    parsed[k] = v
            if parsed:
                with self._state_lock:
                    self._state = parsed

    def get_state(self):
        with self._state_lock:
            return dict(self._state)

    def get_battery(self):
        """Battery from the pushed state, falling back to a `battery?` query."""
        st = self.get_state()
        if 'bat' in st:
            return int(st['bat'])
        try:
            return int(self.query('battery?'))
        except (TypeError, ValueError):
            return None

    def telemetry(self):
        """Return a uniform snapshot used by the HUD and the CSV log."""
        st = self.get_state()
        return {
            'bat': st.get('bat'),
            'tof': st.get('tof'),
            'h': st.get('h'),
            'pitch': st.get('pitch'),
            'roll': st.get('roll'),
            'yaw': st.get('yaw'),
            'baro': st.get('baro'),
        }

    # ---- teardown -----------------------------------------------------
    def close(self):
        self._stopped = True
        time.sleep(0.2)
        try:
            self.cmd_sock.close()
        except OSError:
            pass
        try:
            self.state_sock.close()
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


if __name__ == '__main__':
    # Quick self test: connect, read battery and telemetry, do not fly.
    drone = Tello()
    print("command ->", drone.connect())
    time.sleep(1.0)
    print("battery ->", drone.get_battery(), "%")
    for _ in range(5):
        print("telemetry ->", drone.telemetry())
        time.sleep(0.5)
    drone.close()
