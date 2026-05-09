#!/usr/bin/env python3
"""
Auracle demo bridge — speaks the same WebSocket protocol as the real
`server/ovlm_bridge_server.py` but emits synthetic sensor data so you can
demo the dashboard end-to-end without the Scentience SDK, API key, or BLE
device.

Run:
    python viz/demo_bridge.py                  # ws://0.0.0.0:8765
    PORT=9000 python viz/demo_bridge.py        # custom port
    SCENARIO=meeting python viz/demo_bridge.py # pin one scenario

Pair with cloudflared for "live anywhere":
    ./viz/tunnel.sh
    # paste the printed https://*.trycloudflare.com into the Dashboard
    # → Source sheet on the deployed site.
"""

import asyncio
import json
import logging
import os
import random
import uuid
from datetime import datetime

import websockets

# ── config ──────────────────────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8765"))
TICK = float(os.getenv("TICK", "3"))
PIN_SCENARIO = os.getenv("SCENARIO")  # 'calm' | 'meeting' | 'commute' | 'workout' | None

# ── synthetic scenarios — match web/src/data/olm.js ─────────────────────────
def _j(mid, rng): return max(0.0, mid + (random.random() * 2 - 1) * rng)

SCENARIOS = {
    "calm": lambda: dict(
        NH3=_j(90, 30),  CO=_j(550, 200), VOC=_j(1200, 500),
        CO2=_j(480, 80), NO=_j(3, 3),     NO2=_j(3, 3),
        C2H5OH=_j(80, 60), H2=_j(140, 30), CH4=_j(380, 40),
        ENV_temperatureC=_j(22, 0.6), ENV_humidity=_j(45, 4),
        ENV_pressureHpa=_j(1013, 2), BATT_charge=88,
    ),
    "meeting": lambda: dict(
        NH3=_j(280, 70), CO=_j(950, 250), VOC=_j(2800, 600),
        CO2=_j(950, 200), NO=_j(5, 4),    NO2=_j(6, 4),
        C2H5OH=_j(120, 80), H2=_j(150, 30), CH4=_j(400, 40),
        ENV_temperatureC=_j(24, 0.4), ENV_humidity=_j(38, 3),
        ENV_pressureHpa=_j(1011, 2), BATT_charge=84,
    ),
    "commute": lambda: dict(
        NH3=_j(160, 50), CO=_j(1300, 400), VOC=_j(3300, 800),
        CO2=_j(700, 150), NO=_j(14, 6),   NO2=_j(16, 6),
        C2H5OH=_j(200, 100), H2=_j(160, 30), CH4=_j(420, 40),
        ENV_temperatureC=_j(20, 1.2), ENV_humidity=_j(60, 8),
        ENV_pressureHpa=_j(1009, 3), BATT_charge=80,
    ),
    "workout": lambda: dict(
        NH3=_j(220, 60), CO=_j(700, 300), VOC=_j(1800, 500),
        CO2=_j(600, 100), NO=_j(4, 3),    NO2=_j(4, 3),
        C2H5OH=_j(90, 60), H2=_j(180, 40), CH4=_j(410, 40),
        ENV_temperatureC=_j(23, 0.5), ENV_humidity=_j(55, 5),
        ENV_pressureHpa=_j(1012, 2), BATT_charge=82,
    ),
}


def pick_scenario():
    if PIN_SCENARIO and PIN_SCENARIO in SCENARIOS:
        return PIN_SCENARIO
    keys = list(SCENARIOS.keys())
    return keys[int(datetime.now().timestamp() / 30) % len(keys)]


# ── OLM math (matches the bridge + dashboard) ───────────────────────────────
def score_nh3(v):  return 3 if v > 250 else 2 if v > 150 else 1 if v > 100 else 0
def score_co(v):   return 2 if v > 1000 else 1 if v > 500 else 0
def score_voc(v):  return 2 if v > 3000 else 1 if v > 2000 else 0
def penalty_co2(v):return 3 if v > 1000 else 2 if v > 800 else 1 if v > 600 else 0
def penalty_no(v): return 2 if v > 15 else 1 if v > 10 else 0
def penalty_no2(v):return 2 if v > 15 else 1 if v > 10 else 0
def penalty_voc(v):return 3 if v > 3000 else 2 if v > 2000 else 1 if v > 1000 else 0


def build_message(sensors):
    nh3, co, voc = sensors["NH3"], sensors["CO"], sensors["VOC"]
    co2, no, no2 = sensors["CO2"], sensors["NO"], sensors["NO2"]

    stress = score_nh3(nh3) + score_co(co) + score_voc(voc)
    aqi = max(0, 10 - penalty_co2(co2) - penalty_no(no) - penalty_no2(no2) - penalty_voc(voc))
    level = "high" if stress >= 5 else "moderate" if stress >= 3 else "low"
    quality = ("excellent" if aqi >= 8 else "good" if aqi >= 6
               else "moderate" if aqi >= 4 else "poor")
    conf = min(stress * 0.15, 0.95)
    filtration = aqi < 6 or level != "low"

    ts = datetime.now()
    summary = (
        f"{ts.strftime('%H:%M')} · {sensors['ENV_temperatureC']:.1f}°C, "
        f"{sensors['ENV_humidity']:.0f}% RH. "
        + (f"Elevated stress markers (~{nh3*0.05:.1f} ng/m³, {int(conf*100)}% conf)."
           if level == "high"
           else f"Moderate stress ({int(conf*100)}% conf)." if level == "moderate"
           else "Stress normal.")
        + (f" Air {quality} (AQI {aqi}/10).")
        + (" Stress-response filtration, 30 min." if level == "high"
           else " Standard purification, 15 min." if filtration else "")
    )

    return {
        "type": "olm_analysis",
        "analysis_id": str(uuid.uuid4()),
        "timestamp": ts.isoformat(),
        "natural_language_summary": summary,
        "sensors": sensors,                # ← raw sensor record so all panels populate
        "device_actions": {
            "activate_filter":  filtration,
            "filter_mode":      "stress_reduction" if level == "high" else "standard",
            "duration_minutes": 30 if level == "high" else 15,
            "alert_level":      stress,
            "fan_speed":        85 if level == "high" else 65,
        },
        "raw_metrics": {
            "stress_confidence": conf,
            "air_quality_score": aqi,
            "cortisol_estimate": f"{nh3*0.05:.1f} ng/m³",
        },
    }


# ── server ──────────────────────────────────────────────────────────────────
clients = set()


async def handle_client(ws):
    clients.add(ws)
    logging.info("client connected; total=%d", len(clients))
    try:
        await ws.send(json.dumps({
            "type": "connection_established",
            "message": "🎉 Demo bridge ready (synthetic sensor data).",
            "timestamp": datetime.now().isoformat(),
            "server_status": "ready",
        }))
        async for _ in ws:
            pass  # ignore client messages; we always stream
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(ws)
        logging.info("client disconnected; total=%d", len(clients))


async def streaming_loop():
    while True:
        if clients:
            sensors = SCENARIOS[pick_scenario()]()
            msg = json.dumps(build_message(sensors))
            stale = set()
            for c in clients:
                try:
                    await c.send(msg)
                except Exception:
                    stale.add(c)
            for c in stale:
                clients.discard(c)
        await asyncio.sleep(TICK)


async def main():
    asyncio.create_task(streaming_loop())
    async with websockets.serve(handle_client, HOST, PORT):
        logging.info("demo bridge ready on ws://%s:%d  (scenario=%s, tick=%.1fs)",
                     HOST, PORT, PIN_SCENARIO or "auto", TICK)
        await asyncio.Future()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
