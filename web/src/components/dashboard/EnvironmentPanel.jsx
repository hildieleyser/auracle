/**
 * Environment — straight from the device's environmental sensors.
 * Temperature, humidity, pressure, battery. No derivation, no rules.
 */
export default function EnvironmentPanel({ analysis }) {
  const s = analysis?.sensors;
  if (!s) return null;

  const cells = [
    { label: 'Temperature', value: (s.ENV_temperatureC ?? 0).toFixed(1), unit: '°C' },
    { label: 'Humidity',    value: (s.ENV_humidity ?? 0).toFixed(0),     unit: '%'  },
    { label: 'Pressure',    value: (s.ENV_pressureHpa ?? 0).toFixed(0),  unit: 'hPa' },
    { label: 'Battery',     value: s.BATT_charge != null ? `${s.BATT_charge}` : '—', unit: s.BATT_charge != null ? '%' : '' },
  ];

  return (
    <section className="flex flex-col gap-5">
      <div className="flex items-baseline justify-between">
        <h2 className="font-serif text-2xl italic text-ink">Environment</h2>
        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-graphite">
          ambient
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {cells.map((c) => (
          <div
            key={c.label}
            className="rounded-2xl border border-hairline bg-parchment/70 px-5 py-4"
          >
            <div className="text-[10px] font-semibold uppercase tracking-[0.25em] text-graphite">
              {c.label}
            </div>
            <div className="mt-2 flex items-baseline gap-1">
              <span className="font-serif text-3xl font-light leading-none text-ink tabular-nums">
                {c.value}
              </span>
              {c.unit && (
                <span className="text-sm text-graphite">{c.unit}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
