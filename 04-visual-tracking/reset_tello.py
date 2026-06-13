"""Emergency reset for the Tello link.

Sometimes a script that crashes mid-flight leaves the firmware in a
state where it ignores new SDK commands until the radio link times out.
This script forces `command`, `streamoff` and a zero `rc` to clear it.
Run it before retrying a lab that started misbehaving.
"""
import socket
import time


TELLO_IP = '192.168.10.1'
TELLO_PORT = 8889


def reset():
    tello_addr = (TELLO_IP, TELLO_PORT)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', TELLO_PORT))
    sock.settimeout(2.0)

    print("Sending reset commands")
    try:
        sock.sendto(b'command', tello_addr)
        sock.sendto(b'streamoff', tello_addr)
        sock.sendto(b'rc 0 0 0 0', tello_addr)
        time.sleep(2)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()
        print("Socket closed. You can re-run the lab now.")


if __name__ == '__main__':
    reset()
