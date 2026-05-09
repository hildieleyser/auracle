import { useState } from 'react';
import { useOlmStream } from '../hooks/useOlmStream.js';
import StatusBar from '../components/dashboard/StatusBar.jsx';
import SourceSheet from '../components/dashboard/SourceSheet.jsx';
import RadarPanel from '../components/dashboard/RadarPanel.jsx';
import TimelinePanel from '../components/dashboard/TimelinePanel.jsx';
import AQIPanel from '../components/dashboard/AQIPanel.jsx';
import CompoundsPanel from '../components/dashboard/CompoundsPanel.jsx';
import EnvironmentPanel from '../components/dashboard/EnvironmentPanel.jsx';

/**
 * Dashboard — every panel here is a direct read of the live device stream
 * (or a transparent threshold rule on top of it). No synthesised model
 * outputs, no fabricated metrics.
 */
export default function DashboardView() {
  const { latest, history, status } = useOlmStream();
  const [sourceOpen, setSourceOpen] = useState(false);

  return (
    <>
      <div
        className="h-full overflow-y-auto"
        style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 6rem)' }}
      >
        <div className="mx-auto flex w-full max-w-md flex-col gap-9 px-7 pt-10">
          <Header />
          <StatusBar status={status} onConfigure={() => setSourceOpen(true)} />
          <RadarPanel analysis={latest} />
          <TimelinePanel history={history} />
          <AQIPanel analysis={latest} />
          <CompoundsPanel analysis={latest} />
          <EnvironmentPanel analysis={latest} />
          <Footer status={status} />
        </div>
      </div>

      <SourceSheet
        open={sourceOpen}
        onClose={() => setSourceOpen(false)}
        currentUrl={status.bridgeUrl}
      />
    </>
  );
}

function Header() {
  return (
    <header className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <span className="font-serif text-lg italic text-ink">Auracle</span>
        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-ink">
          Live
        </span>
      </div>

      <div className="h-px bg-hairline" />

      <div className="flex flex-col gap-3">
        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-graphite">
          Sensor stream
        </span>
        <h1 className="font-serif text-6xl font-light leading-[1] text-ink">
          Dashboard
        </h1>
        <p className="max-w-sm text-sm leading-relaxed text-graphite">
          Every reading the device is sending right now — gas channels,
          environmental, and the air-quality index built on top of them.
        </p>
      </div>
    </header>
  );
}

function Footer({ status }) {
  const live = status.source === 'live';
  return (
    <div className="flex items-center justify-between pt-2">
      <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-graphite">
        {live ? 'Streaming from bridge' : 'Showing simulated values'}
      </span>
      <span className="h-1.5 w-1.5 rounded-full border border-ink" />
    </div>
  );
}
