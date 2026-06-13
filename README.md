# Tello Drone Labs

A progression of five labs, in Python, that builds up the components
needed for an autonomous mission on a DJI Tello / RoboMaster TT. Every
lab is self contained but builds on the previous one: the final project
in lab 05 reuses ideas from the four earlier labs.

All scripts talk to the drone with raw UDP sockets. There is no
`robomaster` or `djitellopy` dependency.

## Labs

| # | Folder | Topic |
|---|---|---|
| 01 | [`01-connection-basics/`](./01-connection-basics/) | UDP link, SDK mode, the first takeoff |
| 02 | [`02-basic-motion/`](./02-basic-motion/) | Blocking SDK primitives: `forward`, `cw`, trajectories |
| 03 | [`03-rc-control-and-video/`](./03-rc-control-and-video/) | Continuous `rc` control, video stream recording |
| 04 | [`04-visual-tracking/`](./04-visual-tracking/) | HSV detection plus a PD tracker on yaw and throttle |
| 05 | [`05-final-project-inspector/`](./05-final-project-inspector/) | Autonomous Inspector: visual servoing with a state machine |

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
