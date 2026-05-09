import { COMPOUNDS } from '../../data/olm.js';

const SIZE   = 220;
const STROKE = 14;
const RADIUS = (SIZE - STROKE) / 2;

export default function StressGaugePanel({ analysis }) {
  if (!analysis) return null;
  const score = analysis.hormone.stress_score;
  const level = analysis.hormone.stress_level;
  const conf  = analysis.hormone.confidence;
  const cort  = analysis.hormone.cortisol_estimate_ng_m3;
  const contribs = analysis.hormone.contributions;

  const frac = Math.min(score / 7, 1);
  // semicircle from 180° → 360°
  const arcLen = Math.PI * RADIUS;
  const dashOffset = arcLen * (1 - frac);

  const accent = level === 'high'
    ? '#9c3344'
    : level === 'moderate'
      ? '#a86d50'
      : '#0A0A0A';

  return (
    <section className="flex flex-col gap-5">
      <div className="flex items-baseline justify-between">
        <h2 className="font-serif text-2xl italic text-ink">Stress</h2>
        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-graphite">
          Cortisol gauge
        </span>
      </div>

      <div className="rounded-3xl border border-hairline bg-parchment/70 p-6">
        <div className="flex flex-col items-center">
          <div className="relative" style={{ width: SIZE, height: SIZE / 2 + 10 }}>
            <svg
              width={SIZE}
              height={SIZE}
              viewBox={`0 0 ${SIZE} ${SIZE}`}
              className="absolute inset-x-0 top-0"
            >
              {/* track */}
              <path
                d={`M ${STROKE / 2} ${SIZE / 2} A ${RADIUS} ${RADIUS} 0 0 1 ${SIZE - STROKE / 2} ${SIZE / 2}`}
                fill="none"
                stroke="rgba(10,10,10,0.08)"
                strokeWidth={STROKE}
                strokeLinecap="round"
              />
              {/* fill */}
              <path
                d={`M ${STROKE / 2} ${SIZE / 2} A ${RADIUS} ${RADIUS} 0 0 1 ${SIZE - STROKE / 2} ${SIZE / 2}`}
                fill="none"
                stroke={accent}
                strokeWidth={STROKE}
                strokeLinecap="round"
                strokeDasharray={arcLen}
                strokeDashoffset={dashOffset}
                style={{ transition: 'stroke-dashoffset 600ms cubic-bezier(0.22, 1, 0.36, 1), stroke 300ms ease' }}
              />
            </svg>
            <div className="absolute inset-x-0 top-6 flex flex-col items-center">
              <span className="font-serif text-6xl font-light leading-none text-ink">
                {score}
              </span>
              <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.3em] text-graphite">
                of 7
              </span>
            </div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-4 border-t border-hairline pt-4">
          <Stat label="Level" value={level} />
          <Stat label="Confidence" value={`${Math.round(conf * 100)}%`} />
          <Stat label="Cortisol est." value={`${cort.toFixed(2)} ng/m³`} />
          <Stat label="Driver" value={topDriver(contribs)} />
        </div>

        <div className="mt-5 border-t border-hairline pt-4">
          <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-graphite">
            Contributions
          </span>
          <ul className="mt-3 flex flex-col gap-3">
            {(['NH3', 'CO', 'VOC']).map((k) => {
              const v = contribs[k];
              const max = k === 'NH3' ? 3 : 2;
              const pct = (v / max) * 100;
              return (
                <li key={k} className="flex items-center gap-3">
                  <span className="w-10 font-serif text-sm text-ink">
                    {COMPOUNDS[k].label}
                  </span>
                  <div className="relative h-1 flex-1 overflow-hidden rounded-full bg-ink/8">
                    <div
                      className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-500"
                      style={{ width: `${pct}%`, background: accent }}
                    />
                  </div>
                  <span className="w-8 text-right font-mono text-[11px] tabular-nums text-graphite">
                    +{v}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] font-semibold uppercase tracking-[0.25em] text-graphite">
        {label}
      </span>
      <span className="mt-1 font-serif text-lg text-ink">{value}</span>
    </div>
  );
}

function topDriver(contribs) {
  const entries = Object.entries(contribs).sort((a, b) => b[1] - a[1]);
  if (entries[0][1] === 0) return '—';
  return COMPOUNDS[entries[0][0]].label;
}
