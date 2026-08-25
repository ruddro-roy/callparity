import { useCallback, useEffect, useRef, useState } from "react";

const API = import.meta.env.VITE_PUBLIC_API_URL || "";
const apiPath = (path) => `${API}${path}`;

const TICKETS = [
  { id: "FR-1842", tag: "contradiction" },
  { id: "FR-1900", tag: "control" },
  { id: "FR-1888", tag: "voicemail" },
];

const STATUS_STYLE = {
  CONFIRMED: "bg-emerald-950/70 text-emerald-200 border-emerald-400",
  CONTRADICTED: "bg-rose-950/80 text-rose-100 border-rose-400",
  UNTESTED: "bg-amber-950/70 text-amber-100 border-amber-400",
  UNREACHABLE: "bg-slate-800 text-slate-100 border-slate-400",
  ABSTAIN: "bg-violet-950/70 text-violet-100 border-violet-400",
};

const ACTION_STYLE = {
  RESTAGE_AND_RECALL: "border-rose-400 bg-rose-950/60",
  RELEASE_TRUCK: "border-emerald-400 bg-emerald-950/60",
  HOLD_FOR_HUMAN: "border-amber-400 bg-amber-950/60",
};

const POLARITY_STYLE = {
  asserted: "bg-sky-900 text-sky-200",
  denied: "bg-rose-900 text-rose-200",
  unknown: "bg-slate-800 text-slate-300",
};

const PHASE_LABEL = {
  a_planning: "planning call",
  a_talking: "on the call",
  a_claims: "claims extracted",
  b_planning: "compiling refute plan",
  b_talking: "on the call",
  b_claims: "claims extracted",
  merged: "merged",
};

function maskPhone(phone) {
  if (!phone || phone.length < 9) return phone || "";
  return `${phone.slice(0, 5)}***${phone.slice(-4)}`;
}

function railStatus(role, phase, jobStatus) {
  const aPhases = ["a_planning", "a_talking", "a_claims"];
  const bPhases = ["b_planning", "b_talking", "b_claims"];
  if (role === "A") {
    if (aPhases.includes(phase)) return PHASE_LABEL[phase];
    if (bPhases.includes(phase) || phase === "merged") return "done";
  } else {
    if (bPhases.includes(phase)) return PHASE_LABEL[phase];
    if (phase === "merged") return "done";
    if (aPhases.includes(phase)) return "waiting for A";
  }
  return jobStatus === "completed" ? "done" : "idle";
}

function ClaimCard({ claim }) {
  return (
    <li className="rounded-lg border border-slate-700 bg-slate-900/80 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-base text-slate-100">{claim.predicate}</span>
        <span className={`rounded px-2 py-0.5 text-sm font-semibold ${POLARITY_STYLE[claim.polarity] || ""}`}>
          {claim.polarity}
        </span>
      </div>
      <p className="mt-1 text-sm text-slate-400">confidence {Number(claim.confidence).toFixed(2)}</p>
      {claim.evidence_span && (
        <p className="mt-2 text-base leading-snug text-slate-200">&quot;{claim.evidence_span}&quot;</p>
      )}
    </li>
  );
}

function EdgeRow({ edge }) {
  return (
    <li className={`rounded-lg border p-4 ${STATUS_STYLE[edge.status] || "border-slate-600"}`}>
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-lg">{edge.predicate || edge.hypothesis_id}</span>
        <span className="text-lg font-bold tracking-wide">{edge.status}</span>
      </div>
      <div className="mt-2 grid gap-2 lg:grid-cols-2">
        {edge.a_span && (
          <p className="text-base leading-snug">
            <span className="mr-2 font-semibold text-slate-300">A</span>
            &quot;{edge.a_span}&quot;
          </p>
        )}
        {edge.b_span && (
          <p className="text-base leading-snug">
            <span className="mr-2 font-semibold text-slate-300">B</span>
            &quot;{edge.b_span}&quot;
          </p>
        )}
      </div>
    </li>
  );
}

function Column({ title, subtitle, children }) {
  return (
    <section className="flex min-h-0 flex-col rounded-xl border border-slate-700 bg-slate-900/60 p-4">
      <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
      {subtitle && <p className="mt-0.5 text-sm text-slate-400">{subtitle}</p>}
      <div className="mt-3 min-h-0 flex-1 overflow-auto">{children}</div>
    </section>
  );
}

export default function App() {
  const [ticketId, setTicketId] = useState("FR-1842");
  const [ticket, setTicket] = useState(null);
  const [graph, setGraph] = useState([]);
  const [action, setAction] = useState(null);
  const [job, setJob] = useState(null);
  const [preview, setPreview] = useState(null);
  const [phase, setPhase] = useState("idle");
  const [mode, setMode] = useState(null);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);
  const inflight = useRef(false);

  useEffect(() => {
    fetch(apiPath("/healthz"))
      .then((res) => res.json())
      .then((body) => setMode(body.mode || null))
      .catch(() => setMode(null));
  }, []);

  const loadTicket = useCallback(async (id) => {
    const res = await fetch(apiPath(`/v1/tickets/${id}`));
    if (!res.ok) throw new Error(`ticket ${res.status}`);
    const body = await res.json();
    setTicket(body.ticket);
    setGraph(body.graph || []);
    setAction(body.action);
  }, []);

  useEffect(() => {
    setError("");
    setPreview(null);
    setJob(null);
    setPhase("idle");
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
          if (body.status === "failed") setError(body.error || "run failed");
        }
      } catch {
        /* poll again */
      }
    }, 280);
    return () => clearInterval(timer);
  }, [job?.id, job?.status]);

  useEffect(() => {
    const es = new EventSource(apiPath(`/v1/tickets/${ticketId}/events`));
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.phase) setPhase(data.phase);
      } catch {
        /* ping */
      }
    };
    es.onerror = () => es.close();
    return () => es.close();
  }, [ticketId]);

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

  const runParity = async () => {
    if (inflight.current || running) return;
    const missingConsent = (ticket?.parties || []).some((p) => p.consent === false);
    if (missingConsent) {
      setError("Cannot run: stored consent is missing for at least one party.");
      return;
    }
    inflight.current = true;
    setRunning(true);
    setError("");
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
      if (body.status === "completed") {
        setRunning(false);
        inflight.current = false;
      }
    } catch (err) {
      setError(String(err.message || err));
      setRunning(false);
      inflight.current = false;
    }
  };

  const parties = ticket?.parties || [];
  const partyA = parties.find((p) => p.role === "A");
  const partyB = parties.find((p) => p.role === "B");
  const claimsA = job?.result?.claims_a || preview?.claims_a || [];
  const claimsB = job?.result?.claims_b || [];
  const planB = job?.result?.plan_b || preview?.plan_b;
  const telemetry = job?.telemetry || {};
  const actionKind = action?.action;

  return (
    <div className="flex h-screen flex-col bg-slate-950 text-slate-100">
      {mode === "fixture" && (
        <div className="bg-amber-400 px-4 py-1 text-center text-sm font-semibold text-slate-950" role="status">
          FIXTURE MODE (USE_FIXTURES=true). Same CallePort as live. No live carrier.
        </div>
      )}
      {mode === "live" && (
        <div className="bg-sky-400 px-4 py-1 text-center text-sm font-semibold text-slate-950" role="status">
          LIVE MODE. CALL-E Developer API via POST /v1/calls.
        </div>
      )}

      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 px-6 py-3">
        <div className="flex items-baseline gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">CallParity workbench</p>
            <h1 className="mt-0.5 text-3xl font-bold">{ticketId}</h1>
          </div>
          <p className="max-w-xl text-base text-slate-300">{ticket?.fact || "Loading..."}</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="font-mono text-xl text-rose-300">
              ${Math.round((ticket?.sla_usd_per_hour || 0) / 1000)}k/hour SLA
            </p>
            <p className="font-mono text-sm text-slate-400">
              {ticket?.entities?.pallet_id} {ticket?.entities?.sku}
            </p>
          </div>
          <button
            type="button"
            onClick={runPreview}
            className="rounded-md bg-slate-100 px-5 py-2.5 text-base font-semibold text-slate-950 hover:bg-white"
          >
            Preview (0 calls)
          </button>
          <button
            type="button"
            onClick={runParity}
            disabled={running}
            className="rounded-md bg-sky-400 px-5 py-2.5 text-base font-semibold text-slate-950 hover:bg-sky-300 disabled:opacity-50"
          >
            {running ? "Running..." : "Run parity"}
          </button>
        </div>
      </header>

      <div className="flex items-center justify-between gap-4 border-b border-slate-800 px-6 py-1.5 text-sm">
        <div className="flex items-center gap-5 font-mono text-slate-300">
          <span>
            A {partyA?.label || "-"} {maskPhone(partyA?.phone_e164)}
            <span className="ml-2 text-sky-300">{railStatus("A", phase, job?.status)}</span>
          </span>
          <span>
            B {partyB?.label || "-"} {maskPhone(partyB?.phone_e164)}
            <span className="ml-2 text-sky-300">{railStatus("B", phase, job?.status)}</span>
          </span>
          {error && <span className="text-rose-300" role="alert">{error}</span>}
        </div>
        <nav className="flex gap-1.5" aria-label="Ticket controls">
          {TICKETS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTicketId(t.id)}
              className={`rounded px-2.5 py-1 font-mono ${
                t.id === ticketId ? "bg-slate-100 text-slate-950" : "bg-slate-900 text-slate-400 hover:text-slate-200"
              }`}
            >
              {t.id} {t.tag}
            </button>
          ))}
        </nav>
      </div>

      <main className="grid min-h-0 flex-1 grid-cols-12 gap-4 px-6 py-4">
        <div className="col-span-3 min-h-0">
          <Column title="Party A claims" subtitle={`${partyA?.label || "warehouse"}, typed from the transcript`}>
            {!claimsA.length && <p className="text-base text-slate-400">Click Preview to extract claims. Zero calls.</p>}
            <ul className="space-y-2.5">
              {claimsA.map((c) => (
                <ClaimCard key={c.id} claim={c} />
              ))}
            </ul>
          </Column>
        </div>

        <div className="col-span-3 min-h-0">
          <Column title="Refute plan for Party B" subtitle="B never hears what A asserted">
            {!planB && <p className="text-base text-slate-400">Compiled from A&apos;s claims at Preview.</p>}
            {planB && (
              <>
                <ul className="space-y-2">
                  {(planB.selected_questions || []).map((q) => (
                    <li key={q.id} className="rounded-lg border border-slate-700 bg-slate-900/80 p-3">
                      <p className="text-base leading-snug text-slate-100">{q.question}</p>
                      <p className="mt-1 font-mono text-sm text-emerald-300">leak 0.0 · covers {q.covers.length}</p>
                    </li>
                  ))}
                </ul>
                {(planB.dropped_questions || []).length > 0 && (
                  <div className="mt-3 border-t border-slate-800 pt-2">
                    <p className="text-sm font-semibold text-amber-300">Dropped by leak check</p>
                    <ul className="mt-1.5 space-y-2">
                      {planB.dropped_questions.map((q) => (
                        <li key={q.id} className="rounded-lg border border-amber-900/60 bg-slate-900/60 p-3">
                          <p className="text-base leading-snug text-slate-500 line-through">{q.question}</p>
                          <p className="mt-1 font-mono text-sm text-amber-300">
                            leak {Number(q.leak).toFixed(1)} · {(q.leak_kinds || []).join(", ")}
                          </p>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </Column>
        </div>

        <div className="col-span-3 min-h-0">
          <Column title="Party B claims" subtitle={`${partyB?.label || "driver"}, typed from the transcript`}>
            {!claimsB.length && (
              <p className="text-base text-slate-400">
                {phase === "merged" && job?.status === "completed"
                  ? "No claims. Voicemail and silence never confirm."
                  : "Filled by Run parity."}
              </p>
            )}
            <ul className="space-y-2.5">
              {claimsB.map((c) => (
                <ClaimCard key={c.id} claim={c} />
              ))}
            </ul>
          </Column>
        </div>

        <div className="col-span-3 min-h-0">
          <section
            className={`flex h-full flex-col rounded-xl border-2 p-4 ${ACTION_STYLE[actionKind] || "border-sky-400 bg-sky-950/40"}`}
          >
            <p className="text-xs uppercase tracking-[0.25em] text-slate-300">Action card · human-owned</p>
            <h2 className="mt-2 text-3xl font-bold leading-tight">{actionKind || "\u2014"}</h2>
            <p className="mt-3 text-base leading-snug text-slate-100">
              {action?.rationale || "Waiting for the two-call merge."}
            </p>
            {job && (
              <p className="mt-auto pt-3 font-mono text-sm text-slate-300">
                {job.id} · {job.status} · phase {phase}
              </p>
            )}
          </section>
        </div>
      </main>

      <section className="border-t border-slate-800 px-6 py-3">
        <h2 className="text-lg font-semibold">Claim graph</h2>
        {!graph.length && <p className="mt-1 text-base text-slate-400">Edges appear after Run parity.</p>}
        <ul className="mt-2 grid gap-2.5 lg:grid-cols-3">
          {graph.map((edge) => (
            <EdgeRow key={edge.hypothesis_id} edge={edge} />
          ))}
        </ul>
      </section>

      <footer className="flex flex-wrap gap-5 border-t border-slate-800 px-6 py-2 font-mono text-sm text-slate-400">
        <span>mode {telemetry.mode || mode || "-"}</span>
        <span>claims A {telemetry.claims_a ?? claimsA.length}</span>
        <span>claims B {telemetry.claims_b ?? claimsB.length}</span>
        <span>edges {telemetry.edges ?? graph.length}</span>
        <span>latency {telemetry.latency_ms ?? "-"} ms</span>
      </footer>
    </div>
  );
}
