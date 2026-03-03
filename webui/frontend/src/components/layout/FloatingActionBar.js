import { Play, Square, RotateCcw, AlertTriangle } from 'lucide-react';
import clsx from 'clsx';

function FloatingActionBar({
  onStart,
  onStop,
  onRestart,
  onEmergency,
  running = false,
  loading = false,
  isMobile = false,
}) {
  if (isMobile) {
    return (
      <div
        className="fixed inset-x-0 bottom-3 z-50 px-4 animate-slide-up-spring"
        style={{
          paddingBottom: `calc(env(safe-area-inset-bottom) + 0.75rem)`,
        }}
      >
        <div className="flex items-stretch justify-between gap-2 rounded-2xl border border-slate-800/70 bg-slate-950/90 px-3 py-2 shadow-2xl backdrop-blur">
          <button
            type="button"
            onClick={onStart}
            disabled={loading || running}
            className={clsx(
              'flex flex-1 flex-col items-center justify-center gap-1 rounded-xl px-2 py-2 text-[11px] font-semibold transition',
              running
                ? 'cursor-not-allowed border border-emerald-500/10 bg-emerald-900/10 text-emerald-300/60'
                : 'border border-emerald-500/20 bg-emerald-500/10 text-emerald-200 hover:border-emerald-400 hover:bg-emerald-500/20'
            )}
          >
            <Play className="h-4 w-4" />
            Start
          </button>
          <button
            type="button"
            onClick={onStop}
            disabled={loading || !running}
            className={clsx(
              'flex flex-1 flex-col items-center justify-center gap-1 rounded-xl px-2 py-2 text-[11px] font-semibold transition',
              !running
                ? 'cursor-not-allowed border border-rose-500/10 bg-rose-900/10 text-rose-200/60'
                : 'border border-rose-500/30 bg-rose-500/10 text-rose-200 hover:border-rose-400 hover:bg-rose-500/20'
            )}
          >
            <Square className="h-4 w-4" />
            Stop
          </button>
          <button
            type="button"
            onClick={onRestart}
            disabled={loading}
            className={clsx(
              'flex flex-1 flex-col items-center justify-center gap-1 rounded-xl px-2 py-2 text-[11px] font-semibold transition',
              loading
                ? 'cursor-not-allowed border border-sky-500/10 bg-sky-500/10 text-sky-200/60'
                : 'border border-sky-500/30 bg-sky-500/10 text-sky-200 hover:border-sky-400 hover:bg-sky-500/20'
            )}
          >
            <RotateCcw className="h-4 w-4" />
            Restart
          </button>
          <button
            type="button"
            onClick={onEmergency}
            className="flex flex-1 flex-col items-center justify-center gap-1 rounded-xl border border-amber-500/30 bg-amber-500/10 px-2 py-2 text-[11px] font-semibold text-amber-100 transition hover:border-amber-400 hover:bg-amber-500/20"
          >
            <AlertTriangle className="h-4 w-4" />
            Emergency
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className="fixed bottom-5 inset-x-0 z-40 flex justify-center px-4 animate-slide-up-spring"
      style={{
        paddingBottom: `calc(env(safe-area-inset-bottom) + 1.25rem)`,
      }}
    >
      <div
        className={clsx(
          'flex w-full max-w-xl items-center justify-between gap-3 rounded-2xl border border-slate-800/70 bg-slate-900/95 p-3 shadow-2xl backdrop-blur',
          isMobile ? 'flex-col gap-2 p-4' : 'flex-row'
        )}
      >
        <button
          type="button"
          onClick={onStart}
          disabled={loading || running}
          className={clsx(
            'flex flex-1 items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition w-full',
            running
              ? 'cursor-not-allowed border border-emerald-500/20 bg-emerald-900/20 text-emerald-400/60'
              : 'border border-emerald-400/40 bg-emerald-500/10 text-emerald-200 hover:border-emerald-300 hover:bg-emerald-500/20'
          )}
        >
          <Play className="h-4 w-4" />
          Start
        </button>
        <button
          type="button"
          onClick={onStop}
          disabled={loading || !running}
          className={clsx(
            'flex flex-1 items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition w-full',
            !running
              ? 'cursor-not-allowed border border-rose-500/20 bg-rose-900/20 text-rose-300/60'
              : 'border border-rose-500/40 bg-rose-500/10 text-rose-200 hover:border-rose-400 hover:bg-rose-500/20'
          )}
        >
          <Square className="h-4 w-4" />
          Stop
        </button>
        <button
          type="button"
          onClick={onRestart}
          disabled={loading}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-sky-400/40 bg-sky-500/10 px-4 py-2 text-sm font-semibold text-sky-200 transition hover:border-sky-300 hover:bg-sky-500/20 disabled:cursor-not-allowed disabled:opacity-60 w-full"
        >
          <RotateCcw className="h-4 w-4" />
          Restart
        </button>
        <button
          type="button"
          onClick={onEmergency}
          className={clsx(
            'items-center justify-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-sm font-semibold text-amber-100 transition hover:border-amber-400 hover:bg-amber-500/20 w-full',
            isMobile ? 'flex' : 'hidden lg:flex'
          )}
        >
          <AlertTriangle className="h-4 w-4" />
          Emergency
        </button>
      </div>
    </div>
  );
}

export default FloatingActionBar;
