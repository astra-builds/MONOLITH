import { useState, useEffect } from "react";
import { api, guard, setErrorHandler } from "./api";
import CalendarView from "./CalendarView";
import ProjectsView from "./ProjectsView";
import TasksView from "./TasksView";
import CommitmentsView from "./CommitmentsView";
import SettingsView from "./SettingsView";
import CommandBar from "./CommandBar";
import Waybar, { type ViewType } from "./components/Waybar";
import FooterBar from "./components/FooterBar";

export default function App() {
  const [view, setView] = useState<ViewType>("calendar");
  const [settings, setSettings] = useState<any>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [showCommandBar, setShowCommandBar] = useState(true);
  const [totalBlocks, setTotalBlocks] = useState(0);
  const [conflictCount, setConflictCount] = useState(0);
  const [completedPercent, setCompletedPercent] = useState(0);
  const [nextEvent, setNextEvent] = useState<{ title: string; time: string } | undefined>(undefined);
  const [apiError, setApiError] = useState<string | null>(null);

  const refresh = () => setRefreshKey((k) => k + 1);

  // Surface API failures in a shared banner instead of silent console errors.
  useEffect(() => {
    setErrorHandler((message: string) => {
      setApiError(message);
      setTimeout(() => setApiError(null), 5000);
    });
  }, []);

  const clearError = () => setApiError(null);

  // Load telemetry stats for Waybar and FooterBar
  const loadTelemetry = async () => {
    const blocks = await guard(api.schedule.list(), "schedule list");
    if (!blocks) return;
    setTotalBlocks(blocks.length);

    // Today's blocks
    const now = new Date();
    const todayStr = now.toISOString().slice(0, 10);
    const todayBlocks = blocks.filter((b: any) => b.start_dt.slice(0, 10) === todayStr);
    if (todayBlocks.length > 0) {
      const completed = todayBlocks.filter((b: any) => b.status === "completed").length;
      setCompletedPercent(Math.round((completed / todayBlocks.length) * 100));
    }

    // Next upcoming event
    const upcoming = blocks
      .filter((b: any) => new Date(b.start_dt) > now && b.status === "scheduled")
      .sort((a: any, b: any) => a.start_dt.localeCompare(b.start_dt))[0];

    if (upcoming) {
      const diffMs = new Date(upcoming.start_dt).getTime() - now.getTime();
      const diffMins = Math.round(diffMs / 60000);
      const h = Math.floor(diffMins / 60);
      const m = diffMins % 60;
      setNextEvent({
        title: upcoming.title,
        time: h > 0 ? `in ${h}h ${m}m` : `in ${m}m`,
      });
    }

    // Check conflicts from preview
    const preview = await guard(api.schedule.preview(), "schedule preview");
    if (preview && preview.unscheduled) {
      setConflictCount(preview.unscheduled.length);
    }
  };

  useEffect(() => {
    guard(api.settings.get(), "settings get").then(setSettings);
    loadTelemetry();
  }, [refreshKey]);

  // Keyboard shortcut for CommandBar toggle (Ctrl+K or Cmd+K)
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setShowCommandBar((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  const handleSeedDemo = async () => {
    if (!confirm("Load Scenario A (Agentic AI Course) & Scenario B (University Timetable) demo data?")) {
      return;
    }
    try {
      await api.demo.seed();
      await api.schedule.apply();
      refresh();
    } catch (e: any) {
      alert("Error seeding demo: " + e.message);
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-[#080b0d] text-slate-300 font-mono select-none antialiased overflow-hidden">
      {apiError && (
        <div className="bg-[#3a1419] border-b border-[#7d222e] text-[#ff7d8d] px-3 py-1.5 text-[10px] font-mono flex items-center justify-between shrink-0">
          <span>API ERROR</span>
          <div className="flex items-center gap-1">
            <span className="truncate max-w-xs">{apiError}</span>
            <button onClick={clearError} className="ml-2 hover:text-white">✕</button>
          </div>
        </div>
      )}
      {/* Waybar / Hyprland Status Bar */}
      <Waybar
        currentView={view}
        onViewChange={setView}
        conflictCount={conflictCount}
        completedPercent={completedPercent}
        onOpenCommandBar={() => setShowCommandBar((v) => !v)}
        onSeedDemo={handleSeedDemo}
      />

      {/* Command / Planning Input */}
      {showCommandBar && (
        <CommandBar
          onApplied={() => {
            refresh();
          }}
        />
      )}

      {/* Main Content Area */}
      <main className="flex-1 overflow-hidden flex flex-col">
        {view === "calendar" && <CalendarView key={refreshKey} />}
        {view === "projects" && <ProjectsView key={refreshKey} onChange={refresh} />}
        {view === "tasks" && <TasksView key={refreshKey} onChange={refresh} />}
        {view === "routines" && <CommitmentsView key={refreshKey} onChange={refresh} />}
        {view === "settings" && (
          <div className="flex-1 overflow-y-auto p-4 flex justify-center">
            <SettingsView
              key={refreshKey}
              settings={settings}
              onChange={(s: any) => {
                setSettings(s);
                refresh();
              }}
            />
          </div>
        )}
      </main>

      {/* Bottom Footer Status Bar */}
      <FooterBar
        totalBlocks={totalBlocks}
        nextEventTitle={nextEvent?.title}
        nextEventTime={nextEvent?.time}
      />
    </div>
  );
}
