# Tello Drone Labs

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)
[![Drone](https://img.shields.io/badge/Hardware-DJI%20Tello-000000?logo=dji)](https://www.ryzerobotics.com/tello)
[![Final demo](https://img.shields.io/badge/Final_demo-YouTube-FF0000?logo=youtube&logoColor=white)](https://youtu.be/uXXDjiPWrlk)

A progression of five labs, in Python, that builds up the components
needed for an autonomous mission on a DJI Tello / RoboMaster TT. Every
lab is self contained but builds on the previous one: the final project
in lab 05 reuses ideas from the four earlier labs.

All scripts talk to the drone with raw UDP sockets. There is no
`robomaster` or `djitellopy` dependency.

## Demo

The final project in action, with the HUD overlay showing the active
phase frame by frame:

[![Inspector demo](./05-final-project-inspector/figures/hud_orbit_dynamic.png)](https://youtu.be/uXXDjiPWrlk)

> Click the frame to watch the Inspector mission on YouTube.

## Labs

| # | Folder | Topic | Demo |
|---|---|---|---|
| 01 | [`01-connection-basics/`](./01-connection-basics/) | UDP link, SDK mode, the first takeoff | [video](https://youtu.be/WFx7TkTSZhw) |
| 02 | [`02-basic-motion/`](./02-basic-motion/) | Blocking SDK primitives: `forward`, `cw`, trajectories | [video](https://youtu.be/rVmfCdu8WVA) |
| 03 | [`03-rc-control-and-video/`](./03-rc-control-and-video/) | Continuous `rc` control, video stream recording | [video](https://youtu.be/NSjJu2TxvZ8) |
| 04 | [`04-visual-tracking/`](./04-visual-tracking/) | HSV detection plus a PD tracker on yaw and throttle | [video](https://youtu.be/FGLN-wSKNz8) |
| 05 | [`05-final-project-inspector/`](./05-final-project-inspector/) | Autonomous Inspector: visual servoing with a state machine | [video](https://youtu.be/uXXDjiPWrlk) |

Every lab folder ships its own README with the per-script breakdown,
the relevant SDK details, and the safety notes specific to that lab.

## Requirements

- Python 3.8 or newer.
- A Tello EDU or Tello (firmware exposing SDK 3.0).
- `pip install -r requirements.txt`. The full list is `opencv-python`,
  `numpy`, `matplotlib`. The recording scripts in lab 03 also need the
  `ffmpeg` binary available on PATH; on Ubuntu: `sudo apt install ffmpeg`.

## Quick start

```
git clone <this repo>
cd tello-drone-labs
python3 -m pip install -r requirements.txt

# Connect your computer to the Tello WiFi (TELLO-XXXXXX), then:
python3 01-connection-basics/test_udp.py
```

If that returns `ok` and an SDK version, you are ready to walk through
the rest of the labs in order.

## How the drone talks

The Tello exposes three UDP channels at `192.168.10.1`. None of them
uses TCP; commands and video are independent streams that you can run
in parallel.

| Port | Direction | Use |
|---|---|---|
| 8889 | bidirectional | Commands (`takeoff`, `rc`, `battery?`) and their text response |
| 8890 | drone to host | Telemetry push: semicolon separated fields several times per second |
| 11111 | drone to host | H.264 video stream |

More detail and a tabular reference in [`docs/tello_sdk_quickref.md`](./docs/tello_sdk_quickref.md).

## Safety

A short checklist that applies to every lab is in
[`docs/safety_checklist.md`](./docs/safety_checklist.md). The most
important points:

- Indoor only, with at least one observer keeping line of sight.
- 2 m of clear space in every direction the drone may move.
- Battery above 25% before takeoff.
- Hands free to manually catch the drone if the link drops.

## Layout

```
tello-drone-labs/
├── README.md
├── LICENSE
├── requirements.txt
├── .gitignore
├── docs/
│   ├── tello_sdk_quickref.md
│   └── safety_checklist.md
├── 01-connection-basics/
├── 02-basic-motion/
├── 03-rc-control-and-video/
├── 04-visual-tracking/
└── 05-final-project-inspector/
    ├── inspector_mission.py
    ├── tello_driver.py
    ├── vision.py
    ├── config.py
    ├── preflight.py
    ├── calibrate.py
    ├── analyze.py
    ├── evidence/        # mp4 + csv + png written by mission runs
    └── figures/         # plots written by analyze.py
```

## Author

José Luis Domínguez Morales. Tecnológico de Monterrey, Module 4 (UAVs),
under Dr. Herman Castañeda Cuevas.

## License

MIT. See [`LICENSE`](./LICENSE).
