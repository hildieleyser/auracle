import { useEffect, useState } from 'react';
import { X, Sparkles, Trash2 } from 'lucide-react';
import { setBridgeUrl, normaliseWsUrl } from '../../hooks/useOlmStream.js';

/**
 * Source — bottom sheet that lets the user point the dashboard at any
 * WebSocket bridge. Pasting a Cloudflare quick-tunnel URL is the canonical
 * "make it work anywhere" flow.
 */
export default function SourceSheet({ open, onClose, currentUrl }) {
  const [draft, setDraft] = useState(currentUrl || '');

  useEffect(() => { setDraft(currentUrl || ''); }, [currentUrl, open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [open, onClose]);

  function save() {
    setBridgeUrl(draft || '');
    onClose();
  }

  function clear() {
    setBridgeUrl('');
    setDraft('');
    onClose();
  }

  const preview = draft ? normaliseWsUrl(draft) : '';

  return (
    <div
      className={[
        'fixed inset-0 z-[100] transition-opacity duration-300',
        open ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0',
      ].join(' ')}
      aria-hidden={!open}
    >
      <div className="absolute inset-0 bg-ink/30" onClick={onClose} />

      <div
        className={[
          'absolute inset-x-0 bottom-0 flex flex-col rounded-t-[2rem] bg-sand shadow-[0_-30px_60px_-30px_rgba(10,10,10,0.4)] transition-transform duration-300 ease-out',
          open ? 'translate-y-0' : 'translate-y-full',
        ].join(' ')}
        style={{ height: '88dvh' }}
        role="dialog"
        aria-modal="true"
      >
        <div className="mx-auto mt-3 h-1 w-10 rounded-full bg-ink/20" />

        <header className="flex items-center justify-between px-7 pt-5">
          <span className="font-serif text-base italic text-ink">Auracle</span>
          <button
            onClick={onClose}
            aria-label="Close"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-ink/15 text-ink transition-colors hover:bg-ink hover:text-parchment"
          >
            <X size={16} strokeWidth={1.5} />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-7 pt-6">
          <div className="mx-auto flex w-full max-w-md flex-col gap-5">
            <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-graphite">
              Configuration · Source
            </span>
            <h1 className="font-serif text-5xl font-light leading-[1.05] text-ink">
              Live data, anywhere.
            </h1>
            <div className="h-px bg-hairline" />

            <p className="text-[15px] leading-[1.7] text-ink/85">
              The OLM bridge runs on the laptop attached to your sensor.
              To stream from anywhere, expose it through a tunnel and paste
              the URL below — it's saved on this device and reused every time.
            </p>

            <div className="rounded-2xl border border-hairline bg-parchment/70 p-5">
              <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-graphite">
                Quick tunnel · Cloudflare
              </span>
              <pre className="mt-3 overflow-x-auto rounded-xl bg-ink p-4 font-mono text-[12px] leading-relaxed text-parchment">
{`# 1. install (once)
brew install cloudflared

# 2. start the bridge
python server/ovlm_bridge_server.py

# 3. open a free tunnel
cloudflared tunnel --url http://localhost:8765
# → prints  https://<random>.trycloudflare.com`}
              </pre>
              <p className="mt-3 text-[13px] leading-relaxed text-graphite">
                Paste that URL below. The dashboard automatically rewrites it
                to <span className="font-mono text-ink">wss://</span> for
                WebSocket use.
              </p>
            </div>

            <div className="flex flex-col gap-2 pt-2">
              <label className="text-[10px] font-semibold uppercase tracking-[0.25em] text-graphite">
                Bridge URL
              </label>
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="https://random-name.trycloudflare.com"
                spellCheck={false}
                autoCapitalize="off"
                className="rounded-xl border border-hairline bg-parchment px-4 py-3 font-mono text-sm text-ink outline-none focus:border-ink"
              />
              {preview && preview !== draft && (
                <span className="font-mono text-[11px] text-graphite">
                  → {preview}
                </span>
              )}
            </div>

            <div className="flex flex-col gap-3 pt-2 pb-2">
              <button
                type="button"
                onClick={save}
                disabled={!draft.trim()}
                className="group flex w-full items-center justify-between rounded-full bg-ink px-7 py-5 text-parchment transition-transform active:scale-[0.99] disabled:opacity-30"
              >
                <span className="text-sm font-medium uppercase tracking-[0.25em]">
                  Connect this source
                </span>
                <Sparkles size={18} strokeWidth={1.25} />
              </button>
              {currentUrl && (
                <button
                  type="button"
                  onClick={clear}
                  className="flex w-full items-center justify-between rounded-full border border-ink/15 px-7 py-4 text-ink transition-colors hover:bg-ink hover:text-parchment"
                >
                  <span className="text-sm font-medium uppercase tracking-[0.25em]">
                    Clear saved source
                  </span>
                  <Trash2 size={16} strokeWidth={1.25} />
                </button>
              )}
            </div>

            <div className="h-2" />
          </div>
        </div>
      </div>
    </div>
  );
}
