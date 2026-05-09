import { useEffect, useRef } from 'react';

const SERIES = [
  { key: 'NH3', color: '#9c3344', scale: 350 },
  { key: 'CO',  color: '#a86d50', scale: 1500 },
  { key: 'VOC', color: '#6b5b95', scale: 4000 },
];

/**
 * Rolling timeline of the last ~60 OLM analyses.
 * Three normalised sensor traces + the stress score on a right-axis,
 * with cyan bands marking when the filter is active.
 */
export default function TimelinePanel({ history }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;

    function draw() {
      const rect = canvas.getBoundingClientRect();
      const w = Math.max(rect.width, 320);
      const h = 200;
      canvas.width  = w * dpr;
      canvas.height = h * dpr;
      canvas.style.height = `${h}px`;
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      if (history.length < 2) return;
      const padL = 32, padR = 12, padT = 10, padB = 22;
      const plotW = w - padL - padR;
      const plotH = h - padT - padB;

      // grid
      ctx.strokeStyle = 'rgba(10,10,10,0.06)';
      ctx.lineWidth = 1;
      for (let i = 0; i < 5; i++) {
        const y = padT + (i / 4) * plotH;
        ctx.beginPath();
        ctx.moveTo(padL, y); ctx.lineTo(padL + plotW, y);
        ctx.stroke();
      }
      ctx.fillStyle = 'rgba(77,72,67,0.85)';
      ctx.font = '10px Inter, system-ui, sans-serif';
      ctx.fillText('normalized 0–1', 6, padT + 8);

      // filter-active bands
      ctx.fillStyle = 'rgba(10,10,10,0.04)';
      let bandStart = null;
      const N = history.length;
      history.forEach((a, i) => {
        const x = padL + (i / (N - 1)) * plotW;
        const active = a.device_actions.activate_filter;
        if (active && bandStart === null) bandStart = x;
        if (!active && bandStart !== null) {
          ctx.fillRect(bandStart, padT, x - bandStart, plotH);
          bandStart = null;
        }
      });
      if (bandStart !== null) {
        const x = padL + plotW;
        ctx.fillRect(bandStart, padT, x - bandStart, plotH);
      }

      // sensor traces
      SERIES.forEach((s) => {
        ctx.strokeStyle = s.color;
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        history.forEach((a, i) => {
          const v = (a.sensors?.[s.key] ?? 0) / s.scale;
          const x = padL + (i / (N - 1)) * plotW;
          const y = padT + plotH - Math.min(v, 1) * plotH;
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.stroke();
      });

      // stress score (right axis 0..7)
      ctx.strokeStyle = '#0A0A0A';
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      history.forEach((a, i) => {
        const v = a.hormone.stress_score / 7;
        const x = padL + (i / (N - 1)) * plotW;
        const y = padT + plotH - v * plotH;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // x-axis time labels
      ctx.fillStyle = 'rgba(77,72,67,0.85)';
      ctx.font = '10px Inter, system-ui, sans-serif';
      ctx.fillText('now', padL + plotW - 18, h - 6);
      ctx.fillText(`-${Math.round((N * 3))}s`, padL, h - 6);
    }

    draw();
    const ro = new ResizeObserver(draw);
    ro.observe(canvas);
    return () => ro.disconnect();
  }, [history]);

  return (
    <section className="flex flex-col gap-5">
      <div className="flex items-baseline justify-between">
        <h2 className="font-serif text-2xl italic text-ink">Timeline</h2>
        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-graphite">
          last {Math.round((history.length * 3))}s
        </span>
      </div>

      <div className="rounded-3xl border border-hairline bg-parchment/70 p-5">
        <canvas ref={canvasRef} className="block w-full" />
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] uppercase tracking-[0.25em] text-graphite">
          <Legend color="#9c3344" label="NH₃" />
          <Legend color="#a86d50" label="CO" />
          <Legend color="#6b5b95" label="VOC" />
          <Legend color="#0A0A0A" label="stress" />
          <Legend color="rgba(10,10,10,0.18)" label="filter on" block />
        </div>
      </div>
    </section>
  );
}

function Legend({ color, label, block = false }) {
  return (
    <span className="flex items-center gap-2">
      {block ? (
        <span className="inline-block h-3 w-3 rounded-sm" style={{ background: color }} />
      ) : (
        <span className="inline-block h-[2px] w-4" style={{ background: color }} />
      )}
      {label}
    </span>
  );
}
