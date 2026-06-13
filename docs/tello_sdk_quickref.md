# Tello SDK Quick Reference

A compressed summary of the SDK 3.0 surface used in this repository.
For the authoritative document see the *Tello SDK 3.0 User Guide*
published by DJI.

## Network

| Item | Value |
|---|---|
| Drone IP | `192.168.10.1` |
| Command port | UDP 8889 (bidirectional) |
| Telemetry push port | UDP 8890 (drone to host) |
| Video stream port | UDP 11111 (drone to host) |

Connect the host computer to the access point advertised by the drone
(SSID looks like `TELLO-XXXXXX`). The host loses its existing internet
connection while on this network.

## Modes

| Command | Effect |
|---|---|
| `command` | Enter SDK mode. Required as the first message after a fresh power-up. The drone responds with `ok`. |
| `streamon` | Start the H.264 push on UDP 11111. |
| `streamoff` | Stop the H.264 push. |
| `emergency` | Cut motor power immediately. Does not reply reliably. |

## Blocking primitives

All distances are in centimetres, all angles in degrees, all speeds in
cm/s. The drone replies with `ok` once the action completes, or
`error` on a rejection.

| Command | Range | Notes |
|---|---|---|
| `takeoff` | no args | Reply can arrive late after the drone is already airborne. |
| `land` | no args | Always send `rc 0 0 0 0` before landing if you were using `rc`. |
| `forward d` / `back d` | 20..500 | Distance in cm. |
| `left d` / `right d` | 20..500 | |
| `up d` / `down d` | 20..500 | |
| `cw a` / `ccw a` | 1..360 | Yaw in degrees. |
| `go x y z s` | -500..500, 10..100 | Cartesian point at speed s. |
| `curve x1 y1 z1 x2 y2 z2 s` | radius 50..1000, 10..60 | Arc through (x1,y1,z1) ending at (x2,y2,z2). |
| `speed s` | 10..100 | Default speed for `forward`/`back`/etc. |

## Continuous control

```
rc a b c d
```

| Channel | Meaning |
|---|---|
| `a` | Roll. Positive moves right. |
| `b` | Pitch. Positive moves forward. |
| `c` | Throttle. Positive moves up. |
| `d` | Yaw. Positive rotates clockwise from above. |

Each channel is an integer in `-100..100`. The drone keeps applying
the last command until a new `rc` arrives or until the radio link goes
quiet for a few seconds.

`rc` does NOT acknowledge. Do not read from the command socket after
sending it.

## Queries

Sent on port 8889, with text response on the same port.

| Query | Response example |
|---|---|
| `battery?` | `"73"` (percent) |
| `sdk?` | `"30"` (SDK version) |
| `tof?` | `"15"` (cm, downward ToF reading) |
| `height?` | `"40"` (cm) |
| `attitude?` | `"pitch:0;roll:0;yaw:0;"` |
| `baro?` | floating point altitude in metres |
| `speed?` | current default speed |

## Telemetry push (port 8890)

The drone pushes a single semicolon separated text frame several times
per second. Common fields:

| Key | Meaning |
|---|---|
| `bat` | Battery percent |
| `tof` | Downward time of flight distance, cm |
| `h` | Estimated altitude above takeoff, cm |
| `pitch`, `roll`, `yaw` | Attitude in degrees |
| `vgx`, `vgy`, `vgz` | Velocity components |
| `templ`, `temph` | IMU temperature bounds, C |
| `baro` | Barometric altitude, m |
| `time` | Motor on time, s |

Parsing example in `05-final-project-inspector/tello_driver.py`.

## Video stream

The drone pushes a raw H.264 stream on UDP 11111. Two ways to consume
it:

- **ffmpeg subprocess** (lab 03). Best when you only need to record.
- **OpenCV `VideoCapture('udp://@0.0.0.0:11111')`** (lab 04 and 05).
  Best when you need decoded frames inside Python. Run the read inside
  a thread to keep the main loop responsive.

For both options, bind the local socket before sending `streamon`, or
the first packets get dropped while the listener is being set up.

## Common pitfalls

- **Socket already in use.** A previous script left port 8889 bound.
  Use `SO_REUSEADDR` or wait a few seconds for the OS to release it.
- **Firewall.** On Ubuntu, allow inbound UDP on the ports you use:
  `sudo ufw allow 8889/udp; sudo ufw allow 8890/udp; sudo ufw allow 11111/udp`.
- **Late acknowledgements.** `takeoff` sometimes acknowledges seconds
  after the drone is already airborne, so the next `recvfrom` reads
  the stale `ok`. The driver in lab 05 drains the socket after
  `takeoff` to avoid this.
- **SDK timeout.** If you go more than ~15 s without sending a
  command, the firmware drops out of SDK mode. A `battery?` heartbeat
  every 5 s keeps the link alive.
