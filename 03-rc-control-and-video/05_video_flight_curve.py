"""Circle traced with the SDK `curve` primitive instead of timed `rc`.

`curve` takes the start tangent and the end tangent of a circular arc.
It is a closed loop manoeuvre, so the arc closes accurately and there
is no yaw drift. The drawback is that radius and speed are bounded:

  radius : 50..1000 cm
  speed  : 10..60 cm/s

A full circle is two semicircles back to back. From the current pose
the script flies:

  1. forward semicircle:  (0,0) -> (0, 2R) passing through (R, R)
  2. return semicircle:   (0, 2R) -> (0, 0) passing through (-R, R)
"""
import math
import socket
import subprocess
import time


TELLO_IP = '192.168.10.1'
TELLO_PORT = 8889
VIDEO_URL = 'udp://@0.0.0.0:11111'
OUTPUT_FILE = 'drone_flight_curve.mp4'
BATTERY_MIN = 25

RADIUS = 60
SPEED = 30

_flight_time = int(2 * math.pi * RADIUS / SPEED) + 8
RECORD_SECONDS = _flight_time + 6


def send_command(sock, command, tello_addr, expect_response=True, timeout=30):
    print(f"Sending: {command}")
    sock.sendto(command.encode('utf-8'), tello_addr)
    if not expect_response:
        return None
    sock.settimeout(timeout)
    try:
        response, _ = sock.recvfrom(1024)
        resp = response.decode('utf-8').strip()
        print(f"Response: {resp}")
        return resp
    except socket.timeout:
        print("No response (timeout)")
        return None


def get_battery(sock, tello_addr):
    resp = send_command(sock, 'battery?', tello_addr, timeout=5)
    try:
        return int(resp)
    except (TypeError, ValueError):
        return None


def start_recording(url, output, seconds):
    cmd = [
        'ffmpeg',
        '-y',
        '-hide_banner',
        '-loglevel', 'warning',
        '-f', 'h264',
        '-use_wallclock_as_timestamps', '1',
        '-fflags', '+discardcorrupt+igndts',
        '-err_detect', 'ignore_err',
        '-i', url,
        '-t', str(seconds),
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p',
        '-an',
        output,
    ]
    print(f"Recording up to {seconds}s into {output}...")
    return subprocess.Popen(cmd)


if __name__ == '__main__':
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', TELLO_PORT))
    sock.settimeout(10)

    tello_addr = (TELLO_IP, TELLO_PORT)

    send_command(sock, 'command', tello_addr, timeout=5)

    battery = get_battery(sock, tello_addr)
    print(f"Battery: {battery}%")

    if battery is None or battery < BATTERY_MIN:
        print(f"Battery too low ({battery}%). Aborting flight.")
        sock.close()
        raise SystemExit

    send_command(sock, 'streamon', tello_addr, timeout=5)
    time.sleep(2)

    ffmpeg = start_recording(VIDEO_URL, OUTPUT_FILE, RECORD_SECONDS)
    time.sleep(2)

    R = RADIUS
    try:
        send_command(sock, 'takeoff', tello_addr)
        time.sleep(1)

        send_command(sock, 'up 40', tello_addr)
        time.sleep(1)

        send_command(sock, f'curve {R} {R} 0 0 {2 * R} 0 {SPEED}', tello_addr)
        send_command(sock, f'curve {-R} {-R} 0 0 {-2 * R} 0 {SPEED}', tello_addr)

        send_command(sock, 'land', tello_addr)
        time.sleep(3)
    finally:
        try:
            ffmpeg.wait(timeout=RECORD_SECONDS + 5)
        except subprocess.TimeoutExpired:
            ffmpeg.terminate()
            ffmpeg.wait(timeout=3)
        send_command(sock, 'streamoff', tello_addr, timeout=5)
        sock.close()

    if ffmpeg.returncode == 0:
        print(f"Saved: {OUTPUT_FILE}")
    else:
        print(f"ffmpeg exited with code {ffmpeg.returncode}")
