import { useEffect, useRef, useState } from 'react';
import { SCENARIOS, olmAnalyze, scenarioFromMetrics } from '../data/olm.js';

const HISTORY_LIMIT = 60;
const TICK_MS = 3000;

function resolveBridgeUrl() {
  const params = new URLSearchParams(window.location.search);
  const override = params.get('ws');
  if (override) return override;
  // dev convention: bridge runs on :8765 on the same host
  const host = window.location.hostname || 'localhost';
  return `ws://${host}:8765`;
}

/**
 * useOlmStream — keeps a rolling history of OLM analyses.
 *
 *   - Tries to subscribe to the OVLM bridge WebSocket.
 *   - Falls back to demo scenarios if the bridge is offline so the dashboard
 *     never goes blank.
 *   - Reports honestly whether the values are LIVE or DEMO so the status
 *     bar can tell the user where the numbers are coming from.
 */
export function useOlmStream(scenario = 'auto') {
  const [history, setHistory] = useState(() => seedDemoHistory());
  const [status, setStatus] = useState({
    source: 'connecting',         // 'live' | 'demo' | 'connecting'
    connected: false,
    bridgeUrl: resolveBridgeUrl(),
    lastReceivedAt: null,
    sensorsInBroadcast: false,
  });

  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const demoTimerRef = useRef(null);
  const scenarioRef = useRef(scenario);
  scenarioRef.current = scenario;

  useEffect(() => {
    let cancelled = false;

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
      let ws;
      try {
        ws = new WebSocket(status.bridgeUrl);
      } catch {
        setStatus((s) => ({ ...s, source: 'demo', connected: false }));
        startDemoLoop();
        return;
      }
      wsRef.current = ws;
      setStatus((s) => ({ ...s, source: 'connecting' }));

      ws.onopen = () => {
        stopDemoLoop();
        setStatus((s) => ({ ...s, source: 'live', connected: true }));
        try { ws.send(JSON.stringify({ type: 'start_streaming' })); } catch {}
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

      const onClose = () => {
        wsRef.current = null;
        if (cancelled) return;
        setStatus((s) => ({ ...s, source: 'demo', connected: false }));
        startDemoLoop();
        clearTimeout(reconnectRef.current);
        reconnectRef.current = setTimeout(connect, 4000);
      };
      ws.onclose = onClose;
      ws.onerror = () => { try { ws.close(); } catch {} };
    }

    connect();

    return () => {
      cancelled = true;
      clearTimeout(reconnectRef.current);
      stopDemoLoop();
      try { wsRef.current && wsRef.current.close(); } catch {}
    };
  }, [status.bridgeUrl]);

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
