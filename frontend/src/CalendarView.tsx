import { useState, useEffect, useMemo, useRef } from "react";
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

const HOUR_HEIGHT = 56; // 56px per hour matching dotfiles inspiration
const START_HOUR = 7; // 07:00
const END_HOUR = 22; // 22:00
const TOTAL_HOURS = END_HOUR - START_HOUR;

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

  const scrollRef = useRef<HTMLDivElement>(null);

  // Load schedule blocks for current range
  const loadSchedule = async () => {
    setLoading(true);
    try {
      const rangeStart = subWeeks(startOfWeek(currentDate, { weekStartsOn: 1 }), 2);
      const rangeEnd = addWeeks(endOfWeek(currentDate, { weekStartsOn: 1 }), 4);
      const data = await api.schedule.list(rangeStart.toISOString(), rangeEnd.toISOString());
      setBlocks(data);

      // Also fetch preview to get latest unscheduled diagnostics
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

  // Keyboard navigation shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if typing in an input
      if (["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement).tagName)) {
        return;
      }
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
        regenerate();
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

  // Week calculation (Monday to Sunday)
  const weekStart = useMemo(
    () => startOfWeek(currentDate, { weekStartsOn: 1 }),
    [currentDate]
  );
  const weekDays = useMemo(
    () => Array.from({ length: 7 }).map((_, i) => addDays(weekStart, i)),
    [weekStart]
  );

  // Month calculation
  const monthDays = useMemo(() => {
    const s = startOfWeek(startOfMonth(currentDate), { weekStartsOn: 1 });
    const e = endOfWeek(endOfMonth(currentDate), { weekStartsOn: 1 });
    return eachDayOfInterval({ start: s, end: e });
  }, [currentDate]);

  // Filtered blocks
  const visibleBlocks = useMemo(() => {
    if (filterTag === "all") return blocks;
    return blocks.filter((b) => b.tag === filterTag);
  }, [blocks, filterTag]);

  // Daily workload calculations (minutes scheduled per day of the active week)
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

  // Telemetry statistics
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

  // Live Scrubber current position
  const now = new Date();
  const isCurrentWeek = weekDays.some((d) => isSameDay(d, now));
  const currentHourDecimal = now.getHours() + now.getMinutes() / 60;
  const scrubberTop = (currentHourDecimal - START_HOUR) * HOUR_HEIGHT;

  // Styling helper for event cards by tag
  const getBlockStyle = (block: ScheduleBlock) => {
    const isSelected = selectedBlock?.id === block.id;
    let bg = "bg-[#161c27]/90 border-[#3b5880] text-[#73a7f7]"; // default project/task

    if (block.tag === "university") {
      bg = "bg-[#221735]/95 border-[#8b61c9] text-[#c19bf5]";
    } else if (block.tag === "course") {
      bg = "bg-[#162714]/95 border-[#4e8529] text-[#c5ff42]";
    } else if (block.tag === "personal" || block.tag === "health") {
      bg = "bg-[#12231e]/90 border-[#28665c] text-[#4ee6b6]";
    }

    if (block.status === "completed") {
      bg = "bg-[#132218]/80 border-[#2f5934] text-[#86efac] opacity-75";
    } else if (block.status === "missed" || block.status === "skipped") {
      bg = "bg-[#3a131a]/90 border-[#e0314b] text-[#ff7d8d]";
    }

    return `${bg} ${isSelected ? "ring-2 ring-[#c5ff42] z-20 shadow-[0_0_12px_rgba(197,255,66,0.3)]" : ""}`;
  };

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-68px)] overflow-hidden bg-[#0d0f12] text-zinc-300 font-mono text-[11px] select-none">
      {/* SUB-BAR & FILTER CONTROLS */}
      <div className="bg-[#0f1217] border-b border-[#232733] px-3 py-1.5 flex flex-wrap items-center justify-between gap-y-2 shrink-0 text-[10px]">
        {/* Left: Views + Cycle + Commands */}
        <div className="flex flex-wrap items-center gap-2">
          {/* View mode toggles */}
          <div className="flex items-center bg-[#151922] p-0.5 rounded border border-[#232733] font-bold">
            {(["day", "week", "month"] as ViewMode[]).map((v, i) => (
              <button
                key={v}
                onClick={() => setViewMode(v)}
                className={`px-2 py-0.5 rounded-sm uppercase transition-colors ${
                  viewMode === v
                    ? "bg-[#8b61c9] text-white shadow"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                {i + 1}: {v}
              </button>
            ))}
          </div>

          {/* Cycle tag & date range */}
          <div className="flex items-center gap-1.5 bg-[#151922] px-2 py-1 rounded border border-[#232733]">
            <span className="bg-[#242b3b] text-[#c5ff42] px-1 font-bold text-[9px] rounded">
              W{format(currentDate, "w")}
            </span>
            <span className="font-bold text-white tracking-wider">
              {viewMode === "week"
                ? `${format(weekStart, "MMM d")} — ${format(addDays(weekStart, 6), "MMM d, yyyy")}`
                : viewMode === "day"
                ? format(currentDate, "EEEE, MMMM d, yyyy")
                : format(currentDate, "MMMM yyyy")}
            </span>
          </div>

          {/* Nav buttons */}
          <div className="flex items-center gap-1 text-zinc-400">
            <button
              onClick={() => navigate(-1)}
              className="px-1.5 py-0.5 bg-[#151922] hover:bg-[#202635] text-zinc-300 rounded border border-[#232733]"
              title="Previous [h]"
            >
              <strong>[h]</strong> PREV
            </button>
            <button
              onClick={() => setCurrentDate(new Date())}
              className="px-1.5 py-0.5 bg-[#151922] hover:bg-[#202635] text-[#c5ff42] rounded border border-[#232733] font-bold"
              title="Today [t]"
            >
              <strong>[t]</strong> TODAY
            </button>
            <button
              onClick={() => navigate(1)}
              className="px-1.5 py-0.5 bg-[#151922] hover:bg-[#202635] text-zinc-300 rounded border border-[#232733]"
              title="Next [l]"
            >
              <strong>[l]</strong> NEXT
            </button>
            <button
              onClick={regenerate}
              disabled={loading}
              className="px-1.5 py-0.5 bg-[#151922] hover:bg-[#202635] text-[#71d99b] rounded border border-[#232733] flex items-center gap-1"
              title="Regenerate Schedule [r]"
            >
              <span>⟳</span> REGEN <span className="text-zinc-500">[r]</span>
            </button>
            <button
              onClick={() => setShowNewModal(true)}
              className="px-2 py-0.5 bg-[#253245] hover:bg-[#c5ff42] hover:text-black text-[#c5ff42] font-bold rounded border border-[#232733] flex items-center gap-1 transition-colors"
              title="Add New Block [n]"
            >
              <span>+ NEW BLOCK</span> <span className="opacity-70 text-[9px]">[n]</span>
            </button>
          </div>
        </div>

        {/* Right: Telemetry & Tag Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="hidden md:flex items-center gap-2 text-zinc-400 border-r border-[#232733] pr-3 text-[9px]">
            <span>TOTAL: <strong className="text-white">{telemetry.totalHours}h</strong></span>
            <span>DEEP WORK: <strong className="text-[#c5ff42]">{telemetry.deepHours}h ({telemetry.deepPercent}%)</strong></span>
            <span className={unscheduled.length > 0 ? "text-[#ff7d8d] font-bold" : "text-[#71d99b]"}>
              ● {unscheduled.length} CONFLICTS
            </span>
          </div>

          {/* Tag filters */}
          <div className="flex items-center gap-1 text-[9px]">
            <span className="text-zinc-500">FILTER:</span>
            {["all", "university", "course", "project", "personal"].map((t) => (
              <button
                key={t}
                onClick={() => setFilterTag(t)}
                className={`px-1.5 py-0.5 rounded border uppercase transition-colors ${
                  filterTag === t
                    ? "bg-[#253245] text-white border-[#c5ff42]"
                    : "bg-[#181d29] text-zinc-400 border-[#232733] hover:border-zinc-500"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      {statusMsg && (
        <div className="bg-[#1b2318] border-b border-[#3b661d] text-[#c5ff42] px-3 py-1 text-[10px] flex items-center justify-between">
          <span>{statusMsg}</span>
          <button onClick={() => setStatusMsg("")} className="text-zinc-400 hover:text-white">✕</button>
        </div>
      )}

      {/* MAIN VIEWPORT: 2-COLUMN BSP-TILED WINDOW SPLIT */}
      <main className="flex-1 flex overflow-hidden p-1 gap-1">
        {/* LEFT COLUMN: WEEK / DAY / MONTH TIMELINE */}
        <section className="flex-1 flex flex-col bg-[#11141a] rounded border border-[#232733] overflow-hidden min-w-0">
          {/* Window Titlebar */}
          <div className="h-6 bg-[#161a22] border-b border-[#232733] px-2 flex items-center justify-between text-[10px] shrink-0">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-[#ff5f56]"></span>
                <span className="w-2 h-2 rounded-full bg-[#ffbd2e]"></span>
                <span className="w-2 h-2 rounded-full bg-[#27c93f]"></span>
              </div>
              <span className="font-bold text-zinc-300 tracking-wider">
                matrix::{viewMode}-view.hypr
              </span>
            </div>
            <div className="flex items-center gap-3 text-zinc-400">
              <span className="text-zinc-500">LAYOUT: <strong className="text-zinc-300">BSP_TILED</strong></span>
              <span className="flex items-center gap-1 text-[#c5ff42] font-bold">
                <span className="w-1.5 h-1.5 rounded-full bg-[#c5ff42] animate-pulse"></span>
                LIVE SCRUBBER
              </span>
            </div>
          </div>

          {/* ==================== WEEK VIEW ==================== */}
          {viewMode === "week" && (
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Day Header Row */}
              <div className="grid grid-cols-[50px_repeat(7,1fr)] bg-[#131720] border-b border-[#232733] shrink-0 text-center">
                <div className="py-1 text-zinc-500 font-mono text-[9px] border-r border-[#232733] flex items-center justify-center">
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
                      className={`py-1 border-r border-[#232733] ${
                        activeToday ? "bg-[#182613]/50" : ""
                      }`}
                    >
                      <div className="font-bold text-zinc-300 text-[10px]">
                        {format(d, "EEE d").toUpperCase()}
                      </div>
                      <div className="text-[8px] text-zinc-500">
                        {hrs}h / 8h
                      </div>
                      {activeToday && (
                        <span className="inline-block mt-0.5 px-1 bg-[#1f3817] border border-[#c5ff42]/60 rounded text-[#c5ff42] font-black text-[7px] uppercase">
                          TODAY
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Scrollable Timeline Grid */}
              <div ref={scrollRef} className="flex-1 overflow-y-auto relative bg-[#0e1117]">
                {/* Live Scrubber Line (current week only) */}
                {isCurrentWeek && scrubberTop >= 0 && scrubberTop <= TOTAL_HOURS * HOUR_HEIGHT && (
                  <div
                    className="absolute left-0 right-0 z-30 pointer-events-none flex items-center"
                    style={{ top: `${scrubberTop}px` }}
                  >
                    <div className="w-[50px] flex items-center justify-end pr-1">
                      <span className="bg-[#c5ff42] text-black font-black text-[9px] px-1 py-0.2 rounded-sm shadow-[0_0_8px_rgba(197,255,66,0.6)]">
                        {format(now, "HH:mm")}
                      </span>
                    </div>
                    <div className="flex-1 h-[1.5px] bg-[#c5ff42] shadow-[0_0_6px_rgba(197,255,66,0.8)] relative">
                      <span className="absolute -top-1 left-2 w-2 h-2 rounded-full bg-[#c5ff42]"></span>
                    </div>
                  </div>
                )}

                {/* 15 Hourly Background Lines */}
                <div className="relative min-w-[700px]">
                  <div className="flex flex-col">
                    {Array.from({ length: TOTAL_HOURS }).map((_, idx) => {
                      const hourNum = START_HOUR + idx;
                      return (
                        <div
                          key={idx}
                          className="h-14 border-b border-[#232733]/40 grid grid-cols-[50px_repeat(7,1fr)]"
                        >
                          <span className="text-[9px] text-zinc-600 border-r border-[#232733]/40 text-center pt-1 font-mono">
                            {String(hourNum).padStart(2, "0")}:00
                          </span>
                          {Array.from({ length: 7 }).map((_, col) => (
                            <div key={col} className="border-r border-[#232733]/20"></div>
                          ))}
                        </div>
                      );
                    })}
                  </div>

                  {/* Absolute Positioned Blocks for 7 Columns */}
                  <div className="absolute inset-0 left-[50px] grid grid-cols-7 pointer-events-auto">
                    {weekDays.map((day, colIndex) => {
                      const dayStr = format(day, "yyyy-MM-dd");
                      const dayBlocks = visibleBlocks.filter(
                        (b) => b.start_dt.slice(0, 10) === dayStr
                      );

                      return (
                        <div key={colIndex} className="relative border-r border-[#232733]/20 h-full">
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
                                onClick={() => setSelectedBlock(b)}
                                style={{ top: `${topPx}px`, height: `${heightPx}px` }}
                                className={`absolute left-0.5 right-0.5 rounded p-1 flex flex-col justify-between cursor-pointer border transition-all ${getBlockStyle(
                                  b
                                )}`}
                                title={`${b.title} (${format(start, "HH:mm")} - ${format(
                                  end,
                                  "HH:mm"
                                )})`}
                              >
                                <div className="overflow-hidden">
                                  <div className="flex items-center justify-between text-[8px] leading-tight mb-0.5">
                                    <span className="font-bold uppercase tracking-tight truncate">
                                      {b.tag}
                                    </span>
                                    <span className="font-mono text-zinc-400 shrink-0">
                                      {format(start, "HH:mm")}
                                    </span>
                                  </div>
                                  <span className="font-bold text-white block truncate text-[9px] leading-tight">
                                    {b.title}
                                  </span>
                                </div>

                                {heightPx > 40 && (
                                  <div className="flex items-center justify-between text-[7px] text-zinc-400 pt-0.5 border-t border-white/10">
                                    <span>{b.locked ? "LOCKED" : "FLEX"}</span>
                                    <span className="capitalize">{b.status}</span>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ==================== DAY VIEW ==================== */}
          {viewMode === "day" && (
            <div className="flex-1 flex flex-col overflow-y-auto bg-[#0e1117] p-2">
              <div className="bg-[#14171f] p-3 rounded border border-[#232733] mb-2 flex items-center justify-between">
                <div>
                  <span className="text-xs text-zinc-400 block">DAILY AGENDA</span>
                  <span className="text-base font-headline font-black text-white">
                    {format(currentDate, "EEEE, MMMM d, yyyy")}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-[10px] text-zinc-400 block">SCHEDULED WORK</span>
                  <span className="text-sm font-bold text-[#c5ff42]">
                    {(
                      (visibleBlocks.filter(
                        (b) => b.start_dt.slice(0, 10) === format(currentDate, "yyyy-MM-dd")
                      ).reduce((acc, b) => acc + (new Date(b.end_dt).getTime() - new Date(b.start_dt).getTime()) / 3600000, 0))
                    ).toFixed(1)} hrs
                  </span>
                </div>
              </div>

              <div className="space-y-1.5">
                {visibleBlocks
                  .filter((b) => b.start_dt.slice(0, 10) === format(currentDate, "yyyy-MM-dd"))
                  .sort((a, b) => a.start_dt.localeCompare(b.start_dt))
                  .map((b) => {
                    const start = new Date(b.start_dt);
                    const end = new Date(b.end_dt);
                    return (
                      <div
                        key={b.id}
                        onClick={() => setSelectedBlock(b)}
                        className={`p-2.5 rounded border cursor-pointer flex items-center justify-between ${getBlockStyle(
                          b
                        )}`}
                      >
                        <div className="flex items-center gap-3">
                          <div className="text-center w-14 shrink-0 font-mono">
                            <span className="font-bold text-white block text-xs">
                              {format(start, "HH:mm")}
                            </span>
                            <span className="text-[9px] text-zinc-500">
                              {format(end, "HH:mm")}
                            </span>
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold text-white">{b.title}</span>
                              <span className="text-[8px] uppercase px-1 rounded border border-white/20">
                                {b.tag}
                              </span>
                            </div>
                            {b.reason && (
                              <p className="text-[9px] text-zinc-400 mt-0.5">{b.reason}</p>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              markComplete(b);
                            }}
                            className="px-2 py-1 bg-[#172514] border border-[#3b661d] text-[#c5ff42] text-[9px] font-bold rounded"
                          >
                            DONE
                          </button>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* ==================== MONTH VIEW ==================== */}
          {viewMode === "month" && (
            <div className="flex-1 grid grid-cols-7 grid-rows-6 gap-px bg-[#232733] overflow-y-auto p-px">
              {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d, i) => (
                <div key={i} className="bg-[#131720] text-center py-1 text-[10px] font-bold text-zinc-400">
                  {d}
                </div>
              ))}
              {monthDays.map((d, i) => {
                const dayKey = format(d, "yyyy-MM-dd");
                const dayBlocks = visibleBlocks.filter((b) => b.start_dt.slice(0, 10) === dayKey);
                const active = isToday(d);
                return (
                  <div
                    key={i}
                    onClick={() => {
                      setCurrentDate(d);
                      setViewMode("day");
                    }}
                    className={`bg-[#0e1117] p-1 flex flex-col justify-between cursor-pointer hover:bg-[#161a22] transition-colors ${
                      active ? "ring-1 ring-[#c5ff42] bg-[#141d14]" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between text-[9px]">
                      <span className={`font-bold ${active ? "text-[#c5ff42]" : "text-zinc-400"}`}>
                        {format(d, "d")}
                      </span>
                      {dayBlocks.length > 0 && (
                        <span className="text-[8px] text-zinc-500 font-mono">
                          {dayBlocks.length} acts
                        </span>
                      )}
                    </div>
                    <div className="space-y-0.5 overflow-hidden max-h-12 mt-1">
                      {dayBlocks.slice(0, 3).map((b) => (
                        <div
                          key={b.id}
                          className="text-[8px] truncate px-1 py-0.2 rounded bg-[#18202c] text-zinc-300 border border-[#232733]"
                        >
                          {b.title}
                        </div>
                      ))}
                      {dayBlocks.length > 3 && (
                        <span className="text-[7px] text-zinc-500 block">
                          +{dayBlocks.length - 3} more
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* RIGHT COLUMN: ASIDE TILED INSPECTOR & COGNITIVE TELEMETRY */}
        <aside className="w-80 flex flex-col gap-1 overflow-y-auto shrink-0 select-none">
          {/* WINDOW 1: Activity Inspector & Quick Actions */}
          <div className="bg-[#11141a] rounded border border-[#232733] overflow-hidden shrink-0">
            <div className="h-6 bg-[#161a22] border-b border-[#232733] px-2 flex items-center justify-between text-[10px]">
              <div className="flex items-center gap-1.5">
                <span className="text-[#c5ff42]">■</span>
                <span className="font-bold text-zinc-200">Activity Node Inspector</span>
              </div>
              <span className="text-zinc-500 text-[9px]">ID: {selectedBlock ? selectedBlock.id : "NONE"}</span>
            </div>

            <div className="p-3">
              {!selectedBlock ? (
                <p className="text-zinc-500 text-[10px] leading-relaxed">
                  Click on any activity chip in the timeline to inspect its constraints, dependencies, scheduling reason, and quick actions.
                </p>
              ) : (
                <div className="space-y-2.5">
                  <div>
                    <span className="text-[9px] text-[#c5ff42] font-bold uppercase tracking-wider block">
                      {selectedBlock.tag} · {selectedBlock.status}
                    </span>
                    <h3 className="font-bold text-white text-xs leading-snug mt-0.5">
                      {selectedBlock.title}
                    </h3>
                    <p className="text-[10px] text-zinc-400 font-mono mt-0.5">
                      {format(new Date(selectedBlock.start_dt), "EEE, MMM d · HH:mm")} —{" "}
                      {format(new Date(selectedBlock.end_dt), "HH:mm")}
                    </p>
                  </div>

                  {/* Scheduling reason transparency */}
                  {selectedBlock.reason && (
                    <div className="bg-[#0c0e13] p-2 rounded border border-[#232733] text-[9px] text-zinc-300 leading-normal">
                      <span className="text-zinc-500 block text-[8px] uppercase font-bold mb-0.5">
                        SCHEDULER TRANSPARENCY:
                      </span>
                      {selectedBlock.reason}
                    </div>
                  )}

                  {/* Action buttons */}
                  <div className="grid grid-cols-2 gap-1.5 pt-1">
                    <button
                      onClick={() => markComplete(selectedBlock)}
                      className="py-1 bg-[#172514] hover:bg-[#20361c] text-[#c5ff42] border border-[#3b661d] font-bold text-[9px] rounded"
                    >
                      ✓ COMPLETE
                    </button>
                    <button
                      onClick={() => markSkip(selectedBlock)}
                      className="py-1 bg-[#1c1c24] hover:bg-[#282835] text-zinc-300 border border-[#232733] text-[9px] rounded"
                    >
                      ↷ SKIP
                    </button>
                    <button
                      onClick={() => moveBlockDays(selectedBlock, 1)}
                      className="py-1 bg-[#151922] hover:bg-[#202635] text-zinc-300 border border-[#232733] text-[9px] rounded"
                    >
                      ◷ +1 DAY
                    </button>
                    <button
                      onClick={() => moveBlockDays(selectedBlock, -1)}
                      className="py-1 bg-[#151922] hover:bg-[#202635] text-zinc-300 border border-[#232733] text-[9px] rounded"
                    >
                      ◶ -1 DAY
                    </button>
                    <button
                      onClick={() =>
                        api.schedule
                          .updateBlock(selectedBlock.id, { locked: !selectedBlock.locked })
                          .then(() => loadSchedule())
                      }
                      className="py-1 bg-[#151922] hover:bg-[#202635] text-zinc-300 border border-[#232733] text-[9px] rounded"
                    >
                      {selectedBlock.locked ? "🔓 UNLOCK" : "🔒 LOCK TIME"}
                    </button>
                    <button
                      onClick={() => deleteBlock(selectedBlock)}
                      className="py-1 bg-[#261418] hover:bg-[#381a20] text-[#ff7d8d] border border-[#7d222e] text-[9px] rounded"
                    >
                      ✕ DELETE
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* WINDOW 2: Cognitive Load Matrix & Vector Distribution */}
          <div className="bg-[#11141a] rounded border border-[#232733] overflow-hidden shrink-0">
            <div className="h-6 bg-[#161a22] border-b border-[#232733] px-2 flex items-center justify-between text-[10px]">
              <div className="flex items-center gap-1.5">
                <span className="text-[#8b61c9]">☵</span>
                <span className="font-bold text-zinc-200">Cognitive Load Matrix</span>
              </div>
              <span className="text-[#c5ff42] font-bold text-[9px]">
                {telemetry.totalHours} hrs Total
              </span>
            </div>

            <div className="p-2.5 space-y-2.5">
              {/* Vector distribution bars */}
              <div className="space-y-1.5">
                <div>
                  <div className="flex justify-between text-[9px] mb-0.5">
                    <span className="text-zinc-300 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#8b61c9]"></span>
                      University & Timetable
                    </span>
                    <span className="text-zinc-400 font-mono">
                      {(telemetry.vectorMinutes.university / 60).toFixed(1)}h
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-[#1c202a] rounded overflow-hidden">
                    <div
                      className="h-full bg-[#8b61c9] rounded"
                      style={{
                        width: `${
                          telemetry.totalMinutes
                            ? (telemetry.vectorMinutes.university / telemetry.totalMinutes) * 100
                            : 0
                        }%`,
                      }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-[9px] mb-0.5">
                    <span className="text-zinc-300 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#c5ff42]"></span>
                      Course Study & Projects
                    </span>
                    <span className="text-[#c5ff42] font-bold font-mono">
                      {((telemetry.vectorMinutes.course + telemetry.vectorMinutes.project) / 60).toFixed(1)}h
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-[#1c202a] rounded overflow-hidden">
                    <div
                      className="h-full bg-[#c5ff42] rounded"
                      style={{
                        width: `${
                          telemetry.totalMinutes
                            ? ((telemetry.vectorMinutes.course + telemetry.vectorMinutes.project) /
                                telemetry.totalMinutes) *
                              100
                            : 0
                        }%`,
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Daily Workload Bars (7 Days) */}
              <div className="pt-2 border-t border-[#232733]">
                <div className="flex justify-between text-[9px] text-zinc-400 mb-1">
                  <span>DAILY WORKLOAD (7 DAYS)</span>
                  <span className="text-zinc-500 font-mono">cap: 8h/day</span>
                </div>
                <div className="grid grid-cols-7 gap-1 text-center font-mono">
                  {weekDays.map((d, i) => {
                    const key = format(d, "yyyy-MM-dd");
                    const mins = dailyWorkload[key] || 0;
                    const hrs = (mins / 60).toFixed(1);
                    const overbooked = mins > 480;
                    return (
                      <div
                        key={i}
                        className={`rounded py-1 border ${
                          overbooked
                            ? "bg-[#3a131a] border-[#e0314b]"
                            : mins > 0
                            ? "bg-[#172514] border-[#3b661d]"
                            : "bg-[#141b24] border-[#232733]"
                        }`}
                      >
                        <span className="block text-[8px] text-zinc-400 font-bold">
                          {format(d, "EEE")[0]}
                        </span>
                        <span
                          className={`block text-[9px] font-bold ${
                            overbooked
                              ? "text-[#ff7d8d]"
                              : mins > 0
                              ? "text-white"
                              : "text-zinc-600"
                          }`}
                        >
                          {hrs}h
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* WINDOW 3: Unscheduled Tasks & Conflicts */}
          <div className="bg-[#11141a] rounded border border-[#232733] overflow-hidden shrink-0">
            <div className="h-6 bg-[#161a22] border-b border-[#232733] px-2 flex items-center justify-between text-[10px]">
              <div className="flex items-center gap-1.5">
                <span className="text-[#ff4a68]">⏰</span>
                <span className="font-bold text-zinc-200">Conflicts & Unscheduled</span>
              </div>
              <span
                className={`px-1.5 py-0.2 text-[9px] font-bold rounded border ${
                  unscheduled.length > 0
                    ? "bg-[#3a1419] text-[#ff7d8d] border-[#7d222e]"
                    : "bg-[#162714] text-[#c5ff42] border-[#3b661d]"
                }`}
              >
                {unscheduled.length} CONFLICTS
              </span>
            </div>

            <div className="p-2 space-y-1.5 max-h-48 overflow-y-auto">
              {unscheduled.length === 0 ? (
                <div className="text-center py-2 text-zinc-500 text-[10px]">
                  All tasks scheduled within capacity.
                </div>
              ) : (
                unscheduled.map((u, i) => (
                  <div
                    key={i}
                    className="bg-[#151922] border-l-2 border-[#ff4a68] p-1.5 rounded-r border border-[#232733] text-[9px]"
                  >
                    <div className="font-bold text-white leading-tight">{u.title}</div>
                    <div className="text-zinc-400 text-[8px] mt-0.5 leading-normal">
                      {u.reason}
                    </div>
                  </div>
                ))
              )}

              <div className="flex gap-1 pt-1 border-t border-[#232733]">
                <button
                  onClick={rescheduleMissed}
                  className="flex-1 py-1 bg-[#1a2538] hover:bg-[#253650] text-[#73a7f7] border border-[#3b5880] rounded text-[9px] font-bold"
                >
                  RESCHEDULE MISSED
                </button>
              </div>
            </div>
          </div>

          {/* WINDOW 4: Hypr / Keybindings Reference */}
          <div className="bg-[#11141a] rounded border border-[#232733] overflow-hidden shrink-0">
            <div className="h-6 bg-[#161a22] border-b border-[#232733] px-2 flex items-center justify-between text-[10px]">
              <div className="flex items-center gap-1.5">
                <span>⌨</span>
                <span className="font-bold text-zinc-200 uppercase text-[9px]">
                  HYPR / DOTFILES KEYBINDINGS
                </span>
              </div>
              <span className="text-zinc-500 text-[9px]">MODE: NORMAL</span>
            </div>
            <div className="p-2 text-[9px] font-mono grid grid-cols-2 gap-x-2 gap-y-1">
              <div className="flex justify-between py-0.5 border-b border-[#232733]/50">
                <span className="text-[#c5ff42] font-bold">[n]</span>
                <span className="text-zinc-400">new block</span>
              </div>
              <div className="flex justify-between py-0.5 border-b border-[#232733]/50">
                <span className="text-[#c5ff42] font-bold">[r]</span>
                <span className="text-zinc-400">recalculate</span>
              </div>
              <div className="flex justify-between py-0.5 border-b border-[#232733]/50">
                <span className="text-[#c5ff42] font-bold">[t]</span>
                <span className="text-zinc-400">jump today</span>
              </div>
              <div className="flex justify-between py-0.5 border-b border-[#232733]/50">
                <span className="text-[#c5ff42] font-bold">[h / l]</span>
                <span className="text-zinc-400">&lt; / &gt; week</span>
              </div>
            </div>
          </div>
        </aside>
      </main>

      {/* QUICK NEW BLOCK MODAL */}
      {showNewModal && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <div className="bg-[#11141a] border border-[#232733] w-full max-w-md rounded p-4 space-y-3 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#232733] pb-2">
              <span className="font-headline font-bold text-white text-sm">
                + NEW TASK BLOCK
              </span>
              <button onClick={() => setShowNewModal(false)} className="text-zinc-400 hover:text-white">✕</button>
            </div>

            <div>
              <label className="text-[10px] text-zinc-400 block mb-1">TASK TITLE</label>
              <input
                className="w-full bg-[#0d0f12] border border-[#232733] px-2 py-1.5 text-xs text-white rounded outline-none focus:border-[#c5ff42]"
                placeholder="e.g. Distributed Systems PSet"
                value={newTask.title}
                onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-zinc-400 block mb-1">ESTIMATED MINUTES</label>
                <input
                  type="number"
                  className="w-full bg-[#0d0f12] border border-[#232733] px-2 py-1.5 text-xs text-white rounded outline-none"
                  value={newTask.estimated_minutes}
                  onChange={(e) => setNewTask({ ...newTask, estimated_minutes: Number(e.target.value) })}
                />
              </div>
              <div>
                <label className="text-[10px] text-zinc-400 block mb-1">DEADLINE (OPTIONAL)</label>
                <input
                  type="date"
                  className="w-full bg-[#0d0f12] border border-[#232733] px-2 py-1.5 text-xs text-white rounded outline-none"
                  value={newTask.deadline}
                  onChange={(e) => setNewTask({ ...newTask, deadline: e.target.value })}
                />
              </div>
            </div>

            <div className="flex gap-2 pt-2 border-t border-[#232733]">
              <button
                onClick={createQuickTask}
                className="flex-1 py-1.5 bg-[#c5ff42] text-black font-bold text-xs rounded hover:bg-[#b5f030]"
              >
                CREATE & SCHEDULE
              </button>
              <button
                onClick={() => setShowNewModal(false)}
                className="px-3 py-1.5 bg-[#1c202a] text-zinc-400 text-xs rounded border border-[#232733]"
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
