import { useEffect, useRef, useState } from 'react';
import { SCENARIOS, olmAnalyze, scenarioFromMetrics } from '../data/olm.js';

const HISTORY_LIMIT = 60;
const TICK_MS = 3000;
const STORAGE_KEY = 'auracle:wsUrl';

/** Normalise whatever the user pastes into a usable WS URL. */
export function normaliseWsUrl(input) {
  let s = (input || '').trim();
  if (!s) return '';
  if (s.startsWith('https://')) s = 'wss://' + s.slice(8);
  else if (s.startsWith('http://')) s = 'ws://' + s.slice(7);
  else if (!s.startsWith('ws://') && !s.startsWith('wss://')) {
    // bare host: assume secure tunnel
    s = 'wss://' + s;
  }
  return s.replace(/\/+$/, '');
}

/**
 * Resolve the bridge URL the dashboard should connect to.
 *
 *   1. ?ws=wss://... query param (highest priority — for sharing links)
 *   2. localStorage 'auracle:wsUrl' (set via the Source sheet)
 *   3. ws://<this host>:8765   (only useful for local dev over http://)
 *
 * Returns null when the page is on https:// and there's no saved URL —
 * we can't blindly try ws://localhost:8765 from a public site (mixed content
 * is blocked) so we surface "demo mode, configure source" instead.
 */
export function resolveBridgeUrl() {
  if (typeof window === 'undefined') return null;
  const params = new URLSearchParams(window.location.search);
  const override = params.get('ws');
  if (override) return normaliseWsUrl(override);

  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) return normaliseWsUrl(saved);
  } catch { /* localStorage may be blocked */ }

  if (window.location.protocol === 'https:') return null;
  return `ws://${window.location.hostname || 'localhost'}:8765`;
}

export function setBridgeUrl(url) {
  if (typeof window === 'undefined') return;
  try {
    if (url) window.localStorage.setItem(STORAGE_KEY, normaliseWsUrl(url));
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch { /* ignore */ }
  window.dispatchEvent(new Event('auracle:source-changed'));
}

/**
 * useOlmStream — keeps a rolling history of OLM analyses.
 *
 *   - Tries to subscribe to the configured WS URL.
 *   - Falls back to demo scenarios if the bridge is offline / unset.
 *   - Reactive: if the user updates the source via setBridgeUrl(), the
 *     hook reconnects automatically.
 */
export function useOlmStream(scenario = 'auto') {
  const [bridgeUrl, setUrlState] = useState(() => resolveBridgeUrl());
  const [history, setHistory] = useState(() => seedDemoHistory());
  const [status, setStatus] = useState({
    source: 'connecting',         // 'live' | 'demo' | 'connecting'
    connected: false,
    bridgeUrl: bridgeUrl,
    lastReceivedAt: null,
    sensorsInBroadcast: false,
  });

  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const demoTimerRef = useRef(null);
  const scenarioRef = useRef(scenario);
  scenarioRef.current = scenario;

  useEffect(() => {
    const onChange = () => setUrlState(resolveBridgeUrl());
    window.addEventListener('storage', onChange);
    window.addEventListener('auracle:source-changed', onChange);
    return () => {
      window.removeEventListener('storage', onChange);
      window.removeEventListener('auracle:source-changed', onChange);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setStatus((s) => ({ ...s, bridgeUrl }));

    function pushAnalysis(a) {
      setHistory((prev) => {
        const next = prev.concat([a]);
        return next.length > HISTORY_LIMIT ? next.slice(next.length - HISTORY_LIMIT) : next;
      });
    }

    function startDemoLoop() {
      if (demoTimerRef.current) return;
      demoTimerRef.current = setInterval(() => {
        const scn = scenarioRef.current;
        const name = scn === 'auto'
          ? Object.keys(SCENARIOS)[Math.floor(Date.now() / 30000) % 4]
          : scn;
        const sample = (SCENARIOS[name] || SCENARIOS.calm)();
        pushAnalysis(olmAnalyze(sample));
      }, TICK_MS);
    }

    function stopDemoLoop() {
      if (demoTimerRef.current) {
        clearInterval(demoTimerRef.current);
        demoTimerRef.current = null;
      }
    }

    function connect() {
      if (cancelled) return;
      // No URL configured (HTTPS site, no source set) → demo only.
      if (!bridgeUrl) {
        setStatus((s) => ({ ...s, source: 'demo', connected: false, bridgeUrl: null }));
        startDemoLoop();
        return;
      }
      let ws;
      try {
        ws = new WebSocket(bridgeUrl);
      } catch {
        setStatus((s) => ({ ...s, source: 'demo', connected: false }));
        startDemoLoop();
        return;
      }
      wsRef.current = ws;
      setStatus((s) => ({ ...s, source: 'connecting', bridgeUrl }));

      ws.onopen = () => {
        stopDemoLoop();
        setStatus((s) => ({ ...s, source: 'live', connected: true }));
        try { ws.send(JSON.stringify({ type: 'start_streaming' })); } catch { /* ignore */ }
      };

      ws.onmessage = (ev) => {
        let msg;
        try { msg = JSON.parse(ev.data); } catch { return; }
        if (msg.type !== 'olm_analysis' && msg.type !== 'ovlm_analysis') return;

        const sensors = msg.sensors || msg.raw_sensors || null;
        const analysis = sensors ? olmAnalyze(sensors) : olmAnalyze(scenarioFromMetrics(msg));
        analysis.natural_language_summary = msg.natural_language_summary || analysis.natural_language_summary;
        analysis.timestamp = msg.timestamp || analysis.timestamp;
        analysis.device_actions = msg.device_actions || analysis.device_actions;
        if (msg.aroma && Array.isArray(msg.aroma.top)) analysis.aroma = msg.aroma;

        setStatus((s) => ({
          ...s,
          source: 'live',
          connected: true,
          lastReceivedAt: Date.now(),
          sensorsInBroadcast: !!sensors,
        }));
        pushAnalysis(analysis);
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (cancelled) return;
        setStatus((s) => ({ ...s, source: 'demo', connected: false }));
        startDemoLoop();
        clearTimeout(reconnectRef.current);
        reconnectRef.current = setTimeout(connect, 4000);
      };
      ws.onerror = () => { try { ws.close(); } catch { /* ignore */ } };
    }

    connect();

    return () => {
      cancelled = true;
      clearTimeout(reconnectRef.current);
      stopDemoLoop();
      try { wsRef.current && wsRef.current.close(); } catch { /* ignore */ }
    };
  }, [bridgeUrl]);

  const latest = history[history.length - 1] || null;
  return { latest, history, status };
}

function seedDemoHistory() {
  const out = [];
  for (let i = 0; i < 12; i++) {
    const a = olmAnalyze(SCENARIOS.calm());
    a.timestamp = new Date(Date.now() - (12 - i) * TICK_MS).toISOString();
    out.push(a);
  }
  return out;
}
