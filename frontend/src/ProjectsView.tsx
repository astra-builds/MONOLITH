import { useState, useEffect } from "react";
import { api } from "./api";

export default function ProjectsView({ onChange }: { onChange: () => void }) {
  const [projects, setProjects] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [showForm, setShowForm] = useState(false);
  const [showCourseGen, setShowCourseGen] = useState(false);

  const [form, setForm] = useState<any>({
    name: "",
    description: "",
    kind: "course",
    total_sessions: 10,
    session_minutes: 120,
    target_deadline: "",
  });

  const [courseGenForm, setCourseGenForm] = useState({
    total_sessions: 10,
    session_minutes: 120,
    half: true,
    day_of_week: 5, // Saturday
    deadline: "",
  });

  const load = async () => {
    try {
      const data = await api.projects.list();
      setProjects(data);
      if (selected) {
        setSelected(await api.projects.get(selected.id));
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    if (!form.name.trim()) return;
    const p = await api.projects.create({
      ...form,
      target_deadline: form.target_deadline || null,
      total_sessions: Number(form.total_sessions),
      session_minutes: Number(form.session_minutes),
    });
    setShowForm(false);
    load();
    open(p.id);
    onChange();
  };

  const open = async (id: number) => {
    try {
      const proj = await api.projects.get(id);
      setSelected(proj);
    } catch (e) {
      console.error(e);
    }
  };

  const del = async (id: number) => {
    if (!confirm("Delete project and its tasks?")) return;
    await api.projects.delete(id);
    setSelected(null);
    load();
    onChange();
  };

  const handleGenerateCourseSessions = async () => {
    if (!selected) return;
    try {
      await api.projects.generateSessions(selected.id, {
        title: selected.name,
        total_sessions: Number(courseGenForm.total_sessions),
        session_minutes: Number(courseGenForm.session_minutes),
        half: courseGenForm.half,
        day_of_week: Number(courseGenForm.day_of_week),
        deadline: courseGenForm.deadline || null,
      });
      await api.schedule.apply();
      setShowCourseGen(false);
      open(selected.id);
      onChange();
    } catch (e: any) {
      alert("Error generating sessions: " + e.message);
    }
  };

  const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 bg-obsidian-900 overflow-hidden text-slate-300 font-mono">
      {/* Top Banner */}
      <div className="bg-obsidian-900 border border-obsidian-750 p-3 rounded flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-headline font-black text-white text-base tracking-tight uppercase">
            Project & Course Architecture Lab
          </span>
          <span className="text-[10px] text-slate-500">
            Ordered session roadmaps, milestones, and projected completion telemetry
          </span>
        </div>

        <button
          onClick={() => setShowForm(!showForm)}
          className="px-3 py-1 bg-[#c5ff42] hover:bg-[#b5f030] text-black font-bold text-[10px] rounded flex items-center gap-1 transition-colors"
        >
          <span>+ NEW PROJECT / COURSE</span>
        </button>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-2 overflow-hidden">
        {/* Left Column: Projects & Courses List */}
        <div className="lg:col-span-1 bg-obsidian-900 border border-obsidian-750 p-3 rounded flex flex-col gap-2 overflow-y-auto">
          {showForm && (
            <div className="bg-obsidian-900 border border-obsidian-750 p-3 rounded space-y-2 mb-2">
              <span className="font-bold text-white text-xs block">NEW GOAL SPECIFICATION</span>
              <input
                placeholder="Title (e.g. Agentic AI Course)"
                className="w-full bg-obsidian-850 border border-obsidian-750 p-1.5 text-xs text-white rounded outline-none focus:border-[#c5ff42]"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
              <textarea
                placeholder="Description / curriculum notes..."
                className="w-full bg-obsidian-850 border border-obsidian-750 p-1.5 text-xs text-white rounded outline-none h-14"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-[9px] text-slate-400 block mb-0.5">KIND</span>
                  <select
                    className="w-full bg-obsidian-850 border border-obsidian-750 p-1.5 text-xs text-white rounded"
                    value={form.kind}
                    onChange={(e) => setForm({ ...form, kind: e.target.value })}
                  >
                    <option value="course">Course</option>
                    <option value="project">Project</option>
                  </select>
                </div>
                <div>
                  <span className="text-[9px] text-slate-400 block mb-0.5">SESSIONS</span>
                  <input
                    type="number"
                    className="w-full bg-obsidian-850 border border-obsidian-750 p-1.5 text-xs text-white rounded"
                    value={form.total_sessions}
                    onChange={(e) => setForm({ ...form, total_sessions: e.target.value })}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-[9px] text-slate-400 block mb-0.5">SESSION MINS</span>
                  <input
                    type="number"
                    className="w-full bg-obsidian-850 border border-obsidian-750 p-1.5 text-xs text-white rounded"
                    value={form.session_minutes}
                    onChange={(e) => setForm({ ...form, session_minutes: e.target.value })}
                  />
                </div>
                <div>
                  <span className="text-[9px] text-slate-400 block mb-0.5">TARGET DEADLINE</span>
                  <input
                    type="date"
                    className="w-full bg-obsidian-850 border border-obsidian-750 p-1.5 text-xs text-white rounded"
                    value={form.target_deadline}
                    onChange={(e) => setForm({ ...form, target_deadline: e.target.value })}
                  />
                </div>
              </div>
              <div className="flex gap-2 pt-1">
                <button
                  onClick={create}
                  className="flex-1 py-1.5 bg-[#c5ff42] text-black font-bold text-xs rounded hover:bg-[#b5f030]"
                >
                  CREATE
                </button>
                <button
                  onClick={() => setShowForm(false)}
                  className="px-3 py-1.5 bg-[#1c202a] text-slate-400 text-xs rounded"
                >
                  CANCEL
                </button>
              </div>
            </div>
          )}

          <span className="text-[10px] text-slate-500 font-bold uppercase block mb-1">
            GOALS & COURSES ({projects.length})
          </span>

          <div className="space-y-1 overflow-y-auto">
            {projects.map((p) => {
              const active = selected?.id === p.id;
              return (
                <button
                  key={p.id}
                  onClick={() => open(p.id)}
                  className={`w-full text-left p-2 rounded border flex flex-col gap-1 transition-colors ${
                    active
                      ? "bg-[#182613] border-[#c5ff42] text-white"
                      : "bg-obsidian-900 border-obsidian-750 text-slate-300 hover:border-zinc-500"
                  }`}
                >
                  <div className="flex items-center justify-between text-[9px]">
                    <span
                      className={`px-1 rounded uppercase font-bold text-[8px] ${
                        p.kind === "course"
                          ? "bg-[#162714] text-[#c5ff42] border border-[#4e8529]"
                          : "bg-[#161c27] text-[#73a7f7] border border-[#3b5880]"
                      }`}
                    >
                      {p.kind}
                    </span>
                    <span className="text-slate-500">
                      {p.total_sessions ? `${p.total_sessions} sessions` : ""}
                    </span>
                  </div>
                  <span className="font-bold text-xs truncate block">{p.name}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right 2 Columns: Detailed Inspection, Session Roadmap, and Course Generator */}
        <div className="lg:col-span-2 bg-obsidian-900 border border-obsidian-750 p-4 rounded overflow-y-auto">
          {!selected ? (
            <div className="h-full flex items-center justify-center text-slate-500 text-xs">
              Select a project or course from the list to view its architecture trace and session roadmap.
            </div>
          ) : (
            <div className="space-y-4">
              {/* Header */}
              <div className="flex items-start justify-between border-b border-obsidian-750 pb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-1.5 py-0.2 rounded font-bold uppercase text-[9px] ${
                        selected.kind === "course"
                          ? "bg-[#162714] text-[#c5ff42] border border-[#4e8529]"
                          : "bg-[#161c27] text-[#73a7f7] border border-[#3b5880]"
                      }`}
                    >
                      {selected.kind}
                    </span>
                    <h2 className="text-xl font-headline font-bold text-white tracking-tight">
                      {selected.name}
                    </h2>
                  </div>
                  {selected.description && (
                    <p className="text-slate-400 text-xs mt-1">{selected.description}</p>
                  )}
                </div>

                <div className="flex gap-2">
                  {selected.kind === "course" && (
                    <button
                      onClick={() => setShowCourseGen(true)}
                      className="px-2.5 py-1 bg-[#1a2538] hover:bg-[#253650] text-[#73a7f7] border border-[#3b5880] text-[10px] font-bold rounded"
                      title="Generate ordered study sessions"
                    >
                      ⚡ GENERATE SESSIONS
                    </button>
                  )}
                  <button
                    onClick={() => del(selected.id)}
                    className="px-2.5 py-1 bg-[#261418] hover:bg-[#381a20] text-[#ff7d8d] border border-[#7d222e] text-[10px] font-bold rounded"
                  >
                    DELETE
                  </button>
                </div>
              </div>

              {/* Course Session Generator Modal (Scenario A) */}
              {showCourseGen && (
                <div className="bg-obsidian-900 border border-[#3b5880] p-3 rounded space-y-2">
                  <span className="font-bold text-[#73a7f7] text-xs block">
                    SCENARIO A: BATCH COURSE SESSION GENERATOR
                  </span>
                  <p className="text-[10px] text-slate-400">
                    Creates sequential, ordered study tasks chained with prerequisite dependencies and assigns preferred day.
                  </p>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                    <div>
                      <span className="text-[9px] text-slate-400 block mb-0.5">TOTAL SESSIONS</span>
                      <input
                        type="number"
                        className="w-full bg-obsidian-850 border border-obsidian-750 p-1.5 text-white rounded"
                        value={courseGenForm.total_sessions}
                        onChange={(e) =>
                          setCourseGenForm({ ...courseGenForm, total_sessions: Number(e.target.value) })
                        }
                      />
                    </div>
                    <div>
                      <span className="text-[9px] text-slate-400 block mb-0.5">SESSION DURATION (M)</span>
                      <input
                        type="number"
                        className="w-full bg-obsidian-850 border border-obsidian-750 p-1.5 text-white rounded"
                        value={courseGenForm.session_minutes}
                        onChange={(e) =>
                          setCourseGenForm({ ...courseGenForm, session_minutes: Number(e.target.value) })
                        }
                      />
                    </div>
                    <div>
                      <span className="text-[9px] text-slate-400 block mb-0.5">STUDY DAY</span>
                      <select
                        className="w-full bg-obsidian-850 border border-obsidian-750 p-1.5 text-white rounded"
                        value={courseGenForm.day_of_week}
                        onChange={(e) =>
                          setCourseGenForm({ ...courseGenForm, day_of_week: Number(e.target.value) })
                        }
                      >
                        {dayNames.map((d, i) => (
                          <option key={i} value={i}>
                            {d}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <span className="text-[9px] text-slate-400 block mb-0.5">SPLIT HALF-SESSIONS</span>
                      <label className="flex items-center gap-1.5 mt-2 cursor-pointer text-zinc-200">
                        <input
                          type="checkbox"
                          checked={courseGenForm.half}
                          onChange={(e) =>
                            setCourseGenForm({ ...courseGenForm, half: e.target.checked })
                          }
                        />
                        <span className="text-[10px]">
                          {courseGenForm.half
                            ? `Yes (${courseGenForm.total_sessions * 2} blocks of ${
                                courseGenForm.session_minutes / 2
                              }m)`
                            : "No"}
                        </span>
                      </label>
                    </div>
                  </div>

                  <div className="flex gap-2 pt-2 border-t border-obsidian-750">
                    <button
                      onClick={handleGenerateCourseSessions}
                      className="px-4 py-1.5 bg-[#c5ff42] text-black font-bold text-xs rounded hover:bg-[#b5f030]"
                    >
                      GENERATE & SCHEDULE BLOCKS
                    </button>
                    <button
                      onClick={() => setShowCourseGen(false)}
                      className="px-3 py-1.5 bg-[#1c202a] text-slate-400 text-xs rounded"
                    >
                      CANCEL
                    </button>
                  </div>
                </div>
              )}

              {/* Progress & Estimated Completion Telemetry */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs font-mono">
                <div className="bg-obsidian-900 p-2.5 rounded border border-obsidian-750">
                  <span className="text-[9px] text-slate-500 uppercase block">COMPLETION STATUS</span>
                  <span className="text-base font-bold text-white block mt-0.5">
                    {selected.completed} / {selected.tasks?.length || 0}
                  </span>
                  <span className="text-[9px] text-[#c5ff42]">
                    {selected.progress?.toFixed(0)}% PROGRESS
                  </span>
                </div>

                <div className="bg-obsidian-900 p-2.5 rounded border border-obsidian-750">
                  <span className="text-[9px] text-slate-500 uppercase block">ESTIMATED COMPLETION</span>
                  <span className="text-xs font-bold text-[#c5ff42] block mt-1 truncate">
                    {selected.estimated_completion
                      ? selected.estimated_completion.slice(0, 10)
                      : "Pending schedule"}
                  </span>
                  <span className="text-[9px] text-slate-500">
                    {selected.target_deadline
                      ? `Target: ${selected.target_deadline}`
                      : "No target deadline"}
                  </span>
                </div>

                <div className="bg-obsidian-900 p-2.5 rounded border border-obsidian-750">
                  <span className="text-[9px] text-slate-500 uppercase block">REMAINING WORK</span>
                  <span className="text-base font-bold text-white block mt-0.5">
                    {selected.remaining_tasks} tasks
                  </span>
                  <span className="text-[9px] text-slate-500">
                    {(
                      (selected.tasks || []).reduce(
                        (acc: number, t: any) => acc + (t.remaining_minutes || 0),
                        0
                      ) / 60
                    ).toFixed(1)}{" "}
                    hrs
                  </span>
                </div>

                <div className="bg-obsidian-900 p-2.5 rounded border border-obsidian-750">
                  <span className="text-[9px] text-slate-500 uppercase block">SCHEDULED BLOCKS</span>
                  <span className="text-base font-bold text-white block mt-0.5">
                    {selected.blocks?.length || 0}
                  </span>
                  <span className="text-[9px] text-[#73a7f7]">In calendar</span>
                </div>
              </div>

              {/* Progress bar */}
              <div>
                <div className="h-1.5 bg-obsidian-900 border border-obsidian-750 rounded overflow-hidden">
                  <div
                    className="h-full bg-[#c5ff42]"
                    style={{ width: `${selected.progress || 0}%` }}
                  />
                </div>
              </div>

              {/* Ordered Session Roadmap */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-white uppercase">
                    ORDERED SESSION ROADMAP ({selected.tasks?.length || 0})
                  </span>
                </div>

                <div className="space-y-1">
                  {(selected.tasks || []).map((t: any, index: number) => {
                    const done = t.status === "done";
                    return (
                      <div
                        key={t.id}
                        className={`p-2 rounded border flex items-center justify-between text-xs ${
                          done
                            ? "bg-[#14231b]/60 border-[#2b593a] text-slate-400"
                            : "bg-obsidian-900 border-obsidian-750 text-zinc-200"
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <span className="font-bold text-slate-500 text-[10px] w-6">
                            #{String(index + 1).padStart(2, "0")}
                          </span>
                          <span className={done ? "line-through text-slate-500" : "font-bold text-white"}>
                            {t.title}
                          </span>
                        </div>

                        <div className="flex items-center gap-3 text-[10px] font-mono">
                          <span className="text-slate-500">
                            {t.remaining_minutes}m
                          </span>
                          <span
                            className={`px-1 rounded uppercase font-bold text-[8px] ${
                              done
                                ? "bg-[#1f3817] text-[#c5ff42]"
                                : "bg-[#1c202a] text-slate-400"
                            }`}
                          >
                            {t.status}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
