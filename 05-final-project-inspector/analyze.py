"""Render the report figures from a flight CSV and extract one HUD
frame per phase from the recorded mp4.

If `--csv` is not given the script picks the most recent
`telemetry_inspector_*.csv` it can find in `evidence/`.
"""
import argparse
import csv
import glob
import math
import os

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import config as C


TEC_BLUE = '#0039A6'
PHASE_ORDER = ['SEARCH', 'APPROACH', 'ORBIT_STATIC', 'ORBIT_DYNAMIC',
               'CAPTURE', 'LAND']
PHASE_COLOR = {
    'SEARCH':        '#3b82f6',
    'APPROACH':      '#f59e0b',
    'ORBIT_STATIC':  '#10b981',
    'ORBIT_DYNAMIC': '#ef4444',
    'CAPTURE':       '#8b5cf6',
    'LAND':          '#6b7280',
}


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return math.nan


def load(path):
    cols = {}
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for k in reader.fieldnames:
            cols[k] = []
        for row in reader:
            for k, v in row.items():
                if k in ('phase', 'action'):
                    cols[k].append(v)
                else:
                    cols[k].append(_f(v))
    return cols


def _phase_spans(d):
    """List of (t_start, t_end, phase) used to shade plots."""
    t, p = d['t'], d['phase']
    spans = []
    if not t:
        return spans
    cur, t0 = p[0], t[0]
    for i in range(1, len(t)):
        if p[i] != cur:
            spans.append((t0, t[i], cur))
            cur, t0 = p[i], t[i]
    spans.append((t0, t[-1], cur))
    return spans


def _shade_phases(ax, spans, alpha=0.18):
    for t0, t1, ph in spans:
        ax.axvspan(t0, t1, color=PHASE_COLOR.get(ph, '#cccccc'),
                   alpha=alpha, lw=0)


def fig_phases(d, outdir, spans):
    fig, ax = plt.subplots(figsize=(9, 2.6))
    y = [PHASE_ORDER.index(p) if p in PHASE_ORDER else math.nan
         for p in d['phase']]
    ax.step(d['t'], y, where='post', color=TEC_BLUE, lw=2.2)
    _shade_phases(ax, spans, alpha=0.22)
    ax.set_yticks(range(len(PHASE_ORDER)))
    ax.set_yticklabels(PHASE_ORDER)
    ax.set_xlabel('time (s)')
    ax.set_title('Mission timeline')
    ax.grid(alpha=0.3)
    for t0, t1, ph in spans:
        if t1 - t0 > 1.0 and ph in PHASE_ORDER:
            ax.annotate(f"{t1 - t0:.1f}s",
                        ((t0 + t1) / 2, PHASE_ORDER.index(ph)),
                        ha='center', va='bottom', fontsize=8, color='#333')
    p = os.path.join(outdir, 'mission_phases.png')
    fig.tight_layout()
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def fig_orbit_control(d, outdir, spans):
    """RC channels roll/pitch/yaw during the two orbit phases."""
    fig, ax = plt.subplots(figsize=(9, 3.4))
    spans_orbit = [s for s in spans
                   if s[2] in ('ORBIT_STATIC', 'ORBIT_DYNAMIC')]
    if not spans_orbit:
        plt.close(fig)
        return None
    t_min = min(s[0] for s in spans_orbit)
    t_max = max(s[1] for s in spans_orbit)
    mask = [i for i, ti in enumerate(d['t']) if t_min <= ti <= t_max]
    t = [d['t'][i] for i in mask]
    for k, lbl, c in [('rc_a', 'roll (lateral)', '#1e40af'),
                      ('rc_b', 'pitch (advance)', '#16a34a'),
                      ('rc_d', 'yaw (centering)', '#dc2626')]:
        ax.plot(t, [d[k][i] for i in mask], lw=1.3, color=c, label=lbl)
    _shade_phases(ax, spans_orbit, alpha=0.18)
    for s in spans_orbit:
        if s[2] == 'ORBIT_DYNAMIC':
            ax.axvline(s[0], color='black', lw=1.0, ls='--')
            ax.annotate('phase 1 -> phase 2\n(operator moves target)',
                        (s[0], 35),
                        ha='center', fontsize=8, color='#333')
            break
    ax.set_xlabel('time (s)')
    ax.set_ylabel('rc command (-100..100)')
    ax.set_title('Control law during orbit (static then dynamic)')
    ax.legend(loc='upper right', fontsize=8, ncol=3)
    ax.grid(alpha=0.3)
    p = os.path.join(outdir, 'orbit_control.png')
    fig.tight_layout()
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def fig_orbit_vision(d, outdir, spans):
    """Target area and horizontal offset during the orbit."""
    spans_orbit = [s for s in spans
                   if s[2] in ('ORBIT_STATIC', 'ORBIT_DYNAMIC')]
    if not spans_orbit:
        return None
    t_min = min(s[0] for s in spans_orbit)
    t_max = max(s[1] for s in spans_orbit)
    mask = [i for i, ti in enumerate(d['t'])
            if t_min <= ti <= t_max and d['obs_found'][i] == 1]
    t = [d['t'][i] for i in mask]
    area = [d['obs_area'][i] for i in mask]
    off = [d['obs_off_x'][i] for i in mask]

    fig, axs = plt.subplots(2, 1, figsize=(9, 4.6), sharex=True)
    axs[0].plot(t, area, color=TEC_BLUE, lw=1.4, label='target area')
    axs[0].axhline(35000, color='red', ls='--', lw=1.0,
                   label='target ($A_{near}$=35000)')
    axs[0].set_ylabel('area (px$^2$)')
    axs[0].legend(fontsize=8, loc='upper right')
    axs[0].set_title('Visual feedback during the orbit')
    _shade_phases(axs[0], spans_orbit, alpha=0.18)
    axs[0].grid(alpha=0.3)

    axs[1].plot(t, off, color='#16a34a', lw=1.4, label='offset_x')
    axs[1].axhline(0, color='black', ls=':', lw=0.8)
    axs[1].axhspan(-60, 60, color='gray', alpha=0.15, label='centered band')
    axs[1].set_ylabel('offset_x (px)')
    axs[1].set_xlabel('time (s)')
    axs[1].legend(fontsize=8, loc='upper right')
    _shade_phases(axs[1], spans_orbit, alpha=0.18)
    axs[1].grid(alpha=0.3)

    p = os.path.join(outdir, 'orbit_vision.png')
    fig.tight_layout()
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def extract_hud_frames(video_path, csv_data, outdir):
    """Save one mid-phase HUD frame for every phase that lasted >1 s."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 20
    targets = {}
    spans = _phase_spans(csv_data)
    for t0, t1, ph in spans:
        if ph in PHASE_ORDER and ph != 'LAND' and (t1 - t0) > 1.0:
            targets.setdefault(ph, (t0 + t1) / 2)
    saved = []
    for ph, t_target in targets.items():
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t_target * fps))
        ret, fr = cap.read()
        if ret:
            out_p = os.path.join(outdir, f'hud_{ph.lower()}.png')
            cv2.imwrite(out_p, fr)
            saved.append((ph, t_target, out_p))
    cap.release()
    return saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', type=str, default=None)
    ap.add_argument('--video', type=str, default=None)
    ap.add_argument('--outdir', type=str, default=C.FIGURES_DIR)
    args = ap.parse_args()

    if args.csv is None:
        candidates = sorted(glob.glob(
            os.path.join(C.EVIDENCE_DIR, 'telemetry_inspector_*.csv')))
        if not candidates:
            print("No CSV found in evidence/. Pass --csv explicitly.")
            return
        args.csv = candidates[-1]

    if args.video is None:
        mp4s = sorted(glob.glob(
            os.path.join(C.EVIDENCE_DIR, 'inspector_mission_*.mp4')))
        if mp4s:
            args.video = mp4s[-1]

    print(f"CSV    : {args.csv}")
    print(f"Video  : {args.video}")
    print(f"Outdir : {args.outdir}")
    os.makedirs(args.outdir, exist_ok=True)

    d = load(args.csv)
    spans = _phase_spans(d)
    print(f"Phases detected: "
          f"{[(round(t0, 1), round(t1, 1), p) for t0, t1, p in spans]}")

    made = [
        fig_phases(d, args.outdir, spans),
        fig_orbit_control(d, args.outdir, spans),
        fig_orbit_vision(d, args.outdir, spans),
    ]

    if args.video and os.path.exists(args.video):
        frames = extract_hud_frames(args.video, d, args.outdir)
        for ph, t, p in frames:
            print(f"  HUD {ph:14s} @t={t:5.1f}s -> {p}")

    print(f"\nFigures in {args.outdir}:")
    for p in made:
        if p:
            print(f"  - {os.path.basename(p)}")


if __name__ == '__main__':
    main()
