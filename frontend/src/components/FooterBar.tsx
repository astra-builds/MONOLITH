interface FooterBarProps {
  totalBlocks: number;
  nextEventTitle?: string;
  nextEventTime?: string;
}

export default function FooterBar({
  totalBlocks,
  nextEventTitle,
  nextEventTime,
}: FooterBarProps) {
  return (
    <footer className="h-7 bg-obsidian-950 border-t border-obsidian-750 px-3 flex items-center justify-between text-[11px] text-slate-400 shrink-0 z-40 select-none font-mono">
      {/* Left: statusline and engine status */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <span className="text-cyber-green font-black">λ</span>
          <span className="text-slate-300 font-semibold">monolith:</span>
          <span className="text-slate-400">
            {totalBlocks} scheduled blocks / SQLite local-first
          </span>
        </div>
        {nextEventTitle && (
          <>
            <span className="text-slate-600">|</span>
            <div className="flex items-center gap-1 text-slate-300">
              <span className="text-slate-500">NEXT EVENT:</span>
              <span className="text-cyber-neon font-semibold">{nextEventTitle}</span>
              {nextEventTime && (
                <span className="text-slate-500 font-mono">({nextEventTime})</span>
              )}
            </div>
          </>
        )}
      </div>

      {/* Right: vim navigation tips, zoom scale, & display protocol */}
      <div className="flex items-center gap-3">
        <div className="hidden md:flex items-center gap-2 text-slate-500">
          <span><kbd className="text-slate-400">[t]</kbd> today</span>
          <span>·</span>
          <span><kbd className="text-slate-400">[h/l]</kbd> nav</span>
          <span>·</span>
          <span><kbd className="text-slate-400">[1-5]</kbd> views</span>
          <span>·</span>
          <span className="text-slate-400 font-mono">zoom: 1h/58px</span>
        </div>
        <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-obsidian-900 border border-obsidian-750 text-cyber-neon font-bold text-[10px]">
          <span className="w-1.5 h-1.5 rounded-full bg-cyber-neon animate-pulse"></span>
          <span className="text-slate-500 hidden md:inline">WAYLAND // HYPR</span>
        </div>
      </div>
    </footer>
  );
}
