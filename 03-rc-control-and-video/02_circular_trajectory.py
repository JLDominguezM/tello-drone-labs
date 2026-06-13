"""Draw a horizontal circle by holding `rc 0 PITCH 0 YAW` for one period.

The radius is set indirectly by the ratio of `PITCH` over `YAW`:

  radius_cm ~= pitch * 57 / yaw
  period_s  ~= 360 / yaw

The constants below give a circle of roughly 50 cm radius traced in
10 s. Tune them to your space; the formula is approximate because the
Tello has no closed loop position control and the gyro drifts a few
degrees per second.
"""
import socket
import time


TELLO_IP = '192.168.10.1'
TELLO_PORT = 8889
BATTERY_MIN = 25

PITCH = 25
YAW = 36
CIRCLE_SECONDS = 10


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

        send_command(sock, 'up 40', tello_addr)
        time.sleep(2)

        print(f"Tracing circle for {CIRCLE_SECONDS}s (pitch={PITCH}, yaw={YAW})")
        send_rc(sock, 0, PITCH, 0, YAW, tello_addr)
        time.sleep(CIRCLE_SECONDS)

        send_rc(sock, 0, 0, 0, 0, tello_addr)
        time.sleep(2)

        send_command(sock, 'land', tello_addr)

    sock.close()
