import { useState, useEffect } from "react";
import { api } from "./api";

interface Commitment {
  id: number;
  title: string;
  kind: string;
  tag: string;
  recurrence: string;
  days_of_week: number[];
  start_time: string;
  end_time: string;
  start_date?: string;
  end_date?: string;
  one_time_date?: string;
}

export default function CommitmentsView({ onChange }: { onChange: () => void }) {
  const [commitments, setCommitments] = useState<Commitment[]>([]);
  const [filterTag, setFilterTag] = useState<string>("all");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  const [form, setForm] = useState<{
    title: string;
    kind: string;
    tag: string;
    recurrence: string;
    days_of_week: number[];
    start_time: string;
    end_time: string;
    one_time_date: string;
  }>({
    title: "",
    kind: "fixed",
    tag: "university",
    recurrence: "weekly",
    days_of_week: [2], // Wednesday default
    start_time: "10:00",
    end_time: "12:00",
    one_time_date: "",
  });

  const load = async () => {
    try {
      const list = await api.commitments.list(filterTag === "all" ? undefined : filterTag);
      setCommitments(list);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    load();
  }, [filterTag]);

  const toggleDay = (dayIndex: number) => {
    setForm((prev) => {
      const exists = prev.days_of_week.includes(dayIndex);
      return {
        ...prev,
        days_of_week: exists
          ? prev.days_of_week.filter((d) => d !== dayIndex)
          : [...prev.days_of_week, dayIndex].sort(),
      };
    });
  };

  const save = async () => {
    if (!form.title.trim()) return;
    try {
      if (editingId) {
        await api.commitments.update(editingId, form);
      } else {
        await api.commitments.create(form);
      }
      setShowForm(false);
      setEditingId(null);
      setForm({
        title: "",
        kind: "fixed",
        tag: "university",
        recurrence: "weekly",
        days_of_week: [2],
        start_time: "10:00",
        end_time: "12:00",
        one_time_date: "",
      });
      load();
      onChange();
    } catch (err) {
      console.error(err);
    }
  };

  const remove = async (id: number) => {
    if (!confirm("Delete this recurring commitment?")) return;
    try {
      await api.commitments.delete(id);
      load();
      onChange();
    } catch (err) {
      console.error(err);
    }
  };

  const startEdit = (c: Commitment) => {
    setEditingId(c.id);
    setForm({
      title: c.title,
      kind: c.kind,
      tag: c.tag,
      recurrence: c.recurrence,
      days_of_week: c.days_of_week || [],
      start_time: c.start_time,
      end_time: c.end_time,
      one_time_date: c.one_time_date || "",
    });
    setShowForm(true);
  };

  const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  const tagColors: Record<string, string> = {
    university: "border-[#8b61c9] text-[#c19bf5] bg-[#221735]/60",
    personal: "border-[#3b5880] text-[#73a7f7] bg-[#161c27]/60",
    course: "border-[#4e8529] text-[#c5ff42] bg-[#162714]/60",
    health: "border-[#28665c] text-[#4ee6b6] bg-[#122a27]/60",
  };

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 bg-[#0d0f12] overflow-hidden text-zinc-300 font-mono">
      {/* Top Header & Filters */}
      <div className="bg-[#11141a] border border-[#232733] p-3 rounded flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <span className="font-headline font-black text-white text-base tracking-tight uppercase">
            Fixed Commitments & University Timetable
          </span>
          <span className="text-[10px] text-zinc-500">
            Rules 1 & 2: Fixed commitments take absolute precedence over flexible work
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Tag filters */}
          <div className="flex items-center bg-[#151922] p-0.5 rounded border border-[#232733] text-[10px]">
            {["all", "university", "personal", "course", "health"].map((t) => (
              <button
                key={t}
                onClick={() => setFilterTag(t)}
                className={`px-2 py-0.5 uppercase font-bold rounded-sm transition-colors ${
                  filterTag === t
                    ? "bg-[#8b61c9] text-white"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          <button
            onClick={() => {
              setEditingId(null);
              setShowForm(!showForm);
            }}
            className="px-3 py-1 bg-[#c5ff42] hover:bg-[#b5f030] text-black font-bold text-[10px] rounded flex items-center gap-1 transition-colors"
          >
            <span>+ NEW COMMITMENT</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Form Modal/Drawer + Timetable Cards */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-2 overflow-hidden">
        {/* Left Column: Form or Overview */}
        {showForm && (
          <div className="lg:col-span-1 bg-[#11141a] border border-[#232733] p-3 rounded overflow-y-auto space-y-3">
            <div className="flex items-center justify-between border-b border-[#232733] pb-2">
              <span className="font-bold text-white text-xs">
                {editingId ? "Edit Commitment" : "Add Fixed Commitment"}
              </span>
              <button
                onClick={() => setShowForm(false)}
                className="text-zinc-500 hover:text-white text-xs"
              >
                ✕
              </button>
            </div>

            <div>
              <label className="text-[10px] text-zinc-400 block mb-1">TITLE</label>
              <input
                className="w-full bg-[#0d0f12] border border-[#232733] px-2 py-1.5 text-xs text-white rounded focus:border-[#c5ff42] outline-none"
                placeholder="e.g. CS101 Lecture or Team Sync"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-zinc-400 block mb-1">TAG / CATEGORY</label>
                <select
                  className="w-full bg-[#0d0f12] border border-[#232733] px-2 py-1.5 text-xs text-white rounded outline-none"
                  value={form.tag}
                  onChange={(e) => setForm({ ...form, tag: e.target.value })}
                >
                  <option value="university">University</option>
                  <option value="personal">Personal Project</option>
                  <option value="course">Course Study</option>
                  <option value="health">Health / Routine</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] text-zinc-400 block mb-1">RECURRENCE</label>
                <select
                  className="w-full bg-[#0d0f12] border border-[#232733] px-2 py-1.5 text-xs text-white rounded outline-none"
                  value={form.recurrence}
                  onChange={(e) => setForm({ ...form, recurrence: e.target.value })}
                >
                  <option value="weekly">Weekly (Recurring)</option>
                  <option value="once">One-Time Only</option>
                </select>
              </div>
            </div>

            {form.recurrence === "weekly" ? (
              <div>
                <label className="text-[10px] text-zinc-400 block mb-1">DAYS OF WEEK</label>
                <div className="flex gap-1 flex-wrap">
                  {dayNames.map((d, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => toggleDay(i)}
                      className={`px-2 py-1 text-[10px] font-bold rounded border ${
                        form.days_of_week.includes(i)
                          ? "bg-[#c5ff42] text-black border-[#c5ff42]"
                          : "bg-[#151922] text-zinc-400 border-[#232733]"
                      }`}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div>
                <label className="text-[10px] text-zinc-400 block mb-1">DATE (YYYY-MM-DD)</label>
                <input
                  type="date"
                  className="w-full bg-[#0d0f12] border border-[#232733] px-2 py-1.5 text-xs text-white rounded outline-none"
                  value={form.one_time_date}
                  onChange={(e) => setForm({ ...form, one_time_date: e.target.value })}
                />
              </div>
            )}

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-zinc-400 block mb-1">START TIME</label>
                <input
                  type="time"
                  className="w-full bg-[#0d0f12] border border-[#232733] px-2 py-1.5 text-xs text-white rounded outline-none"
                  value={form.start_time}
                  onChange={(e) => setForm({ ...form, start_time: e.target.value })}
                />
              </div>
              <div>
                <label className="text-[10px] text-zinc-400 block mb-1">END TIME</label>
                <input
                  type="time"
                  className="w-full bg-[#0d0f12] border border-[#232733] px-2 py-1.5 text-xs text-white rounded outline-none"
                  value={form.end_time}
                  onChange={(e) => setForm({ ...form, end_time: e.target.value })}
                />
              </div>
            </div>

            <div className="flex gap-2 pt-2 border-t border-[#232733]">
              <button
                onClick={save}
                className="flex-1 py-1.5 bg-[#c5ff42] text-black font-bold text-xs rounded hover:bg-[#b5f030] transition-colors"
              >
                {editingId ? "SAVE CHANGES" : "CREATE COMMITMENT"}
              </button>
              <button
                onClick={() => setShowForm(false)}
                className="px-3 py-1.5 bg-[#1c202a] text-zinc-400 text-xs rounded border border-[#232733]"
              >
                CANCEL
              </button>
            </div>
          </div>
        )}

        {/* Right / Full Column: Weekly Visual Grid & Commitments List */}
        <div className={`${showForm ? "lg:col-span-2" : "lg:col-span-3"} bg-[#11141a] border border-[#232733] p-3 rounded flex flex-col gap-3 overflow-y-auto`}>
          {/* Visual Weekly Distribution */}
          <div>
            <span className="text-[10px] text-zinc-500 font-bold uppercase block mb-1">
              WEEKLY TIMETABLE OVERVIEW
            </span>
            <div className="grid grid-cols-7 gap-1">
              {dayNames.map((d, i) => {
                const dayCommits = commitments.filter(
                  (c) => c.recurrence === "weekly" && (c.days_of_week || []).includes(i)
                );
                return (
                  <div
                    key={i}
                    className="bg-[#0e1117] border border-[#232733] p-2 rounded flex flex-col gap-1 min-h-[120px]"
                  >
                    <div className="flex items-center justify-between border-b border-[#232733] pb-1">
                      <span className="text-[10px] font-bold text-white">{d}</span>
                      <span className="text-[9px] text-zinc-500 font-mono">
                        {dayCommits.length}
                      </span>
                    </div>
                    <div className="flex flex-col gap-1 overflow-y-auto max-h-[140px]">
                      {dayCommits.map((c) => (
                        <div
                          key={c.id}
                          onClick={() => startEdit(c)}
                          className={`p-1 rounded border text-[9px] cursor-pointer hover:border-[#c5ff42] transition-colors ${
                            tagColors[c.tag] || "border-[#232733] bg-[#14171f]"
                          }`}
                        >
                          <div className="font-bold truncate">{c.title}</div>
                          <div className="text-[8px] text-zinc-400">
                            {c.start_time}–{c.end_time}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* List View */}
          <div className="pt-2 border-t border-[#232733]">
            <span className="text-[10px] text-zinc-500 font-bold uppercase block mb-2">
              ALL COMMITMENT RULES ({commitments.length})
            </span>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
              {commitments.map((c) => (
                <div
                  key={c.id}
                  className="bg-[#0e1117] border border-[#232733] p-2.5 rounded flex flex-col justify-between hover:border-zinc-500 transition-colors"
                >
                  <div>
                    <div className="flex items-center justify-between text-[9px] mb-1">
                      <span
                        className={`px-1.5 py-0.2 rounded font-bold uppercase ${
                          c.tag === "university"
                            ? "bg-[#221735] text-[#c19bf5] border border-[#8b61c9]"
                            : c.tag === "course"
                            ? "bg-[#162714] text-[#c5ff42] border border-[#4e8529]"
                            : "bg-[#161c27] text-[#73a7f7] border border-[#3b5880]"
                        }`}
                      >
                        {c.tag}
                      </span>
                      <span className="text-zinc-500 font-mono">
                        {c.recurrence === "weekly"
                          ? (c.days_of_week || []).map((di) => dayNames[di]).join(", ")
                          : c.one_time_date}
                      </span>
                    </div>
                    <span className="text-xs font-bold text-white block mt-1">
                      {c.title}
                    </span>
                    <span className="text-[10px] text-zinc-400 font-mono mt-0.5 block">
                      {c.start_time} — {c.end_time}
                    </span>
                  </div>

                  <div className="flex items-center justify-between pt-2 mt-2 border-t border-[#232733] text-[9px]">
                    <span className="text-[#c5ff42] flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#c5ff42]"></span>
                      LOCKED
                    </span>
                    <div className="flex gap-2">
                      <button
                        onClick={() => startEdit(c)}
                        className="text-zinc-400 hover:text-white"
                      >
                        edit
                      </button>
                      <button
                        onClick={() => remove(c.id)}
                        className="text-red-400 hover:text-red-300"
                      >
                        del
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
