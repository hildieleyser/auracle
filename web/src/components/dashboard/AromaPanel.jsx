/**
 * Aroma classification — top match prominent, top-5 anchors with cosine bars.
 * Mirrors viz/dashboard.html and demo.py output.
 */
export default function AromaPanel({ aroma }) {
  if (!aroma || !aroma.top) return null;
  const top5 = aroma.top.slice(0, 5);
  const top  = top5[0];
  const lo = 0.20, hi = 0.36;

  return (
    <section className="rounded-3xl bg-ink p-7 text-parchment shadow-[0_24px_60px_-30px_rgba(10,10,10,0.6)]">
      <div className="flex items-start justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-parchment/70">
          Aroma · OLM
        </span>
        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-parchment/70">
          COLIP
        </span>
      </div>

      <div className="mt-5 flex items-baseline gap-3">
        <span className="font-serif text-4xl font-light leading-none">
          {top.label}
        </span>
      </div>
      <div className="mt-2 flex items-baseline justify-between">
        <span className="font-serif text-base italic text-parchment/70 tabular-nums">
          {top.score.toFixed(4)}
        </span>
        <span
          className={[
            'rounded-full px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.25em]',
            top.filter_recommended
              ? 'bg-rose-500/90 text-parchment'
              : 'bg-emerald-500/90 text-ink',
          ].join(' ')}
        >
          {top.filter_recommended ? 'Filter recommended' : 'Air acceptable'}
        </span>
      </div>

      <div className="my-6 h-px bg-parchment/15" />

      <div className="mb-3 flex items-baseline justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-parchment/70">
          Top 5 matches
        </span>
        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-parchment/70">
          cos similarity
        </span>
      </div>

      <ul className="flex flex-col gap-3">
        {top5.map((r, idx) => {
          const pct = Math.max(0, Math.min(1, (r.score - lo) / (hi - lo))) * 100;
          return (
            <li key={r.label} className="flex items-center gap-3">
              <span
                className={[
                  'w-32 truncate font-serif text-sm',
                  idx === 0 ? 'text-parchment' : 'text-parchment/80',
                ].join(' ')}
                title={r.desc}
              >
                {r.label}
              </span>
              <div className="relative h-1 flex-1 overflow-hidden rounded-full bg-parchment/15">
                <div
                  className={[
                    'absolute inset-y-0 left-0 rounded-full transition-[width] duration-500',
                    r.filter_recommended ? 'bg-rose-400/80' : 'bg-parchment/80',
                  ].join(' ')}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="w-12 text-right font-mono text-[11px] tabular-nums text-parchment/70">
                {r.score.toFixed(3)}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
