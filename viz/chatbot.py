#!/usr/bin/env python3
"""
Auracle OLM chatbot.

Sits between the bridge (ws://localhost:8765) and the dashboard chat panel
(ws://localhost:8766 by default). Lets you interrogate the live data and run
the real COLIP model on whatever the bridge is broadcasting.

Commands (from the dashboard panel or `--cli` mode):

    status               is the data real, live, and where is it coming from?
    smell                run COLIP top-3 on the current sample
    match <description>  cosine similarity vs a free-form smell description
    raw                  dump the latest bridge message (JSON)

Run:
    python viz/chatbot.py            # WebSocket server on :8766
    python viz/chatbot.py --cli      # also drop into a terminal prompt

Optional dependencies (for real model inference):
    pip install torch transformers Pillow torchvision scentience

Without those, the chatbot still runs and answers `status` and `raw`, and
explains why model inference isn't available. So `status` always works — it's
the honest data-source diagnostic.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

import websockets

# ── Optional model deps ─────────────────────────────────────────────────────
try:
    import torch
    from PIL import Image
    from torchvision import transforms
    from scentience.models import ColipModel
    from transformers import CLIPTokenizer
    OLM_AVAILABLE = True
    OLM_LOAD_ERROR = None
except ImportError as e:
    OLM_AVAILABLE = False
    OLM_LOAD_ERROR = f"missing dependency: {e}"
    torch = None
    transforms = None

# ── Config ──────────────────────────────────────────────────────────────────
BRIDGE_URL = os.getenv("BRIDGE_URL", "ws://localhost:8765")
CHAT_HOST  = os.getenv("CHAT_HOST", "0.0.0.0")
CHAT_PORT  = int(os.getenv("CHAT_PORT", "8766"))

# ── COLIP config — must match demo.py exactly ───────────────────────────────
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

SENSOR_KEYS = [
    "CO2", "NH3_A", "NH3_B", "NO_A", "NO_B", "NO2_A", "NO2_B",
    "CO_A", "CO_B", "H2_A", "H2_B", "CH4_A", "CH4_B",
    "C2H5OH_A", "C2H5OH_B", "C3H8_A", "C3H8_B", "C4H10_A", "C4H10_B",
    "ENV_temperatureC", "ENV_humidity", "ENV_pressureHpa",
]
SENSOR_MAX = {
    "CO2": 5000.0, "NH3_A": 500.0, "NH3_B": 500.0, "NO_A": 100.0, "NO_B": 100.0,
    "NO2_A": 100.0, "NO2_B": 100.0, "CO_A": 2000.0, "CO_B": 2000.0,
    "H2_A": 1000.0, "H2_B": 1000.0, "CH4_A": 10000.0, "CH4_B": 10000.0,
    "C2H5OH_A": 1000.0, "C2H5OH_B": 1000.0, "C3H8_A": 5000.0, "C3H8_B": 5000.0,
    "C4H10_A": 5000.0, "C4H10_B": 5000.0,
    "ENV_temperatureC": 60.0, "ENV_humidity": 100.0, "ENV_pressureHpa": 1100.0,
}
OLF_DIM = 112


def make_olf_vec(data):
    vec = []
    for k in SENSOR_KEYS:
        val = float(data.get(k, 0.0) or 0.0)
        vec.append(min(max(val / SENSOR_MAX.get(k, 1.0), 0.0), 1.0))
    vec += [0.0] * (OLF_DIM - len(vec))
    return vec[:OLF_DIM]


# ── State ───────────────────────────────────────────────────────────────────
class State:
    def __init__(self):
        self.bridge_connected = False
        self.last_message = None
        self.last_received_at = None
        self.bridge_url = BRIDGE_URL
        self.olm_loaded = False
        self.olm_error = OLM_LOAD_ERROR
        # COLIP
        self.model = None
        self.tokenizer = None
        self.anchor_feats = None
        self.transform = None
        self.lock = asyncio.Lock()


state = State()
chat_clients = set()


def diagnostic_blob():
    age = None
    if state.last_received_at:
        age = (datetime.now() - state.last_received_at).total_seconds()
    msg = state.last_message or {}
    return {
        "bridge_connected":    state.bridge_connected,
        "bridge_url":          state.bridge_url,
        "last_sample_age_s":   age,
        "sensors_in_broadcast": bool(msg.get("sensors")),
        "olm_loaded":          state.olm_loaded,
        "olm_available":       OLM_AVAILABLE,
        "olm_error":           state.olm_error,
        "last_message_type":   msg.get("type"),
    }


# ── COLIP loader ────────────────────────────────────────────────────────────
async def load_olm():
    """Load COLIP lazily on first inference call. Returns True on success."""
    if state.olm_loaded:
        return True
    if not OLM_AVAILABLE:
        return False
    async with state.lock:
        if state.olm_loaded:
            return True
        try:
            logging.info("Loading COLIP (colip-small-base)...")
            model = ColipModel.from_pretrained("colip-small-base", device="cpu")
            model._clip.eval()
            model._olf_encoder.eval()
            model._gnn.eval()
            tokenizer = CLIPTokenizer.from_pretrained("openai/clip-vit-base-patch32")

            descriptions = [a[1] for a in AROMA_ANCHORS]
            tokens = tokenizer(descriptions, padding=True, return_tensors="pt")
            with torch.no_grad():
                out = model._clip.get_text_features(**tokens)
                feats = out.pooler_output if hasattr(out, "pooler_output") else out
                feats = feats / feats.norm(dim=-1, keepdim=True)

            state.model = model
            state.tokenizer = tokenizer
            state.anchor_feats = feats
            state.transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
            ])
            state.olm_loaded = True
            state.olm_error = None
            logging.info("COLIP ready.")
            return True
        except Exception as exc:
            state.olm_error = str(exc)
            logging.error("COLIP load failed: %s", exc)
            return False


# ── Inference helpers ───────────────────────────────────────────────────────
def _embed_sensors(sensors):
    blank = Image.new("RGB", (224, 224), (128, 128, 128))
    img = state.transform(blank).unsqueeze(0)
    olf = torch.tensor([make_olf_vec(sensors)], dtype=torch.float32)
    with torch.no_grad():
        v = state.model._clip.get_image_features(pixel_values=img)
        v = v.pooler_output if hasattr(v, "pooler_output") else v
        if state.model._vision_proj is not None:
            v = state.model._vision_proj(v)
        o = state.model._olf_encoder(olf)
        emb = state.model._gnn(v, o).squeeze()
        emb = emb / emb.norm()
    return emb


def _embed_text(text):
    tokens = state.tokenizer([text], padding=True, return_tensors="pt")
    with torch.no_grad():
        out = state.model._clip.get_text_features(**tokens)
        feats = out.pooler_output if hasattr(out, "pooler_output") else out
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats[0]


# ── Bridge subscriber ───────────────────────────────────────────────────────
async def bridge_subscriber():
    backoff = 1
    while True:
        try:
            logging.info("Connecting to bridge at %s ...", state.bridge_url)
            async with websockets.connect(state.bridge_url) as ws:
                state.bridge_connected = True
                logging.info("Connected to bridge.")
                backoff = 1
                await ws.send(json.dumps({"type": "start_streaming"}))
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("type") in ("ovlm_analysis", "olm_analysis"):
                        state.last_message = msg
                        state.last_received_at = datetime.now()
        except Exception as exc:
            state.bridge_connected = False
            logging.warning("Bridge connection lost: %s — retry in %ds", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)


# ── Chat router ─────────────────────────────────────────────────────────────
async def answer(text: str) -> dict:
    text = (text or "").strip()
    lower = text.lower()
    msg = state.last_message
    sensors = (msg or {}).get("sensors")
    age = None
    if state.last_received_at:
        age = (datetime.now() - state.last_received_at).total_seconds()

    # ── status (the headline diagnostic) ────────────────────────────────────
    if lower in ("status", "diagnostic", "is this real", "is the data real",
                 "real?", "live?", "is it live", "is data live", "what's going on"):
        lines = []
        if not state.bridge_connected:
            lines.append("🔴 Bridge OFFLINE — no live data is flowing.")
            lines.append(f"Tried {state.bridge_url}.")
            lines.append("Start it with: python server/ovlm_bridge_server.py")
            lines.append("(After: bluetoothctl connect <SCENTIENCE_DEVICE_ADDRESS>)")
        elif age is None:
            lines.append("🟡 Bridge connected, but no analysis frames received yet.")
        else:
            lines.append(f"🟢 Bridge LIVE — last sample {age:.1f}s ago.")
            if sensors:
                lines.append(f"Raw sensor record IS in the broadcast ({len(sensors)} fields). "
                             "Radar/timeline/AQI panels are reflecting real device readings.")
            else:
                lines.append("⚠ Raw sensors NOT in the broadcast.")
                lines.append("→ stress/AQI numbers are real (rule-based on the bridge side).")
                lines.append("→ radar/timeline are reconstructed from raw_metrics (synthesized fallback).")
                lines.append("Patch: add `\"sensors\": sensor_data` to the message in "
                             "process_sensor_sample() to fix.")
        if state.olm_loaded:
            lines.append("OLM (COLIP) loaded — try `smell` or `does it smell like X` to run live inference.")
        elif OLM_AVAILABLE:
            lines.append("OLM dependencies present — first inference call will load COLIP.")
        else:
            lines.append(f"OLM unavailable: {state.olm_error}. Diagnostic-only mode.")
            lines.append("Install: pip install torch transformers Pillow torchvision scentience")
        return {"text": "\n".join(lines)}

    # ── raw dump ─────────────────────────────────────────────────────────────
    if lower in ("raw", "show raw", "dump", "sample", "show sample", "json"):
        if not msg:
            return {"text": "No samples received yet. Try `status`."}
        return {"text": "```json\n" + json.dumps(msg, indent=2) + "\n```"}

    # ── smell / classify ─────────────────────────────────────────────────────
    if lower in ("smell", "what", "what is this", "what does it smell like",
                 "classify", "what am i smelling", "what am i breathing"):
        if not await load_olm():
            return {"text": (
                f"Cannot run COLIP: {state.olm_error}\n"
                "Install:  pip install torch transformers Pillow torchvision scentience"
            )}
        if not sensors:
            return {"text": "No raw sensors in the bridge broadcast — cannot run COLIP. "
                            "Run `status` for the patch instructions."}
        emb = _embed_sensors(sensors)
        sims = (emb @ state.anchor_feats.T).tolist()
        ranked = sorted(zip(sims,
                            [a[0] for a in AROMA_ANCHORS],
                            [a[2] for a in AROMA_ANCHORS]),
                        reverse=True)
        lines = ["🌫 COLIP top-3 on the live sample:"]
        for i, (s, lbl, flt) in enumerate(ranked[:3]):
            mark = "▶" if i == 0 else " "
            lines.append(f"  {mark} {lbl:<22} {s:.4f}  {'⚠ filter' if flt else 'ok'}")
        return {
            "text": "\n".join(lines),
            "ranked": [{"label": l, "score": round(s, 4), "filter": f}
                       for s, l, f in ranked],
        }

    # ── free-form match ──────────────────────────────────────────────────────
    target = None
    if lower.startswith("match "):
        target = text[6:].strip()
    elif "smell like" in lower:
        target = text.split("smell like", 1)[1].strip(" ?.")
    elif "smell of" in lower:
        target = text.split("smell of", 1)[1].strip(" ?.")
    if target:
        if not await load_olm():
            return {"text": f"Cannot run COLIP: {state.olm_error}"}
        if not sensors:
            return {"text": "No raw sensors — cannot match. Run `status`."}
        emb = _embed_sensors(sensors)
        text_emb = _embed_text(target)
        sim = float((emb @ text_emb).item())
        verdict = "strong" if sim > 0.30 else "moderate" if sim > 0.25 else "weak"
        return {"text": f"💬 cos(\"{target}\", live sample) = {sim:.4f}  →  {verdict} match",
                "match": {"target": target, "score": round(sim, 4), "verdict": verdict}}

    # ── help / fallthrough ───────────────────────────────────────────────────
    return {"text": (
        "Commands:\n"
        "  status         — is the data real and live?\n"
        "  smell          — run COLIP top-3 on the current sample\n"
        "  match <text>   — cosine similarity vs a free-form description\n"
        "  raw            — dump the latest bridge message\n"
        "Or just describe a smell ('does this smell like rain?') and I'll match."
    )}


# ── Chat WebSocket server ───────────────────────────────────────────────────
async def chat_handler(websocket):
    chat_clients.add(websocket)
    try:
        await websocket.send(json.dumps({
            "type": "system",
            "text": ("OLM chatbot ready. Ask `status` to verify the data source, "
                     "`smell` to run COLIP on the live sample."),
            "diagnostic": diagnostic_blob(),
        }))
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") != "chat":
                continue
            reply = await answer(msg.get("text", ""))
            reply["type"] = "chat_reply"
            reply["diagnostic"] = diagnostic_blob()
            await websocket.send(json.dumps(reply))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        chat_clients.discard(websocket)


# ── CLI mode ────────────────────────────────────────────────────────────────
async def cli_loop():
    print("Auracle OLM chatbot — terminal mode. Type `quit` to exit.")
    print("Try: status, smell, does this smell like coffee?, raw")
    loop = asyncio.get_event_loop()
    while True:
        try:
            text = await loop.run_in_executor(None, input, "> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        text = text.strip()
        if text in ("quit", "exit"):
            return
        if not text:
            continue
        reply = await answer(text)
        print(reply["text"])
        print()


# ── Entry point ─────────────────────────────────────────────────────────────
async def main(cli: bool):
    asyncio.create_task(bridge_subscriber())
    server = await websockets.serve(chat_handler, CHAT_HOST, CHAT_PORT)
    logging.info("OLM chatbot ready at ws://%s:%d  (bridge: %s)",
                 CHAT_HOST, CHAT_PORT, BRIDGE_URL)
    if OLM_AVAILABLE:
        logging.info("OLM dependencies present. COLIP loads on first inference call.")
    else:
        logging.info("OLM unavailable: %s. Diagnostic-only mode.", OLM_LOAD_ERROR)

    if cli:
        await cli_loop()
        server.close()
        await server.wait_closed()
    else:
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    p = argparse.ArgumentParser(description="Auracle OLM chatbot")
    p.add_argument("--cli", action="store_true",
                   help="also drop into a terminal prompt after starting the server")
    args = p.parse_args()
    try:
        asyncio.run(main(args.cli))
    except KeyboardInterrupt:
        pass
