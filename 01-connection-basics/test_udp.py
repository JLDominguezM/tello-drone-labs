"""Minimal UDP smoke test against the Tello on 8889.

Useful as a first diagnostic when 'check_connection.py' fails: it shows
whether the socket binds, whether datagrams reach the drone, and whether
the drone answers at all.
"""
import socket
import time


TELLO_IP = '192.168.10.1'
TELLO_PORT = 8889
LOCAL_PORT = 8889


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', LOCAL_PORT))
    sock.settimeout(5)

    print("Sending: command")
    sock.sendto(b'command', (TELLO_IP, TELLO_PORT))
    try:
        response, _ = sock.recvfrom(1024)
        print(f"Response: {response.decode('utf-8').strip()}")
    except socket.timeout:
        print("No response. Drone is not reachable on this network.")
        sock.close()
        return

    time.sleep(1)
    print("Sending: sdk?")
    sock.sendto(b'sdk?', (TELLO_IP, TELLO_PORT))
    try:
        response, _ = sock.recvfrom(1024)
        print(f"SDK version: {response.decode('utf-8').strip()}")
    except socket.timeout:
        print("No response to 'sdk?'")

    sock.close()


if __name__ == '__main__':
    main()
