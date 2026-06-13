"""Send a single 'command' to enter SDK mode and query the SDK version.

Run this after connecting your computer to the Tello WiFi (TELLO-XXXXXX).
If both responses are 'ok' / '20', the link is healthy.
"""
import socket


TELLO_IP = '192.168.10.1'
TELLO_PORT = 8889


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
    sock.settimeout(5)

    send_command(sock, 'command', (TELLO_IP, TELLO_PORT))
    send_command(sock, 'sdk?', (TELLO_IP, TELLO_PORT))

    sock.close()
