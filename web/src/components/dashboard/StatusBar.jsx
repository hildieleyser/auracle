import { useEffect, useState } from 'react';
import { Settings2 } from 'lucide-react';

/**
 * The data-source diagnostic — answers "is this real?" at a glance.
 * Tap to open the source-configuration sheet.
 */
export default function StatusBar({ status, onConfigure }) {
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const ageSec = status.lastReceivedAt
    ? Math.max(0, (Date.now() - status.lastReceivedAt) / 1000)
    : null;

  let kind, label, detail;
  if (!status.bridgeUrl) {
    kind = 'unconfigured';
    label = 'No source';
    detail = 'Tap to connect a bridge';
  } else if (status.source === 'connecting') {
    kind = 'connecting';
    label = 'Connecting';
    detail = trimUrl(status.bridgeUrl);
  } else if (status.source === 'demo') {
    kind = 'demo';
    label = 'Demo';
    detail = 'Bridge unreachable — values simulated';
  } else if (ageSec == null) {
    kind = 'waiting';
    label = 'Waiting';
    detail = 'Connected — no samples yet';
  } else if (ageSec > 15) {
    kind = 'stale';
    label = 'Stale';
    detail = `Last sample ${ageSec.toFixed(0)}s ago`;
  } else {
    kind = 'live';
    label = 'Live';
    detail = `Last sample ${ageSec.toFixed(1)}s ago${
      status.sensorsInBroadcast ? '' : ' · sensors fallback'
    }`;
  }

  const dot = {
    live:         'bg-emerald-500',
    waiting:      'bg-amber-500',
    stale:        'bg-amber-500',
    demo:         'bg-ink',
    unconfigured: 'bg-graphite',
    connecting:   'bg-graphite',
  }[kind];

  return (
    <button
      type="button"
      onClick={onConfigure}
      className="flex w-full items-center justify-between rounded-2xl border border-hairline bg-parchment/70 px-5 py-4 text-left transition-colors active:bg-parchment"
      aria-label="Configure source"
    >
      <div className="flex items-center gap-3">
        <span className="relative flex h-2 w-2">
          {kind === 'live' && (
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-50" />
          )}
          <span className={`relative inline-flex h-2 w-2 rounded-full ${dot}`} />
        </span>
        <div className="flex flex-col">
          <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-ink">
            {label}
          </span>
          <span className="text-[11px] leading-tight text-graphite">{detail}</span>
        </div>
      </div>
      <Settings2 size={16} strokeWidth={1.25} className="text-graphite" />
    </button>
  );
}

function trimUrl(url) {
  // strip protocol for compactness
  return url.replace(/^wss?:\/\//, '');
}
