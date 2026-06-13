"""Record the onboard video while flying a small circle.

Two child processes are running in parallel:

  * the Python script, which talks SDK over 8889 and drives the drone;
  * ffmpeg, which reads the H.264 stream on 11111 and saves it as mp4.

The `try/finally` block makes sure we always reach `streamoff` and let
ffmpeg flush its buffer, even if the user aborts with Ctrl-C.
"""
import socket
import subprocess
import time


TELLO_IP = '192.168.10.1'
TELLO_PORT = 8889
VIDEO_URL = 'udp://@0.0.0.0:11111'
OUTPUT_FILE = 'drone_flight.mp4'
BATTERY_MIN = 25

# Small circle: radius ~28 cm, one revolution in ~12 s.
PITCH = 15
YAW = 30
CIRCLE_SECONDS = 16
RECORD_SECONDS = CIRCLE_SECONDS + 12


def send_command(sock, command, tello_addr, expect_response=True):
    print(f"Sending: {command}")
    sock.sendto(command.encode('utf-8'), tello_addr)
    if not expect_response:
        return None
    try:
        response, _ = sock.recvfrom(1024)
        resp = response.decode('utf-8').strip()
        print(f"Response: {resp}")
        return resp
    except socket.timeout:
        print("No response (timeout)")
        return None


def send_rc(sock, a, b, c, d, tello_addr):
    send_command(sock, f'rc {a} {b} {c} {d}', tello_addr, expect_response=False)


def get_battery(sock, tello_addr):
    resp = send_command(sock, 'battery?', tello_addr)
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

    send_command(sock, 'command', tello_addr)

    battery = get_battery(sock, tello_addr)
    print(f"Battery: {battery}%")

    if battery is None or battery < BATTERY_MIN:
        print(f"Battery too low ({battery}%). Aborting flight.")
        sock.close()
        raise SystemExit

    send_command(sock, 'streamon', tello_addr)
    time.sleep(2)

    ffmpeg = start_recording(VIDEO_URL, OUTPUT_FILE, RECORD_SECONDS)
    time.sleep(2)

    try:
        send_command(sock, 'takeoff', tello_addr)
        time.sleep(4)

        send_command(sock, 'up 40', tello_addr)
        time.sleep(2)

        send_rc(sock, 0, PITCH, 0, YAW, tello_addr)
        time.sleep(CIRCLE_SECONDS)
        send_rc(sock, 0, 0, 0, 0, tello_addr)
        time.sleep(2)

        send_command(sock, 'land', tello_addr)
        time.sleep(3)
    finally:
        try:
            ffmpeg.wait(timeout=RECORD_SECONDS + 5)
        except subprocess.TimeoutExpired:
            ffmpeg.terminate()
            ffmpeg.wait(timeout=3)
        send_command(sock, 'streamoff', tello_addr)
        sock.close()

    if ffmpeg.returncode == 0:
        print(f"Saved: {OUTPUT_FILE}")
    else:
        print(f"ffmpeg exited with code {ffmpeg.returncode}")
