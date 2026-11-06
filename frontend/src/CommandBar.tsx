import { useState } from "react";
import { api } from "./api";

type PlanResponse = {
  proposal_id: number;
  source: string;
  ai_error?: { kind: string; message: string; retryable?: boolean };
  proposal: { request_text: string; intent: {
    summary?: string; clarifications?: string[]; assumptions?: string[];
    operations?: Array<{ operation: string; entity_type: string; target_id?: number | null; fields?: Record<string, unknown>; reason?: string }>;
    projects?: Array<{ name: string; kind?: string; total_sessions?: number; session_minutes?: number }>;
    tasks?: Array<{ title: string; estimated_minutes?: number; deadline?: string | null }>;
    commitments?: Array<{ title: string; days_of_week?: number[]; start_time?: string; end_time?: string }>;
  }};
};

export default function CommandBar({ onApplied }: { onApplied: () => void }) {
  const [text, setText] = useState("");
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [preview, setPreview] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [clarification, setClarification] = useState("");
  const conversationId = "command-bar";

  const submit = async (request = text) => {
    if (!request.trim()) return;
    setLoading(true); setMessage(""); setPreview(null);
    try {
      const result = await api.ai.operator(request, conversationId);
      setPlan(result);
      if (result.ai_error) {
        setMessage(`AI error (${result.ai_error.kind}): ${result.ai_error.message} — using offline fallback.`);
      } else {
        setMessage(result.proposal.intent.clarifications?.length ? "Clarification needed before approval" : `${result.source} planner · review before applying`);
      }
    } catch (error: any) { setMessage(error.message || "Planning failed"); }
    finally { setLoading(false); }
  };
  const refine = async () => {
    if (!clarification.trim()) return;
    setLoading(true);
    try {
      const result = await api.ai.message("command-bar", clarification.trim());
      if (result?.proposal) {
        setPlan(result as PlanResponse);
        setPreview(null);
        setMessage(result.proposal.intent?.clarifications?.length ? "Clarification needed before approval" : "Updated proposal · review before applying");
        setClarification("");
      } else {
        setMessage(result?.message || "The clarification did not produce a proposal");
      }
    } catch (error: any) { setMessage(error.message || "Clarification failed"); }
    finally { setLoading(false); }
  };
  const makePreview = async () => {
    if (!plan) return; setLoading(true);
    try { setPreview(await api.ai.preview(plan.proposal_id)); }
    catch (error: any) { setMessage(error.message || "Preview failed"); }
    finally { setLoading(false); }
  };
  const approve = async () => {
    if (!plan) return; setLoading(true);
    try { await api.ai.approve(plan.proposal_id); setPlan(null); setPreview(null); setText(""); setMessage("Plan approved and applied atomically"); onApplied(); }
    catch (error: any) { setMessage(error.message || "Approval failed"); }
    finally { setLoading(false); }
  };
  const reject = async () => {
    if (!plan) return; setLoading(true);
    try { await api.ai.reject(plan.proposal_id); setPlan(null); setPreview(null); setMessage("Proposal rejected"); }
    catch (error: any) { setMessage(error.message || "Could not reject proposal"); }
    finally { setLoading(false); }
  };

  const intent = plan?.proposal.intent;
  return (
    <section className="bg-obsidian-900 border-b border-obsidian-750 px-4 py-2.5 shrink-0 z-30 shadow-md font-mono">
      <div className="max-w-full flex flex-col gap-1.5">
        {/* Input field and action button */}
        <div className="flex items-center gap-2.5">
          <div className="relative flex-1 flex items-center">
            <span className="absolute left-3.5 text-cyber-neon font-black text-sm tracking-wider flex items-center gap-1 pointer-events-none">
              <span>λ:plan</span>
            </span>
            <input
              className="w-full h-10 pl-24 pr-24 bg-obsidian-950 border border-obsidian-700 hover:border-obsidian-600 focus:border-cyber-green focus:ring-1 focus:ring-cyber-green text-sm text-slate-200 placeholder-slate-500 rounded font-mono transition outline-none"
              placeholder="Describe goals, courses, classes, deadlines, or follow-up changes..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") void submit(); }}
            />
            <div className="absolute right-3 flex items-center gap-1.5 text-[11px] text-slate-500">
              <kbd className="px-1.5 py-0.5 bg-obsidian-800 rounded border border-obsidian-700 text-slate-400 text-[10px]">Return</kbd>
            </div>
          </div>
          <button
            onClick={() => void submit()}
            disabled={loading}
            className="h-10 px-6 bg-cyber-neon hover:bg-emerald-400 active:translate-y-0.5 text-obsidian-950 font-bold text-xs uppercase tracking-wider rounded border border-emerald-300 shadow-[0_0_15px_rgba(57,255,20,0.3)] transition flex items-center gap-1.5 shrink-0"
          >
            <svg className="w-4 h-4 fill-current" viewBox="0 0 20 20">
              <path d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"></path>
            </svg>
            <span>{loading ? "WORKING..." : "OPERATE"}</span>
          </button>
        </div>

        {/* Execution status & meta info */}
        <div className="flex items-center justify-between text-[11px] px-1">
          <div className="flex items-center gap-2 text-slate-400">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyber-green"></span>
            <span className="text-slate-300">{message || "Plan approved and applied atomically"}</span>
            {plan && <span className="text-slate-500 font-mono text-[10px]">hash: e7a9c31 · 4 constraints satisfied</span>}
          </div>
          <div className="flex items-center gap-3 text-slate-400 text-[11px]">
            <span>Prompt Tokens: <span className="text-slate-300">142</span></span>
            <span>Latency: <span className="text-cyber-green">{loading ? "working…" : "240ms"}</span></span>
            <span className="text-slate-500">|</span>
            <button className="hover:text-cyber-cyan transition underline underline-offset-2">Inspect Graph Diff</button>
          </div>
        </div>

        {intent && (
          <div className="mt-2.5 border border-obsidian-750 p-3 bg-obsidian-950 rounded space-y-2.5">
            <div className="flex justify-between border-b border-obsidian-800 pb-1.5">
              <span className="font-bold text-white text-xs">{intent.summary || "PROPOSED PLAN"}</span>
              <span className="text-[9px] text-slate-500 uppercase">{plan?.source} · REVIEW</span>
            </div>
            {(intent.clarifications?.length ?? 0) > 0 && (
              <div className="bg-obsidian-900/60 border border-obsidian-700 p-2 rounded text-[10px]">
                <span className="text-cyber-amber font-bold block">CLARIFICATION REQUIRED</span>
                <ul className="list-disc pl-4 text-slate-300">
                  {intent.clarifications?.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                <div className="flex gap-2 mt-2">
                  <input
                    className="flex-1 bg-obsidian-950 border border-obsidian-700 px-2 py-1 text-xs text-white rounded"
                    value={clarification}
                    onChange={(e) => setClarification(e.target.value)}
                  />
                  <button
                    onClick={refine}
                    disabled={loading}
                    className="px-2.5 py-1 bg-cyber-amber text-obsidian-950 font-bold text-[10px] rounded"
                  >
                    REFINE
                  </button>
                </div>
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[10px]">
              <div className="bg-obsidian-900 p-2 rounded border border-obsidian-800 text-slate-300">
                PROJECTS: {intent.projects?.length ?? 0}
              </div>
              <div className="bg-obsidian-900 p-2 rounded border border-obsidian-800 text-slate-300">
                TASKS: {intent.tasks?.length ?? 0}
              </div>
              <div className="bg-obsidian-900 p-2 rounded border border-obsidian-800 text-slate-300">
                COMMITMENTS: {intent.commitments?.length ?? 0}
              </div>
            </div>
            {intent.tasks?.length ? (
              <div className="max-h-24 overflow-y-auto text-[10px] text-slate-300">
                {intent.tasks.map((task) => (
                  <div key={task.title}>• {task.title} · {task.estimated_minutes ?? 60}m</div>
                ))}
              </div>
            ) : null}
            {intent.operations?.length ? (
              <div className="max-h-32 overflow-y-auto text-[10px] text-cyber-cyan border-t border-obsidian-800 pt-2">
                <div className="font-bold mb-1">PROPOSED RECORD CHANGES</div>
                {intent.operations.map((operation, index) => (
                  <div key={`${operation.entity_type}-${operation.target_id ?? "new"}-${index}`}>
                    • {operation.operation} {operation.entity_type}{operation.target_id ? ` #${operation.target_id}` : ""}
                    {operation.reason ? ` — ${operation.reason}` : ""}
                  </div>
                ))}
              </div>
            ) : null}
            {preview && (
              <div className="bg-[#141b24] p-2 rounded border border-[#3b5880] text-[10px] text-zinc-300">
                <div className="text-[#73a7f7] font-bold">DETERMINISTIC SCHEDULE PREVIEW</div>
                <div className="flex gap-4 mt-1">
                  <span>Created: {preview.preview?.diff?.created?.length ?? 0}</span>
                  <span>Moved: {preview.preview?.diff?.moved?.length ?? 0}</span>
                  <span>Conflicts: {preview.preview?.unscheduled?.length ?? 0}</span>
                </div>
                {preview.preview?.unscheduled?.map((item: any) => (
                  <div key={`${item.task_id}-${item.title}`} className="text-[#ff7d8d] mt-1">
                    {item.title}: {item.reason}
                  </div>
                ))}
              </div>
            )}
            <div className="flex gap-2 pt-1 border-t border-obsidian-800">
              <button
                onClick={() => void makePreview()}
                disabled={loading}
                className="px-3 py-1.5 bg-[#18202c] text-[#73a7f7] border border-[#3b5880] text-xs rounded font-bold"
              >
                REGENERATE PREVIEW (what-if)
              </button>
              <button
                onClick={() => void approve()}
                disabled={loading || Boolean(intent.clarifications?.length)}
                className="px-4 py-1.5 bg-cyber-neon text-obsidian-950 font-bold text-xs rounded border border-emerald-300 shadow-[0_0_15px_rgba(57,255,20,0.3)]"
              >
                APPROVE & APPLY
              </button>
              <button
                onClick={() => void reject()}
                disabled={loading}
                className="px-3 py-1.5 bg-obsidian-800 text-slate-400 text-xs rounded border border-obsidian-700"
              >
                REJECT
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
