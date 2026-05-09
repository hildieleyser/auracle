/**
 * Story feed — the OLM's natural-language summaries with the underlying
 * numbers attached. Most-recent first.
 */
export default function StoryFeedPanel({ history }) {
  const items = history.slice(-6).reverse();
  if (!items.length) return null;

  return (
    <section className="flex flex-col gap-5">
      <div className="flex items-baseline justify-between">
        <h2 className="font-serif text-2xl italic text-ink">Story</h2>
        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-graphite">
          {items.length} dispatches
        </span>
      </div>

      <ul className="flex flex-col">
        {items.map((a, idx) => {
          const lvl = a.hormone.stress_level;
          const accent = lvl === 'high'
            ? 'border-l-rose-500'
            : lvl === 'moderate'
              ? 'border-l-amber-500'
              : 'border-l-emerald-500';
          const ts = new Date(a.timestamp).toLocaleTimeString([], {
            hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
          });
          return (
            <li
              key={a.timestamp + idx}
              className={[
                'flex flex-col gap-2 border-l-2 py-4 pl-4',
                accent,
                idx < items.length - 1 ? 'border-b border-b-hairline' : '',
              ].join(' ')}
            >
              <div className="flex items-baseline justify-between">
                <span className="font-serif text-sm italic text-graphite tabular-nums">
                  {ts}
                </span>
                <span className="text-[10px] font-semibold uppercase tracking-[0.25em] text-graphite">
                  {lvl}
                </span>
              </div>
              <p className="text-[13px] leading-relaxed text-ink/85">
                {a.natural_language_summary}
              </p>
              <div className="flex flex-wrap gap-1.5 pt-1">
                <Chip label={`stress ${a.hormone.stress_score}/7`} />
                <Chip label={`AQI ${a.air_quality.aqi}/10`} />
                <Chip label={`NH₃ ${(a.sensors?.NH3 ?? 0).toFixed(0)}`} />
                <Chip label={`CO ${(a.sensors?.CO ?? 0).toFixed(0)}`} />
                <Chip label={`VOC ${(a.sensors?.VOC ?? 0).toFixed(0)}`} />
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Chip({ label }) {
  return (
    <span className="rounded-full border border-hairline bg-sand-deep/30 px-2.5 py-0.5 text-[10px] uppercase tracking-[0.2em] text-graphite">
      {label}
    </span>
  );
}
