import { useEffect, useRef } from 'react';

/**
 * Filter Theatre — schematic of the wearable's response.
 * LED ring colour follows stress level; fan blades spin proportional to fan_speed.
 */
export default function FilterPanel({ analysis }) {
  if (!analysis) return null;
  const act = analysis.device_actions;
  const lvl = analysis.hormone.stress_level;
  const ledColor = lvl === 'high' ? '#9c3344' : lvl === 'moderate' ? '#a86d50' : '#10b981';
  const fanRef = useRef(null);

  useEffect(() => {
    let raf;
    let angle = 0;
    const step = () => {
      angle = (angle + (act.fan_speed || 0) * 0.06) % 360;
      if (fanRef.current) {
        fanRef.current.setAttribute('transform', `rotate(${angle})`);
      }
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [act.fan_speed]);

  const caption = !act.activate_filter
    ? 'Idle — monitoring air'
    : act.filter_mode === 'stress_reduction'
      ? 'Stress mode · NH₃ + VOCs · 30 min'
      : 'Standard purification · 15 min';

  return (
    <section className="flex flex-col gap-5">
      <div className="flex items-baseline justify-between">
        <h2 className="font-serif text-2xl italic text-ink">Filter</h2>
        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-graphite">
          Device
        </span>
      </div>

      <div className="rounded-3xl border border-hairline bg-parchment/70 p-6">
        <svg viewBox="0 0 320 220" className="h-44 w-full">
          {/* case */}
          <rect
            x="20" y="40" width="280" height="140" rx="18"
            fill="rgba(10,10,10,0.04)"
            stroke="rgba(10,10,10,0.12)"
            strokeWidth="1"
          />

          {/* media */}
          <rect
            x="120" y="60" width="14" height="100"
            fill="rgba(10,10,10,0.10)"
            stroke="#0A0A0A"
            strokeWidth="0.8"
          />
          <text x="127" y="50" textAnchor="middle"
                fill="#4D4843" fontSize="9"
                fontFamily="Inter, system-ui, sans-serif"
                style={{ letterSpacing: '0.18em', textTransform: 'uppercase' }}>
            Media
          </text>

          {/* fan */}
          <g transform="translate(220 110)">
            <circle r="36" fill="rgba(10,10,10,0.05)" stroke="rgba(10,10,10,0.15)" strokeWidth="0.8" />
            <g ref={fanRef} style={{ transformOrigin: 'center', transition: 'opacity 200ms' }}>
              <ellipse cx="0" cy="-18" rx="6" ry="14" fill="#0A0A0A" opacity="0.85" />
              <ellipse cx="16" cy="9"  rx="6" ry="14" fill="#0A0A0A" opacity="0.85" transform="rotate(120)" />
              <ellipse cx="-16" cy="9" rx="6" ry="14" fill="#0A0A0A" opacity="0.85" transform="rotate(240)" />
            </g>
            <circle r="5" fill="#4D4843" />
            <text y="50" textAnchor="middle"
                  fill="#4D4843" fontSize="9"
                  fontFamily="Inter, system-ui, sans-serif"
                  style={{ letterSpacing: '0.18em', textTransform: 'uppercase' }}>
              Fan
            </text>
          </g>

          {/* LED */}
          <circle
            cx="50" cy="110" r="22"
            fill="none"
            stroke={ledColor}
            strokeWidth="3"
            opacity={act.activate_filter ? 1 : 0.3}
            style={{ transition: 'stroke 400ms ease, opacity 300ms ease' }}
          />
          <text x="50" y="148" textAnchor="middle"
                fill="#4D4843" fontSize="9"
                fontFamily="Inter, system-ui, sans-serif"
                style={{ letterSpacing: '0.18em', textTransform: 'uppercase' }}>
            LED
          </text>

          <text x="160" y="206" textAnchor="middle"
                fill="#0A0A0A" fontSize="13"
                fontFamily="Fraunces, Georgia, serif">
            {caption}
          </text>
        </svg>

        <div className="mt-3 grid grid-cols-2 gap-3">
          <Cell label="Mode" value={act.filter_mode} />
          <Cell label="Fan" value={`${act.fan_speed}%`} />
          <Cell label="Duration" value={act.activate_filter ? `${act.duration_minutes} min` : '—'} />
          <Cell label="Alert" value={act.alert_level} />
        </div>
      </div>
    </section>
  );
}

function Cell({ label, value }) {
  return (
    <div className="rounded-2xl border border-hairline bg-sand-deep/40 px-4 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-[0.25em] text-graphite">
        {label}
      </div>
      <div className="mt-1 font-serif text-base text-ink">{value}</div>
    </div>
  );
}
