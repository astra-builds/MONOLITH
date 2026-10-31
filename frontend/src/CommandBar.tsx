import { useState } from "react";
import { api } from "./api";

interface Proposal {
  summary?: string;
  clarifications?: string[];
  projects?: Array<{
    name: string;
    kind?: string;
    total_sessions?: number;
    session_minutes?: number;
    target_deadline?: string;
  }>;
  tasks?: Array<{
    title: string;
    estimated_minutes?: number;
    deadline?: string;
    priority?: number;
    preferred_days?: number[];
  }>;
  commitments?: Array<{
    title: string;
    tag?: string;
    recurrence?: string;
    days_of_week?: number[];
    start_time?: string;
    end_time?: string;
  }>;
}

export default function CommandBar({ onApplied }: { onApplied: () => void }) {
  const [text, setText] = useState("");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [sourceBadge, setSourceBadge] = useState<string>("");
  const [previewSchedule, setPreviewSchedule] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [clarificationAnswer, setClarificationAnswer] = useState("");

  const submit = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setMsg("");
    setProposal(null);
    setPreviewSchedule(null);

    try {
      const res = await api.ai.extract(text);
      if (res && res.proposal) {
        setProposal(res.proposal);
        setSourceBadge(res.source === "ai" ? "AI SYNTHESIS" : "OFFLINE INTERPRETER");
        setMsg(res.message || "");
      } else {
        setMsg("Could not parse request. Try: 'course AI 10 sessions 2h sat' or 'class CS101 wed 10:00-12:00'.");
      }
    } catch (e: any) {
      setMsg(e.message);
    }
    setLoading(false);
  };

  const handlePreview = async () => {
    setLoading(true);
    try {
      const prev = await api.schedule.preview();
      setPreviewSchedule(prev);
    } catch (e: any) {
      setMsg("Preview error: " + e.message);
    }
    setLoading(false);
  };

  const apply = async () => {
    if (!proposal) return;
    setLoading(true);
    try {
      await api.ai.apply(proposal);
      await api.schedule.apply();
      setProposal(null);
      setPreviewSchedule(null);
      setText("");
      setMsg("✓ Applied changes and updated schedule.");
      onApplied();
    } catch (e: any) {
      setMsg("Failed to apply: " + e.message);
    }
    setLoading(false);
  };

  const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  return (
    <div className="border-b border-[#232733] px-3 py-2 bg-[#11141a] font-mono select-none">
      <div className="flex gap-2 items-center">
        <div className="flex items-center gap-1 text-[#c5ff42] font-black text-xs px-2 py-1.5 bg-[#0d0f12] border border-[#232733] rounded">
          <span>λ:plan</span>
        </div>
        <input
          className="flex-1 bg-[#0d0f12] border border-[#232733] px-3 py-1.5 text-xs text-white rounded outline-none focus:border-[#c5ff42] transition-colors"
          placeholder="Describe goals, courses, or classes (e.g. 'course ML 10 sessions 2h sat' or 'class CS101 wed 10:00-12:00')"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
        />
        <button
          onClick={submit}
          disabled={loading}
          className="px-4 py-1.5 bg-[#c5ff42] hover:bg-[#b5f030] text-black font-bold text-xs rounded transition-colors"
        >
          {loading ? "PARSING..." : "INTERPRET"}
        </button>
      </div>

      {msg && (
        <div className="text-[10px] text-zinc-400 mt-1.5 flex items-center gap-1.5">
          <span className="text-[#c5ff42]">✦</span>
          <span>{msg}</span>
        </div>
      )}

      {/* Structured Proposal Review Cards */}
      {proposal && (
        <div className="mt-2.5 border border-[#232733] p-3 bg-[#0d0f12] rounded space-y-2.5 shadow-2xl">
          <div className="flex items-center justify-between border-b border-[#232733] pb-1.5">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#c5ff42] animate-pulse"></span>
              <span className="font-bold text-white text-xs">
                PROPOSED SCHEDULE PLAN: {proposal.summary}
              </span>
              {sourceBadge && (
                <span
                  className={`px-1.5 py-0.2 rounded font-bold text-[8px] uppercase border ${
                    sourceBadge.includes("AI")
                      ? "bg-[#221735] text-[#c19bf5] border-[#8b61c9]"
                      : "bg-[#162714] text-[#c5ff42] border-[#4e8529]"
                  }`}
                >
                  {sourceBadge}
                </span>
              )}
            </div>
            <span className="text-[9px] text-zinc-500 font-mono">
              REVIEW BEFORE APPLYING
            </span>
          </div>

          {/* Clarification questions */}
          {proposal.clarifications && proposal.clarifications.length > 0 && (
            <div className="bg-[#241a15] border border-[#7a481e] p-2 rounded text-[10px] space-y-1.5">
              <span className="text-[#f59e0b] font-bold block">
                CLARIFICATION REQUIRED:
              </span>
              <ul className="list-disc pl-4 text-zinc-300">
                {proposal.clarifications.map((q, idx) => (
                  <li key={idx}>{q}</li>
                ))}
              </ul>
              <div className="flex gap-2 pt-1">
                <input
                  className="flex-1 bg-[#14100c] border border-[#7a481e] px-2 py-1 text-xs text-white rounded outline-none"
                  placeholder="Type your clarification answer..."
                  value={clarificationAnswer}
                  onChange={(e) => setClarificationAnswer(e.target.value)}
                />
                <button
                  onClick={() => {
                    setText((prev) => `${prev}. Note: ${clarificationAnswer}`);
                    setClarificationAnswer("");
                    submit();
                  }}
                  className="px-2 py-1 bg-[#f59e0b] text-black font-bold text-[10px] rounded"
                >
                  REFINE PROPOSAL
                </button>
              </div>
            </div>
          )}

          {/* Structured Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[10px]">
            {/* Projects / Courses */}
            {proposal.projects && proposal.projects.length > 0 && (
              <div className="bg-[#14171f] p-2 rounded border border-[#232733] space-y-1">
                <span className="text-zinc-500 font-bold block text-[8px] uppercase">
                  PROJECTS & COURSES ({proposal.projects.length})
                </span>
                {proposal.projects.map((p, i) => (
                  <div key={i} className="text-zinc-200">
                    <span className="font-bold text-white">{p.name}</span>
                    <span className="text-zinc-500 block text-[9px]">
                      {p.kind} · {p.total_sessions} sessions × {p.session_minutes}m
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Commitments */}
            {proposal.commitments && proposal.commitments.length > 0 && (
              <div className="bg-[#14171f] p-2 rounded border border-[#232733] space-y-1">
                <span className="text-zinc-500 font-bold block text-[8px] uppercase">
                  FIXED COMMITMENTS ({proposal.commitments.length})
                </span>
                {proposal.commitments.map((c, i) => (
                  <div key={i} className="text-zinc-200">
                    <span className="font-bold text-white">{c.title}</span>
                    <span className="text-zinc-500 block text-[9px]">
                      {c.tag} · {(c.days_of_week || []).map((d) => dayNames[d]).join(", ")} ·{" "}
                      {c.start_time}–{c.end_time}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Tasks */}
            {proposal.tasks && proposal.tasks.length > 0 && (
              <div className="bg-[#14171f] p-2 rounded border border-[#232733] space-y-1">
                <span className="text-zinc-500 font-bold block text-[8px] uppercase">
                  TASKS ({proposal.tasks.length})
                </span>
                <div className="max-h-24 overflow-y-auto space-y-0.5">
                  {proposal.tasks.map((t, i) => (
                    <div key={i} className="truncate text-zinc-300">
                      • {t.title} ({t.estimated_minutes}m)
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Schedule Diff Preview (if requested) */}
          {previewSchedule && (
            <div className="bg-[#141b24] p-2 rounded border border-[#3b5880] text-[10px] space-y-1">
              <span className="text-[#73a7f7] font-bold block text-[9px] uppercase">
                CALENDAR PREVIEW DIFF
              </span>
              <div className="flex gap-4 text-zinc-300 font-mono">
                <span>Created: {previewSchedule.diff?.created?.length || 0}</span>
                <span>Unchanged: {previewSchedule.diff?.unchanged?.length || 0}</span>
                <span>Conflicts: {previewSchedule.unscheduled?.length || 0}</span>
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-2 pt-1 border-t border-[#232733]">
            <button
              onClick={apply}
              disabled={loading}
              className="px-4 py-1.5 bg-[#c5ff42] hover:bg-[#b5f030] text-black font-bold text-xs rounded transition-colors flex items-center gap-1.5"
            >
              <span>✓ APPLY & RECALCULATE</span>
            </button>
            <button
              onClick={handlePreview}
              disabled={loading}
              className="px-3 py-1.5 bg-[#18202c] hover:bg-[#222e3e] text-[#73a7f7] border border-[#3b5880] text-xs rounded font-bold"
            >
              PREVIEW ON CALENDAR
            </button>
            <button
              onClick={() => {
                setProposal(null);
                setPreviewSchedule(null);
              }}
              className="px-3 py-1.5 bg-[#1c202a] text-zinc-400 hover:text-white text-xs rounded border border-[#232733]"
            >
              DISCARD
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
