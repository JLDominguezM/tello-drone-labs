"""Minimal flight loop: SDK mode, takeoff, hover 5 s, land.

This is intentionally bare. It does not check battery, does not stream
video, and does not handle interruptions. Use it only to verify that the
basic takeoff/land path works after a fresh setup. Real missions should
go through the modules in 02..05.
"""
import socket
import time


TELLO_IP = '192.168.10.1'
TELLO_PORT = 8889
HOVER_SECONDS = 5


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


if __name__ == '__main__':
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', TELLO_PORT))
    sock.settimeout(10)

    tello_addr = (TELLO_IP, TELLO_PORT)

    send_command(sock, 'command', tello_addr)
    send_command(sock, 'takeoff', tello_addr)

    print(f"Hovering for {HOVER_SECONDS} seconds...")
    time.sleep(HOVER_SECONDS)

    send_command(sock, 'land', tello_addr)

    sock.close()
    print("Done.")
