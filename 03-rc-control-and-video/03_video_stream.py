"""Record the H.264 stream from port 11111 to an mp4 without flying.

Uses ffmpeg as a subprocess. The decoder flags forgive the lossy nature
of the UDP video link (`discardcorrupt`, `igndts`, `ignore_err`) so that
a couple of dropped packets do not abort the recording.

You need `ffmpeg` installed and on PATH. On Ubuntu:

    sudo apt install ffmpeg
"""
import socket
import subprocess
import time


TELLO_IP = '192.168.10.1'
TELLO_PORT = 8889
VIDEO_URL = 'udp://@0.0.0.0:11111'
OUTPUT_FILE = 'drone_stream.mp4'
DURATION = 15


def send_command(sock, command, tello_addr):
    print(f"Sending: {command}")
    sock.sendto(command.encode('utf-8'), tello_addr)
    try:
        response, _ = sock.recvfrom(1024)
        resp = response.decode('utf-8').strip()
        print(f"Response: {resp}")
        return resp
    except socket.timeout:
        print("No response (timeout)")
        return None


def record_to_file(url, output, seconds):
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
    print(f"Recording {seconds}s to {output}...")
    return subprocess.run(cmd)


if __name__ == '__main__':
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', TELLO_PORT))
    sock.settimeout(10)

    tello_addr = (TELLO_IP, TELLO_PORT)

    send_command(sock, 'command', tello_addr)
    send_command(sock, 'streamon', tello_addr)
    time.sleep(2)

    result = record_to_file(VIDEO_URL, OUTPUT_FILE, DURATION)

    send_command(sock, 'streamoff', tello_addr)
    sock.close()

    if result.returncode == 0:
        print(f"Saved: {OUTPUT_FILE}")
    else:
        print(f"ffmpeg exited with code {result.returncode}")
