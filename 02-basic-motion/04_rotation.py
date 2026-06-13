"""Yaw test: rotate clockwise and counter clockwise by symmetric angles.

If the drone reports the yaw integral after a full pattern you can use
this script to estimate the gyro drift over a hover.
"""
import socket
import time


TELLO_IP = '192.168.10.1'
TELLO_PORT = 8889
BATTERY_MIN = 25


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


def get_battery(sock, tello_addr):
    resp = send_command(sock, 'battery?', tello_addr)
    try:
        return int(resp)
    except (TypeError, ValueError):
        return None


if __name__ == '__main__':
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', TELLO_PORT))
    sock.settimeout(15)

    tello_addr = (TELLO_IP, TELLO_PORT)

    send_command(sock, 'command', tello_addr)

    battery = get_battery(sock, tello_addr)
    print(f"Battery: {battery}%")

    if battery is None or battery < BATTERY_MIN:
        print(f"Battery too low ({battery}%). Aborting flight.")
    else:
        send_command(sock, 'takeoff', tello_addr)
        time.sleep(3)

        for angle in (180, 90):
            send_command(sock, f'cw {angle}', tello_addr)
            send_command(sock, f'ccw {angle}', tello_addr)

        send_command(sock, 'land', tello_addr)

    sock.close()
