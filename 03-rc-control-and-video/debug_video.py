"""Diagnose the video stream without OpenCV or ffmpeg.

The script binds the UDP socket at port 11111 BEFORE sending `streamon`.
That ordering matters: if the listener is not up when the firmware
starts pushing packets, the first burst is lost and OpenCV can take
several seconds to lock onto the stream.

If no packets arrive within the timeout the most common reasons are:
  * UFW or another firewall is blocking UDP 11111
    (`sudo ufw allow 11111/udp` on Ubuntu).
  * You are not on the Tello WiFi network.
  * Another script left the socket bound and the OS denies a new bind.
"""
import socket
import time


TELLO_IP = '192.168.10.1'
TELLO_CMD_PORT = 8889
VIDEO_PORT = 11111
DURATION = 8


if __name__ == '__main__':
    tello = (TELLO_IP, TELLO_CMD_PORT)

    video_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    video_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    video_sock.bind(('0.0.0.0', VIDEO_PORT))
    video_sock.settimeout(1)
    print(f"[OK] Video socket bound on 0.0.0.0:{VIDEO_PORT}")

    cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cmd_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    cmd_sock.bind(('', TELLO_CMD_PORT))
    cmd_sock.settimeout(5)

    cmd_sock.sendto(b'command', tello)
    print("command ->", cmd_sock.recvfrom(1024)[0])

    time.sleep(0.5)
    cmd_sock.sendto(b'streamon', tello)
    print("streamon ->", cmd_sock.recvfrom(1024)[0])

    print(f"\nListening on UDP:{VIDEO_PORT} for {DURATION}s...")
    start = time.time()
    count = 0
    total_bytes = 0
    first_packet = None
    sources = set()

    while time.time() - start < DURATION:
        try:
            data, addr = video_sock.recvfrom(4096)
            if first_packet is None:
                first_packet = time.time() - start
                print(f"First packet at t={first_packet:.2f}s from {addr} ({len(data)} B)")
            sources.add(addr[0])
            count += 1
            total_bytes += len(data)
        except socket.timeout:
            continue

    print(f"\nResult: {count} packets, {total_bytes} bytes in {DURATION}s")
    print(f"Sources: {sources}")
    if count == 0:
        print("\nNo packets received. Likely causes:")
        print("  - Firewall blocking UDP 11111 (sudo ufw allow 11111/udp).")
        print("  - Not connected to the Tello WiFi.")
        print("  - Drone lost the link right after streamon.")
    else:
        rate = count // DURATION
        kbps = total_bytes // DURATION // 1024
        print(f"\nStream is active ({rate} pkt/s, ~{kbps} KB/s)")

    cmd_sock.sendto(b'streamoff', tello)
    try:
        cmd_sock.recvfrom(1024)
    except socket.timeout:
        pass

    cmd_sock.close()
    video_sock.close()
