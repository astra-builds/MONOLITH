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
    <footer className="h-6 w-full bg-[#0a0c0f] border-t border-[#232733] px-3 flex items-center justify-between text-[9px] font-mono select-none shrink-0 text-zinc-400">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 text-zinc-300">
          <span className="text-[#c5ff42] font-bold">λ</span>
          <span>monolith: {totalBlocks} scheduled blocks / SQLite local-first</span>
        </div>
        {nextEventTitle && (
          <>
            <span className="text-[#232733]">|</span>
            <div className="flex items-center gap-1">
              <span className="text-zinc-500">NEXT EVENT:</span>
              <span className="text-white font-bold">{nextEventTitle}</span>
              {nextEventTime && (
                <span className="text-zinc-400">({nextEventTime})</span>
              )}
            </div>
          </>
        )}
      </div>

      <div className="flex items-center gap-3">
        <span className="hidden sm:inline text-zinc-500">[t] today · [h/l] nav · [1-3] views</span>
        <span className="text-[#232733] hidden sm:inline">|</span>
        <span>zoom: <strong className="text-zinc-200">1h/56px</strong></span>
        <span className="text-[#232733]">|</span>
        <div className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-[#c5ff42]"></span>
          <span className="text-[#c5ff42] font-bold tracking-wider">WAYLAND // HYPR</span>
        </div>
      </div>
    </footer>
  );
}
