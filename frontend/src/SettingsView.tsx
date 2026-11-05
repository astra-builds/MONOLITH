import { useState, useEffect } from "react";
import { api } from "./api";

const PROVIDERS = ["none", "gemini", "openrouter"];

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

interface ProviderStatus {
  configured: boolean;
  provider: string;
  model: string;
  status: "connected" | "error" | "not_configured";
  capabilities: Record<string, unknown>;
  last_error: { kind: string; message: string; retryable: boolean } | null;
}

export default function SettingsView({
  settings,
  onChange,
}: {
  settings: any;
  onChange: (s: any) => void;
}) {
  const [form, setForm] = useState<any>(settings || {});
  const [provider, setProvider] = useState<ProviderStatus | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (settings) setForm(settings);
  }, [settings]);

  // Fetch real AI provider connection status (Refine.txt §8: AI config must
  // make obvious whether the provider is connected and AI is available).
  const loadProviderStatus = async () => {
    try {
      const s = await api.ai.provider();
      setProvider(s as ProviderStatus);
    } catch {
      setProvider(null);
    }
  };

  useEffect(() => {
    loadProviderStatus();
  }, []);

  const save = async () => {
    try {
      const s = await api.settings.update(form);
      onChange(s);
      setForm(s);
      await loadProviderStatus();
      setMsg("✓ Settings saved successfully.");
      setTimeout(() => setMsg(""), 3000);
    } catch (e: any) {
      setMsg("Error saving: " + e.message);
    }
  };

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
    if (
      !confirm(
        "DANGER: WIPE ALL DATA? This will permanently delete all tasks, projects, commitments, and schedules."
      )
    )
      return;
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

  const keyPresent = Boolean(form.ai_api_key);
  const aiAvailable = provider?.configured === true && provider?.status === "connected";
  const providerActive = provider?.provider && provider?.provider !== "none";

  const sectionBadge = (label: string, color: string) => (
    <span className={`text-[9px] font-black uppercase tracking-wider px-2 py-0.5 rounded ${color}`}>
      {label}
    </span>
  );

  return (
    <div className="w-full max-w-none bg-[#0d0f12] border border-[#232733] rounded p-6 font-mono text-zinc-300 text-xs">
      {/* Title bar: spans full width, SAVE primary action immediately recognizable */}
      <div className="border-b border-[#232733] pb-3 mb-6 flex items-center justify-between">
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
          className="px-4 py-2 bg-[#c5ff42] hover:bg-[#b5f030] text-black font-bold text-xs rounded transition-colors btn-focus btn-active"
        >
          SAVE SETTINGS
        </button>
      </div>

      {msg && (
        <div className="bg-[#172514] border border-[#3b661d] text-[#c5ff42] px-3 py-1.5 rounded text-xs mb-4">
          {msg}
        </div>
      )}

      {/* Two-column architectural grid using available screen space */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ====== SECTION 1: AVAILABILITY ====== */}
        <section className="bg-[#11141a] border border-[#232733] rounded overflow-hidden flex flex-col">
          <div className="bg-[#151922] border-b border-[#232733] px-3 py-2 flex items-center justify-between">
            {sectionBadge("1 · AVAILABILITY", "bg-[#c5ff42]/10 text-[#c5ff42] border border-[#c5ff42]/30")}
          </div>
          <div className="p-4 space-y-4">
            <div>
              <span className="text-[10px] text-zinc-400 block mb-2">WORKING DAYS</span>
              <div className="flex gap-1.5 flex-wrap">
                {DAY_NAMES.map((d, i) => {
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
          </div>
        </section>

        {/* ====== SECTION 2: SCHEDULING ====== */}
        <section className="bg-[#11141a] border border-[#232733] rounded overflow-hidden flex flex-col">
          <div className="bg-[#151922] border-b border-[#232733] px-3 py-2 flex items-center justify-between">
            {sectionBadge("2 · SCHEDULING", "bg-[#73a7f7]/10 text-[#73a7f7] border border-[#73a7f7]/30")}
          </div>
          <div className="p-4 space-y-4">
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
        </section>

        {/* ====== SECTION 3: AI PROVIDER ====== */}
        <section className="bg-[#11141a] border border-[#232733] rounded overflow-hidden flex flex-col">
          <div className="bg-[#151922] border-b border-[#232733] px-3 py-2 flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              {sectionBadge("3 · AI PROVIDER (OPTIONAL)", "bg-[#ff7d8d]/10 text-[#ff7d8d] border border-[#ff7d8d]/30")}
              {provider && (
                <span
                  className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${
                    provider.status === "connected"
                      ? "bg-[#172514] text-[#c5ff42] border-[#3b661d]"
                      : provider.status === "error"
                      ? "bg-[#3a1419] text-[#ff7d8d] border-[#7d222e]"
                      : "bg-[#1c202a] text-zinc-500 border-[#232733]"
                  }`}
                >
                  {provider.status === "connected"
                    ? "AI CONNECTED"
                    : provider.status === "error"
                    ? "AI ERROR"
                    : "AI NOT CONFIGURED"}
                </span>
              )}
            </div>
          </div>
          <div className="p-4 space-y-4">
            {/* Connection status line */}
            <div className="bg-[#0c0e13] rounded border border-[#232733] p-2.5 text-[10px]">
              <div className="flex justify-between mb-1">
                <span className="text-zinc-400">ACTIVE PROVIDER</span>
                <span className="text-white font-mono">
                  {providerActive ? provider.provider.toUpperCase() : "NONE (OFFLINE)"}
                </span>
              </div>
              <div className="flex justify-between mb-1">
                <span className="text-zinc-400">SELECTED MODEL</span>
                <span className="text-white font-mono truncate max-w-xs">
                  {provider && provider.model ? provider.model : "—"}
                </span>
              </div>
              <div className="flex justify-between mb-1">
                <span className="text-zinc-400">API KEY STORED</span>
                <span className={`text-[9px] font-mono ${keyPresent ? "text-[#c5ff42]" : "text-zinc-500"}`}>
                  {keyPresent ? "YES (backend only)" : "NO"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">AI AVAILABLE</span>
                <span className={`text-[9px] font-mono ${aiAvailable ? "text-[#c5ff42]" : "text-zinc-500"}`}>
                  {aiAvailable ? "YES" : "NO — APP USABLE WITHOUT AI"}
                </span>
              </div>
            </div>

            <div>
              <span className="text-[10px] text-zinc-400 block mb-2">CONFIGURATION</span>
              <p className="text-[10px] text-zinc-500 mb-2">
                Free Gemini API or free OpenRouter models. Keys are stored locally on the backend —
                never sent to the browser.
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
                    placeholder="e.g. gemini-2.5-flash"
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
              {provider?.last_error && (
                <div className="bg-[#3a1419] border border-[#7d222e] text-[#ff7d8d] p-2 rounded text-[9px]">
                  <span className="text-[#ff7d8d] font-bold block mb-0.5">LAST AI ERROR</span>
                  {provider.last_error.kind.toUpperCase()}: {provider.last_error.message}
                </div>
              )}
            </div>
          </div>
        </section>

        {/* ====== SECTION 4: DATA / STORAGE ====== */}
        <section className="bg-[#11141a] border border-[#232733] rounded overflow-hidden flex flex-col">
          <div className="bg-[#151922] border-b border-[#232733] px-3 py-2 flex items-center justify-between">
            {sectionBadge("4 · DATA / STORAGE", "bg-[#c5ff42]/10 text-[#c5ff42] border border-[#c5ff42]/30")}
          </div>
          <div className="p-4 space-y-3">
            <p className="text-[10px] text-zinc-400">
              Local-first SQLite storage in <code className="text-zinc-200">backend/data/monolith.db</code>.
              No cloud dependency or account required.
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <button
                onClick={handleExport}
                className="px-3 py-2 bg-[#14171f] hover:bg-[#202635] text-zinc-200 border border-[#232733] rounded text-xs font-bold btn-focus btn-active"
              >
                📥 EXPORT BACKUP (.JSON)
              </button>
              <label className="px-3 py-2 bg-[#14171f] hover:bg-[#202635] text-zinc-200 border border-[#232733] rounded text-xs font-bold cursor-pointer inline-block btn-focus btn-active">
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
                className="px-3 py-2 bg-[#162714] hover:bg-[#20361c] text-[#c5ff42] border border-[#3b661d] rounded text-xs font-bold btn-focus btn-active"
              >
                ✦ LOAD DEMO SCENARIOS
              </button>
              <button
                onClick={handleReset}
                className="px-3 py-2 bg-[#261418] hover:bg-[#381a20] text-[#ff7d8d] border border-[#7d222e] rounded text-xs font-bold btn-focus btn-active"
              >
                ✕ WIPE DATABASE
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
