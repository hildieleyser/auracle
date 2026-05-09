import { useEffect, useMemo, useRef, useState } from 'react';
import ChatMessage from '../components/ChatMessage.jsx';
import ChatComposer from '../components/ChatComposer.jsx';
import { useOlmStream } from '../hooks/useOlmStream.js';
import { respond } from '../data/auracleAgent.js';

const SUGGESTIONS = [
  "How's the air?",
  "What's elevated?",
  'Should I ventilate?',
  'Is this real?',
  'Tell me about CO₂',
];

export default function AskAuracleView() {
  const { latest, history, status } = useOlmStream();
  const [messages, setMessages] = useState(() => [welcome()]);
  const scrollRef = useRef(null);

  // give the agent the same reactive view the Dashboard has
  const ctxRef = useRef({ latest, history, status });
  useEffect(() => { ctxRef.current = { latest, history, status }; }, [latest, history, status]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  function ask(text) {
    if (!text || !text.trim()) return;
    const userMsg = { id: `u-${Date.now()}`, role: 'user', text };
    setMessages((prev) => [...prev, userMsg]);
    // small delay so the user sees their message land before the reply
    setTimeout(() => {
      const reply = {
        id: `a-${Date.now()}`,
        role: 'auracle',
        text: respond(text, ctxRef.current),
      };
      setMessages((prev) => [...prev, reply]);
    }, 250);
  }

  return (
    <div className="flex h-full flex-col">
      <header className="px-7 pt-10 pb-4">
        <div className="flex items-center justify-between">
          <span className="font-serif text-lg italic text-ink">Auracle</span>
          <SourcePill status={status} />
        </div>
        <h1 className="mt-3 font-serif text-4xl font-light italic text-ink">
          What's on your mind?
        </h1>
        <p className="mt-2 max-w-sm text-[13px] leading-relaxed text-graphite">
          Every answer is built from the live sensor stream. Ask about
          specific compounds, what's elevated, what to do.
        </p>
        <div className="mt-5 h-px bg-hairline" />
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5">
        <div className="mx-auto flex w-full max-w-md flex-col gap-4 pb-4">
          {messages.map((m) => (
            <ChatMessage key={m.id} role={m.role} text={m.text} />
          ))}
        </div>
      </div>

      <div
        className="mx-auto w-full max-w-md px-5 pt-2"
        style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 5.5rem)' }}
      >
        {messages.length <= 1 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => ask(s)}
                className="rounded-full border border-hairline bg-parchment/70 px-3 py-1.5 text-[12px] text-ink/80 transition-colors hover:bg-ink hover:text-parchment"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        <ChatComposer onSend={ask} />
      </div>
    </div>
  );
}

function welcome() {
  return {
    id: 'm-welcome',
    role: 'auracle',
    text:
      "Hi. I'm reading your sensor stream live — I can tell you how the air is right now, what's elevated, whether to ventilate, " +
      "or explain any specific compound (CO₂, NH₃, VOC, etc.). " +
      "Ask 'is this real?' to see exactly where the numbers are coming from.",
  };
}

function SourcePill({ status }) {
  let dot = 'bg-graphite', label = 'Source';
  if (!status.bridgeUrl) { dot = 'bg-graphite'; label = 'No source'; }
  else if (status.source === 'connecting') { dot = 'bg-amber-500'; label = 'Connecting'; }
  else if (status.source === 'demo') { dot = 'bg-ink'; label = 'Demo'; }
  else if (status.source === 'live') { dot = 'bg-emerald-500'; label = 'Live'; }
  return (
    <span className="flex items-center gap-2">
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${dot}`} />
      <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-ink">
        {label}
      </span>
    </span>
  );
}
