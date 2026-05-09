import { COMPOUNDS, RADAR_KEYS } from '../../data/olm.js';

const UNITS = {
  CO2: 'ppm', NH3: 'ppb', CO: 'ppb', NO: 'ppb', NO2: 'ppb',
  VOC: 'ppb', C2H5OH: 'ppb', H2: 'ppb', CH4: 'ppb',
};

const TONE_LABEL = { ok: 'normal', warn: 'elevated', bad: 'high' };
const TONE_TEXT  = {
  ok:   'text-graphite',
  warn: 'text-amber-700',
  bad:  'text-rose-700',
};

/**
 * Compounds — every gas channel the device reports, with unit and how it
 * compares to the healthy-air thresholds. Real numbers from the sensor;
 * the only derived field is the {ok | warn | bad} tone, which is a direct
 * threshold check on the value.
 */
export default function CompoundsPanel({ analysis }) {
  const sensors = analysis?.sensors;
  if (!sensors) return null;

  const rows = RADAR_KEYS.map((k) => {
    const v = sensors[k] ?? 0;
    const c = COMPOUNDS[k];
    const tone = v >= c.bad ? 'bad' : v >= c.warn ? 'warn' : 'ok';
    return { k, v, c, norm: v / c.bad, tone };
  }).sort((a, b) => b.norm - a.norm);

  return (
    <section className="flex flex-col gap-5">
      <div className="flex items-baseline justify-between">
        <h2 className="font-serif text-2xl italic text-ink">Compounds</h2>
        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-graphite">
          live values
        </span>
      </div>

      <p className="text-sm leading-relaxed text-graphite">
        Each row is a compound the sensor reads. Sorted by how close it sits
        to its high-air-quality threshold.
      </p>

      <ol className="flex flex-col">
        {rows.map((r, idx) => (
          <li
            key={r.k}
            className={[
              'flex items-center gap-5 py-4',
              idx < rows.length - 1 ? 'border-b border-hairline' : '',
            ].join(' ')}
          >
            <span className="font-serif text-sm italic text-graphite">
              {String(idx + 1).padStart(2, '0')}
            </span>

            <div className="flex flex-1 flex-col">
              <span className="font-serif text-xl font-light text-ink">
                {r.c.label}
              </span>
              <span className="text-[10px] font-semibold uppercase tracking-[0.25em] text-graphite">
                {r.c.name}
              </span>
            </div>

            <div className="flex flex-col items-end">
              <span className="font-serif text-xl text-ink tabular-nums">
                {r.v.toFixed(r.v < 10 ? 1 : 0)}
                <span className="ml-1 text-sm text-graphite">{UNITS[r.k]}</span>
              </span>
              <span
                className={[
                  'text-[10px] font-semibold uppercase tracking-[0.25em]',
                  TONE_TEXT[r.tone],
                ].join(' ')}
              >
                {TONE_LABEL[r.tone]}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
