import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const DEFAULT_TICKET = "FR-1842";
const PUBLIC_API =
  import.meta.env.VITE_PUBLIC_API_URL ||
  import.meta.env.NEXT_PUBLIC_API_URL ||
  "";

function apiPath(path) {
  return `${PUBLIC_API}${path}`;
}

const STATUS_COLOR = {
  CONFIRMED: "bg-emerald-950/70 text-emerald-200 border-emerald-400",
  CONTRADICTED: "bg-rose-950/80 text-rose-100 border-rose-400",
  UNTESTED: "bg-amber-950/70 text-amber-100 border-amber-400",
  UNREACHABLE: "bg-slate-800 text-slate-100 border-slate-400",
  ABSTAIN: "bg-violet-950/70 text-violet-100 border-violet-400",
};

const RAIL_PHASE = {
  idle: "idle",
  a_planning: "planning",
  a_talking: "talking",
  a_claims: "structured result",
  b_planning: "planning",
  b_talking: "talking",
  b_claims: "structured result",
  merged: "merged",
};

export default function App() {
  const [ticketId, setTicketId] = useState(DEFAULT_TICKET);
  const [ticket, setTicket] = useState(null);
  const [graph, setGraph] = useState([]);
  const [action, setAction] = useState(null);
  const [job, setJob] = useState(null);
  const [preview, setPreview] = useState(null);
  const [mode, setMode] = useState("preview");
  const [error, setError] = useState("");
  const [empty, setEmpty] = useState(false);
  const [running, setRunning] = useState(false);
  const [phase, setPhase] = useState("idle");
  const [fixtures] = useState(true);
  const [started] = useState(() => Date.now() - 47 * 60 * 1000);
  const [now, setNow] = useState(Date.now());
  const [networkDown, setNetworkDown] = useState(false);
  const inflight = useRef(false);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const slaUsd = ticket?.sla_usd_per_hour || 18000;
  const burnUsd = ((now - started) / 3600000) * slaUsd;

  const loadTicket = useCallback(async (id) => {
    const res = await fetch(apiPath(`/v1/tickets/${id}`));
    if (res.status === 404) {
      setEmpty(true);
      setTicket(null);
      setGraph([]);
      setAction(null);
      return;
    }
    if (!res.ok) throw new Error(`ticket ${res.status}`);
    const body = await res.json();
    setEmpty(false);
    setTicket(body.ticket);
    setGraph(body.graph || []);
    setAction(body.action);
  }, []);

  useEffect(() => {
    setError("");
    loadTicket(ticketId).catch((err) => setError(String(err.message || err)));
  }, [ticketId, loadTicket]);

  useEffect(() => {
    if (!job?.id || job.status === "completed" || job.status === "failed") return undefined;
    const timer = setInterval(async () => {
      try {
        const res = await fetch(apiPath(`/v1/jobs/${job.id}`));
        if (!res.ok) return;
        const body = await res.json();
        setJob(body);
        setPhase(body.phase || "running");
        if (body.result?.graph) setGraph(body.result.graph);
        if (body.result?.action) setAction(body.result.action);
        if (body.status === "completed" || body.status === "failed") {
          setRunning(false);
          inflight.current = false;
        }
      } catch {
        setNetworkDown(true);
      }
    }, 280);
    return () => clearInterval(timer);
  }, [job?.id, job?.status]);

  useEffect(() => {
    if (!ticketId) return undefined;
    const es = new EventSource(apiPath(`/v1/tickets/${ticketId}/events`));
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.phase) setPhase(data.phase);
        if (data.type === "job_complete") loadTicket(ticketId);
      } catch {
        /* ping */
      }
    };
    es.onerror = () => {
      es.close();
    };
    return () => es.close();
  }, [ticketId, loadTicket]);

  const missingConsent = useMemo(
    () => (ticket?.parties || []).some((p) => p.consent === false),
    [ticket],
  );

  const runParity = async () => {
    if (inflight.current || running) return;
    if (empty) {
      setError("No ticket loaded. Choose FR-1842 or FR-1900.");
      return;
    }
    if (missingConsent) {
      setError("Cannot run: stored consent is missing for at least one party.");
      return;
    }
    inflight.current = true;
    setRunning(true);
    setError("");
    setNetworkDown(false);
    setPhase("queued");
    try {
      const res = await fetch(apiPath(`/v1/tickets/${ticketId}/parity`), {
        method: "POST",
        headers: { "Idempotency-Key": `ui-${ticketId}` },
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `parity ${res.status}`);
      setJob(body);
      setPhase(body.phase || "queued");
      if (body.result?.graph) setGraph(body.result.graph);
      if (body.result?.action) setAction(body.result.action);
    } catch (err) {
      setNetworkDown(true);
      setError(String(err.message || err));
      setRunning(false);
      inflight.current = false;
    }
  };

  const runPreview = async () => {
    setError("");
    try {
      const res = await fetch(apiPath(`/v1/tickets/${ticketId}/preview`), { method: "POST" });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || "preview failed");
      setPreview(body);
    } catch (err) {
      setError(String(err.message || err));
    }
  };

  const parties = ticket?.parties || [];
  const claimsA = job?.result?.claims_a || preview?.claims_a || [];
  const claimsB = job?.result?.claims_b || [];
  const planB = job?.result?.plan_b || preview?.plan_b;
  const telemetry = job?.telemetry || {};

  const slaClock = useMemo(() => {
    const s = Math.floor((now - started) / 1000);
    const m = String(Math.floor(s / 60)).padStart(2, "0");
    const r = String(s % 60).padStart(2, "0");
    return `${m}:${r}`;
  }, [now, started]);

  const railStatus = (role) => {
    if (role === "A") {
      if (["a_planning", "a_talking", "a_claims"].includes(phase)) return RAIL_PHASE[phase];
      if (["b_planning", "b_talking", "b_claims", "merged"].includes(phase)) return "completed";
    }
    if (role === "B") {
      if (["b_planning", "b_talking", "b_claims"].includes(phase)) return RAIL_PHASE[phase];
      if (phase === "merged") return "completed";
      if (["a_planning", "a_talking", "a_claims"].includes(phase)) return "waiting for A";
    }
    return job?.status === "completed" ? "completed" : "idle";
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {fixtures && (
        <div className="bg-amber-400 text-slate-950 text-xs font-semibold tracking-wide px-4 py-1.5" role="status">
          FIXTURE MODE. USE_FIXTURES=true. CALL-E behind CallePort. No live carrier.
        </div>
      )}
      <header className="border-b border-slate-800 px-6 py-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">CallParity workbench</p>
          <label className="block mt-2 text-xs text-slate-400" htmlFor="ticket-select">Ticket</label>
          <select id="ticket-select" className="bg-slate-900 border border-slate-700 rounded-md px-2 py-1 text-lg font-semibold" value={ticketId} onChange={(e) => setTicketId(e.target.value)}>
            <option value="FR-1842">FR-1842 contradiction</option>
            <option value="FR-1900">FR-1900 control</option>
            <option value="EMPTY">Empty ticket</option>
          </select>
          <h1 className="sr-only">{ticket?.id || ticketId}</h1>
          <p className="text-slate-300 max-w-2xl mt-2">{ticket?.fact || (empty ? "No ticket in ledger." : "Loading...")}</p>
        </div>
        <div className="text-right" aria-live="polite">
          <p className="font-mono text-3xl text-rose-300" aria-label="SLA clock">{slaClock}</p>
          <p className="text-sm text-rose-200">SLA burn ${burnUsd.toFixed(0)} / ${Math.round(slaUsd / 1000)}k/hr</p>
          <p className="text-xs text-slate-400">{ticket?.entities?.pallet_id} {ticket?.entities?.sku}</p>
        </div>
      </header>
      <main className="px-6 py-6 grid gap-6 lg:grid-cols-12">
        <section className="lg:col-span-4 space-y-4">
          <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-4">
            <fieldset>
              <legend className="font-semibold">Execution</legend>
              <div className="mt-3 flex gap-4 text-sm">
                <label className="inline-flex items-center gap-2">
                  <input type="radio" name="mode" value="preview" checked={mode === "preview"} onChange={() => setMode("preview")} /> Preview
                </label>
                <label className="inline-flex items-center gap-2">
                  <input type="radio" name="mode" value="run" checked={mode === "run"} onChange={() => setMode("run")} /> Run
                </label>
              </div>
            </fieldset>
            <div className="mt-4 flex gap-2">
              {mode === "preview" ? (
                <button type="button" onClick={runPreview} className="rounded-md bg-slate-100 hover:bg-white text-slate-950 font-semibold px-4 py-2">Compile plans</button>
              ) : (
                <button type="button" onClick={runParity} disabled={running || missingConsent || empty} className="rounded-md bg-sky-400 hover:bg-sky-300 disabled:opacity-50 text-slate-950 font-semibold px-4 py-2">{running ? "Running..." : "Run parity"}</button>
              )}
            </div>
            {error && <p className="mt-3 text-sm text-rose-200" role="alert">{error}</p>}
            {job && <p className="mt-3 text-xs font-mono text-slate-300">job {job.id} {job.status} phase {phase}</p>}
          </div>
          <div className="grid grid-cols-2 gap-3" aria-label="Call rails">
            {["A", "B"].map((role) => {
              const p = parties.find((x) => x.role === role);
              return (
                <article key={role} className="rounded-xl border border-slate-700 bg-slate-900/80 p-4">
                  <p className="text-xs text-slate-400">Party {role}</p>
                  <h3 className="font-medium leading-tight mt-1">{p?.label || "-"}</h3>
                  <p className="font-mono text-xs text-slate-400 mt-2">{p?.phone_e164 || "no number"}</p>
                  <p className="text-xs mt-3 text-sky-200">{railStatus(role)}</p>
                </article>
              );
            })}
          </div>
          {planB && (
            <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-4">
              <h2 className="font-semibold mb-2">Compiled B plan</h2>
              <p className="text-sm text-slate-200">{planB.goal}</p>
              <ul className="mt-2 text-xs text-slate-300 list-disc pl-4">
                {(planB.selected_questions || []).map((q) => (<li key={q.id}>{q.question}</li>))}
              </ul>
            </div>
          )}
        </section>
        <section className="lg:col-span-5 space-y-4">
          <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-4">
            <h2 className="font-semibold mb-3">Claim graph</h2>
            {!graph.length && <p className="text-sm text-slate-300">No edges yet. Preview or run parity.</p>}
            <ul className="space-y-3">
              {graph.map((edge) => (
                <li key={edge.hypothesis_id} className={`border rounded-lg p-3 ${STATUS_COLOR[edge.status] || "border-slate-600"}`}>
                  <div className="flex justify-between gap-2">
                    <span className="font-mono text-sm">{edge.predicate || edge.hypothesis_id}</span>
                    <span className="text-xs font-semibold">{edge.status}</span>
                  </div>
                  {edge.a_span && <p className="text-xs mt-2">A: {edge.a_span}</p>}
                  {edge.b_span && <p className="text-xs mt-1">B: {edge.b_span}</p>}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-4">
            <h2 className="font-semibold mb-2">Evidence drawer</h2>
            {[...claimsA, ...claimsB].map((c) => (
              <p key={c.id} className="text-xs text-slate-300 mb-2">
                <span className="font-mono text-slate-100">{c.source_party} {c.predicate}</span> {c.confidence} {c.evidence_span}
              </p>
            ))}
          </div>
        </section>
        <section className="lg:col-span-3">
          <div className="rounded-xl border-2 border-sky-400 bg-sky-950 p-4 sticky top-4">
            <p className="text-xs uppercase tracking-widest text-sky-200">Action card (human-owned)</p>
            <h2 className="text-xl font-semibold mt-2">{action?.action || "-"}</h2>
            <p className="text-sm text-slate-100 mt-3">{action?.rationale || "Waiting for the two-call merge."}</p>
          </div>
        </section>
      </main>
      <footer className="border-t border-slate-800 px-6 py-3 text-xs font-mono text-slate-300 flex flex-wrap gap-4">
        <span>latency {telemetry.latency_ms ?? "-"} ms</span>
        <span>mode {telemetry.mode || (fixtures ? "fixture" : "live")}</span>
        <span>claims A {telemetry.claims_a ?? claimsA.length}</span>
        <span>claims B {telemetry.claims_b ?? claimsB.length}</span>
        <span>edges {telemetry.edges ?? graph.length}</span>
        <span>phase {phase}</span>
      </footer>
    </div>
  );
}
