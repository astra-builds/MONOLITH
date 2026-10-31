import { useState, useEffect } from "react";
import { api } from "./api";
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
  const [completedPercent, setCompletedPercent] = useState(72);
  const [nextEvent, setNextEvent] = useState<{ title: string; time: string } | undefined>(undefined);

  const refresh = () => setRefreshKey((k) => k + 1);

  // Load telemetry stats for Waybar and FooterBar
  const loadTelemetry = async () => {
    try {
      const now = new Date();
      const todayStr = now.toISOString().slice(0, 10);
      const blocks = await api.schedule.list();
      setTotalBlocks(blocks.length);

      // Today's blocks
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
      const preview = await api.schedule.preview();
      if (preview && preview.unscheduled) {
        setConflictCount(preview.unscheduled.length);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    api.settings.get().then(setSettings).catch(console.error);
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
    <div className="h-screen w-screen flex flex-col bg-[#0a0c0f] text-zinc-300 font-mono overflow-hidden">
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
      <main className="flex-1 overflow-hidden flex flex-col bg-[#0d0f12]">
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
