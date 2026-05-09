import { Sparkles, Sun, Leaf, Radar } from 'lucide-react';

const TABS = [
  { id: 'ask', label: 'Ask', Icon: Sparkles },
  { id: 'today', label: 'Today', Icon: Sun },
  { id: 'vitals', label: 'Vitals', Icon: Leaf },
  { id: 'dashboard', label: 'Dashboard', Icon: Radar },
];

export default function BottomNav({ active, onChange }) {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-50 flex justify-center px-4"
      style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 0.75rem)' }}
    >
      <div className="flex w-full max-w-md items-center justify-around rounded-full border border-ink/10 bg-parchment/70 px-2 py-1.5 shadow-[0_8px_30px_rgba(10,10,10,0.08)] backdrop-blur-md">
        {TABS.map(({ id, label, Icon }) => {
          const isActive = active === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onChange(id)}
              className={[
                'flex flex-1 items-center justify-center gap-2 rounded-full px-4 py-2.5 transition-all duration-300',
                isActive ? 'bg-ink text-parchment' : 'text-ink/60 hover:text-ink',
              ].join(' ')}
              aria-label={label}
              aria-current={isActive ? 'page' : undefined}
            >
              <Icon size={18} strokeWidth={1.25} />
              <span
                className={[
                  'text-[10px] font-medium uppercase tracking-[0.25em] transition-all',
                  isActive ? 'inline' : 'hidden sm:inline',
                ].join(' ')}
              >
                {label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}

