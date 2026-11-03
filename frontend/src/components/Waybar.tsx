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
      setDateStr(format(now, "yyyy-MM-dd EEE"));
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

  return (
    <header className="h-8 w-full bg-[#0a0c0f] border-b border-[#232733] flex items-center justify-between px-2 text-[10px] tracking-wide select-none z-50 shrink-0 font-mono">
      {/* Left: Workspaces + Routine path + Scrubber timestamp + Completion Pill */}
      <div className="flex items-center gap-2">
        {/* Workspaces */}
        <div className="flex items-center bg-[#14171f] p-0.5 rounded border border-[#232733]">
          {WORKSPACES.map((ws) => {
            const active = currentView === ws.id;
            return (
              <button
                key={ws.id}
                onClick={() => onViewChange(ws.id)}
                className={`px-1.5 py-0.5 font-bold text-[9px] rounded-sm transition-colors ${
                  active
                    ? "bg-[#8b61c9] text-white shadow"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
                title={`Switch to workspace ${ws.num} (${ws.label})`}
              >
                {ws.num}:{ws.label}
              </button>
            );
          })}
        </div>

        {/* Command / Routine path indicator */}
        <div className="hidden md:flex items-center gap-1 bg-[#14171f] px-2 py-0.5 rounded border border-[#232733] text-zinc-400">
          <span className="text-[#c5ff42] font-bold">λ</span>
          <span className="text-zinc-300 font-mono">~/dotfiles/routine.sh</span>
        </div>

        {/* Live Scrubber Timestamp */}
        <div className="flex items-center gap-1 bg-[#14171f] px-2 py-0.5 rounded border border-[#232733] text-zinc-300 font-medium">
          <span className="text-zinc-400">{dateStr}</span>
          <span className="text-white font-bold tabular-nums">{timeStr}</span>
        </div>

        {/* Completion / Workload Pill */}
        <div
          className={`flex items-center gap-1.5 px-2 py-0.5 rounded font-bold text-[9px] border ${
            conflictCount > 0
              ? "bg-[#3a181d] border-[#7d222e] text-[#ff7d8d]"
              : "bg-[#172514] border-[#3b661d] text-[#c5ff42]"
          }`}
          title={conflictCount > 0 ? `${conflictCount} scheduling conflicts require attention` : "Schedule status"}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              conflictCount > 0
                ? "bg-[#ff4a68] animate-pulse"
                : "bg-[#c5ff42] animate-pulse"
            }`}
          />
          <span>
            {conflictCount > 0
              ? `! ${conflictCount} CONFLICT${conflictCount > 1 ? "S" : ""}`
              : `${Math.round(completedPercent)}% DAY COMPLETED`}
          </span>
        </div>
      </div>

      {/* Center Breadcrumbs / Navigation */}
      <nav className="hidden xl:flex items-center gap-3 text-[10px] font-bold text-zinc-400 uppercase">
        {WORKSPACES.map((ws) => (
          <button
            key={ws.id}
            onClick={() => onViewChange(ws.id)}
            className={`transition-colors pb-0.5 ${
              currentView === ws.id
                ? "text-white border-b border-[#c5ff42]"
                : "hover:text-white"
            }`}
          >
            {ws.label}
          </button>
        ))}
      </nav>

      {/* Right: Telemetry & Status Badges */}
      <div className="flex items-center gap-2">
        {/* Planner Quick Trigger */}
        {onOpenCommandBar && (
          <button
            onClick={onOpenCommandBar}
            className="hidden sm:flex items-center gap-1.5 px-2 py-0.5 bg-[#14171f] hover:bg-[#202635] text-zinc-300 hover:text-white rounded border border-[#232733] transition-colors text-[9px]"
            title="Open Natural Language Planner (Ctrl+K)"
          >
            <span className="text-[#c5ff42] font-black">■</span>
            <span>⌘K / PLANNER</span>
          </button>
        )}

        {/* Demo Seed Quick Trigger */}
        {onSeedDemo && (
          <button
            onClick={onSeedDemo}
            className="hidden lg:flex items-center gap-1 px-1.5 py-0.5 bg-[#1c2738] hover:bg-[#283850] text-[#73a7f7] rounded border border-[#3b5880] text-[9px]"
            title="Seed Scenario A & B Demo Data"
          >
            <span>⟳ SEED DEMO</span>
          </button>
        )}

        {/* Arch & Network telemetry status (decorative) */}
        <div className="hidden sm:flex items-center gap-2 bg-[#14171f] px-2 py-0.5 rounded border border-[#232733] text-zinc-400 font-mono text-[9px]">
          <span className="opacity-50">DECORATIVE</span>
          <span>CPU <strong className="text-zinc-200">12%</strong></span>
          <span className="text-[#232733]">|</span>
          <span>RAM <strong className="text-zinc-200">4.2G</strong></span>
        </div>

        {/* Status indicator */}
        <div className="flex items-center gap-1.5 text-zinc-400 pl-1">
          <span className="w-1.5 h-1.5 rounded-full bg-[#c5ff42]"></span>
          <span className="text-zinc-500 text-[10px] hidden md:inline">monolith @ local</span>
        </div>
      </div>
    </header>
  );
}
