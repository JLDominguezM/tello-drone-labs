"""Closed trajectories from blocking SDK primitives: a square and a
triangle. The pattern is forward + rotate, repeated as many times as the
polygon has sides.

Useful both as a sanity check that the open loop sequence terminates
where it started and as a baseline before moving to the `rc` continuous
control used in lab 03.
"""
import socket
import time


TELLO_IP = '192.168.10.1'
TELLO_PORT = 8889
BATTERY_MIN = 25
SIDE_CM = 100
RISE_CM = 50


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


def square(sock, tello_addr):
    for _ in range(4):
        send_command(sock, f'forward {SIDE_CM}', tello_addr)
        send_command(sock, 'cw 90', tello_addr)


def triangle(sock, tello_addr):
    for _ in range(3):
        send_command(sock, f'forward {SIDE_CM}', tello_addr)
        send_command(sock, 'cw 120', tello_addr)


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

        send_command(sock, f'up {RISE_CM}', tello_addr)
        square(sock, tello_addr)
        send_command(sock, f'down {RISE_CM}', tello_addr)

        send_command(sock, 'land', tello_addr)

    sock.close()
