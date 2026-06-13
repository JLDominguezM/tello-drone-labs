# Lab 02: Basic Motion

Open loop motion. Every script in this folder uses blocking SDK
primitives (`forward`, `cw`, `up`, ...) and exposes the same battery
gated structure that the rest of the repo will mirror.

[![Demo](https://img.shields.io/badge/Demo_video-YouTube-red?logo=youtube)](https://youtu.be/rVmfCdu8WVA)

## Scripts

| File | Pattern |
|---|---|
| `01_battery_takeoff.py` | Query battery, take off, hover, land. The minimal closed flight. |
| `02_forward_backward.py` | Forward 100 cm, back 100 cm, forward 150 cm, back 150 cm. |
| `03_up_down_lateral.py` | Up 40 cm, left 80 cm, right 80 cm, down 40 cm. |
| `04_rotation.py` | Symmetric yaw sweep at 180 deg and 90 deg. |
| `05_trajectory.py` | Square trajectory at 1 m altitude. Triangle helper is provided in code. |

## SDK numeric bounds

Each command has hard limits enforced by the Tello firmware. If you go
outside the range the drone responds with `error` and ignores the
command. Useful values:

| Command | Range |
|---|---|
| `forward`, `back`, `left`, `right`, `up`, `down` | 20..500 cm |
| `cw`, `ccw` | 1..360 deg |
| `go x y z s` | x,y,z in -500..500 cm, speed in 10..100 cm/s |

## Battery threshold

All scripts refuse to take off below 25%. The Tello reports state of
charge via `battery?` and the firmware will also auto land at low
voltage, but blocking ourselves at 25% gives enough margin to finish a
short routine without a forced descent in the middle of a movement.

## Run

```
python3 01_battery_takeoff.py
python3 02_forward_backward.py
python3 03_up_down_lateral.py
python3 04_rotation.py
python3 05_trajectory.py
```

Keep at least 2 m of clear space in the heading direction. The
`forward 150` step alone moves the drone 1.5 m before stopping.
