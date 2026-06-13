# Safety Checklist

Run through this list before every flight, even the short ones in
lab 02. Most incidents in indoor experiments come from skipped pre-flight
checks, not from spectacular control failures.

## Before powering on the drone

- [ ] Propellers tight. Spin each one by hand; they should not wobble
      laterally.
- [ ] Battery snapped fully into the bay. The plastic clip should make
      an audible click.
- [ ] Body clean. No tape residue or dust on the bottom optical flow
      sensor.

## Before connecting to the network

- [ ] Host computer is on AC power or above 30% battery. A laptop that
      sleeps mid-flight is the same as a radio link drop.
- [ ] All other scripts that talk to the drone are closed. Two scripts
      bound to port 8889 will fight over commands.
- [ ] Firewall allows the relevant UDP ports. On Ubuntu:
      ```
      sudo ufw allow 8889/udp
      sudo ufw allow 8890/udp
      sudo ufw allow 11111/udp
      ```

## Before the first takeoff

- [ ] Battery state of charge is above 25%. The scripts in this repo
      refuse to take off below this number.
- [ ] At least 2 m of clear space in every direction the drone may
      move. The Tello has no obstacle avoidance.
- [ ] No reflective floor right under the drone. Mirror surfaces
      confuse the optical flow sensor and the drone yaws to find a
      texture.
- [ ] An observer keeps line of sight. The pilot looks at the screen,
      the observer at the drone.
- [ ] Hands free to physically catch the drone if needed. A canvas
      glove is helpful but not strictly required for a Tello.

## During the flight

- [ ] Pilot has the kill key under a finger. In every script in this
      repo:
      - `q` lands cleanly.
      - `e` (in the missions that handle it) sends `emergency`,
        cutting motor power.
- [ ] Observer is ready to shout "land" if the drone deviates.

## After the flight

- [ ] `streamoff` was sent. If not, the firmware keeps pushing video
      and drains the battery faster.
- [ ] Battery removed if you are done for the session. Stored at
      ~50% charge, not full.
- [ ] mp4 / CSV from the run are off the drone storage and into
      `evidence/`.

## Recovery cheatsheet

If the drone behaves unexpectedly:

- It is hovering but not responding to commands: another script is
  probably bound to 8889. Stop the rogue process, then
  `python3 04-visual-tracking/reset_tello.py`.
- It refuses to take off and reports `error`: read the battery. A
  cold battery can be far below its rated voltage.
- The video window is black but the link works: the listener was not
  bound when `streamon` ran. Use `debug_video.py` in lab 03 to
  diagnose.
