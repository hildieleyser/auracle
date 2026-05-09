import { COMPOUNDS } from '../../data/olm.js';

export default function AQIPanel({ analysis }) {
  if (!analysis) return null;
  const { aqi, level, penalties } = analysis.air_quality;

  const levelColor = {
    excellent: 'text-emerald-700',
    good:      'text-emerald-600',
    moderate:  'text-amber-700',
    poor:      'text-rose-700',
  }[level] || 'text-ink';

  const rows = [
    { k: 'CO2', max: 3 },
    { k: 'NO',  max: 2 },
    { k: 'NO2', max: 2 },
    { k: 'VOC', max: 3 },
  ];

  return (
    <section className="flex flex-col gap-5">
      <div className="flex items-baseline justify-between">
        <h2 className="font-serif text-2xl italic text-ink">Air quality</h2>
        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-graphite">
          10 minus penalties
        </span>
      </div>

      <div className="rounded-3xl border border-hairline bg-parchment/70 p-7">
        <div className="flex items-baseline gap-3">
          <span className="font-serif text-7xl font-light leading-none text-ink tabular-nums">
            {aqi}
          </span>
          <span className="font-serif text-base italic text-graphite">/ 10</span>
          <span className={`ml-auto font-serif text-base italic ${levelColor}`}>
            {level}
          </span>
        </div>

        <div className="my-5 h-px bg-hairline" />

        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-graphite">
          Penalties
        </span>

        <ul className="mt-3 flex flex-col gap-3">
          {rows.map(({ k, max }) => {
            const v = penalties[k] ?? 0;
            const pct = (v / max) * 100;
            const tone = v === 0 ? 'bg-emerald-500' : v === max ? 'bg-rose-500' : 'bg-amber-500';
            return (
              <li key={k} className="flex items-center gap-3">
                <span className="w-12 font-serif text-sm text-ink">
                  {COMPOUNDS[k].label}
                </span>
                <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-ink/8">
                  <div
                    className={`absolute inset-y-0 left-0 rounded-full transition-[width] duration-500 ${tone}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="w-10 text-right font-mono text-[11px] tabular-nums text-graphite">
                  −{v}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
