#!/usr/bin/env python3
"""
Auracle OLM offline analytics.

Two modes:

  python analytics.py record [--ws ws://localhost:8765] [--out session.jsonl] [--seconds 600]
      Connect to the bridge, log every analysis frame (ovlm_analysis or
      olm_analysis) to JSONL.

  python analytics.py report session.jsonl [--out-dir reports/]
      Read a JSONL session and produce a multi-panel matplotlib figure:
        - sensor traces (NH3, CO, VOC) with filter-active bands
        - stress score timeline with high/moderate thresholds
        - AQI penalty stack (which gas cost which point, per sample)
        - radar of mean vs peak readings
        - story feed printed to stdout

This script is deliberately separate from the in-app dashboard. The dashboard
is for live, didactic interaction. This is for "what happened in that session?"
analysis, with figures suitable for a notebook, slide, or paper.

Dependencies: matplotlib, numpy, websockets (only for `record`).
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# ---- Compound metadata mirrors viz/dashboard.html ---------------------------

COMPOUNDS = {
    "CO2":    {"label": "CO2",  "baseline": 450,  "warn": 800,  "bad": 1200},
    "NH3":    {"label": "NH3",  "baseline": 100,  "warn": 150,  "bad": 250},
    "NO":     {"label": "NO",   "baseline": 5,    "warn": 10,   "bad": 15},
    "NO2":    {"label": "NO2",  "baseline": 5,    "warn": 10,   "bad": 15},
    "CO":     {"label": "CO",   "baseline": 600,  "warn": 1000, "bad": 1500},
    "C2H5OH": {"label": "EtOH", "baseline": 100,  "warn": 300,  "bad": 500},
    "H2":     {"label": "H2",   "baseline": 130,  "warn": 180,  "bad": 220},
    "CH4":    {"label": "CH4",  "baseline": 350,  "warn": 450,  "bad": 550},
    "VOC":    {"label": "VOC",  "baseline": 1500, "warn": 2500, "bad": 3500},
}
RADAR_KEYS = ["NH3", "CO", "VOC", "CO2", "NO", "NO2", "C2H5OH", "H2", "CH4"]


def score_nh3(v):  return 3 if v > 250 else 2 if v > 150 else 1 if v > 100 else 0
def score_co(v):   return 2 if v > 1000 else 1 if v > 500 else 0
def score_voc(v):  return 2 if v > 3000 else 1 if v > 2000 else 0
def penalty_co2(v):return 3 if v > 1000 else 2 if v > 800 else 1 if v > 600 else 0
def penalty_no(v): return 2 if v > 15 else 1 if v > 10 else 0
def penalty_no2(v):return 2 if v > 15 else 1 if v > 10 else 0
def penalty_voc(v):return 3 if v > 3000 else 2 if v > 2000 else 1 if v > 1000 else 0


def reanalyze(sensors):
    """Reproduce the bridge's OLM math when only sensors are present."""
    nh3 = sensors.get("NH3", 0)
    co  = sensors.get("CO", 0)
    voc = sensors.get("VOC", 0)
    co2 = sensors.get("CO2", 400)
    no  = sensors.get("NO", 0)
    no2 = sensors.get("NO2", 0)

    stress_score = score_nh3(nh3) + score_co(co) + score_voc(voc)
    aqi = max(0, 10 - penalty_co2(co2) - penalty_no(no) - penalty_no2(no2) - penalty_voc(voc))
    level = "high" if stress_score >= 5 else "moderate" if stress_score >= 3 else "low"

    return {
        "stress_score": stress_score,
        "stress_level": level,
        "aqi": aqi,
        "contributions": {"NH3": score_nh3(nh3), "CO": score_co(co), "VOC": score_voc(voc)},
        "penalties":     {"CO2": penalty_co2(co2), "NO": penalty_no(no),
                          "NO2": penalty_no2(no2), "VOC": penalty_voc(voc)},
    }


# ---- record -----------------------------------------------------------------

async def record_async(ws_url, out_path, seconds):
    import websockets
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[record] connecting to {ws_url}")
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"type": "start_streaming"}))
        deadline = asyncio.get_event_loop().time() + seconds
        n = 0
        with out_path.open("w") as f:
            while asyncio.get_event_loop().time() < deadline:
                msg = await ws.recv()
                try:
                    data = json.loads(msg)
                except json.JSONDecodeError:
                    continue
                if data.get("type") not in ("olm_analysis", "ovlm_analysis"):
                    continue
                f.write(json.dumps(data) + "\n")
                n += 1
                if n % 5 == 0:
                    print(f"[record] {n} frames")
        print(f"[record] wrote {n} frames to {out_path}")


def cmd_record(args):
    asyncio.run(record_async(args.ws, args.out, args.seconds))


# ---- report -----------------------------------------------------------------

def load_session(path):
    frames = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                frames.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return frames


def cmd_report(args):
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    frames = load_session(args.session)
    if not frames:
        print("no frames found", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    times, nh3, co, voc, stress, aqi, filter_active = [], [], [], [], [], [], []
    contribs_acc = {"NH3": [], "CO": [], "VOC": []}
    penalty_acc  = {"CO2": [], "NO": [], "NO2": [], "VOC": []}
    radar_vals   = {k: [] for k in RADAR_KEYS}
    summaries    = []

    for fr in frames:
        ts = fr.get("timestamp")
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else datetime.now()
        except ValueError:
            t = datetime.now()
        sensors = fr.get("sensors") or fr.get("raw_sensors") or {}
        a = reanalyze(sensors) if sensors else {
            "stress_score": int(round((fr.get("raw_metrics", {}).get("stress_confidence", 0)) * 7)),
            "aqi": fr.get("raw_metrics", {}).get("air_quality_score", 8),
            "contributions": {"NH3": 0, "CO": 0, "VOC": 0},
            "penalties": {"CO2": 0, "NO": 0, "NO2": 0, "VOC": 0},
        }
        times.append(t)
        nh3.append(sensors.get("NH3", 0))
        co.append(sensors.get("CO", 0))
        voc.append(sensors.get("VOC", 0))
        stress.append(a["stress_score"])
        aqi.append(a["aqi"])
        filter_active.append(bool(fr.get("device_actions", {}).get("activate_filter")))
        for k, v in a["contributions"].items(): contribs_acc[k].append(v)
        for k, v in a["penalties"].items():     penalty_acc[k].append(v)
        for k in RADAR_KEYS:
            radar_vals[k].append(sensors.get(k, COMPOUNDS[k]["baseline"]))
        summaries.append((t, fr.get("natural_language_summary", "")))

    fig = plt.figure(figsize=(14, 11), facecolor="#0a0d14")
    gs = fig.add_gridspec(3, 2, hspace=0.45, wspace=0.25)

    def style(ax):
        ax.set_facecolor("#11151f")
        for spine in ax.spines.values():
            spine.set_color("#232a3a")
        ax.tick_params(colors="#a9b2c4")
        ax.yaxis.label.set_color("#a9b2c4")
        ax.xaxis.label.set_color("#a9b2c4")
        ax.title.set_color("#e8ecf4")
        ax.grid(True, color="#232a3a", linewidth=0.5)

    # 1. Sensor traces with filter bands
    ax1 = fig.add_subplot(gs[0, :]); style(ax1)
    ax1.set_title("Sensor traces with filter-active intervals shaded", loc="left")
    ax1.plot(times, nh3, color="#ff6b81", label="NH3", lw=1.3)
    ax1.plot(times, co,  color="#ffb86b", label="CO",  lw=1.3)
    ax1.plot(times, voc, color="#b18cff", label="VOC", lw=1.3)
    band_start = None
    for i, (t, on) in enumerate(zip(times, filter_active)):
        if on and band_start is None:
            band_start = t
        elif not on and band_start is not None:
            ax1.axvspan(band_start, t, color="#6bb8ff", alpha=0.10)
            band_start = None
    if band_start is not None:
        ax1.axvspan(band_start, times[-1], color="#6bb8ff", alpha=0.10)
    ax1.legend(loc="upper right", facecolor="#11151f", edgecolor="#232a3a", labelcolor="#a9b2c4")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

    # 2. Stress timeline
    ax2 = fig.add_subplot(gs[1, 0]); style(ax2)
    ax2.set_title("Stress score (max 7)", loc="left")
    ax2.plot(times, stress, color="#7cf3c2", lw=1.6)
    ax2.axhline(3, color="#ffc857", linestyle="--", lw=0.8, alpha=0.6, label="moderate")
    ax2.axhline(5, color="#ff5c7a", linestyle="--", lw=0.8, alpha=0.6, label="high")
    ax2.set_ylim(0, 7.3)
    ax2.legend(loc="upper right", facecolor="#11151f", edgecolor="#232a3a", labelcolor="#a9b2c4")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    # 3. AQI penalty stack
    ax3 = fig.add_subplot(gs[1, 1]); style(ax3)
    ax3.set_title("AQI penalty composition (stacked)", loc="left")
    bottom = np.zeros(len(times))
    palette = {"CO2": "#ffb86b", "NO": "#ff6b81", "NO2": "#b18cff", "VOC": "#7cf3c2"}
    width = (mdates.date2num(times[-1]) - mdates.date2num(times[0])) / max(len(times), 2)
    for k in ("CO2", "NO", "NO2", "VOC"):
        vals = np.array(penalty_acc[k])
        ax3.bar(times, vals, bottom=bottom, color=palette[k], width=width, label=k, edgecolor="none")
        bottom += vals
    ax3.set_ylabel("points subtracted from 10")
    ax3.legend(loc="upper right", facecolor="#11151f", edgecolor="#232a3a", labelcolor="#a9b2c4")
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    # 4. Radar mean vs peak
    ax4 = fig.add_subplot(gs[2, 0], projection="polar")
    ax4.set_facecolor("#11151f")
    angles = np.linspace(0, 2*np.pi, len(RADAR_KEYS), endpoint=False).tolist()
    angles += angles[:1]
    means = [np.mean(radar_vals[k]) / COMPOUNDS[k]["bad"] for k in RADAR_KEYS]
    peaks = [np.max(radar_vals[k]) / COMPOUNDS[k]["bad"] for k in RADAR_KEYS]
    means += means[:1]; peaks += peaks[:1]
    ax4.plot(angles, peaks, color="#ff6b81", lw=1.5, label="peak")
    ax4.fill(angles, peaks, color="#ff6b81", alpha=0.10)
    ax4.plot(angles, means, color="#7cf3c2", lw=1.5, label="mean")
    ax4.fill(angles, means, color="#7cf3c2", alpha=0.20)
    ax4.set_thetagrids(np.degrees(angles[:-1]), [COMPOUNDS[k]["label"] for k in RADAR_KEYS], color="#a9b2c4")
    ax4.set_ylim(0, 1.2)
    ax4.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax4.set_yticklabels(["", "warn", "", "bad"], color="#6b7488")
    ax4.tick_params(colors="#a9b2c4")
    ax4.set_title("Mean vs peak across session", color="#e8ecf4", loc="left", pad=18)
    ax4.legend(loc="upper right", facecolor="#11151f", edgecolor="#232a3a", labelcolor="#a9b2c4", bbox_to_anchor=(1.25, 1.1))

    # 5. Stress contributions stacked
    ax5 = fig.add_subplot(gs[2, 1]); style(ax5)
    ax5.set_title("Stress score: which gas contributed?", loc="left")
    bottom = np.zeros(len(times))
    cpalette = {"NH3": "#ff6b81", "CO": "#ffb86b", "VOC": "#b18cff"}
    for k in ("NH3", "CO", "VOC"):
        vals = np.array(contribs_acc[k])
        ax5.bar(times, vals, bottom=bottom, color=cpalette[k], width=width, label=k, edgecolor="none")
        bottom += vals
    ax5.set_ylabel("score points")
    ax5.legend(loc="upper right", facecolor="#11151f", edgecolor="#232a3a", labelcolor="#a9b2c4")
    ax5.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    fig.suptitle(
        f"Auracle session report  ·  {len(frames)} frames  ·  "
        f"{times[0].strftime('%H:%M:%S')} to {times[-1].strftime('%H:%M:%S')}",
        color="#e8ecf4", fontsize=13, x=0.02, ha="left",
    )

    fig_path = out_dir / "session_report.png"
    fig.savefig(fig_path, dpi=160, facecolor=fig.get_facecolor(), bbox_inches="tight")
    print(f"[report] wrote {fig_path}")

    story_path = out_dir / "story.txt"
    with story_path.open("w") as f:
        for t, s in summaries:
            f.write(f"[{t.strftime('%H:%M:%S')}] {s}\n")
    print(f"[report] wrote {story_path}")

    print()
    print(f"frames:           {len(frames)}")
    print(f"high-stress %:    {100*sum(1 for s in stress if s >= 5)/len(stress):.1f}%")
    print(f"filter active %:  {100*sum(filter_active)/len(filter_active):.1f}%")
    print(f"mean AQI:         {np.mean(aqi):.1f} / 10")
    print(f"peak NH3:         {max(nh3):.0f}")


# ---- entry ------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Auracle OLM offline analytics")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_rec = sub.add_parser("record", help="record a live session from the bridge")
    p_rec.add_argument("--ws", default="ws://localhost:8765")
    p_rec.add_argument("--out", default="session.jsonl")
    p_rec.add_argument("--seconds", type=int, default=600)
    p_rec.set_defaults(func=cmd_record)

    p_rep = sub.add_parser("report", help="render a session JSONL into figures")
    p_rep.add_argument("session")
    p_rep.add_argument("--out-dir", default="reports")
    p_rep.set_defaults(func=cmd_report)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
