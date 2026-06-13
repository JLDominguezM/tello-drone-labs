"""Battery gated takeoff: query the state of charge, abort if it is below
the threshold, otherwise take off, hover briefly and land.

Every later script reuses the same pattern. Keeping the helpers inline
on purpose for readability; once you understand them they get factored
out in `tello_driver.py` of the final project.
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
    sock.settimeout(10)

    tello_addr = (TELLO_IP, TELLO_PORT)

    send_command(sock, 'command', tello_addr)

    battery = get_battery(sock, tello_addr)
    print(f"Battery: {battery}%")

    if battery is None or battery < BATTERY_MIN:
        print(f"Battery too low ({battery}%). Aborting flight.")
    else:
        send_command(sock, 'takeoff', tello_addr)
        time.sleep(5)
        send_command(sock, 'land', tello_addr)
        print("Done.")

    sock.close()
