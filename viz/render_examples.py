#!/usr/bin/env python3
"""
Render dashboard / analytics previews from a real Netholabs cage session.

Usage:
  python render_examples.py SESSION_DIR --out-dir examples/

SESSION_DIR is the rig log folder, e.g.
  ~/Downloads/5.01.001_all_2026_04_30_21_00_00_000

Reads scentience/, beambreaker/, led/, speaker/, pelletdispenser/, lcd1/, lcd2/
and produces:

  examples/dashboard_preview.png     mockup of the live dashboard with this data
  examples/session_report.png        analytics-style multi-panel session report
  examples/experiment_overlay.png    cage-event timeline overlaid on gas traces

The mapping from the dual-sensor cage format (NH3_A / NH3_B / ...) to the
single-channel dashboard format (NH3 / CO / VOC ...) is deliberately simple:
  NH3 = max(A, B), CO = max(A, B), NO = max, NO2 = max, CO2 direct.
  VOC = sum of organic channels (C2H5OH + H2 + CH4 + C3H8 + C4H10) max(A,B).
  C2H5OH, H2, CH4 = max(A, B) for the radar.
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
from matplotlib import font_manager
from matplotlib.lines import Line2D
import numpy as np

# ---- Auracle palette + typography (matches brand + dashboard.html) ----------

BG_0   = "#efede8"   # page — soft cool cream
BG_1   = "#f5f3ee"   # lifted card
BG_2   = "#e6e3dc"   # sunken / track
LINE   = "#d5d2c9"   # subtle hairline
INK_0  = "#0f0f0f"   # primary near-black
INK_1  = "#3a3a3a"   # secondary
INK_2  = "#8a8780"   # muted
CREAM  = "#ffffff"   # highlight
ACCENT = "#0f0f0f"   # near-black accent
WARM   = "#a86d50"   # terracotta
HOT    = "#9c3344"   # brick
COOL   = "#5a6a82"   # muted slate
VIOLET = "#6b5b95"   # dusty violet
GOOD   = "#5a7848"   # sage
WARN   = "#a86d50"
BAD    = "#9c3344"

# Typography: prefer brand serif, fall back to Georgia / Didot / Bodoni 72
# (all ship on macOS) so figures look right without downloading fonts.
def _pick(family_list, default):
    avail = {f.name for f in font_manager.fontManager.ttflist}
    for n in family_list:
        if n in avail:
            return n
    return default

SERIF = _pick(["Fraunces 144pt", "Fraunces", "Canela", "Cormorant Garamond",
               "Playfair Display", "Bodoni 72", "Didot", "Georgia"], "serif")
SANS  = _pick(["Inter", "Söhne", "SF Pro Text", "Helvetica Neue", "Avenir Next",
               "Avenir", "Helvetica"], "sans-serif")

plt.rcParams.update({
    "font.family":     SANS,
    "font.size":       10,
    "axes.labelcolor": INK_1,
    "axes.edgecolor":  LINE,
    "axes.titlecolor": INK_0,
    "axes.titlesize":  12,
    "axes.titleweight": "regular",
    "xtick.color":     INK_2,
    "ytick.color":     INK_2,
    "axes.grid":       True,
    "grid.color":      LINE,
    "grid.alpha":      0.5,
    "grid.linewidth":  0.5,
    "figure.facecolor": BG_0,
    "axes.facecolor":   BG_1,
    "savefig.facecolor": BG_0,
    "legend.frameon":   False,
})

COMPOUNDS = {
    "CO2":    {"label": "CO₂",  "baseline": 450,  "warn": 800,  "bad": 1200},
    "NH3":    {"label": "NH₃",  "baseline": 100,  "warn": 150,  "bad": 250},
    "NO":     {"label": "NO",   "baseline": 5,    "warn": 10,   "bad": 15},
    "NO2":    {"label": "NO₂",  "baseline": 5,    "warn": 10,   "bad": 15},
    "CO":     {"label": "CO",   "baseline": 600,  "warn": 1000, "bad": 1500},
    "C2H5OH": {"label": "EtOH", "baseline": 100,  "warn": 300,  "bad": 500},
    "H2":     {"label": "H₂",   "baseline": 130,  "warn": 180,  "bad": 220},
    "CH4":    {"label": "CH₄",  "baseline": 350,  "warn": 450,  "bad": 550},
    "VOC":    {"label": "VOC",  "baseline": 1500, "warn": 2500, "bad": 3500},
}
RADAR_KEYS = ["NH3", "CO", "VOC", "CO2", "NO", "NO2", "C2H5OH", "H2", "CH4"]

# COLIP aroma anchors — must match demo.py AROMA_ANCHORS so the static
# preview agrees with whatever the model would produce live.
AROMA_ANCHORS = [
    ("Fresh air",            "fresh clean outdoor air, no pollutants, pure breathable",                 False),
    ("Urban pollution",      "diesel exhaust fumes, nitrogen dioxide, carbon monoxide, traffic",         True),
    ("Cigarette smoke",      "cigarette tobacco smoke, burnt paper, nicotine fumes",                     True),
    ("Ammonia / cleaning",   "ammonia bleach cleaning chemicals disinfectant",                           True),
    ("Cooking / kitchen",    "cooking food smells, kitchen fumes, frying oil, burnt food",               False),
    ("Mould / damp",         "mold mildew musty damp basement, fungal spores",                           True),
    ("Petrol / fuel",        "petrol gasoline fuel station, hydrocarbons, VOC solvent fumes",            True),
    ("Industrial / chemical","industrial chemical factory, solvent, paint fumes, acetone",               True),
    ("Smoke / fire",         "wood smoke bonfire wildfire, burnt carbon particulates",                   True),
    ("Floral / natural",     "floral perfume flowers garden, fresh natural botanical scent",             False),
]


def synthesize_aroma(s):
    """Stand-in for the COLIP forward pass. Mirrors viz/dashboard.html's
    synthesizeAroma() so static previews and the live dashboard agree."""
    import random
    nh3 = s.get("NH3", 0); co = s.get("CO", 0); voc = s.get("VOC", 0)
    co2 = s.get("CO2", 400); no = s.get("NO", 0); no2 = s.get("NO2", 0)
    eth = s.get("C2H5OH", 0); ch4 = s.get("CH4", 0); h2 = s.get("H2", 0)
    hum = s.get("ENV_humidity", 45)
    bias = {
        "Fresh air":             0.20 + max(0, 1 - (voc + co + nh3) / 6000) * 0.08,
        "Urban pollution":       0.21 + min(1, (co + no + no2*2) / 1500) * 0.13,
        "Cigarette smoke":       0.21 + min(1, (co + voc/2) / 2500) * 0.11,
        "Ammonia / cleaning":    0.21 + min(1, nh3 / 250) * 0.14,
        "Cooking / kitchen":     0.21 + min(1, (ch4 + voc/3) / 3000) * 0.10,
        "Mould / damp":          0.21 + min(1, hum / 100) * 0.07 + min(1, h2 / 250) * 0.04,
        "Petrol / fuel":         0.21 + min(1, (eth + voc/2) / 2500) * 0.12,
        "Industrial / chemical": 0.21 + min(1, (voc + co) / 4000) * 0.13,
        "Smoke / fire":          0.21 + min(1, (co + voc/3) / 3000) * 0.11,
        "Floral / natural":      0.21 + min(1, (eth/3) / 200) * 0.05,
    }
    rng = random.Random(hash(tuple(sorted(s.items()))) & 0xFFFFFFFF)
    ranked = sorted(
        [{"label": L, "desc": D, "filter": F,
          "score": max(0.20, min(0.36, bias[L] + (rng.random() - 0.5) * 0.012))}
         for (L, D, F) in AROMA_ANCHORS],
        key=lambda r: -r["score"],
    )
    return {"top": ranked, "filter_recommended": ranked[0]["filter"]}

# ---- parsing ----------------------------------------------------------------

TIMESTAMP_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\]")


def parse_ts(line):
    m = TIMESTAMP_RE.match(line)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f")


def parse_kv_line(line):
    """Parse `key=value | key=value | ...` segment."""
    out = {}
    for chunk in line.split("|"):
        chunk = chunk.strip()
        if "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        k = k.strip(); v = v.strip()
        try:
            out[k] = float(v)
        except ValueError:
            out[k] = v
    return out


def parse_scentience_dir(d):
    samples = []
    for p in sorted(d.glob("Scentience_*.txt")):
        line = p.read_text().strip()
        ts = parse_ts(line)
        kv = parse_kv_line(line.split("] ", 2)[-1])
        # collapse A/B sensors
        def mx(a, b): return max(kv.get(a, 0), kv.get(b, 0))
        nh3 = mx("NH3_A", "NH3_B")
        co  = mx("CO_A", "CO_B")
        no  = mx("NO_A", "NO_B")
        no2 = mx("NO2_A", "NO2_B")
        eth = mx("C2H5OH_A", "C2H5OH_B")
        h2  = mx("H2_A", "H2_B")
        ch4 = mx("CH4_A", "CH4_B")
        c3h8 = mx("C3H8_A", "C3H8_B")
        c4h10 = mx("C4H10_A", "C4H10_B")
        voc = eth + h2 + ch4 + c3h8 + c4h10  # synthesized total
        samples.append({
            "t": ts,
            "CO2": kv.get("CO2", 0),
            "NH3": nh3, "CO": co, "NO": no, "NO2": no2,
            "C2H5OH": eth, "H2": h2, "CH4": ch4, "VOC": voc,
            "ENV_temperatureC": kv.get("ENV_temperatureC", 0),
            "ENV_humidity": kv.get("ENV_humidity", 0),
            "BATT_charge": kv.get("BATT_charge", 0),
            "ble_latency": kv.get("ble_latency", 0),
        })
    return samples


def parse_event_dir(d, kind, parser=None):
    out = []
    if not d.exists():
        return out
    for p in sorted(d.glob(f"{kind}_*.txt")):
        line = p.read_text().strip()
        ts = parse_ts(line)
        if ts is None:
            continue
        body = line.split("] ", 2)[-1] if "] " in line else line
        info = parser(body) if parser else {"raw": body}
        info["t"] = ts
        out.append(info)
    return out


# event-specific parsers
def parse_led_body(b):
    m = re.search(r"duration=(\d+)ms", b)
    return {"kind": "LED flash", "duration_ms": int(m.group(1)) if m else 0}

def parse_speaker_body(b):
    m1 = re.search(r"freq=(\d+)Hz", b); m2 = re.search(r"duration=(\d+)ms", b)
    return {"kind": "tone", "freq_hz": int(m1.group(1)) if m1 else 0,
            "duration_ms": int(m2.group(1)) if m2 else 0}

def parse_lcd_body(b):
    m1 = re.search(r"image(\w+)\.jpg", b); m2 = re.search(r"duration=(\d+)ms", b)
    return {"kind": "image", "image": m1.group(1) if m1 else "?",
            "duration_ms": int(m2.group(1)) if m2 else 0}

def parse_simple_body(b):
    return {"kind": b.replace("[BeamBreaker]", "").replace("[PelletDispenser]", "").strip()}


# ---- OLM math (mirrors bridge) ----------------------------------------------

def score_nh3(v):  return 3 if v > 250 else 2 if v > 150 else 1 if v > 100 else 0
def score_co(v):   return 2 if v > 1000 else 1 if v > 500 else 0
def score_voc(v):  return 2 if v > 3000 else 1 if v > 2000 else 0
def penalty_co2(v):return 3 if v > 1000 else 2 if v > 800 else 1 if v > 600 else 0
def penalty_no(v): return 2 if v > 15 else 1 if v > 10 else 0
def penalty_no2(v):return 2 if v > 15 else 1 if v > 10 else 0
def penalty_voc(v):return 3 if v > 3000 else 2 if v > 2000 else 1 if v > 1000 else 0


def analyze(s):
    nh3, co, voc = s["NH3"], s["CO"], s["VOC"]
    co2, no, no2 = s["CO2"], s["NO"], s["NO2"]
    stress = score_nh3(nh3) + score_co(co) + score_voc(voc)
    aqi = max(0, 10 - penalty_co2(co2) - penalty_no(no) - penalty_no2(no2) - penalty_voc(voc))
    level = "high" if stress >= 5 else "moderate" if stress >= 3 else "low"
    quality = "excellent" if aqi >= 8 else "good" if aqi >= 6 else "moderate" if aqi >= 4 else "poor"
    return {
        "stress_score": stress, "stress_level": level,
        "aqi": aqi, "quality_level": quality,
        "contributions": {"NH3": score_nh3(nh3), "CO": score_co(co), "VOC": score_voc(voc)},
        "penalties": {"CO2": penalty_co2(co2), "NO": penalty_no(no),
                      "NO2": penalty_no2(no2), "VOC": penalty_voc(voc)},
        "filter_active": aqi < 6 or level != "low",
        "fan_speed": 85 if level == "high" else 65 if level == "moderate" else 0,
        "filter_mode": "stress_reduction" if level == "high"
                       else "standard" if level != "low" else "standby",
    }


# ---- styling helpers --------------------------------------------------------

def style_axes(ax):
    ax.set_facecolor(BG_1)
    for s in ax.spines.values(): s.set_color(LINE)
    ax.tick_params(colors=INK_2, which="both", labelsize=9)
    ax.yaxis.label.set_color(INK_2)
    ax.xaxis.label.set_color(INK_2)
    ax.title.set_color(INK_0)
    ax.grid(True, color=LINE, linewidth=0.5, alpha=0.5)


# ---- panel renderers --------------------------------------------------------

def render_aroma(ax, latest):
    """Aroma classification panel — top-5 anchors with cosine bars."""
    ax.set_facecolor(BG_1)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    aroma = synthesize_aroma(latest)
    top5 = aroma["top"][:5]
    top = top5[0]

    # Top match: big serif label + score + filter pill
    ax.text(0.04, 0.86, top["label"], color=INK_0, fontsize=18,
            fontfamily=SERIF, transform=ax.transAxes)
    ax.text(0.04, 0.76, f"{top['score']:.4f}",
            color=INK_1, fontsize=11, fontfamily=SANS,
            transform=ax.transAxes)
    pill_color = BAD if top["filter"] else GOOD
    pill_text  = "filter recommended" if top["filter"] else "air acceptable"
    ax.add_patch(mpatches.FancyBboxPatch(
        (0.65, 0.76), 0.32, 0.07,
        boxstyle="round,pad=0.005,rounding_size=0.035",
        facecolor=pill_color, edgecolor=pill_color, lw=0,
        transform=ax.transAxes))
    ax.text(0.81, 0.795, pill_text, color=CREAM, fontsize=9,
            ha="center", va="center", style="italic",
            transform=ax.transAxes)

    ax.plot([0.04, 0.96], [0.69, 0.69], color=LINE, lw=0.6, transform=ax.transAxes)
    ax.text(0.04, 0.63, "TOP 5 MATCHES", color=INK_2, fontsize=8,
            transform=ax.transAxes, style="italic")

    # Bars
    lo, hi = 0.20, 0.36
    for i, r in enumerate(top5):
        y = 0.55 - i * 0.10
        ax.text(0.04, y, r["label"],
                color=(INK_0 if i == 0 else INK_1),
                fontsize=10, transform=ax.transAxes)
        ax.add_patch(mpatches.Rectangle((0.40, y + 0.002), 0.45, 0.008,
            linewidth=0, facecolor=BG_2, transform=ax.transAxes))
        pct = max(0, min(1, (r["score"] - lo) / (hi - lo)))
        bar_color = BAD if r["filter"] else ACCENT
        ax.add_patch(mpatches.Rectangle((0.40, y + 0.002), 0.45 * pct, 0.008,
            linewidth=0, facecolor=bar_color, transform=ax.transAxes))
        ax.text(0.97, y, f"{r['score']:.3f}",
                color=INK_2, fontsize=8, ha="right",
                family="monospace", transform=ax.transAxes)


def render_radar(ax, latest):
    ax.set_facecolor(BG_1)
    ax.spines["polar"].set_color(LINE)
    angles = np.linspace(0, 2 * np.pi, len(RADAR_KEYS), endpoint=False).tolist()
    angles_closed = angles + angles[:1]
    base = [COMPOUNDS[k]["baseline"] / COMPOUNDS[k]["bad"] for k in RADAR_KEYS]
    live = [min(latest[k] / COMPOUNDS[k]["bad"], 1.15) for k in RADAR_KEYS]
    base_c = base + base[:1]; live_c = live + live[:1]

    ax.plot(angles_closed, base_c, color=COOL, lw=1, ls="--", alpha=0.7)
    ax.fill(angles_closed, base_c, color=COOL, alpha=0.07)
    ax.plot(angles_closed, live_c, color=ACCENT, lw=1.8)
    ax.fill(angles_closed, live_c, color=ACCENT, alpha=0.18)

    # dots colored by zone
    for ang, k in zip(angles, RADAR_KEYS):
        v = latest[k]; c = COMPOUNDS[k]
        color = HOT if v >= c["bad"] else WARM if v >= c["warn"] else ACCENT
        r = min(v / c["bad"], 1.15)
        ax.plot([ang], [r], "o", color=color, markersize=5,
                markeredgecolor=BG_1, markeredgewidth=1.2)

    ax.set_thetagrids(np.degrees(angles), [COMPOUNDS[k]["label"] for k in RADAR_KEYS],
                      color=INK_1, fontsize=10)
    ax.set_ylim(0, 1.2)
    ax.set_yticks([0.5, 1.0])
    ax.set_yticklabels(["warn", "bad"], color=INK_2, fontsize=8, style="italic")
    ax.tick_params(colors=INK_2, pad=8)
    ax.grid(color=LINE, linewidth=0.5, alpha=0.6)
    # rotate label-positions slightly outward
    ax.tick_params(axis="x", pad=10)


def render_stress(ax, latest_an, latest):
    """Three vertical zones: gauge (top), meta (middle), contributions (bottom)."""
    ax.set_facecolor(BG_1)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    score = latest_an["stress_score"]; level = latest_an["stress_level"]
    frac = min(score / 7, 1.0)
    color = HOT if level == "high" else WARM if level == "moderate" else ACCENT

    # ---- Top zone: gauge (y 0.55–1.0) ----
    cx, cy, r = 0.5, 0.66, 0.30
    theta = np.linspace(np.pi, 0, 200)
    ax.plot(cx + r * np.cos(theta), cy + r * np.sin(theta),
            color=BG_2, lw=10, solid_capstyle="round")
    fg_theta = np.linspace(np.pi, np.pi - frac * np.pi, 200)
    ax.plot(cx + r * np.cos(fg_theta), cy + r * np.sin(fg_theta),
            color=color, lw=10, solid_capstyle="round")
    ang = np.pi - frac * np.pi
    nx, ny = cx + (r - 0.04) * np.cos(ang), cy + (r - 0.04) * np.sin(ang)
    ax.plot([cx, nx], [cy, ny], color=INK_0, lw=1.8)
    ax.plot([cx], [cy], "o", color=INK_0, markersize=5)
    ax.text(cx, cy + 0.06, f"{score}", color=INK_0, ha="center", va="center",
            fontsize=32, fontfamily=SERIF)
    ax.text(cx - r - 0.03, cy + 0.005, "0",
            color=INK_2, ha="center", fontsize=8, style="italic")
    ax.text(cx + r + 0.03, cy + 0.005, "7",
            color=INK_2, ha="center", fontsize=8, style="italic")
    ax.text(cx, cy - 0.03, "stress score",
            color=INK_2, ha="center", va="center", fontsize=8, style="italic")

    # ---- divider ----
    ax.plot([0.04, 0.96], [0.50, 0.50], color=LINE, lw=0.6, transform=ax.transAxes)

    # ---- Middle zone: meta (y 0.34–0.50) ----
    ax.text(0.04, 0.45, "LEVEL", color=INK_2, fontsize=8,
            transform=ax.transAxes, style="italic")
    ax.text(0.04, 0.36, level, color=INK_0, fontsize=14, fontfamily=SERIF,
            transform=ax.transAxes)
    ax.text(0.55, 0.45, "CORTISOL EST.", color=INK_2, fontsize=8,
            transform=ax.transAxes, style="italic")
    ax.text(0.55, 0.36, f"{latest['NH3']*0.05:.2f} ng/m³",
            color=INK_0, fontsize=12, fontfamily=SANS, fontweight=500,
            transform=ax.transAxes)

    # ---- divider ----
    ax.plot([0.04, 0.96], [0.32, 0.32], color=LINE, lw=0.6, transform=ax.transAxes)

    # ---- Bottom zone: contribution bars (y 0–0.30) ----
    ax.text(0.04, 0.27, "CONTRIBUTIONS", color=INK_2, fontsize=8,
            transform=ax.transAxes, style="italic")
    contribs = latest_an["contributions"]
    maxes = {"NH3": 3, "CO": 2, "VOC": 2}
    keys = ["NH3", "CO", "VOC"]
    for i, k in enumerate(keys):
        y = 0.05 + (2 - i) * 0.06
        ax.text(0.04, y, COMPOUNDS[k]["label"],
                color=INK_1, fontsize=10, transform=ax.transAxes)
        ax.add_patch(mpatches.Rectangle((0.20, y + 0.002), 0.62, 0.010,
            linewidth=0, facecolor=BG_2, transform=ax.transAxes))
        v = contribs[k]; m = maxes[k]
        if v > 0:
            ax.add_patch(mpatches.Rectangle((0.20, y + 0.002), 0.62 * (v / m), 0.010,
                linewidth=0, facecolor=color, transform=ax.transAxes))
        ax.text(0.86, y, f"+{v}", color=INK_2, fontsize=9, transform=ax.transAxes)


def render_aqi(ax, latest_an):
    ax.set_facecolor(BG_1)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    aqi = latest_an["aqi"]; lvl = latest_an["quality_level"]
    lvl_color = GOOD if lvl == "excellent" else ACCENT if lvl == "good" \
        else WARN if lvl == "moderate" else BAD

    # ---- Top zone: big number + level pill (y 0.66–1.0) ----
    ax.text(0.05, 0.78, f"{aqi}", color=INK_0, fontsize=50, fontfamily=SERIF,
            transform=ax.transAxes)
    ax.text(0.32, 0.81, "/ 10", color=INK_2, fontsize=13, style="italic", transform=ax.transAxes)
    ax.add_patch(mpatches.FancyBboxPatch((0.05, 0.66), 0.42, 0.07,
        boxstyle="round,pad=0.01,rounding_size=0.035",
        facecolor=BG_2, edgecolor=LINE, lw=0.8, transform=ax.transAxes))
    ax.text(0.26, 0.70, lvl, color=lvl_color, ha="center", va="center",
            fontsize=10, style="italic", transform=ax.transAxes)

    # ---- divider ----
    ax.plot([0.04, 0.96], [0.59, 0.59], color=LINE, lw=0.6, transform=ax.transAxes)

    # ---- Bottom zone: penalty rows (y 0–0.55) ----
    ax.text(0.04, 0.52, "PENALTIES", color=INK_2, fontsize=8,
            transform=ax.transAxes, style="italic")
    penalties = latest_an["penalties"]
    maxes = {"CO2": 3, "NO": 2, "NO2": 2, "VOC": 3}
    keys = ["CO2", "NO", "NO2", "VOC"]
    for i, k in enumerate(keys):
        y = 0.40 - i * 0.105
        ax.text(0.04, y, COMPOUNDS[k]["label"],
                color=INK_1, fontsize=10, transform=ax.transAxes)
        ax.add_patch(mpatches.Rectangle((0.22, y + 0.002), 0.60, 0.012,
            linewidth=0, facecolor=BG_2, transform=ax.transAxes))
        v = penalties[k]; m = maxes[k]
        bar_color = GOOD if v == 0 else BAD if v == m else WARN
        if v > 0:
            ax.add_patch(mpatches.Rectangle((0.22, y + 0.002), 0.60 * (v / m), 0.012,
                linewidth=0, facecolor=bar_color, transform=ax.transAxes))
        ax.text(0.88, y, f"−{v}", color=INK_2, fontsize=9,
                transform=ax.transAxes)


def render_timeline(ax, samples, analyses, events):
    style_axes(ax)
    times = [s["t"] for s in samples]
    nh3 = np.array([s["NH3"] for s in samples])
    co = np.array([s["CO"] for s in samples])
    voc = np.array([s["VOC"] for s in samples])
    stress = np.array([a["stress_score"] for a in analyses])

    # twin axis for stress
    ax2 = ax.twinx()
    style_axes(ax2)
    ax2.spines["right"].set_color(LINE)
    ax2.tick_params(colors=INK_2)

    # filter active bands
    for s, a in zip(samples, analyses):
        if a["filter_active"]:
            ax.axvspan(s["t"], s["t"], color=COOL, alpha=0)  # placeholder

    ax.plot(times, nh3, color=HOT, lw=1.6, label="NH₃", marker="o", markersize=4)
    ax.plot(times, co,  color=WARM, lw=1.6, label="CO",  marker="o", markersize=4)
    ax.plot(times, voc, color=VIOLET, lw=1.6, label="VOC", marker="o", markersize=4)
    ax2.plot(times, stress, color=ACCENT, lw=2.2, label="stress", linestyle="-")
    ax2.set_ylim(-0.3, 7.3)

    # cage events as vertical markers
    event_styles = {
        "LED":            {"color": WARM,   "marker": "^", "label": "LED flash"},
        "Speaker":        {"color": COOL,   "marker": "v", "label": "tone"},
        "LCD1":           {"color": VIOLET, "marker": "s", "label": "image"},
        "PelletDispenser":{"color": ACCENT, "marker": "D", "label": "pellet"},
        "BeamBreaker":    {"color": INK_1,  "marker": "x", "label": "beam"},
    }
    plotted = set()
    ymax_left = max(max(nh3.max(), co.max(), voc.max()) * 1.05, 10)
    ax.set_ylim(0, ymax_left)
    for kind, evs in events.items():
        st = event_styles.get(kind, {"color": INK_1, "marker": "o", "label": kind})
        for e in evs:
            ax.plot([e["t"]], [ymax_left * 0.95], st["marker"], color=st["color"],
                    markersize=8, markeredgecolor=BG_0, markeredgewidth=1,
                    label=st["label"] if kind not in plotted else None)
            plotted.add(kind)

    # legend — single horizontal row at the bottom outside the plot
    handles = [
        Line2D([0], [0], color=HOT, lw=1.6, marker="o", markersize=4, label="NH₃"),
        Line2D([0], [0], color=WARM, lw=1.6, marker="o", markersize=4, label="CO"),
        Line2D([0], [0], color=VIOLET, lw=1.6, marker="o", markersize=4, label="VOC"),
        Line2D([0], [0], color=ACCENT, lw=2.2, label="stress (right)"),
    ]
    for kind, st in event_styles.items():
        if kind in plotted:
            handles.append(Line2D([0], [0], color=st["color"], lw=0,
                marker=st["marker"], markersize=7, label=st["label"]))
    leg = ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.12),
                    facecolor=BG_0, edgecolor="none",
                    labelcolor=INK_1, fontsize=9, ncol=len(handles), frameon=False)
    for t in leg.get_texts(): t.set_color(INK_1)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax.set_ylabel("ppm-equivalent", color=INK_2, fontsize=9, style="italic")
    ax2.set_ylabel("stress score", color=INK_2, fontsize=9, style="italic")


def render_filter(ax, latest_an):
    ax.set_facecolor(BG_1)
    ax.set_xlim(0, 320); ax.set_ylim(0, 220); ax.axis("off")

    # case
    ax.add_patch(mpatches.FancyBboxPatch((20, 40), 280, 140,
        boxstyle="round,pad=2,rounding_size=14",
        facecolor=BG_2, edgecolor=LINE, lw=1.5))

    # media
    ax.add_patch(mpatches.Rectangle((120, 60), 14, 100,
        facecolor=ACCENT, alpha=0.18, edgecolor=ACCENT, lw=1))
    ax.text(127, 50, "media", color=INK_2, ha="center", fontsize=8)

    # fan circle
    fan_x, fan_y = 220, 110
    ax.add_patch(mpatches.Circle((fan_x, fan_y), 36, facecolor=BG_2, edgecolor=LINE, lw=1.2))
    # blades
    for off in (0, 120, 240):
        a = np.deg2rad(off)
        ax.add_patch(mpatches.Ellipse((fan_x + 0 * np.cos(a), fan_y + 0 * np.sin(a)),
            12, 28, angle=off, facecolor=ACCENT, alpha=0.85))
    ax.add_patch(mpatches.Circle((fan_x, fan_y), 5, facecolor=INK_1))
    ax.text(fan_x, fan_y - 50, "fan", color=INK_2, ha="center", fontsize=8)

    # LED ring
    led_color = HOT if latest_an["stress_level"] == "high" else WARM if latest_an["stress_level"] == "moderate" else GOOD
    ax.add_patch(mpatches.Circle((50, 110), 22, facecolor="none",
        edgecolor=led_color, lw=4, alpha=1 if latest_an["filter_active"] else 0.3))
    ax.text(50, 80, "LED", color=INK_2, ha="center", fontsize=8)

    # particles
    voc = latest_an.get("voc", None)
    n = max(2, min(20, int(latest_an["aqi"] == 0 and 18 or 6)))
    np.random.seed(0)
    for _ in range(n):
        px = 30 + np.random.rand() * 80
        py = 55 + np.random.rand() * 110
        col = HOT if latest_an["stress_level"] != "low" else INK_1
        ax.plot([px], [py], "o", color=col, markersize=2, alpha=0.6)

    # caption
    cap = ("idle: monitoring air" if not latest_an["filter_active"]
           else "stress mode · NH₃ + VOCs"
                if latest_an["filter_mode"] == "stress_reduction"
           else "standard purification")
    ax.text(160, 200, cap, color=INK_0, ha="center", fontsize=11, fontfamily=SERIF)

    # meta cells
    cells = [
        ("MODE",     latest_an["filter_mode"]),
        ("FAN",      f"{latest_an['fan_speed']}%"),
    ]
    for i, (k, v) in enumerate(cells):
        x = 30 + i * 140; y = 12
        ax.add_patch(mpatches.Rectangle((x, y), 130, 20,
            facecolor=BG_2, edgecolor=LINE, lw=1))
        ax.text(x + 8, y + 14, k, color=INK_2, fontsize=7, style="italic")
        ax.text(x + 50, y + 14, v, color=INK_0, fontsize=11, fontfamily=SERIF)


def render_story(ax, samples, analyses):
    """Compact bubble feed — timestamp left, message + chips stacked right."""
    ax.set_facecolor(BG_1)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    n = len(samples)
    # bubble vertical layout
    pad_top, pad_bot = 0.04, 0.04
    avail = 1 - pad_top - pad_bot
    bubble_h = avail / n          # full row height
    inner_h  = bubble_h * 0.84    # actual bubble height (row gap = 16% of row)
    gap      = bubble_h - inner_h

    for i, (s, a) in enumerate(zip(samples, analyses)):
        # most-recent first
        y_top = 1 - pad_top - i * bubble_h
        y_bot = y_top - inner_h

        ts = s["t"].strftime("%H:%M:%S")
        lvl = a["stress_level"]
        edge = HOT if lvl == "high" else WARM if lvl == "moderate" else GOOD

        # bubble container
        ax.add_patch(mpatches.Rectangle((0.005, y_bot), 0.99, inner_h,
            facecolor=BG_2, edgecolor=LINE, lw=0.8))
        # left accent bar
        ax.add_patch(mpatches.Rectangle((0.005, y_bot), 0.004, inner_h,
            facecolor=edge, edgecolor="none"))

        # left column: timestamp + level
        col_x = 0.025
        ax.text(col_x, y_top - inner_h * 0.30, ts,
                color=INK_1, fontsize=10, style="italic", va="center")
        ax.text(col_x, y_top - inner_h * 0.65, lvl.upper(),
                color=edge, fontsize=8, va="center")

        # vertical separator between columns
        ax.plot([0.115, 0.115], [y_bot + inner_h * 0.18, y_top - inner_h * 0.18],
                color=LINE, lw=0.6)

        # right column row 1: message
        msg = (f"{s['ENV_temperatureC']:.0f}°C · {s['ENV_humidity']:.0f}% RH · "
               f"AQI {a['aqi']}/10 ({a['quality_level']}) · "
               + ("filter " + a["filter_mode"] if a["filter_active"] else "filter idle"))
        ax.text(0.13, y_top - inner_h * 0.30, msg,
                color=INK_0, fontsize=10, va="center")

        # right column row 2: chips
        chips = [
            ("stress",  f"{a['stress_score']}/7"),
            ("AQI",     f"{a['aqi']}/10"),
            ("NH₃",     f"{s['NH3']:.0f}"),
            ("CO",      f"{s['CO']:.0f}"),
            ("VOC",     f"{s['VOC']:.0f}"),
        ]
        chip_y = y_top - inner_h * 0.72
        chip_h = inner_h * 0.28
        chip_x = 0.13
        for label, value in chips:
            text = f"{label} {value}"
            # measure-free fixed width — each chip is ~80 chars wide
            chip_w = 0.085
            ax.add_patch(mpatches.FancyBboxPatch(
                (chip_x, chip_y - chip_h * 0.5),
                chip_w, chip_h * 0.78,
                boxstyle="round,pad=0.003,rounding_size=0.012",
                facecolor=BG_1, edgecolor=LINE, lw=0.6))
            ax.text(chip_x + chip_w / 2, chip_y - chip_h * 0.10, text,
                    color=INK_2, fontsize=8, ha="center", va="center", style="italic")
            chip_x += chip_w + 0.012


# ---- top-level renderers -----------------------------------------------------

def render_dashboard_preview(samples, analyses, events, out):
    fig = plt.figure(figsize=(18, 14), facecolor=BG_0)
    gs = fig.add_gridspec(
        3, 12,
        height_ratios=[1.05, 1.0, 1.0],
        hspace=1.0, wspace=1.05,
        left=0.045, right=0.965, top=0.880, bottom=0.05,
    )

    ax_aroma  = fig.add_subplot(gs[0, 0:5])
    ax_stress = fig.add_subplot(gs[0, 5:9])
    ax_aqi    = fig.add_subplot(gs[0, 9:12])
    ax_radar  = fig.add_subplot(gs[1, 0:4], projection="polar")
    ax_time   = fig.add_subplot(gs[1, 4:12])
    ax_filt   = fig.add_subplot(gs[2, 0:4])
    ax_story  = fig.add_subplot(gs[2, 4:12])

    latest = samples[-1]; latest_an = analyses[-1]
    render_aroma(ax_aroma, latest)
    render_radar(ax_radar, latest)
    render_stress(ax_stress, latest_an, latest)
    render_aqi(ax_aqi, latest_an)
    render_timeline(ax_time, samples, analyses, events)
    render_filter(ax_filt, latest_an)
    render_story(ax_story, samples, analyses)

    # ---- Panel titles (single line, no subtitle clutter) ----
    titles = [
        (ax_aroma,  "Aroma Classification"),
        (ax_stress, "Cortisol Stress Gauge"),
        (ax_aqi,    "AQI Waterfall"),
        (ax_radar,  "Olfactory Radar"),
        (ax_time,   "Rolling Timeline"),
        (ax_filt,   "Filter Theatre"),
        (ax_story,  "Story Feed"),
    ]
    for ax, title in titles:
        bbox = ax.get_position()
        fig.text(bbox.x0, bbox.y1 + 0.012, title,
                 color=INK_0, fontsize=13, fontfamily=SERIF)

    # ---- Header: wordmark + tagline + session info, hairline below ----
    t0 = samples[0]["t"]; t1 = samples[-1]["t"]
    fig.text(0.045, 0.948, "Auracle",
             color=INK_0, fontsize=34, fontfamily=SERIF, va="center")
    fig.text(0.045, 0.910,
             "Know the air. Shape your aura.",
             color=INK_1, fontsize=11, va="center")
    fig.text(0.965, 0.948,
             f"{t0.strftime('%Y-%m-%d')}  ·  {t0.strftime('%H:%M:%S')} → {t1.strftime('%H:%M:%S')}",
             color=INK_1, fontsize=11, ha="right", va="center")
    fig.text(0.965, 0.910,
             f"{len(samples)} samples  ·  cage rig telemetry",
             color=INK_2, fontsize=10, ha="right", va="center")
    fig.add_artist(plt.Line2D([0.045, 0.965], [0.885, 0.885],
                              color=LINE, linewidth=0.5, transform=fig.transFigure))

    fig.savefig(out, dpi=160, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out}")


def render_session_report(samples, analyses, events, out):
    fig = plt.figure(figsize=(15, 12), facecolor=BG_0)
    gs = fig.add_gridspec(3, 2, hspace=0.75, wspace=0.30,
                          left=0.055, right=0.955, top=0.85, bottom=0.05)

    times = [s["t"] for s in samples]
    nh3 = [s["NH3"] for s in samples]
    co  = [s["CO"]  for s in samples]
    voc = [s["VOC"] for s in samples]
    stress = [a["stress_score"] for a in analyses]
    aqi    = [a["aqi"] for a in analyses]
    filt   = [a["filter_active"] for a in analyses]

    # 1. sensor traces
    ax = fig.add_subplot(gs[0, :]); style_axes(ax)
    ax.plot(times, nh3, color=HOT,    lw=1.6, marker="o", markersize=5, label="NH₃")
    ax.plot(times, co,  color=WARM,   lw=1.6, marker="o", markersize=5, label="CO")
    ax.plot(times, voc, color=VIOLET, lw=1.6, marker="o", markersize=5, label="VOC")
    # event markers
    em = {"LED":             (WARM,   "^", "LED"),
          "Speaker":         (COOL,   "v", "tone"),
          "LCD1":            (VIOLET, "s", "image"),
          "PelletDispenser": (ACCENT, "D", "pellet"),
          "BeamBreaker":     (INK_1,  "x", "beam")}
    plotted = set()
    ymax = max(max(nh3), max(co), max(voc)) * 1.12
    for kind, evs in events.items():
        st = em.get(kind, (INK_1, "o", kind))
        for e in evs:
            ax.plot([e["t"]], [ymax * 0.95], st[1], color=st[0],
                    markersize=9, markeredgecolor=BG_0, markeredgewidth=1,
                    label=st[2] if kind not in plotted else None)
            plotted.add(kind)
    ax.set_ylim(0, ymax)
    leg = ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10),
                    facecolor=BG_0, edgecolor="none", frameon=False,
                    labelcolor=INK_1, fontsize=9, ncol=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    # (header text drawn below)

    # 2. stress + AQI
    ax2 = fig.add_subplot(gs[1, 0]); style_axes(ax2)
    ax2.plot(times, stress, color=ACCENT, lw=2, marker="o", markersize=5)
    ax2.axhline(3, color=WARN, linestyle="--", lw=0.8, alpha=0.6, label="moderate≥3")
    ax2.axhline(5, color=BAD,  linestyle="--", lw=0.8, alpha=0.6, label="high≥5")
    ax2.set_ylim(0, 7.3); ax2.set_ylabel("stress score")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax2.legend(loc="upper right", facecolor=BG_1, edgecolor=LINE, labelcolor=INK_1, fontsize=8)
    # (subtitle drawn below)

    ax3 = fig.add_subplot(gs[1, 1]); style_axes(ax3)
    bottom = np.zeros(len(times))
    palette = {"CO2": WARM, "NO": HOT, "NO2": VIOLET, "VOC": ACCENT}
    width = 0.0001 if len(times) < 2 else (mdates.date2num(times[-1]) - mdates.date2num(times[0])) / max(len(times), 1)
    for k in ("CO2", "NO", "NO2", "VOC"):
        vals = np.array([a["penalties"][k] for a in analyses])
        ax3.bar(times, vals, bottom=bottom, color=palette[k], width=width,
                label=COMPOUNDS[k]["label"], edgecolor="none")
        bottom += vals
    ax3.set_ylabel("AQI penalty (out of 10)")
    ax3.set_ylim(0, 10.5)
    ax3.legend(loc="upper right", facecolor=BG_1, edgecolor=LINE, labelcolor=INK_1, fontsize=8)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    # (subtitle drawn below)

    # 3. radar
    ax4 = fig.add_subplot(gs[2, 0], projection="polar")
    ax4.set_facecolor(BG_1)
    angles = np.linspace(0, 2*np.pi, len(RADAR_KEYS), endpoint=False).tolist()
    angles_c = angles + angles[:1]
    means = [np.mean([s[k] for s in samples]) / COMPOUNDS[k]["bad"] for k in RADAR_KEYS]
    peaks = [np.max([s[k] for s in samples]) / COMPOUNDS[k]["bad"] for k in RADAR_KEYS]
    means_c = means + means[:1]; peaks_c = peaks + peaks[:1]
    ax4.plot(angles_c, peaks_c, color=HOT, lw=1.6, label="peak")
    ax4.fill(angles_c, peaks_c, color=HOT, alpha=0.10)
    ax4.plot(angles_c, means_c, color=ACCENT, lw=1.6, label="mean")
    ax4.fill(angles_c, means_c, color=ACCENT, alpha=0.20)
    ax4.set_thetagrids(np.degrees(angles), [COMPOUNDS[k]["label"] for k in RADAR_KEYS],
                       color=INK_1, fontsize=9)
    ax4.set_ylim(0, max(1.2, max(peaks) * 1.05))
    ax4.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax4.set_yticklabels(["", "warn", "", "bad"], color=INK_2, fontsize=7)
    ax4.tick_params(colors=INK_2)
    ax4.grid(color=LINE, linewidth=0.5)
    leg = ax4.legend(loc="upper right", facecolor=BG_1, edgecolor=LINE, labelcolor=INK_1,
                     fontsize=8, bbox_to_anchor=(1.25, 1.1))
    # (subtitle drawn below)

    # 4. summary stats panel
    ax5 = fig.add_subplot(gs[2, 1]); ax5.set_facecolor(BG_1)
    ax5.set_xlim(0, 1); ax5.set_ylim(0, 1); ax5.axis("off")
    n_events = sum(len(v) for v in events.values())
    stats = [
        ("frames",                    f"{len(samples)} Scentience samples"),
        ("session length",            f"{(samples[-1]['t']-samples[0]['t']).total_seconds():.0f}s"),
        ("mean AQI",                  f"{np.mean(aqi):.1f} / 10"),
        ("peak NH₃",                  f"{max(nh3):.0f}"),
        ("peak CO",                   f"{max(co):.0f}"),
        ("peak VOC",                  f"{max(voc):.0f}"),
        ("filter-active fraction",    f"{100*sum(filt)/len(filt):.0f}%"),
        ("cage events",               f"{n_events} ({sum(len(v) for k,v in events.items() if v)} kinds)"),
        ("temperature",               f"{np.mean([s['ENV_temperatureC'] for s in samples]):.1f}°C"),
        ("humidity",                  f"{np.mean([s['ENV_humidity'] for s in samples]):.0f}%"),
    ]
    for i, (k, v) in enumerate(stats):
        y = 0.93 - i * 0.085
        ax5.text(0.04, y, k, color=INK_2, fontsize=10, style="italic",
                 transform=ax5.transAxes)
        ax5.text(0.96, y, v, color=INK_0, fontsize=11, ha="right",
                 fontfamily=SANS, fontweight=500, transform=ax5.transAxes)

    # ---- Header: wordmark + tagline + session info ----
    fig.text(0.055, 0.945, "Auracle",
             color=INK_0, fontsize=32, fontfamily=SERIF, va="center")
    fig.text(0.055, 0.905, "Session report",
             color=INK_1, fontsize=11, va="center")
    fig.text(0.955, 0.945,
        f"{samples[0]['t'].strftime('%Y-%m-%d')}  ·  "
        f"{samples[0]['t'].strftime('%H:%M:%S')} → {samples[-1]['t'].strftime('%H:%M:%S')}",
        color=INK_1, fontsize=11, ha="right", va="center")
    fig.text(0.955, 0.905, "cage rig telemetry",
             color=INK_2, fontsize=10, ha="right", va="center")
    fig.add_artist(plt.Line2D([0.055, 0.955], [0.880, 0.880],
                              color=LINE, linewidth=0.5, transform=fig.transFigure))

    # ---- Subplot titles (clean, single-line) ----
    fig.text(0.055, 0.853, "Sensor traces with cage events",
             color=INK_0, fontsize=12, fontfamily=SERIF)
    fig.text(0.055, 0.555, "Stress score (max 7)",
             color=INK_0, fontsize=12, fontfamily=SERIF)
    fig.text(0.515, 0.555, "AQI penalty composition",
             color=INK_0, fontsize=12, fontfamily=SERIF)
    fig.text(0.055, 0.260, "Mean vs peak across session",
             color=INK_0, fontsize=12, fontfamily=SERIF)
    fig.text(0.515, 0.260, "Session summary",
             color=INK_0, fontsize=12, fontfamily=SERIF)

    fig.savefig(out, dpi=160, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out}")


def render_experiment_overlay(samples, analyses, events, out):
    """Single zoomed timeline showing the stimulus → gas response pattern."""
    fig, ax = plt.subplots(figsize=(15, 7), facecolor=BG_0)
    fig.subplots_adjust(left=0.06, right=0.96, top=0.78, bottom=0.10)
    style_axes(ax)
    times = [s["t"] for s in samples]
    nh3 = [s["NH3"] for s in samples]
    co  = [s["CO"]  for s in samples]
    voc = [s["VOC"] for s in samples]

    ax.plot(times, nh3, color=HOT,    lw=2, marker="o", markersize=7, label="NH₃ max(A,B)")
    ax.plot(times, co,  color=WARM,   lw=2, marker="o", markersize=7, label="CO max(A,B)")
    ax.plot(times, voc, color=VIOLET, lw=2, marker="o", markersize=7, label="VOC (Σ organics)")

    ymax = max(max(nh3), max(co), max(voc)) * 1.18
    ax.set_ylim(0, ymax)

    # event lanes
    lanes = {"LED": ymax * 0.97, "Speaker": ymax * 0.92, "LCD1": ymax * 0.87,
             "PelletDispenser": ymax * 0.82, "BeamBreaker": ymax * 0.77}
    em = {"LED": (WARM, "L"), "Speaker": (COOL, "T"), "LCD1": (VIOLET, "I"),
          "PelletDispenser": (ACCENT, "P"), "BeamBreaker": (INK_1, "B")}
    plotted = set()
    for kind, evs in events.items():
        for e in evs:
            y = lanes.get(kind, ymax * 0.7)
            color, marker = em.get(kind, (INK_1, "•"))
            ax.axvline(e["t"], ymin=0, ymax=0.6, color=color, alpha=0.18, lw=1)
            ax.text(e["t"], y, marker, color=color, ha="center", va="center",
                    fontsize=12, fontweight="bold")
            label = e.get("kind", kind)
            if "freq_hz" in e: label = f"{e['freq_hz']/1000:.0f}kHz"
            if "image" in e:   label = f"img{e['image']}"
            if "duration_ms" in e and "freq_hz" not in e and "image" not in e:
                label = f"{e['duration_ms']}ms"
            ax.text(e["t"], y - ymax * 0.03, label,
                    color=color, ha="center", va="top", fontsize=7)
            plotted.add(kind)

    # annotate the spike
    spike_idx = int(np.argmax(co))
    if co[spike_idx] > min(co) * 5:
        ax.annotate(f"transient spike\nCO={co[spike_idx]:.0f}, VOC={voc[spike_idx]:.0f}",
                    xy=(times[spike_idx], co[spike_idx]),
                    xytext=(times[spike_idx], co[spike_idx] * 0.55),
                    color=INK_0, fontsize=10, ha="center",
                    arrowprops=dict(arrowstyle="->", color=INK_1, lw=1))

    ax.legend(loc="upper left", facecolor=BG_1, edgecolor=LINE, labelcolor=INK_1, fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax.set_ylabel("ppm-equivalent", color=INK_2)

    # ---- Header: wordmark + tagline ----
    fig.text(0.06, 0.935, "Auracle",
             color=INK_0, fontsize=32, fontfamily=SERIF, va="center")
    fig.text(0.06, 0.886,
             "Stimulus → olfactory response  ·  cage events overlaid on gas traces",
             color=INK_1, fontsize=11, va="center")
    fig.text(0.96, 0.935,
        f"{samples[0]['t'].strftime('%Y-%m-%d')}  ·  "
        f"{samples[0]['t'].strftime('%H:%M:%S')} → {samples[-1]['t'].strftime('%H:%M:%S')}",
        color=INK_1, fontsize=11, ha="right", va="center")
    fig.add_artist(plt.Line2D([0.06, 0.96], [0.855, 0.855],
                              color=LINE, linewidth=0.5, transform=fig.transFigure))

    fig.savefig(out, dpi=160, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out}")


# ---- main -------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session_dir")
    ap.add_argument("--out-dir", default="examples")
    args = ap.parse_args()

    sd = Path(args.session_dir)
    if not sd.exists():
        print(f"no such dir: {sd}", file=sys.stderr); sys.exit(1)

    samples = parse_scentience_dir(sd / "scentience")
    if not samples:
        print("no scentience samples", file=sys.stderr); sys.exit(1)
    analyses = [analyze(s) for s in samples]
    events = {
        "LED":             parse_event_dir(sd / "led",             "LED",             parse_led_body),
        "Speaker":         parse_event_dir(sd / "speaker",         "Speaker",         parse_speaker_body),
        "LCD1":            parse_event_dir(sd / "lcd1",            "LCD1",            parse_lcd_body),
        "PelletDispenser": parse_event_dir(sd / "pelletdispenser", "PelletDispenser", parse_simple_body),
        "BeamBreaker":     parse_event_dir(sd / "beambreaker",     "BeamBreaker",     parse_simple_body),
    }

    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    print(f"parsed {len(samples)} samples, {sum(len(v) for v in events.values())} cage events")
    render_dashboard_preview (samples, analyses, events, out / "dashboard_preview.png")
    render_session_report    (samples, analyses, events, out / "session_report.png")
    render_experiment_overlay(samples, analyses, events, out / "experiment_overlay.png")
    print(f"\ndone → {out.resolve()}")


if __name__ == "__main__":
    main()
