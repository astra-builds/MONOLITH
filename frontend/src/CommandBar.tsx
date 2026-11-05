import { useState } from "react";
import { api } from "./api";

type PlanResponse = {
  proposal_id: number;
  source: string;
  ai_error?: { kind: string; message: string; retryable?: boolean };
  proposal: { request_text: string; intent: {
    summary?: string; clarifications?: string[]; assumptions?: string[];
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

  const submit = async (request = text) => {
    if (!request.trim()) return;
    setLoading(true); setMessage(""); setPreview(null);
    try {
      const result = await api.ai.plan(request);
      setPlan(result);
      if (result.ai_error) {
        setMessage(`AI error (${result.ai_error.kind}): ${result.ai_error.message} — using offline fallback.`);
      } else {
        setMessage(result.proposal.intent.clarifications?.length ? "Clarification needed before approval" : `${result.source} planner · review before applying`);
      }
    } catch (error: any) { setMessage(error.message || "Planning failed"); }
    finally { setLoading(false); }
  };
  const refine = () => { const next = `${text}. Clarification: ${clarification}`; setText(next); setClarification(""); void submit(next); };
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
  return <div className="border-b border-[#232733] px-3 py-2 bg-[#11141a] font-mono select-none">
    <div className="flex gap-2 items-center">
      <span className="text-[#c5ff42] font-black text-xs px-2 py-1.5 bg-[#0d0f12] border border-[#232733] rounded">λ:plan</span>
      <input className="flex-1 bg-[#0d0f12] border border-[#232733] px-3 py-1.5 text-xs text-white rounded outline-none focus:border-[#c5ff42]" placeholder="Describe goals, courses, classes, deadlines, or follow-up changes" value={text} onChange={(event) => setText(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void submit(); }} />
      <button onClick={() => void submit()} disabled={loading} className="px-4 py-1.5 btn-focus btn-active bg-[#c5ff42] text-black font-bold text-xs rounded">{loading ? "WORKING..." : "PLAN"}</button>
    </div>
    {message && <div className="text-[10px] text-zinc-400 mt-1.5">✦ {message}</div>}
    {intent && <div className="mt-2.5 border border-[#232733] p-3 bg-[#0d0f12] rounded space-y-2.5">
      <div className="flex justify-between border-b border-[#232733] pb-1.5"><span className="font-bold text-white text-xs">{intent.summary || "PROPOSED PLAN"}</span><span className="text-[9px] text-zinc-500 uppercase">{plan?.source} · REVIEW</span></div>
      {(intent.clarifications?.length ?? 0) > 0 && <div className="bg-[#241a15] border border-[#7a481e] p-2 rounded text-[10px]"><span className="text-[#f59e0b] font-bold block">CLARIFICATION REQUIRED</span><ul className="list-disc pl-4 text-zinc-300">{intent.clarifications?.map((item) => <li key={item}>{item}</li>)}</ul><div className="flex gap-2 mt-2"><input className="flex-1 bg-[#14100c] border border-[#7a481e] px-2 py-1 text-xs text-white rounded" value={clarification} onChange={(event) => setClarification(event.target.value)} /><button onClick={refine} className="px-2.5 py-1.5 btn-focus btn-active bg-[#f59e0b] text-black font-bold text-[10px] rounded">REFINE</button></div></div>}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[10px]"><div className="bg-[#14171f] p-2 rounded border border-[#232733] text-zinc-300">PROJECTS: {intent.projects?.length ?? 0}</div><div className="bg-[#14171f] p-2 rounded border border-[#232733] text-zinc-300">TASKS: {intent.tasks?.length ?? 0}</div><div className="bg-[#14171f] p-2 rounded border border-[#232733] text-zinc-300">COMMITMENTS: {intent.commitments?.length ?? 0}</div></div>
      {intent.tasks?.length ? <div className="max-h-24 overflow-y-auto text-[10px] text-zinc-300">{intent.tasks.map((task) => <div key={task.title}>• {task.title} · {task.estimated_minutes ?? 60}m</div>)}</div> : null}
      {preview && <div className="bg-[#141b24] p-2 rounded border border-[#3b5880] text-[10px] text-zinc-300"><div className="text-[#73a7f7] font-bold">DETERMINISTIC SCHEDULE PREVIEW</div><div className="flex gap-4 mt-1"><span>Created: {preview.preview?.diff?.created?.length ?? 0}</span><span>Moved: {preview.preview?.diff?.moved?.length ?? 0}</span><span>Conflicts: {preview.preview?.unscheduled?.length ?? 0}</span></div>{preview.preview?.unscheduled?.map((item: any) => <div key={`${item.task_id}-${item.title}`} className="text-red-300 mt-1">{item.title}: {item.reason}</div>)}</div>}
      <div className="flex gap-2 pt-1 border-t border-[#232733]"><button onClick={() => void makePreview()} disabled={loading} className="px-3 py-1.5 btn-focus btn-active bg-[#18202c] text-[#73a7f7] border border-[#3b5880] text-xs rounded font-bold">REGENERATE PREVIEW (what-if)</button><button onClick={() => void approve()} disabled={loading || Boolean(intent.clarifications?.length)} className="px-4 py-1.5 btn-focus btn-active bg-[#c5ff42] text-black font-bold text-xs rounded">APPROVE & APPLY</button><button onClick={() => void reject()} disabled={loading} className="px-3 py-1.5 btn-focus btn-active bg-[#1c202a] text-zinc-400 text-xs rounded border border-[#232733]">REJECT</button></div>
    </div>}
  </div>;
}
