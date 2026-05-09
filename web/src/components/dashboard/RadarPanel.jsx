import { COMPOUNDS, RADAR_KEYS } from '../../data/olm.js';

const VIEW = 320;
const R    = 110;

export default function RadarPanel({ analysis }) {
  if (!analysis) return null;
  const sensors = analysis.sensors || {};

  const points = RADAR_KEYS.map((k, i) => {
    const v = sensors[k] ?? COMPOUNDS[k].baseline;
    const norm = Math.min(v / COMPOUNDS[k].bad, 1.15);
    const ang = -Math.PI / 2 + (i * 2 * Math.PI) / RADAR_KEYS.length;
    return {
      x: Math.cos(ang) * R * norm,
      y: Math.sin(ang) * R * norm,
      v, ang, key: k,
      tone: v >= COMPOUNDS[k].bad ? 'bad' : v >= COMPOUNDS[k].warn ? 'warn' : 'ok',
    };
  });

  const baseline = RADAR_KEYS.map((k, i) => {
    const c = COMPOUNDS[k];
    const norm = c.baseline / c.bad;
    const ang = -Math.PI / 2 + (i * 2 * Math.PI) / RADAR_KEYS.length;
    return { x: Math.cos(ang) * R * norm, y: Math.sin(ang) * R * norm };
  });

  return (
    <section className="flex flex-col gap-5">
      <div className="flex items-baseline justify-between">
        <h2 className="font-serif text-2xl italic text-ink">Olfactory radar</h2>
        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-graphite">
          {RADAR_KEYS.length} channels
        </span>
      </div>

      <div className="rounded-3xl border border-hairline bg-parchment/70 p-6">
        <div className="flex justify-center">
          <svg
            viewBox={`-${VIEW / 2} -${VIEW / 2} ${VIEW} ${VIEW}`}
            className="h-72 w-full max-w-sm"
          >
            {[0.25, 0.5, 0.75, 1].map((r) => (
              <circle
                key={r}
                cx="0"
                cy="0"
                r={R * r}
                fill="none"
                stroke="rgba(10,10,10,0.08)"
                strokeWidth="0.6"
              />
            ))}
            {RADAR_KEYS.map((k, i) => {
              const ang = -Math.PI / 2 + (i * 2 * Math.PI) / RADAR_KEYS.length;
              const lx = Math.cos(ang) * (R + 18);
              const ly = Math.sin(ang) * (R + 18);
              return (
                <g key={k}>
                  <line
                    x1="0"
                    y1="0"
                    x2={Math.cos(ang) * R}
                    y2={Math.sin(ang) * R}
                    stroke="rgba(10,10,10,0.08)"
                    strokeWidth="0.6"
                  />
                  <text
                    x={lx}
                    y={ly}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className="fill-ink"
                    fontFamily="Fraunces, Georgia, serif"
                    fontSize="11"
                  >
                    {COMPOUNDS[k].label}
                  </text>
                </g>
              );
            })}
            <polygon
              points={baseline.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')}
              fill="rgba(10,10,10,0.04)"
              stroke="rgba(10,10,10,0.30)"
              strokeWidth="0.8"
              strokeDasharray="3 3"
            />
            <polygon
              points={points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')}
              fill="rgba(10,10,10,0.10)"
              stroke="#0A0A0A"
              strokeWidth="1.4"
              style={{ transition: 'all 350ms ease' }}
            />
            {points.map((p) => (
              <circle
                key={p.key}
                cx={p.x}
                cy={p.y}
                r="3"
                fill={p.tone === 'bad' ? '#9c3344' : p.tone === 'warn' ? '#a86d50' : '#0A0A0A'}
                stroke="#F5F1EC"
                strokeWidth="1"
              />
            ))}
          </svg>
        </div>

        <div className="mt-3 flex items-center justify-center gap-5 text-[10px] uppercase tracking-[0.25em] text-graphite">
          <span className="flex items-center gap-2">
            <span className="inline-block h-px w-4 border-t border-dashed border-ink/40" />
            baseline
          </span>
          <span className="flex items-center gap-2">
            <span className="inline-block h-[2px] w-4 bg-ink" />
            live
          </span>
        </div>
      </div>
    </section>
  );
}
