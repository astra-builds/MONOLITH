const BASE = "http://127.0.0.1:8000";
async function req(path: string, opts: RequestInit = {}) {
  const r = await fetch(BASE + path, { ...opts, headers: { "Content-Type": "application/json", ...(opts.headers||{}) } });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
export const api = {
  settings: { get: () => req("/settings"), update: (d:any) => req("/settings", { method:"PATCH", body: JSON.stringify(d) }) },
  projects: {
    list: () => req("/projects"),
    get: (id:number) => req(`/projects/${id}`),
    create: (d:any) => req("/projects", {method:"POST", body:JSON.stringify(d)}),
    update: (id:number,d:any) => req(`/projects/${id}`, {method:"PATCH", body:JSON.stringify(d)}),
    delete: (id:number) => req(`/projects/${id}`, {method:"DELETE"}),
    generateSessions: (id:number, d:any) => req(`/projects/${id}/generate-sessions`, {method:"POST", body:JSON.stringify(d)}),
  },
  tasks: {
    list: (p?:any) => req("/tasks" + (p? "?" + new URLSearchParams(p):"")),
    get:(id:number)=>req(`/tasks/${id}`),
    create:(d:any)=>req("/tasks",{method:"POST",body:JSON.stringify(d)}),
    update:(id:number,d:any)=>req(`/tasks/${id}`,{method:"PATCH",body:JSON.stringify(d)}),
    delete:(id:number)=>req(`/tasks/${id}`,{method:"DELETE"}),
    complete:(id:number)=>req(`/tasks/${id}/complete`,{method:"POST"}),
    skip:(id:number)=>req(`/tasks/${id}/skip`,{method:"POST"}),
  },
  commitments: {
    list:(tag?:string)=>req("/commitments" + (tag ? `?tag=${encodeURIComponent(tag)}` : "")),
    create:(d:any)=>req("/commitments",{method:"POST",body:JSON.stringify(d)}),
    update:(id:number,d:any)=>req(`/commitments/${id}`,{method:"PATCH",body:JSON.stringify(d)}),
    delete:(id:number)=>req(`/commitments/${id}`,{method:"DELETE"}),
  },
  schedule: {
    list:(s?:string,e?:string)=>req("/schedule"+(s?`?start=${s}&end=${e}`:"")),
    generate:(preview:boolean)=>req(`/schedule/generate?preview=${preview}`,{method:"POST"}),
    apply:()=>req("/schedule/apply",{method:"POST"}),
    regenerate:()=>req("/schedule/regenerate",{method:"POST"}),
    preview:()=>req("/schedule/preview",{method:"POST"}),
    rescheduleMissed:()=>req("/schedule/reschedule-missed",{method:"POST"}),
    updateBlock:(id:number,d:any)=>req(`/schedule/blocks/${id}`,{method:"PATCH",body:JSON.stringify(d)}),
    deleteBlock:(id:number)=>req(`/schedule/blocks/${id}`,{method:"DELETE"}),
    move:(id:number,s:string,e:string)=>req(`/schedule/blocks/${id}/move?start_dt=${encodeURIComponent(s)}&end_dt=${encodeURIComponent(e)}`,{method:"POST"}),
  },
  ai: {
    extract:(text:string)=>req("/ai/extract",{method:"POST",body:JSON.stringify({text})}),
    apply:(p:any)=>req("/ai/apply",{method:"POST",body:JSON.stringify(p)}),
    chat:(text:string)=>req("/ai/chat",{method:"POST",body:JSON.stringify({text})}),
  },
  demo: {
    seed:()=>req("/demo/seed",{method:"POST"}),
    reset:()=>req("/demo/reset",{method:"POST"}),
  },
  export: ()=>req("/export"),
  import: (data:any)=>req("/import",{method:"POST",body:JSON.stringify(data)}),
};
