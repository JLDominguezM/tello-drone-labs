# Lab 03: RC Control and Video

This lab introduces the two ingredients every autonomous mission in the
final project depends on:

  * Continuous `rc` control. Unlike the blocking primitives in lab 02,
    `rc a b c d` is fire-and-forget and the drone keeps applying the
    last command until a new one arrives.
  * Onboard video. The Tello pushes an H.264 stream over UDP on port
    11111 with no acknowledgement.

## Scripts

| File | What it does |
|---|---|
| `01_rc_test.py` | Take off, run a short sequence of `rc` commands to characterise each axis, land. |
| `02_circular_trajectory.py` | Constant `rc 0 PITCH 0 YAW` for one period, drawing a horizontal circle. |
| `03_video_stream.py` | Record the video stream to an mp4 file with ffmpeg, without flying. |
| `04_video_flight.py` | Combined: record the stream while flying the small circle from script 02. |
| `05_video_flight_curve.py` | Same circle but using the SDK `curve` primitive (closed loop, no drift). |
| `debug_video.py` | Pure UDP diagnostic for the video link. Helpful when `streamon` runs without errors but no frames decode. |

## How `rc` differs from `forward`/`back`

| | `forward 100` | `rc 0 50 0 0` |
|---|---|---|
| Direction | forward | forward |
| Magnitude | 100 cm | normalised 0..100 |
| Duration | blocks until done | applied until next `rc` |
| Response | `ok` or `error` | none |
| Closed loop | yes (IMU + ToF) | no |

Continuous `rc` is the right tool when you have your own feedback loop
(such as a vision tracker). The blocking primitives are easier to reason
about for fixed sequences.

## Why the circle drifts and the curve does not

The circle in `02_circular_trajectory.py` is an open loop trick:
forward speed plus yaw rate. Wind, gyro bias and even battery sag will
make the loop close imperfectly. The SDK `curve` primitive used in
`05_video_flight_curve.py` is a planned manoeuvre with internal
feedback, so it closes the loop accurately but constrains radius and
speed.

## Video recording details

`03` and `04` shell out to ffmpeg. The decoder flags used are:

```
-fflags +discardcorrupt+igndts
-err_detect ignore_err
```

These let the recording survive the occasional lost packet without
aborting. The trade-off is a few mangled frames per second; for
autonomous control we read the stream directly with OpenCV instead, as
done in lab 04 and in the final project.

## Run

The order matters: `01` and `02` only need command port 8889, `03` adds
the video port, `04`/`05` need both at the same time.

```
python3 01_rc_test.py
python3 02_circular_trajectory.py
python3 03_video_stream.py
python3 04_video_flight.py
python3 05_video_flight_curve.py

# Only if the stream looks broken:
python3 debug_video.py
```

ffmpeg must be installed for the recording scripts: `sudo apt install ffmpeg`.
