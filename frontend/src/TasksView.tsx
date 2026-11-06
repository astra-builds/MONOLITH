import { useState, useEffect } from "react";
import { api } from "./api";

export default function TasksView({ onChange }: { onChange: () => void }) {
  const [tasks, setTasks] = useState<any[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  const [form, setForm] = useState<any>({
    title: "",
    description: "",
    project_id: "",
    estimated_minutes: 60,
    min_session_minutes: 25,
    max_session_minutes: 90,
    deadline: "",
    priority: 3,
    preferred_days: [],
    splittable: true,
    flexible: true,
    dependencies: [] as number[],
    preferred_start: "",
    preferred_end: "",
  });

  const load = async () => {
    try {
      const t = await api.tasks.list();
      const p = await api.projects.list();
      setTasks(t);
      setProjects(p);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    if (!form.title.trim()) return;
    await api.tasks.create({
      ...form,
      project_id: form.project_id ? Number(form.project_id) : null,
      deadline: form.deadline || null,
      estimated_minutes: Number(form.estimated_minutes),
      remaining_minutes: Number(form.estimated_minutes),
      min_session_minutes: Number(form.min_session_minutes),
      max_session_minutes: Number(form.max_session_minutes),
      priority: Number(form.priority),
    });
    setShowForm(false);
    setForm({
      title: "",
      description: "",
      project_id: "",
      estimated_minutes: 60,
      deadline: "",
      priority: 3,
      preferred_days: [],
      min_session_minutes: 25,
      max_session_minutes: 90,
      splittable: true,
      flexible: true,
      dependencies: [],
      preferred_start: "",
      preferred_end: "",
    });
    load();
    onChange();
  };

  const startEdit = (t: any) => {
    setEditingId(t.id);
    setForm({
      title: t.title,
      description: t.description || "",
      project_id: t.project_id || "",
      estimated_minutes: t.estimated_minutes || 60,
      deadline: t.deadline || "",
      priority: t.priority || 3,
      preferred_days: t.preferred_days || [],
      min_session_minutes: t.min_session_minutes || 25,
      max_session_minutes: t.max_session_minutes || 90,
      splittable: t.splittable !== false,
      flexible: t.flexible !== false,
      dependencies: t.dependencies || [],
      preferred_start: t.preferred_start || "",
      preferred_end: t.preferred_end || "",
    });
    setShowForm(true);
  };

  const saveEdit = async () => {
    if (!form.title.trim()) return;
    if (!editingId) return;
    // Forbid self-dependency
    const deps = (form.dependencies || []).filter((d: number) => d !== editingId);
    try {
      await api.tasks.update(editingId, {
        ...form,
        dependencies: deps,
        project_id: form.project_id ? Number(form.project_id) : null,
        deadline: form.deadline || null,
        estimated_minutes: Number(form.estimated_minutes),
        min_session_minutes: Number(form.min_session_minutes),
        max_session_minutes: Number(form.max_session_minutes),
        priority: Number(form.priority),
      });
      setShowForm(false);
      setEditingId(null);
      load();
      onChange();
    } catch (e: any) {
      console.error(e);
    }
  };

  const complete = async (id: number) => {
    await api.tasks.complete(id);
    load();
    onChange();
  };

  const del = async (id: number) => {
    if (!confirm("Delete task?")) return;
    await api.tasks.delete(id);
    load();
    onChange();
  };

  const toggleDay = (d: number) => {
    setForm((f: any) => ({
      ...f,
      preferred_days: f.preferred_days.includes(d)
        ? f.preferred_days.filter((x: number) => x !== d)
        : [...f.preferred_days, d],
    }));
  };

  const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  const filteredTasks = tasks.filter((t) => {
    if (statusFilter === "all") return true;
    if (statusFilter === "todo") return t.status !== "done";
    if (statusFilter === "done") return t.status === "done";
    return true;
  });

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 bg-obsidian-900 overflow-hidden text-slate-300 font-mono">
      {/* Header */}
      <div className="bg-obsidian-900 border border-obsidian-750 p-3 rounded flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-headline font-black text-white text-base tracking-tight uppercase">
            Tasks & Backlog Triage
          </span>
          <span className="text-[10px] text-slate-500">
            Manual task controls, dependency graphs, and duration constraints
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Status filter tabs */}
          <div className="flex items-center bg-obsidian-850 p-0.5 rounded border border-obsidian-750 text-[10px]">
            {["all", "todo", "done"].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-2 py-0.5 uppercase font-bold rounded-sm transition-colors ${
                  statusFilter === s
                    ? "bg-[#8b61c9] text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          <button
            onClick={() => setShowForm(!showForm)}
            className="px-3 py-1 bg-[#c5ff42] hover:bg-[#b5f030] text-black font-bold text-[10px] rounded flex items-center gap-1 transition-colors"
          >
            <span>+ NEW TASK</span>
          </button>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-2 overflow-hidden">
        {/* Form Column */}
        {showForm && (
          <div className="lg:col-span-1 bg-obsidian-900 border border-obsidian-750 p-3 rounded overflow-y-auto space-y-2.5">
            <div className="flex items-center justify-between border-b border-obsidian-750 pb-1.5">
              <span className="font-bold text-white text-xs">CREATE NEW TASK</span>
              <button onClick={() => setShowForm(false)} className="text-slate-500 hover:text-white">✕</button>
            </div>

            <div>
              <span className="text-[9px] text-slate-400 block mb-0.5">TITLE</span>
              <input
                placeholder="e.g. Implement Distributed Lock"
                className="w-full bg-obsidian-900 border border-obsidian-750 p-1.5 text-xs text-white rounded outline-none focus:border-[#c5ff42]"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </div>

            <div>
              <span className="text-[9px] text-slate-400 block mb-0.5">PROJECT / COURSE</span>
              <select
                className="w-full bg-obsidian-900 border border-obsidian-750 p-1.5 text-xs text-white rounded"
                value={form.project_id}
                onChange={(e) => setForm({ ...form, project_id: e.target.value })}
              >
                <option value="">No Project (Standalone)</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.kind})
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-[9px] text-slate-400 block mb-0.5">ESTIMATED MINS</span>
                <input
                  type="number"
                  className="w-full bg-obsidian-900 border border-obsidian-750 p-1.5 text-xs text-white rounded"
                  value={form.estimated_minutes}
                  onChange={(e) => setForm({ ...form, estimated_minutes: e.target.value })}
                />
              </div>
              <div>
                <span className="text-[9px] text-slate-400 block mb-0.5">DEADLINE</span>
                <input
                  type="date"
                  className="w-full bg-obsidian-900 border border-obsidian-750 p-1.5 text-xs text-white rounded"
                  value={form.deadline}
                  onChange={(e) => setForm({ ...form, deadline: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-[9px] text-slate-400 block mb-0.5">MIN SESSION MINS</span>
                <input
                  type="number"
                  className="w-full bg-obsidian-900 border border-obsidian-750 p-1.5 text-xs text-white rounded"
                  value={form.min_session_minutes}
                  onChange={(e) => setForm({ ...form, min_session_minutes: Number(e.target.value) || 25 })}
                />
              </div>
              <div>
                <span className="text-[9px] text-slate-400 block mb-0.5">MAX SESSION MINS</span>
                <input
                  type="number"
                  className="w-full bg-obsidian-900 border border-obsidian-750 p-1.5 text-xs text-white rounded"
                  value={form.max_session_minutes}
                  onChange={(e) => setForm({ ...form, max_session_minutes: Number(e.target.value) || 90 })}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-[9px] text-slate-400 block mb-0.5">PREFERRED START</span>
                <input
                  type="time"
                  className="w-full bg-obsidian-900 border border-obsidian-750 p-1.5 text-xs text-white rounded"
                  value={form.preferred_start}
                  onChange={(e) => setForm({ ...form, preferred_start: e.target.value })}
                />
              </div>
              <div>
                <span className="text-[9px] text-slate-400 block mb-0.5">PREFERRED END</span>
                <input
                  type="time"
                  className="w-full bg-obsidian-900 border border-obsidian-750 p-1.5 text-xs text-white rounded"
                  value={form.preferred_end}
                  onChange={(e) => setForm({ ...form, preferred_end: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-[9px] text-slate-400 block mb-0.5">PRIORITY (1=HIGH, 5=LOW)</span>
                <select
                  className="w-full bg-obsidian-900 border border-obsidian-750 p-1.5 text-xs text-white rounded"
                  value={form.priority}
                  onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
                >
                  <option value={1}>1 - Highest / Critical</option>
                  <option value={2}>2 - High</option>
                  <option value={3}>3 - Medium</option>
                  <option value={4}>4 - Low</option>
                  <option value={5}>5 - Lowest</option>
                </select>
              </div>
              <div>
                <span className="text-[9px] text-slate-400 block mb-0.5">SPLITTABLE SESSIONS</span>
                <label className="flex items-center gap-1.5 mt-2 cursor-pointer text-xs">
                  <input
                    type="checkbox"
                    checked={form.splittable}
                    onChange={(e) => setForm({ ...form, splittable: e.target.checked })}
                  />
                  <span>Allow splitting</span>
                </label>
              </div>
            </div>

            <div>
              <span className="text-[9px] text-slate-400 block mb-0.5">PREFERRED DAYS</span>
              <div className="flex gap-1 flex-wrap">
                {dayNames.map((d, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => toggleDay(i)}
                    className={`px-2 py-1 text-[10px] font-bold rounded border ${
                      form.preferred_days.includes(i)
                        ? "bg-[#c5ff42] text-black border-[#c5ff42]"
                        : "bg-obsidian-850 text-slate-400 border-obsidian-750"
                    }`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <span className="text-[9px] text-slate-400 block mb-0.5">PREREQUISITE DEPENDENCY</span>
              <select
                className="w-full bg-obsidian-900 border border-obsidian-750 p-1.5 text-xs text-white rounded"
                value={form.dependencies[0] || ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    dependencies: e.target.value && Number(e.target.value) !== editingId ? [Number(e.target.value)] : [],
                  })
                }
              >
                <option value="">No Prerequisite (Can start anytime)</option>
                {tasks.map((other) => {
                  // Forbid self-dependency when editing
                  if (editingId && other.id === editingId) return null;
                  return (
                    <option key={other.id} value={other.id}>
                      Depends on #{other.id}: {other.title}
                    </option>
                  );
                })}
              </select>
            </div>

            <div className="flex gap-2 pt-2 border-t border-obsidian-750">
              <button
                onClick={editingId ? saveEdit : create}
                className="flex-1 py-1.5 bg-[#c5ff42] text-black font-bold text-xs rounded hover:bg-[#b5f030]"
              >
                {editingId ? "SAVE CHANGES" : "CREATE TASK"}
              </button>
              <button
                onClick={() => {
                  setShowForm(false);
                  setEditingId(null);
                }}
                className="px-3 py-1.5 bg-[#1c202a] text-slate-400 text-xs rounded"
              >
                CANCEL
              </button>
            </div>
          </div>
        )}

        {/* Task List Table */}
        <div
          className={`${
            showForm ? "lg:col-span-2" : "lg:col-span-3"
          } bg-obsidian-900 border border-obsidian-750 p-3 rounded flex flex-col overflow-y-auto`}
        >
          <table className="w-full text-xs text-left">
            <thead className="text-[10px] text-slate-500 uppercase border-b border-obsidian-750">
              <tr>
                <th className="py-2 px-1">ID</th>
                <th className="py-2">Title</th>
                <th className="py-2">Status</th>
                <th className="py-2">Remaining</th>
                <th className="py-2">Priority</th>
                <th className="py-2">Deadline</th>
                <th className="py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#232733]/40">
              {filteredTasks.map((t) => {
                const done = t.status === "done";
                return (
                  <tr key={t.id} className="hover:bg-obsidian-850 transition-colors">
                    <td className="py-2 px-1 font-mono text-slate-500 text-[10px]">
                      #{t.id}
                    </td>
                    <td className="py-2 font-bold text-white">
                      <div className="truncate max-w-xs">{t.title}</div>
                      {t.project_id && (
                        <span className="text-[9px] text-[#73a7f7] font-normal">
                          {projects.find((p) => p.id === t.project_id)?.name}
                        </span>
                      )}
                    </td>
                    <td className="py-2">
                      <span
                        className={`px-1.5 py-0.5 rounded font-bold uppercase text-[8px] ${
                          done
                            ? "bg-[#14231b] text-[#c5ff42] border border-[#3b661d]"
                            : t.status === "overdue"
                              ? "bg-[#3a131a] text-[#ff7d8d] border border-[#7d222e]"
                              : t.status === "waiting"
                                ? "bg-[#2e2115] text-[#f59e0b] border border-[#7d222e]"
                                : "bg-[#161c27] text-slate-300 border border-obsidian-750"
                        }`}
                      >
                        {t.status}
                      </span>
                    </td>
                    <td className="py-2 font-mono text-slate-400">{t.remaining_minutes}m</td>
                    <td className="py-2">
                      <span
                        className={`px-1 py-0.2 rounded font-bold text-[9px] ${
                          t.priority === 1
                            ? "bg-[#3a131a] text-[#ff7d8d]"
                            : t.priority === 2
                            ? "bg-[#2e2115] text-[#f59e0b]"
                            : "text-slate-500"
                        }`}
                      >
                        P{t.priority}
                      </span>
                    </td>
                    <td className="py-2 font-mono text-slate-400 text-[10px]">
                      {t.deadline || "—"}
                    </td>
                    <td className="py-2 text-right space-x-1.5">
                      {!done && (
                        <button
                          onClick={() => complete(t.id)}
                          className="px-2 py-0.5 bg-[#172514] text-[#c5ff42] border border-[#3b661d] rounded text-[9px] font-bold"
                        >
                          DONE
                        </button>
                      )}
                      {!done && editingId !== t.id && (
                        <button
                          onClick={() => startEdit(t)}
                          className="px-2 py-0.5 bg-[#18202c] text-[#73a7f7] border border-[#3b5880] rounded text-[9px] font-bold"
                        >
                          EDIT
                        </button>
                      )}
                      {editingId === t.id && (
                        <button
                          onClick={saveEdit}
                          className="px-2 py-0.5 bg-[#c5ff42] text-black border border-[#c5ff42] rounded text-[9px] font-bold"
                        >
                          SAVE
                        </button>
                      )}
                      <button
                        onClick={() => del(t.id)}
                        className="px-2 py-0.5 bg-[#261418] text-[#ff7d8d] border border-[#7d222e] rounded text-[9px]"
                      >
                        DEL
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
