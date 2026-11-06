import { useState, useEffect } from "react";
import { format } from "date-fns";

export type ViewType = "calendar" | "projects" | "tasks" | "routines" | "settings";

interface WaybarProps {
  currentView: ViewType;
  onViewChange: (v: ViewType) => void;
  conflictCount: number;
  completedPercent: number;
  onOpenCommandBar?: () => void;
  onSeedDemo?: () => void;
}

export default function Waybar({
  currentView,
  onViewChange,
  conflictCount,
  completedPercent,
  onOpenCommandBar,
  onSeedDemo,
}: WaybarProps) {
  const [timeStr, setTimeStr] = useState<string>("");
  const [dateStr, setDateStr] = useState<string>("");

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTimeStr(format(now, "HH:mm:ss"));
      setDateStr(format(now, "yyyy-MM-dd"));
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  const WORKSPACES: { id: ViewType; num: number; label: string }[] = [
    { id: "calendar", num: 1, label: "cal" },
    { id: "projects", num: 2, label: "projects" },
    { id: "tasks", num: 3, label: "tasks" },
    { id: "routines", num: 4, label: "routines" },
    { id: "settings", num: 5, label: "config" },
  ];

  const dayDone = Math.round(completedPercent);

  return (
    <header className="h-10 bg-obsidian-950 border-b border-obsidian-750 flex items-center justify-between px-3 text-xs tracking-wider shrink-0 z-40 select-none font-mono">
      {/* Left: window controls + app tabs + active file path */}
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-1.5 pr-2 border-r border-obsidian-700/60">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80"></span>
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80"></span>
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80"></span>
        </div>
        <nav className="flex items-center space-x-1">
          {WORKSPACES.map((ws) => {
            const active = currentView === ws.id;
            return (
              <button
                key={ws.id}
                onClick={() => onViewChange(ws.id)}
                className={`px-2.5 py-1 rounded font-semibold flex items-center gap-1.5 transition ${
                  active
                    ? "bg-obsidian-800 text-cyber-neon border border-cyber-neon/40 shadow-[0_0_10px_rgba(57,255,20,0.15)]"
                    : "hover:bg-obsidian-800 text-slate-400 hover:text-slate-200"
                }`}
                title={`Switch to workspace ${ws.num} (${ws.label})`}
              >
                <span className={`text-[10px] font-bold opacity-80 ${active ? "text-emerald-400" : "text-slate-500"}`}>
                  {ws.num}:
                </span>
                {ws.label}
              </button>
            );
          })}
        </nav>
        <div className="hidden lg:flex items-center gap-1 text-[11px] text-slate-400 bg-obsidian-900 px-2 py-0.5 rounded border border-obsidian-750">
          <span className="text-cyber-green font-bold">λ</span>
          <span className="text-slate-300 font-mono">~/dotfiles/routine.sh</span>
        </div>
      </div>

      {/* Right: datetime + day-done pill + quick triggers + telemetry */}
      <div className="flex items-center space-x-3 text-[11px]">
        <div className="flex items-center gap-2 bg-obsidian-900 border border-obsidian-750 px-2.5 py-0.5 rounded font-medium">
          <span className="text-slate-400">{dateStr}</span>
          <span className="text-cyber-cyan font-semibold tabular-nums">{timeStr}</span>
          <span className="inline-flex items-center px-1.5 py-0.2 rounded text-[10px] bg-emerald-950/80 text-emerald-400 border border-emerald-700/50">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1 animate-pulse"></span>
            {dayDone}% DAY DONE
          </span>
        </div>
        <div className="flex items-center gap-1">
          {onOpenCommandBar && (
            <button
              onClick={onOpenCommandBar}
              className="px-2.5 py-1 bg-obsidian-850 hover:bg-obsidian-750 border border-obsidian-700 rounded text-slate-300 hover:text-white transition flex items-center gap-1 text-[10px]"
              title="Open Natural Language Planner (Ctrl+K)"
            >
              <span className="text-cyber-purple font-bold">⌘K</span> PLANNER
            </button>
          )}
          {onSeedDemo && (
            <button
              onClick={onSeedDemo}
              className="px-2 py-1 bg-obsidian-850 hover:bg-obsidian-750 border border-obsidian-700 rounded text-cyan-400 hover:text-cyan-300 transition text-[10px]"
              title="Seed Scenario A & B Demo Data"
            >
              SEED DEMO
            </button>
          )}
        </div>
        <div className="hidden xl:flex items-center gap-2 text-slate-400 text-[10px] pl-2 border-l border-obsidian-750">
          <span>CPU <strong className="text-emerald-400 font-semibold">12%</strong></span>
          <span>RAM <strong className="text-cyan-400 font-semibold">4.2G</strong></span>
          <span className="flex items-center gap-1 text-slate-400">
            <span className="w-1.5 h-1.5 rounded-full bg-cyber-green"></span>
            <span className="text-slate-500 text-[10px] hidden md:inline">monolith @ local</span>
          </span>
        </div>
      </div>
    </header>
  );
}
