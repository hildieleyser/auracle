# Auracle visualizations

Brand-aligned, didactic data visualizations for the OLM bridge stream.
Designed to drop into the iOS app via WebView, and to render offline reports
from recorded sessions or cage-rig logs.

```
viz/
  dashboard.html              live single-file SVG/Canvas dashboard (no build step)
  chatbot.py                  OLM chat sidecar — runs COLIP, answers `status` honestly
  render_examples.py          renders branded PNG previews from a cage-rig session
  analytics.py                records bridge sessions to JSONL, renders matplotlib reports
  examples/                   PNG outputs (gitignored)
  integration/
    VizView.swift             SwiftUI / WKWebView wrapper for the iOS app
    AuracleTheme.swift        brand color + typography tokens for the SwiftUI screens
```

## What each panel teaches

The dashboard reads left-to-right, top-to-bottom and walks the user through
the OLM (Olfactory Language Model) pipeline:

| Panel              | Teaches                                                                       |
| ------------------ | ----------------------------------------------------------------------------- |
| Aroma Classification | the OLM (COLIP) ranks 10 aroma categories by cosine similarity; the top match drives the filter recommendation |
| Cortisol Gauge     | the rule-based stress score is built from threshold contributions — the math is visible  |
| AQI Waterfall      | air quality is `10 minus penalties`; each bar shows which gas cost which point |
| Olfactory Radar    | which gases the device watches and how today's reading sits vs baseline       |
| Rolling Timeline   | how stress / filter activation co-evolve with NH₃ / CO / VOC over minutes     |
| Filter Theatre     | what the wearable is physically doing right now (fan, LED, airflow)           |
| Story Feed         | the natural-language summary the bridge emits, with the numbers attached      |

Every panel has a `?` button that opens an explainer with formula + plain
description + a one-paragraph didactic note. Compound labels on the radar
and the contribution bars are clickable and open per-compound explainers.

## Brand tokens

Both `dashboard.html` and `render_examples.py` (and `AuracleTheme.swift`)
share one palette:

| Token        | Hex       | Use                                       |
| ------------ | --------- | ----------------------------------------- |
| `bg-0`       | `#efede8` | page — soft cool cream                    |
| `bg-1`       | `#f5f3ee` | lifted card                               |
| `bg-2`       | `#e6e3dc` | sunken / track                            |
| `line`       | `#d5d2c9` | subtle hairline                           |
| `ink-0`      | `#0f0f0f` | primary near-black                        |
| `ink-1`      | `#3a3a3a` | secondary                                 |
| `ink-2`      | `#8a8780` | muted                                     |
| `accent`     | `#0f0f0f` | near-black (matches wordmark)             |
| `warm`       | `#a86d50` | terracotta                                |
| `hot`        | `#9c3344` | brick (high stress / alerts)              |
| `cool`       | `#5a6a82` | muted slate                               |
| `violet`     | `#6b5b95` | dusty violet                              |
| `good`       | `#5a7848` | sage (excellent AQI, low stress)          |

Wordmark is mixed-case "Auracle" (not all-caps). Tagline:
*Know the air. Shape your aura.*

Type: `Fraunces` for the wordmark + panel titles, `Inter` for body and
numerics. Both are open-source and self-host cleanly.

## Run the dashboard standalone

```bash
cd viz
python3 -m http.server 8000
# open http://localhost:8000/dashboard.html
```

Without the bridge running, the dashboard auto-falls-back to demo mode and
cycles through four scenarios (calm office, stressful meeting, polluted
commute, post-workout). Pick one from the dropdown to study the system's
response to that specific condition.

With the bridge running (`python server/ovlm_bridge_server.py`), the dashboard
connects to `ws://localhost:8765` and shows live data.

URL params:

* `?ws=ws://other.host:8765` override the WebSocket endpoint

## Render previews from a cage-rig session

`render_examples.py` parses a Netholabs rig log directory (Scentience samples
+ beam breaker / LED / speaker / pellet dispenser / LCD events) and produces
three PNGs styled to the brand:

```bash
# create a venv with matplotlib + numpy if you don't have one
python3 -m venv /tmp/auracle_viz
/tmp/auracle_viz/bin/pip install matplotlib numpy

# render
/tmp/auracle_viz/bin/python viz/render_examples.py \
    "/path/to/5.01.001_all_<timestamp>" \
    --out-dir viz/examples
```

Outputs:

* `dashboard_preview.png` — mockup of the live dashboard with this data
* `session_report.png`    — multi-panel matplotlib report
* `experiment_overlay.png` — zoomed timeline with cage events overlaid on the
  gas response (best for showing stimulus → olfactory signature)

The rig-log → dashboard mapping collapses A/B sensors with `max(A, B)` and
synthesizes `VOC = Σ (C₂H₅OH + H₂ + CH₄ + C₃H₈ + C₄H₁₀)`.

## Demo bridge — green Live pill without hardware

`viz/demo_bridge.py` speaks the same WebSocket protocol as the real bridge
but emits synthetic sensor data, so you can demo the dashboard end-to-end
without the Scentience SDK, API key, or BLE device.

```bash
python viz/demo_bridge.py                  # ws://0.0.0.0:8765
SCENARIO=meeting python viz/demo_bridge.py # pin one scenario
TICK=1 python viz/demo_bridge.py           # faster cadence
```

Pair with the tunnel to drive the deployed Pages site from anywhere.

## Live data anywhere — Cloudflare quick tunnel

The deployed dashboard at `https://hildieleyser.github.io/auracle/` is HTTPS,
so it cannot connect to a plain `ws://localhost:8765` bridge from a remote
device (browsers block mixed content). The way to make it work anywhere is
to expose the bridge through a tunnel.

```bash
brew install cloudflared            # one-time

# terminal 1 — start the bridge
python server/ovlm_bridge_server.py

# terminal 2 — open a free tunnel
./viz/tunnel.sh
# → https://goofy-otter-1234.trycloudflare.com
```

Copy the printed URL, open the deployed Auracle site, tap the **status row**
on the Dashboard tab to open the *Source* sheet, paste the URL, and hit
*Connect this source*. The dashboard rewrites `https://` → `wss://`
automatically and saves it on the device for next time.

* The `?ws=` query parameter still works for sharing pre-configured links
  (e.g. `https://hildieleyser.github.io/auracle/?ws=wss://goofy-otter-1234.trycloudflare.com`).
* Saved sources persist in `localStorage`. Tap *Clear saved source* in the
  sheet to reset.
* Cloudflare quick tunnels are free, require no signup, and last as long as
  the `cloudflared` process runs.

## OLM chatbot — verify the data is real

`chatbot.py` is a sidecar service that subscribes to the bridge and runs the
real **COLIP** model locally so you can interrogate the live data. It serves
a chat WebSocket on `ws://localhost:8766` that the dashboard's floating chat
panel auto-connects to.

```bash
# in another terminal (after the bridge is running)
python viz/chatbot.py            # WebSocket on :8766
python viz/chatbot.py --cli      # also drop into a terminal prompt
```

Optional model dependencies (without these the chatbot still runs and
answers `status` and `raw` honestly — it just refuses inference):

```bash
pip install torch transformers Pillow torchvision scentience
```

### Commands

| Command         | What it does                                                            |
| --------------- | ----------------------------------------------------------------------- |
| `status`        | reports bridge connection, last-sample age, whether raw `sensors` are in the broadcast, and whether COLIP is loaded — the honest data-source diagnostic |
| `smell`         | runs COLIP on the live sample and prints top-3 anchor matches           |
| `match <text>`  | cosine similarity between the live sample and a free-form description (e.g. `match coffee`, `match wet basement`) |
| `raw`           | dumps the latest bridge message as JSON                                 |

You can also just describe a smell — `does this smell like rain?` — and the
chatbot will pull the description and run a CLIP-text vs olfactory cosine.

### Dashboard chat panel

The chat panel is the floating "A" button in the dashboard's bottom-right.
Open it, type `status`, and the answer tells you exactly where the numbers
on screen are coming from:

* 🟢 *bridge LIVE — last sample 2.1s ago. Raw sensors present.* → all panels are real.
* 🟡 *bridge LIVE — sensors NOT in broadcast.* → stress/AQI are real, radar/timeline use the raw_metrics fallback.
* 🔵 *demo mode.* → values are synthesized client-side; nothing is hitting BLE.
* 🔴 *bridge offline.* → start `server/ovlm_bridge_server.py` first.

If the chatbot service is offline, the panel still answers `status` and
`raw` from the dashboard's local view of the bridge — so it never lies to
you about whether the data is real.

## Embed in the iOS app

1. Drag `viz/dashboard.html` into the Xcode project's *Copy Bundle Resources*.
2. Add `viz/integration/VizView.swift` and `viz/integration/AuracleTheme.swift`.
3. Add the Fraunces + Inter `.ttf` files and register them under `UIAppFonts`
   in `Info.plist`.
4. Add a tab in `ContentView`:

```swift
TabView {
    existingScrollView
        .tabItem { Label("Live", systemImage: "waveform") }
    VizView(source: .bundled)
        .tabItem { Label("Visualize", systemImage: "chart.xyaxis.line") }
}
```

For hackathon iteration, use `.hosted` and run `python3 -m http.server 8000`
from the `viz/` directory on your laptop. Update `HOST_IP` in `VizView.swift`
to your LAN IP.

To bring the rest of the SwiftUI screens in line with the brand, replace
hard-coded colors and fonts in `NoseFilterApp.swift` with the tokens in
`AuracleTheme.swift` (e.g. `Auracle.Color.ink`, `Auracle.Font.title()`).

## Offline session analytics

Record a live session and produce a multi-panel report:

```bash
pip install matplotlib numpy websockets

# 1. record (while the bridge is streaming)
python viz/analytics.py record --ws ws://localhost:8765 \
    --out session.jsonl --seconds 600

# 2. render
python viz/analytics.py report session.jsonl --out-dir reports/
# writes reports/session_report.png + reports/story.txt
# prints a one-line summary (mean AQI, peak NH3, % time filter active, ...)
```

The Python re-uses the exact same threshold logic the bridge runs, so
report figures and live dashboard agree.

## Bridge → dashboard contract

The dashboard accepts the analysis frame from `server/ovlm_bridge_server.py`
(the file name is upstream-owned; the model running inside it is COLIP — a
CLIP-aligned olfactory encoder that runs in olfaction-only mode for this
device, so we refer to it as the *OLM* in the UI):

```json
{
  "type": "olm_analysis",
  "timestamp": "...",
  "natural_language_summary": "...",
  "device_actions": { "activate_filter": true, "filter_mode": "stress_reduction",
                      "duration_minutes": 30, "alert_level": 5, "fan_speed": 85 },
  "raw_metrics": { "stress_confidence": 0.6, "air_quality_score": 5,
                   "cortisol_estimate": "14.0 ng/m³" }
}
```

If the frame additionally includes a `sensors` field with the raw Scentience
record (`NH3`, `CO`, `VOC`, `CO2`, `NO`, `NO2`, `C2H5OH`, `H2`, `CH4`,
`ENV_temperatureC`, `ENV_humidity`), the radar / timeline / waterfall use it
directly. Otherwise the dashboard fabricates a plausible record from
`raw_metrics` so the panels are never blank — clearly a fallback; the
natural-language summary remains authoritative.

If the frame includes an `aroma` field with the COLIP top-N rankings (shape
shown below), the **Aroma Classification** panel uses it directly. Otherwise
that panel falls back to a rule-based stand-in that mirrors `demo.py`'s
anchor list, so the dashboard remains useful before the bridge starts
emitting model output.

```json
"aroma": {
  "top": [
    {"label": "Urban pollution",  "score": 0.314, "filter_recommended": true},
    {"label": "Industrial / chemical", "score": 0.296, "filter_recommended": true},
    ...
  ],
  "filter_recommended": true
}
```

To get the richest visualization, extend `process_sensor_sample` in
`server/ovlm_bridge_server.py` to include the raw `sensor_data` in the
broadcast message:

```python
message = {
    "type": "olm_analysis",      # rename from "ovlm_analysis"
    ...
    "sensors": sensor_data,      # add this line so the radar/timeline use real values
    ...
}
```

The dashboard accepts both `"olm_analysis"` and `"ovlm_analysis"` so this
rename is safe to roll out independently of the dashboard.

## How this relates to demo.py

`demo.py` at the repo root is a terminal-only renderer that subscribes
directly to the BLE characteristic via D-Bus / BlueZ and runs the actual
**COLIP** model (`scentience.models.ColipModel`, `colip-small-base`) in
olfaction-only mode. It prints the top-3 aroma anchors with confidence
bars and a filter recommendation derived from the top match.

The **Aroma Classification** panel in the dashboard mirrors `demo.py`'s
output one-to-one (same 10 anchor labels, same descriptions, same filter
flags). When the bridge starts including an `aroma` field in its WebSocket
broadcast, the dashboard panel switches from the rule-based stand-in to
the live COLIP rankings transparently.

The **Cortisol Stress Gauge** and **AQI Waterfall** panels stay rule-based
because the bridge's own scoring is rule-based; they're complementary to
the model output rather than replaced by it.

Use `demo.py` when you want a fast textual loop with the real model. Use
`dashboard.html` (driven by `server/ovlm_bridge_server.py`) for the rich
didactic view designed to live inside the app.
