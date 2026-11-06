import { useState, useEffect, useMemo } from "react";
import {
  format,
  startOfWeek,
  endOfWeek,
  addDays,
  addWeeks,
  subWeeks,
  addMonths,
  subMonths,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  isSameDay,
  isToday,
} from "date-fns";
import { api } from "./api";

type ViewMode = "day" | "week" | "month";

interface ScheduleBlock {
  id: number;
  task_id?: number | null;
  commitment_id?: number | null;
  title: string;
  tag: string;
  start_dt: string;
  end_dt: string;
  status: string;
  locked: boolean;
  reason?: string;
}

interface UnscheduledTask {
  task_id: number;
  title: string;
  reason: string;
}

const HOUR_HEIGHT = 58; // 58px per hour, matching the redesign spec
const START_HOUR = 7; // 07:00
const END_HOUR = 22; // 22:00
const TOTAL_HOURS = END_HOUR - START_HOUR;

const VIEW_MODES: ViewMode[] = ["day", "week", "month"];

export default function CalendarView() {
  const [currentDate, setCurrentDate] = useState<Date>(new Date());
  const [viewMode, setViewMode] = useState<ViewMode>("week");
  const [blocks, setBlocks] = useState<ScheduleBlock[]>([]);
  const [unscheduled, setUnscheduled] = useState<UnscheduledTask[]>([]);
  const [selectedBlock, setSelectedBlock] = useState<ScheduleBlock | null>(null);
  const [filterTag, setFilterTag] = useState<string>("all");
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [showNewModal, setShowNewModal] = useState(false);
  const [newTask, setNewTask] = useState({
    title: "",
    estimated_minutes: 60,
    preferred_days: [] as number[],
    deadline: "",
    priority: 3,
  });

  const loadSchedule = async () => {
    setLoading(true);
    try {
      let rangeStart: Date, rangeEnd: Date;
      if (viewMode === "month") {
        rangeStart = subWeeks(startOfMonth(currentDate), 1);
        rangeEnd = addWeeks(endOfMonth(currentDate), 1);
      } else {
        rangeStart = subWeeks(startOfWeek(currentDate, { weekStartsOn: 1 }), 2);
        rangeEnd = addWeeks(endOfWeek(currentDate, { weekStartsOn: 1 }), 4);
      }
      const data = await api.schedule.list(rangeStart.toISOString(), rangeEnd.toISOString());
      setBlocks(data);

      const preview = await api.schedule.preview();
      if (preview && preview.unscheduled) {
        setUnscheduled(preview.unscheduled);
      }
    } catch (err: any) {
      console.error(err);
      setStatusMsg(err.message || "Failed to load schedule");
    }
    setLoading(false);
  };

  useEffect(() => {
    loadSchedule();
  }, [currentDate]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(tag)) return;
      if (e.target instanceof HTMLInputElement && e.target.type === "checkbox") return;
      if (e.key === "t") {
        setCurrentDate(new Date());
      } else if (e.key === "h") {
        navigate(-1);
      } else if (e.key === "l") {
        navigate(1);
      } else if (e.key === "1") {
        setViewMode("day");
      } else if (e.key === "2") {
        setViewMode("week");
      } else if (e.key === "3") {
        setViewMode("month");
      } else if (e.key === "r") {
        regeneratePreview();
      } else if (e.key === "n") {
        setShowNewModal(true);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [viewMode, currentDate]);

  const navigate = (direction: number) => {
    if (viewMode === "day") {
      setCurrentDate((d) => addDays(d, direction));
    } else if (viewMode === "week") {
      setCurrentDate((d) => addWeeks(d, direction));
    } else {
      setCurrentDate((d) => (direction > 0 ? addMonths(d, 1) : subMonths(d, 1)));
    }
  };

  const regenerate = async () => {
    setLoading(true);
    setStatusMsg("Regenerating schedule...");
    try {
      await api.schedule.apply();
      await loadSchedule();
      setStatusMsg("Schedule recalculated.");
    } catch (err: any) {
      setStatusMsg("Regen failed: " + err.message);
    }
    setLoading(false);
  };

  const regeneratePreview = async () => {
    setLoading(true);
    setStatusMsg("Previewing schedule changes...");
    try {
      await api.schedule.preview();
      await loadSchedule();
      setStatusMsg("Preview regenerated (not applied).");
    } catch (err: any) {
      setStatusMsg("Preview failed: " + err.message);
    }
    setLoading(false);
  };

  const rescheduleMissed = async () => {
    setLoading(true);
    setStatusMsg("Rescheduling missed sessions...");
    try {
      const res = await api.schedule.rescheduleMissed();
      await loadSchedule();
      setStatusMsg(`Rescheduled ${res.missed_count} missed session(s).`);
    } catch (err: any) {
      setStatusMsg("Failed: " + err.message);
    }
    setLoading(false);
  };

  const markComplete = async (block: ScheduleBlock) => {
    if (block.task_id) {
      await api.tasks.complete(block.task_id);
    } else {
      await api.schedule.updateBlock(block.id, { status: "completed" });
    }
    setSelectedBlock(null);
    loadSchedule();
  };

  const markSkip = async (block: ScheduleBlock) => {
    if (block.task_id) {
      await api.tasks.skip(block.task_id);
    } else {
      await api.schedule.updateBlock(block.id, { status: "skipped" });
    }
    setSelectedBlock(null);
    loadSchedule();
  };

  const moveBlockDays = async (block: ScheduleBlock, daysOffset: number) => {
    const s = new Date(block.start_dt);
    const e = new Date(block.end_dt);
    s.setDate(s.getDate() + daysOffset);
    e.setDate(e.getDate() + daysOffset);
    await api.schedule.updateBlock(block.id, {
      start_dt: s.toISOString(),
      end_dt: e.toISOString(),
      locked: true,
    });
    loadSchedule();
  };

  const deleteBlock = async (block: ScheduleBlock) => {
    if (!confirm(`Delete activity "${block.title}"?`)) return;
    await api.schedule.deleteBlock(block.id);
    setSelectedBlock(null);
    loadSchedule();
  };

  const createQuickTask = async () => {
    if (!newTask.title.trim()) return;
    await api.tasks.create({
      title: newTask.title,
      estimated_minutes: Number(newTask.estimated_minutes),
      remaining_minutes: Number(newTask.estimated_minutes),
      deadline: newTask.deadline || null,
      priority: Number(newTask.priority),
      preferred_days: newTask.preferred_days,
      splittable: true,
      flexible: true,
    });
    setShowNewModal(false);
    setNewTask({ title: "", estimated_minutes: 60, preferred_days: [], deadline: "", priority: 3 });
    regenerate();
  };

  const weekStart = useMemo(
    () => startOfWeek(currentDate, { weekStartsOn: 1 }),
    [currentDate]
  );
  const weekDays = useMemo(
    () => Array.from({ length: 7 }).map((_, i) => addDays(weekStart, i)),
    [weekStart]
  );

  const monthDays = useMemo(() => {
    const s = startOfWeek(startOfMonth(currentDate), { weekStartsOn: 1 });
    const e = endOfWeek(endOfMonth(currentDate), { weekStartsOn: 1 });
    return eachDayOfInterval({ start: s, end: e });
  }, [currentDate]);

  const visibleBlocks = useMemo(() => {
    if (filterTag === "all") return blocks;
    return blocks.filter((b) => b.tag === filterTag);
  }, [blocks, filterTag]);

  const dailyWorkload = useMemo(() => {
    const map: Record<string, number> = {};
    for (const d of weekDays) {
      const key = format(d, "yyyy-MM-dd");
      map[key] = 0;
    }
    for (const b of blocks) {
      const bDate = b.start_dt.slice(0, 10);
      if (map[bDate] !== undefined) {
        const dur = (new Date(b.end_dt).getTime() - new Date(b.start_dt).getTime()) / 60000;
        map[bDate] += Math.round(dur);
      }
    }
    return map;
  }, [blocks, weekDays]);

  const telemetry = useMemo(() => {
    let totalMinutes = 0;
    let deepWorkMinutes = 0;
    const vectorMinutes: Record<string, number> = {
      university: 0,
      course: 0,
      project: 0,
      personal: 0,
    };

    for (const b of visibleBlocks) {
      const dur = (new Date(b.end_dt).getTime() - new Date(b.start_dt).getTime()) / 60000;
      totalMinutes += dur;
      if (b.tag === "course" || b.tag === "project") {
        deepWorkMinutes += dur;
      }
      const tag = b.tag in vectorMinutes ? b.tag : "personal";
      vectorMinutes[tag] += dur;
    }

    const totalHours = (totalMinutes / 60).toFixed(1);
    const deepHours = (deepWorkMinutes / 60).toFixed(1);
    const deepPercent = totalMinutes ? Math.round((deepWorkMinutes / totalMinutes) * 100) : 0;

    return { totalHours, deepHours, deepPercent, vectorMinutes, totalMinutes };
  }, [visibleBlocks]);

  const now = new Date();
  const isCurrentWeek = weekDays.some((d) => isSameDay(d, now));
  const currentHourDecimal = now.getHours() + now.getMinutes() / 60;
  const scrubberTop = (currentHourDecimal - START_HOUR) * HOUR_HEIGHT;

  const tagAccent = (tag: string) => {
    switch (tag) {
      case "university":
        return {
          text: "text-cyber-purple",
          border: "border-l-cyber-purple",
          bg: "bg-cyber-purple/15",
          hoverBg: "hover:bg-cyber-purple/25",
          borderAll: "border border-cyber-purple/40",
        };
      case "course":
      case "project":
        return {
          text: "text-cyber-cyan",
          border: "border-l-cyber-cyan",
          bg: "bg-cyan-950/40",
          hoverBg: "hover:bg-cyan-900/40",
          borderAll: "border border-cyber-cyan/40",
        };
      case "personal":
      case "health":
        return {
          text: "text-cyber-amber",
          border: "border-l-amber-500",
          bg: "bg-amber-950/30",
          hoverBg: "hover:bg-amber-900/40",
          borderAll: "border border-amber-500/40",
        };
      default:
        return {
          text: "text-slate-400",
          border: "border-l-slate-400",
          bg: "bg-slate-800/40",
          hoverBg: "hover:bg-slate-800/60",
          borderAll: "border border-slate-700",
        };
    }
  };

  const getBlockStyle = (block: ScheduleBlock) => {
    const isSelected = selectedBlock?.id === block.id;
    const a = tagAccent(block.tag);
    let statusOverride = "";

    if (block.status === "completed") {
      statusOverride = "bg-[#132218]/80 border-[#2f5934] text-[#86efac] opacity-75";
    } else if (block.status === "missed" || block.status === "skipped") {
      statusOverride = "bg-[#3a131a]/90 border-[#e0314b] text-[#ff7d8d]";
    }

    const base = `${a.bg} ${a.hoverBg} ${a.border} ${a.borderAll} rounded p-2 text-xs flex flex-col justify-between cursor-pointer transition hover:scale-[1.01] z-10 ${statusOverride}`;
    const selectedExtra = isSelected
      ? "border-2 border-cyber-green border-l-4 border-l-cyber-neon shadow-[0_0_20px_rgba(57,255,20,0.25)] z-20"
      : "";
    return `${base} ${selectedExtra}`;
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-obsidian-950 text-slate-300 font-mono text-[11px] select-none">
      {/* TIMELINE CONTROLS BAR */}
      <div className="h-12 bg-obsidian-850 border-b border-obsidian-750 px-3 flex items-center justify-between gap-3 shrink-0 z-20">
        <div className="flex items-center gap-2">
          {/* View switcher */}
          <div className="flex items-center bg-obsidian-950 p-0.5 rounded border border-obsidian-750">
            {VIEW_MODES.map((v, i) => (
              <button
                key={v}
                onClick={() => setViewMode(v)}
                className={`px-2.5 py-1 text-xs rounded transition font-medium ${
                  viewMode === v
                    ? "bg-obsidian-750 text-cyber-neon font-semibold border border-cyber-neon/30 shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {i + 1}: {v.toUpperCase()}
              </button>
            ))}
          </div>
          {/* Active range badge */}
          <div className="flex items-center gap-2 bg-obsidian-900 border border-obsidian-700/80 px-2.5 py-1 rounded text-xs">
            <span className="px-1.5 py-0.2 bg-obsidian-800 text-cyber-cyan text-[10px] rounded font-bold border border-cyber-cyan/30">
              W{format(currentDate, "w")}
            </span>
            <span className="font-bold text-slate-200 tracking-tight">
              {viewMode === "week"
                ? `${format(weekStart, "MMM d")} — ${format(addDays(weekStart, 6), "MMM d, yyyy")}`
                : viewMode === "day"
                ? format(currentDate, "EEEE, MMMM d, yyyy")
                : format(currentDate, "MMMM yyyy")}
            </span>
          </div>
          {/* Nav controls */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => navigate(-1)}
              className="h-8 px-2.5 bg-obsidian-800 hover:bg-obsidian-700 text-slate-300 hover:text-white border border-obsidian-700 rounded text-xs flex items-center gap-1 transition"
              title="Previous Week [h]"
            >
              <span className="text-[10px] text-slate-500 font-bold">[h]</span> PREV
            </button>
            <button
              onClick={() => setCurrentDate(new Date())}
              className="h-8 px-3 bg-cyber-green/10 hover:bg-cyber-green/20 text-cyber-green hover:text-cyber-neon border border-cyber-green/40 rounded text-xs font-semibold flex items-center gap-1 transition"
              title="Jump to Today [t]"
            >
              <span className="text-[10px] text-cyber-green/80 font-bold">[t]</span> TODAY
            </button>
            <button
              onClick={() => navigate(1)}
              className="h-8 px-2.5 bg-obsidian-800 hover:bg-obsidian-700 text-slate-300 hover:text-white border border-obsidian-700 rounded text-xs flex items-center gap-1 transition"
              title="Next Week [l]"
            >
              <span className="text-[10px] text-slate-500 font-bold">[l]</span> NEXT
            </button>
          </div>
          <button
            onClick={regeneratePreview}
            disabled={loading}
            className="h-8 px-2.5 bg-obsidian-800 hover:bg-obsidian-700 text-slate-300 hover:text-white border border-obsidian-700 rounded text-xs flex items-center gap-1.5 transition"
            title="Regenerate Preview [r]"
          >
            <span className="text-cyber-cyan text-[10px] font-bold">@ REGEN</span>
            <span className="text-[10px] text-slate-500">[r]</span>
          </button>
          <button
            onClick={() => setShowNewModal(true)}
            className="h-8 px-3.5 bg-emerald-600 hover:bg-emerald-500 text-obsidian-950 font-bold text-xs rounded border border-emerald-400 flex items-center gap-1.5 shadow-[0_0_10px_rgba(16,185,129,0.25)] transition"
            title="Add New Block [n]"
          >
            <span>+ NEW BLOCK</span>
            <span className="text-[10px] bg-obsidian-950/30 px-1 rounded text-obsidian-950 font-mono">[n]</span>
          </button>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden 2xl:flex items-center gap-3 text-xs bg-obsidian-900/90 px-3 py-1 rounded border border-obsidian-750">
            <span className="text-slate-400">TOTAL: <strong className="text-slate-200">{telemetry.totalHours}h</strong></span>
            <span className="text-slate-500">|</span>
            <span className="text-slate-400">DEEP WORK: <strong className="text-cyber-cyan">{telemetry.deepHours}h ({telemetry.deepPercent}%)</strong></span>
            <span className={`text-emerald-400 flex items-center gap-1 ${unscheduled.length > 0 ? "text-[#ff7d8d] font-bold" : ""}`}>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              {unscheduled.length} CONFLICTS
            </span>
          </div>
          <div className="flex items-center gap-1 bg-obsidian-950 p-0.5 rounded border border-obsidian-750 text-xs">
            <span className="text-[10px] text-slate-500 px-1 font-semibold uppercase">FILTER:</span>
            {["all", "university", "course", "project", "personal"].map((t) => (
              <button
                key={t}
                onClick={() => setFilterTag(t)}
                className={`px-2 py-0.5 rounded text-[11px] transition ${
                  filterTag === t
                    ? "bg-obsidian-750 text-cyber-neon font-bold border border-cyber-neon/30"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {t.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      {statusMsg && (
        <div className="bg-[#1b2318] border-b border-[#3b661d] text-[#c5ff42] px-3 py-1 text-[10px] flex items-center justify-between shrink-0">
          <span>{statusMsg}</span>
          <button onClick={() => setStatusMsg("")} className="text-zinc-400 hover:text-white">✕</button>
        </div>
      )}

      {/* MAIN SPLIT: CALENDAR + INSPECTOR SIDEBAR */}
      <main className="flex-1 flex overflow-hidden">
        {/* LEFT: CALENDAR VIEW GRID */}
        <div className="flex-1 flex flex-col bg-obsidian-950 overflow-hidden border-r border-obsidian-750">
          <div className="h-7 bg-obsidian-900 border-b border-obsidian-750 px-3 flex items-center justify-between text-[11px] shrink-0 text-slate-400">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 text-slate-500 font-bold">
                <span className="text-rose-500">●</span>
                <span className="text-amber-500">●</span>
                <span className="text-emerald-500">●</span>
              </div>
              <span className="text-cyber-green font-semibold">matrix::{viewMode}-view.hypr</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-slate-500">LAYOUT: <span className="text-slate-300 font-semibold">BSP_TILED</span></span>
              <span className="flex items-center gap-1.5 text-cyber-neon font-semibold">
                <span className="w-2 h-2 rounded-full bg-cyber-neon animate-ping inline-block"></span>
                LIVE SCRUBBER ACTIVE
              </span>
            </div>
          </div>

          {/* Days of week header row */}
          <div className="grid grid-cols-[64px_repeat(7,1fr)] bg-obsidian-900/90 border-b border-obsidian-750 text-xs shrink-0 select-none">
            <div className="py-2 text-center text-slate-500 font-semibold border-r border-obsidian-750/70 text-[11px] flex items-center justify-center">
              UTC
            </div>
            {weekDays.map((d, i) => {
              const dayKey = format(d, "yyyy-MM-dd");
              const activeToday = isToday(d);
              const mins = dailyWorkload[dayKey] || 0;
              const hrs = (mins / 60).toFixed(1);
              return (
                <div
                  key={i}
                  className={`py-2 px-2 text-center flex flex-col items-center relative ${
                    activeToday
                      ? "border-r border-cyber-green/40 bg-cyber-green/5"
                      : i < 6
                      ? "border-r border-obsidian-750/70"
                      : ""
                  }`}
                >
                  <div className="flex items-center gap-1">
                    <span className={`font-bold ${activeToday ? "text-cyber-neon font-extrabold" : "text-slate-300"}`}>
                      {format(d, "EEE d").toUpperCase()}
                    </span>
                    {activeToday && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] bg-cyber-green text-obsidian-950 font-black">
                        TODAY
                      </span>
                    )}
                  </div>
                  <span className={`text-[10px] ${activeToday ? "text-cyber-neon/80" : "text-slate-500"} font-mono font-semibold`}>
                    {hrs}h / 8h
                  </span>
                  {activeToday && (
                    <div className="absolute bottom-0 inset-x-0 h-[0.5px] bg-cyber-neon shadow-[0_0_8px_#39ff14]"></div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Scrollable timetable grid */}
          <div className="flex-1 overflow-y-auto relative cyber-grid">
            <div className="min-w-[900px] h-[928px] relative grid grid-cols-[64px_repeat(7,1fr)]">
              {/* Column 0: time labels */}
              <div className="border-r border-obsidian-750/80 bg-obsidian-900/40 select-none text-[11px] font-mono text-slate-500">
                {Array.from({ length: TOTAL_HOURS }).map((_, idx) => {
                  const hourNum = START_HOUR + idx;
                  return (
                    <div key={idx} className="cal-hour-row flex items-start justify-center pt-1 border-b border-obsidian-800">
                      {String(hourNum).padStart(2, "0")}:00
                    </div>
                  );
                })}
              </div>

              {/* Day columns with absolute blocks */}
              {weekDays.map((day, colIndex) => {
                const dayStr = format(day, "yyyy-MM-dd");
                const dayBlocks = visibleBlocks.filter((b) => b.start_dt.slice(0, 10) === dayStr);
                const isWeekend = colIndex >= 5;

                return (
                  <div
                    key={colIndex}
                    className={`relative h-full ${i < 6 ? "border-r border-obsidian-800/80" : "bg-obsidian-950/30"}`}
                  >
                    <div className="absolute inset-0 pointer-events-none">
                      {Array.from({ length: TOTAL_HOURS }).map(() => (
                        <div className="cal-hour-row border-b border-obsidian-800/50"></div>
                      ))}
                    </div>
                    {isWeekend && (
                      <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-20">
                        <span className="text-xs uppercase tracking-widest text-slate-600 font-bold rotate-90">
                          Open Slot
                        </span>
                      </div>
                    )}
                    {dayBlocks.map((b) => {
                      const start = new Date(b.start_dt);
                      const end = new Date(b.end_dt);
                      const sHour = start.getHours() + start.getMinutes() / 60;
                      const eHour = end.getHours() + end.getMinutes() / 60;
                      const topPx = Math.max(0, (sHour - START_HOUR) * HOUR_HEIGHT);
                      const heightPx = Math.max(22, (eHour - sHour) * HOUR_HEIGHT);

                      return (
                        <div
                          key={b.id}
                          tabIndex={0}
                          role="button"
                          aria-label={b.title}
                          onClick={() => setSelectedBlock(b)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              setSelectedBlock(b);
                            }
                          }}
                          style={{ top: `${topPx}px`, height: `${heightPx}px` }}
                          className={`absolute inset-x-1.5 ${getBlockStyle(b)}`}
                          title={`${b.title} (${format(start, "HH:mm")} - ${format(end, "HH:mm")})`}
                        >
                          <div>
                            <div className="flex items-center justify-between text-[10px] font-bold">
                              <span className={tagAccent(b.tag).text}>
                                {b.tag.toUpperCase()}
                              </span>
                              <span className="text-slate-400">
                                {format(start, "HH:mm")} - {format(end, "HH:mm")}
                              </span>
                            </div>
                            <div className="font-bold text-slate-200 text-[11px] truncate mt-0.5">{b.title}</div>
                            {b.reason && (
                              <div className="text-[10px] text-slate-400 mt-0.5">{b.reason}</div>
                            )}
                            {selectedBlock?.id === b.id && (
                              <div className="flex items-center justify-between text-[10px] pt-1 border-t border-emerald-900/60 mt-1">
                                <span className="text-cyber-neon font-bold">SELECTED TARGET</span>
                                <span className="text-slate-300">{format(start, "EEE h:mm")}</span>
                              </div>
                            )}
                          </div>
                          {heightPx > 40 && (
                            <div className="flex items-center justify-between text-[10px] pt-1 border-t border-white/10">
                              <span>{b.locked ? "LOCKED" : "FLEX"}</span>
                              <span className="capitalize text-slate-400">{b.status}</span>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })}

              {/* Live scrubber line across the week */}
              {isCurrentWeek && scrubberTop >= 0 && scrubberTop <= TOTAL_HOURS * HOUR_HEIGHT && (
                <div
                  className="absolute inset-x-0 z-30 pointer-events-none"
                  style={{ top: `${scrubberTop}px` }}
                >
                  <div className="h-[1px] bg-cyber-neon shadow-[0_0_12px_#39ff14]"></div>
                  <div className="absolute -top-3 -left-2 bg-cyber-neon text-obsidian-950 font-black text-[10px] px-1.5 py-0.5 rounded shadow-[0_0_8px_#39ff14] flex items-center gap-1">
                    {format(now, "HH:mm")}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT: INSPECTOR SIDEBAR */}
        <aside className="w-80 2xl:w-96 bg-obsidian-900 flex flex-col shrink-0 overflow-y-auto divide-y divide-obsidian-750">
          {/* PANE 1: Activity Node Inspector */}
          <section className="p-3.5 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 font-bold text-slate-200">
                <span className="w-2 h-2 bg-cyber-green rounded-sm"></span>
                <span>Activity Node Inspector</span>
              </div>
              <span className="text-[10px] text-cyber-neon font-mono bg-obsidian-950 px-1.5 py-0.5 rounded border border-cyber-green/40">
                ID: {selectedBlock ? `NODE_${selectedBlock.id}` : "NONE"}
              </span>
            </div>
            <div className="bg-obsidian-950 p-3 rounded border border-obsidian-750 space-y-2.5">
              {!selectedBlock ? (
                <p className="text-slate-500 text-[10px] leading-relaxed">
                  Click on any activity chip in the timeline to inspect its constraints, dependencies, scheduling reason, and quick actions.
                </p>
              ) : (
                <div className="space-y-2.5">
                  <div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-cyber-green font-bold uppercase tracking-wider text-[10px]">
                        Active Selection
                      </span>
                      <span className="text-slate-400 text-[10px]">
                        {Math.round(
                          (new Date(selectedBlock.end_dt).getTime() - new Date(selectedBlock.start_dt).getTime()) /
                            60000
                        ) /
                          60
                        } hrs
                      </span>
                    </div>
                    <h3 className="text-sm font-bold text-white mt-0.5">{selectedBlock.title}</h3>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                      {selectedBlock.reason || "Scheduled by the deterministic planner."}
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px] pt-2 border-t border-obsidian-800">
                    <div>
                      <span className="text-slate-500 block text-[10px]">SCHEDULE:</span>
                      <span className="text-slate-200 font-medium">
                        {format(new Date(selectedBlock.start_dt), "EEE, MMM d · HH:mm")} —{" "}
                        {format(new Date(selectedBlock.end_dt), "HH:mm")}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px]">TAG:</span>
                      <span className="text-slate-200 font-medium">{selectedBlock.tag}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px]">LOAD FACTOR:</span>
                      <span className="text-cyber-cyan font-medium">0.85 (High Cognitive)</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px]">RECURRENCE:</span>
                      <span className="text-slate-200 font-medium">Weekly</span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1 pt-1">
                    <span className="px-2 py-0.5 bg-obsidian-850 text-cyber-purple text-[10px] rounded border border-cyber-purple/30">
                      #{selectedBlock.tag}
                    </span>
                    <span className="px-2 py-0.5 bg-obsidian-850 text-cyber-cyan text-[10px] rounded border border-cyber-cyan/30">
                      {selectedBlock.status}
                    </span>
                    <span className="px-2 py-0.5 bg-obsidian-850 text-emerald-400 text-[10px] rounded border border-emerald-400/30">
                      {selectedBlock.locked ? "locked" : "flex"}
                    </span>
                  </div>
                  <div className="pt-2 flex items-center gap-1.5">
                    <button
                      onClick={() => markComplete(selectedBlock!)}
                      className="flex-1 py-1.5 bg-obsidian-800 hover:bg-obsidian-750 text-slate-200 hover:text-white rounded text-xs font-semibold border border-obsidian-700 transition flex items-center justify-center gap-1"
                    >
                      ✓ Complete
                    </button>
                    <button
                      onClick={() => markSkip(selectedBlock!)}
                      className="py-1.5 px-3 bg-obsidian-800 hover:bg-obsidian-750 text-cyber-cyan rounded text-xs font-semibold border border-obsidian-700 transition"
                    >
                      Reschedule
                    </button>
                    <button
                      onClick={() => deleteBlock(selectedBlock!)}
                      className="py-1.5 px-2 bg-obsidian-800 hover:bg-rose-950/60 text-rose-400 rounded text-xs border border-obsidian-700 hover:border-rose-800/80 transition" title="Delete Block"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* PANE 2: Cognitive Load Matrix */}
          <section className="p-3.5 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 font-bold text-slate-200">
                <span className="text-cyber-purple">::</span>
                <span>Cognitive Load Matrix</span>
              </div>
              <span className="text-slate-400 font-mono text-[11px]">{telemetry.totalHours} hrs Total</span>
            </div>
            <div className="space-y-2 bg-obsidian-950 p-3 rounded border border-obsidian-750 text-xs">
              <div>
                <div className="flex justify-between text-[11px] mb-1">
                  <span className="flex items-center gap-1.5 text-slate-300">
                    <span className="w-2 h-2 rounded-full bg-cyber-purple"></span>
                    <span>University & Timetable</span>
                  </span>
                  <span className="font-bold text-slate-200">
                    {(telemetry.vectorMinutes.university / 60).toFixed(1)}h <span className="text-slate-500 font-normal">/ 20h</span>
                  </span>
                </div>
                <div className="w-full bg-obsidian-800 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-cyber-purple h-full rounded-full" style={{ width: telemetry.totalMinutes ? (telemetry.vectorMinutes.university / telemetry.totalMinutes) * 100 : 0 }}></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-[11px] mb-1">
                  <span className="flex items-center gap-1.5 text-slate-300">
                    <span className="w-2 h-2 rounded-full bg-cyber-cyan"></span>
                    <span>Course Study & Projects</span>
                  </span>
                  <span className="font-bold text-slate-200">
                    {((telemetry.vectorMinutes.course + telemetry.vectorMinutes.project) / 60).toFixed(1)}h <span className="text-slate-500 font-normal">/ 15h</span>
                  </span>
                </div>
                <div className="w-full bg-obsidian-800 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-cyber-cyan h-full rounded-full" style={{ width: telemetry.totalMinutes ? ((telemetry.vectorMinutes.course + telemetry.vectorMinutes.project) / telemetry.totalMinutes) * 100 : 0 }}></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-[11px] mb-1">
                  <span className="flex items-center gap-1.5 text-slate-300">
                    <span className="w-2 h-2 rounded-full bg-cyber-amber"></span>
                    <span>Health & Physical Capacity</span>
                  </span>
                  <span className="font-bold text-slate-200">
                    {(telemetry.vectorMinutes.personal / 60).toFixed(1)}h <span className="text-slate-500 font-normal">/ 5h</span>
                  </span>
                </div>
                <div className="w-full bg-obsidian-800 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-cyber-amber h-full rounded-full" style={{ width: telemetry.totalMinutes ? (telemetry.vectorMinutes.personal / telemetry.totalMinutes) * 100 : 0 }}></div>
                </div>
              </div>
            </div>
            <div className="space-y-1.5">
              <div className="flex justify-between text-[10px] text-slate-400 uppercase font-semibold">
                <span>Daily Workload (7 Days)</span>
                <span className="text-slate-500 font-mono">cap: 8h/day</span>
              </div>
              <div className="grid grid-cols-7 gap-1.5 text-center">
                {weekDays.map((d, i) => {
                  const key = format(d, "yyyy-MM-dd");
                  const mins = dailyWorkload[key] || 0;
                  const hrs = (mins / 60).toFixed(1);
                  const today = isToday(d);
                  const pct = Math.min((mins / 480) * 100, 100);
                  return (
                    <div
                      key={i}
                      className={`bg-obsidian-950 p-1.5 rounded border ${today ? "border-cyber-green/40 shadow-[0_0_8px_rgba(57,255,20,0.1)]" : "border-obsidian-750"} ${!today ? "opacity-60" : ""}`}
                    >
                      <div className={`text-[10px] font-bold ${today ? "text-cyber-neon" : "text-slate-400"} ${today ? "font-black" : ""}`}>
                        {format(d, "EEE")[0]}
                      </div>
                      <div className="h-10 flex items-end justify-center my-1 bg-obsidian-900 rounded">
                        <div className={`w-full rounded-b ${today ? "bg-cyber-neon shadow-[0_0_8px_#39ff14]" : "bg-cyber-purple/80"}`} style={{ height: `${pct}%` }}></div>
                      </div>
                      <div className={`text-[9px] font-mono ${today ? "text-cyber-neon font-bold" : "text-slate-400"}`}>{hrs}h</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </section>

          {/* PANE 3: Conflicts & Unscheduled */}
          <section className="p-3.5 space-y-2.5">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 font-bold text-slate-200">
                <span className="text-rose-400">⏰</span>
                <span>Conflicts & Unscheduled</span>
              </div>
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                unscheduled.length > 0 ? "bg-[#3a1419] text-[#ff7d8d] border-[#7d222e]" : "bg-[#162714] text-[#c5ff42] border-[#3b661d]"
              }`}>
                {unscheduled.length} CONFLICTS
              </span>
            </div>
            <div className="bg-obsidian-950 p-3 rounded border border-obsidian-750 text-center space-y-2">
              <p className="text-[11px] text-slate-400">
                {unscheduled.length === 0
                  ? "All tasks scheduled within capacity."
                  : `${unscheduled.length} task(s) need rescheduling.`}
              </p>
              <button
                onClick={rescheduleMissed}
                className="w-full py-2 bg-obsidian-800 hover:bg-obsidian-700 text-cyan-400 hover:text-cyan-300 rounded text-xs font-semibold border border-cyan-800/50 transition"
              >
                RESCHEDULE MISSED ({unscheduled.length})
              </button>
            </div>
          </section>

          {/* PANE 4: Hypr / Dotfiles Keybindings */}
          <section className="p-3.5 space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-300 uppercase text-[11px] tracking-wider">HYPR / DOTFILES KEYBINDINGS</span>
              <span className="text-[10px] text-slate-500">MODE: NORMAL</span>
            </div>
            <div className="bg-obsidian-950 p-2.5 rounded border border-obsidian-750 space-y-2 text-[11px]">
              <div className="flex items-center justify-between">
                <span className="text-cyber-green font-bold">[n]</span>
                <span className="text-slate-400">new block</span>
                <span className="text-cyber-green font-bold">[r]</span>
                <span className="text-slate-400">recalculate</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-cyber-green font-bold">[t]</span>
                <span className="text-slate-400">jump today</span>
                <span className="text-cyber-green font-bold">[h / l]</span>
                <span className="text-slate-400">&lt; / &gt; week</span>
              </div>
              <div className="flex items-center justify-between pt-1 border-t border-obsidian-800">
                <span className="text-slate-500">Space+p</span>
                <span className="text-slate-400">palette</span>
                <span className="text-slate-500">Esc</span>
                <span className="text-slate-400">blur selection</span>
              </div>
            </div>
          </section>
        </aside>
      </main>

      {/* QUICK NEW BLOCK MODAL */}
      {showNewModal && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <div className="bg-obsidian-950 border border-obsidian-750 w-full max-w-md rounded p-4 space-y-3 shadow-2xl">
            <div className="flex items-center justify-between border-b border-obsidian-750 pb-2">
              <span className="font-bold text-white text-sm">+ NEW TASK BLOCK</span>
              <button onClick={() => setShowNewModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            <div>
              <label className="text-[10px] text-slate-400 block mb-1">TASK TITLE</label>
              <input
                className="w-full bg-[#0d0f12] border border-obsidian-750 px-2 py-1.5 text-xs text-slate-200 rounded outline-none focus:border-cyber-green"
                placeholder="e.g. Distributed Systems PSet"
                value={newTask.title}
                onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">ESTIMATED MINUTES</label>
                <input
                  type="number"
                  className="w-full bg-[#0d0f12] border border-obsidian-750 px-2 py-1.5 text-xs text-slate-200 rounded outline-none"
                  value={newTask.estimated_minutes}
                  onChange={(e) => setNewTask({ ...newTask, estimated_minutes: Number(e.target.value) })}
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">DEADLINE (OPTIONAL)</label>
                <input
                  type="date"
                  className="w-full bg-[#0d0f12] border border-obsidian-750 px-2 py-1.5 text-xs text-slate-200 rounded outline-none"
                  value={newTask.deadline}
                  onChange={(e) => setNewTask({ ...newTask, deadline: e.target.value })}
                />
              </div>
            </div>
            <div className="flex gap-2 pt-2 border-t border-obsidian-750">
              <button
                onClick={createQuickTask}
                className="flex-1 py-1.5 bg-cyber-neon text-obsidian-950 font-bold text-xs rounded border border-emerald-300 shadow-[0_0_15px_rgba(57,255,20,0.3)]"
              >
                CREATE & SCHEDULE
              </button>
              <button
                onClick={() => setShowNewModal(false)}
                className="px-3 py-1.5 bg-[#1c202a] text-slate-400 text-xs rounded border border-obsidian-750"
              >
                CANCEL
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


