"""First contact with continuous control via `rc a b c d`.

`rc` is a fire-and-forget command: the drone applies the four channels
until a new `rc` arrives or the link drops. The script does not wait
for a response after sending it, because there isn't one.

  a = roll     (positive = right)
  b = pitch    (positive = forward)
  c = throttle (positive = up)
  d = yaw      (positive = clockwise from above)

Each channel is an integer in -100..100.
"""
import socket
import time


TELLO_IP = '192.168.10.1'
TELLO_PORT = 8889
BATTERY_MIN = 25


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
    else:
        send_command(sock, 'takeoff', tello_addr)
        time.sleep(3)

        print("Sliding right")
        send_rc(sock, 30, 0, 0, 0, tello_addr); time.sleep(4)

        print("Moving forward")
        send_rc(sock, 0, 30, 0, 0, tello_addr); time.sleep(4)

        print("Forward while yawing")
        send_rc(sock, 0, 30, 0, 30, tello_addr); time.sleep(4)

        send_rc(sock, 0, 0, 0, 0, tello_addr); time.sleep(2)

        send_command(sock, 'land', tello_addr)

    sock.close()
