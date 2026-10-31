import { useState, useEffect } from "react";
import { api } from "./api";

const PROVIDERS = ["none", "gemini", "openrouter"];

export default function SettingsView({
  settings,
  onChange,
}: {
  settings: any;
  onChange: (s: any) => void;
}) {
  const [form, setForm] = useState<any>(settings || {});
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (settings) setForm(settings);
  }, [settings]);

  const save = async () => {
    try {
      const s = await api.settings.update(form);
      onChange(s);
      setMsg("✓ Settings saved successfully.");
      setTimeout(() => setMsg(""), 3000);
    } catch (e: any) {
      setMsg("Error saving: " + e.message);
    }
  };

  const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const toggleDay = (d: number) => {
    const days = form.working_days || [];
    setForm({
      ...form,
      working_days: days.includes(d) ? days.filter((x: number) => x !== d) : [...days, d],
    });
  };

  const handleExport = async () => {
    try {
      const data = await api.export();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `monolith_backup_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setMsg("✓ Backup exported successfully.");
    } catch (e: any) {
      setMsg("Export failed: " + e.message);
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!confirm("Importing this backup will overwrite current data. Continue?")) return;

    try {
      const reader = new FileReader();
      reader.onload = async (event) => {
        try {
          const json = JSON.parse(event.target?.result as string);
          await api.import(json);
          setMsg("✓ Database restored successfully from backup.");
          onChange(form);
        } catch (err: any) {
          setMsg("Import parse error: " + err.message);
        }
      };
      reader.readAsText(file);
    } catch (e: any) {
      setMsg("Import error: " + e.message);
    }
  };

  const handleReset = async () => {
    if (!confirm("DANGER: WIPE ALL DATA? This will permanently delete all tasks, projects, commitments, and schedules.")) return;
    try {
      await api.demo.reset();
      setMsg("✓ Database wiped and reset to default state.");
      onChange(form);
    } catch (e: any) {
      setMsg("Reset error: " + e.message);
    }
  };

  const handleSeed = async () => {
    if (!confirm("Load Demo University Timetable (CS101, Math Lab) and Agentic AI Course?")) return;
    try {
      await api.demo.seed();
      await api.schedule.apply();
      setMsg("✓ Demo data seeded and scheduled.");
      onChange(form);
    } catch (e: any) {
      setMsg("Seed error: " + e.message);
    }
  };

  return (
    <div className="w-full max-w-3xl bg-[#11141a] border border-[#232733] rounded p-6 space-y-6 font-mono text-zinc-300 text-xs">
      {/* Title */}
      <div className="border-b border-[#232733] pb-3 flex items-center justify-between">
        <div>
          <span className="font-headline font-black text-white text-lg tracking-tight uppercase">
            System Configuration & Storage
          </span>
          <p className="text-[10px] text-zinc-500 mt-0.5">
            Local scheduling constraints, working capacity, AI model adapters, and persistent storage
          </p>
        </div>
        <button
          onClick={save}
          className="px-4 py-2 bg-[#c5ff42] hover:bg-[#b5f030] text-black font-bold text-xs rounded transition-colors"
        >
          SAVE SETTINGS
        </button>
      </div>

      {msg && (
        <div className="bg-[#172514] border border-[#3b661d] text-[#c5ff42] px-3 py-1.5 rounded text-xs">
          {msg}
        </div>
      )}

      {/* Section 1: Availability & Working Hours */}
      <div className="space-y-3">
        <span className="font-bold text-white text-xs block uppercase text-[#c5ff42]">
          1. AVAILABILITY & WORKING CONSTRAINTS
        </span>

        <div>
          <span className="text-[10px] text-zinc-400 block mb-1">WORKING DAYS</span>
          <div className="flex gap-1.5 flex-wrap">
            {dayNames.map((d, i) => {
              const active = (form.working_days || []).includes(i);
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => toggleDay(i)}
                  className={`px-3 py-1.5 font-bold rounded border transition-colors ${
                    active
                      ? "bg-[#c5ff42] text-black border-[#c5ff42]"
                      : "bg-[#0d0f12] text-zinc-500 border-[#232733]"
                  }`}
                >
                  {d}
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] text-zinc-400 block mb-1">WORKING HOURS START</label>
            <input
              type="time"
              className="w-full bg-[#0d0f12] border border-[#232733] p-2 text-white rounded outline-none focus:border-[#c5ff42]"
              value={form.working_start || "09:00"}
              onChange={(e) => setForm({ ...form, working_start: e.target.value })}
            />
          </div>
          <div>
            <label className="text-[10px] text-zinc-400 block mb-1">WORKING HOURS END</label>
            <input
              type="time"
              className="w-full bg-[#0d0f12] border border-[#232733] p-2 text-white rounded outline-none focus:border-[#c5ff42]"
              value={form.working_end || "18:00"}
              onChange={(e) => setForm({ ...form, working_end: e.target.value })}
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-[10px] text-zinc-400 block mb-1">MAX DAILY MINUTES</label>
            <input
              type="number"
              className="w-full bg-[#0d0f12] border border-[#232733] p-2 text-white rounded outline-none"
              value={form.max_daily_minutes || 480}
              onChange={(e) => setForm({ ...form, max_daily_minutes: Number(e.target.value) })}
            />
            <span className="text-[9px] text-zinc-500 block mt-0.5">8h cap default</span>
          </div>
          <div>
            <label className="text-[10px] text-zinc-400 block mb-1">MIN BREAK (MINUTES)</label>
            <input
              type="number"
              className="w-full bg-[#0d0f12] border border-[#232733] p-2 text-white rounded outline-none"
              value={form.min_break_minutes || 15}
              onChange={(e) => setForm({ ...form, min_break_minutes: Number(e.target.value) })}
            />
            <span className="text-[9px] text-zinc-500 block mt-0.5">Gap between sessions</span>
          </div>
          <div>
            <label className="text-[10px] text-zinc-400 block mb-1">DEFAULT SESSION (MINUTES)</label>
            <input
              type="number"
              className="w-full bg-[#0d0f12] border border-[#232733] p-2 text-white rounded outline-none"
              value={form.default_session_minutes || 60}
              onChange={(e) => setForm({ ...form, default_session_minutes: Number(e.target.value) })}
            />
            <span className="text-[9px] text-zinc-500 block mt-0.5">Atomic session size</span>
          </div>
        </div>
      </div>

      {/* Section 2: AI Provider Integration */}
      <div className="pt-4 border-t border-[#232733] space-y-3">
        <span className="font-bold text-white text-xs block uppercase text-[#73a7f7]">
          2. AI ASSISTANT PROVIDER (OPTIONAL)
        </span>
        <p className="text-[10px] text-zinc-400">
          Supports free Gemini API or free OpenRouter models. The app is 100% usable without AI using manual and offline natural language commands.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="text-[10px] text-zinc-400 block mb-1">PROVIDER</label>
            <select
              className="w-full bg-[#0d0f12] border border-[#232733] p-2 text-white rounded outline-none"
              value={form.ai_provider || "none"}
              onChange={(e) => setForm({ ...form, ai_provider: e.target.value })}
            >
              {PROVIDERS.map((p) => (
                <option key={p} value={p}>
                  {p.toUpperCase()}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-zinc-400 block mb-1">MODEL IDENTIFIER</label>
            <input
              placeholder="e.g. gemini-1.5-flash"
              className="w-full bg-[#0d0f12] border border-[#232733] p-2 text-white rounded outline-none"
              value={form.ai_model || ""}
              onChange={(e) => setForm({ ...form, ai_model: e.target.value })}
            />
          </div>
          <div>
            <label className="text-[10px] text-zinc-400 block mb-1">API KEY</label>
            <input
              type="password"
              placeholder="Stored locally on backend"
              className="w-full bg-[#0d0f12] border border-[#232733] p-2 text-white rounded outline-none"
              value={form.ai_api_key || ""}
              onChange={(e) => setForm({ ...form, ai_api_key: e.target.value })}
            />
          </div>
        </div>
      </div>

      {/* Section 3: Data Management, Backups & Demo Content */}
      <div className="pt-4 border-t border-[#232733] space-y-3">
        <span className="font-bold text-white text-xs block uppercase text-[#ff7d8d]">
          3. DATA PERSISTENCE & BACKUPS
        </span>
        <p className="text-[10px] text-zinc-400">
          Local-first SQLite storage in <code className="text-zinc-200">backend/data/monolith.db</code>. No cloud dependency or account required.
        </p>

        <div className="flex flex-wrap gap-2 pt-1">
          <button
            onClick={handleExport}
            className="px-3 py-2 bg-[#14171f] hover:bg-[#202635] text-zinc-200 border border-[#232733] rounded text-xs font-bold"
          >
            📥 EXPORT BACKUP (.JSON)
          </button>

          <label className="px-3 py-2 bg-[#14171f] hover:bg-[#202635] text-zinc-200 border border-[#232733] rounded text-xs font-bold cursor-pointer inline-block">
            📤 IMPORT BACKUP (.JSON)
            <input
              type="file"
              accept=".json"
              className="hidden"
              onChange={handleImport}
            />
          </label>

          <button
            onClick={handleSeed}
            className="px-3 py-2 bg-[#162714] hover:bg-[#20361c] text-[#c5ff42] border border-[#3b661d] rounded text-xs font-bold"
          >
            ✦ LOAD DEMO SCENARIOS
          </button>

          <button
            onClick={handleReset}
            className="px-3 py-2 bg-[#261418] hover:bg-[#381a20] text-[#ff7d8d] border border-[#7d222e] rounded text-xs font-bold"
          >
            ✕ WIPE DATABASE
          </button>
        </div>
      </div>
    </div>
  );
}
