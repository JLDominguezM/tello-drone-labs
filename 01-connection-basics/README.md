# Lab 01: Connection Basics

The first lab of the course. Three short scripts that verify the radio
link and the SDK before any motor spins.

[![Demo](https://img.shields.io/badge/Demo_video-YouTube-red?logo=youtube)](https://youtu.be/WFx7TkTSZhw)

## Scripts

| File | What it does |
|---|---|
| `test_udp.py` | Binds the local UDP socket and sends `command` + `sdk?`. Use this as a first diagnostic. |
| `check_connection.py` | Same exchange, structured around a reusable `send_command` helper. Closer to the style every later lab will use. |
| `test_flight.py` | Bare takeoff, hover for 5 s, land. Only run it when the previous two scripts succeed. |

## How the Tello link works

The drone exposes three UDP channels at `192.168.10.1`:

| Port | Direction | Use |
|---|---|---|
| 8889 | bidirectional | Control commands (`takeoff`, `rc`, `battery?`) and their text response |
| 8890 | drone to host | Telemetry stream, semicolon separated (`pitch:0;roll:0;yaw:0;...`) |
| 11111 | drone to host | H.264 video stream |

All scripts in this lab use only port 8889.

## Run

1. Join the WiFi network advertised by the drone (`TELLO-XXXXXX`). You
   will lose internet access while connected; that is expected.
2. Run the diagnostic scripts in order:
   ```
   python3 test_udp.py
   python3 check_connection.py
   python3 test_flight.py
   ```
3. If any of them times out, check that no firewall is blocking
   incoming traffic on port 8889 (`sudo ufw allow 8889/udp` on Ubuntu).

## Safety notes

- Indoor only, with at least one observer keeping line of sight.
- Battery should read above 25% before `test_flight.py`.
- A second person should be ready to physically catch the drone if the
  link drops mid-flight. The Tello will hover in place when it loses
  commands, but altitude drift is not zero.
