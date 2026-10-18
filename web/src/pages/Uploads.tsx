import { DragEvent, useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError } from "../api";
import { useSubmit } from "./Auth";

interface Question {
  id: string;
  prompt: string;
  options: { value: string; label: string }[];
}

interface Upload {
  id: string;
  filename: string;
  status: string;
  message: string | null;
  needs_mapping: boolean;
  kind: string | null;
  row_count: number | null;
  data_as_of: string | null;
  created_at: string;
  question: Question | null;
}

interface MappingInfo {
  columns: { name: string; type: string; examples: string[] }[];
  kinds: Record<string, { key: string; label: string; type: string }[]>;
}

interface Figure {
  id: string;
  metric: string;
  period: string;
  value: string;
  kind: string;
  label: string;
}

const STEPS = ["received", "understanding", "calculating", "describing", "ready"];
const STEP_WORDS: Record<string, string> = {
  received: "Received",
  understanding: "Understanding",
  calculating: "Calculating",
  describing: "Describing",
  ready: "Ready",
  shared: "Shared",
  failed: "Could not use",
};
const KIND_WORDS: Record<string, string> = {
  finance: "Finance",
  sales: "Sales pipeline",
  delivery: "Product delivery",
  people: "People",
  plan: "Plan",
};
const METRICS: Record<string, string> = {
  revenue: "Revenue",
  cost_of_sales: "Cost of sales",
  operating_expenses: "Operating expenses",
  cash_balance: "Cash balance",
  net_burn: "Net burn",
  pipeline: "Pipeline",
  closed_won: "Closed won",
  headcount: "Headcount",
};

function busy(u: Upload): boolean {
  return ["received", "understanding", "calculating", "describing"].includes(u.status) && !u.question && !u.needs_mapping;
}

export function UploadsSection({ tenant, onSettled }: { tenant: string; onSettled: () => void }) {
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [mapping, setMapping] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setUploads(await api<Upload[]>("/company/uploads", { tenant }));
  }, [tenant]);

  useEffect(() => {
    void load();
  }, [load]);

  const working = uploads.some(busy);
  useEffect(() => {
    if (!working) return;
    const timer = setTimeout(() => void load(), 1500);
    return () => clearTimeout(timer);
  }, [uploads, load, working]);

  // When the last file finishes, the figures have changed.
  const [wasWorking, setWasWorking] = useState(false);
  useEffect(() => {
    if (wasWorking && !working) onSettled();
    setWasWorking(working);
  }, [working, wasWorking, onSettled]);

  async function add(file: File) {
    setError(null);
    setAdding(true);
    try {
      const link = await api<{ upload_id: string; url: string; method: string; headers: Record<string, string> }>(
        "/company/uploads",
        { method: "POST", tenant, body: { filename: file.name, size_bytes: file.size, content_type: file.type } },
      );
      const put = await fetch(link.url, { method: link.method, headers: link.headers, body: file });
      if (!put.ok) throw new ApiError(put.status, "The file did not upload. Try again.");
      await api(`/company/uploads/${link.upload_id}/complete`, { method: "POST", tenant });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "The file did not upload. Try again.");
    } finally {
      setAdding(false);
      if (input.current) input.current.value = "";
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) void add(file);
  }

  return (
    <section className="card" id="files">
      <h2>Add files</h2>
      <p className="muted">
        Drop in any export: a profit and loss report, a bank summary, a CRM deals list. Nothing to prepare. Salary,
        bank and other personal pay details are removed before anything is stored.
      </p>
      <div
        className={`dropzone${dragging ? " over" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <p>{adding ? "Adding your file" : "Drop a CSV or Excel file here"}</p>
        <button className="primary" disabled={adding} onClick={() => input.current?.click()}>
          Choose a file
        </button>
        <input
          ref={input}
          type="file"
          accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          hidden
          onChange={(e) => e.target.files?.[0] && void add(e.target.files[0])}
        />
      </div>
      {error && <p className="notice err">{error}</p>}
      {uploads.length > 0 && (
        <ul className="list">
          {uploads.map((u) => (
            <li key={u.id} className="upload">
              <UploadRow
                upload={u}
                tenant={tenant}
                onChange={load}
                onMap={() => setMapping(u.id)}
                mapping={mapping === u.id}
                onMapped={async () => {
                  setMapping(null);
                  await load();
                }}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function UploadRow(props: {
  upload: Upload;
  tenant: string;
  onChange: () => Promise<void>;
  onMap: () => void;
  mapping: boolean;
  onMapped: () => Promise<void>;
}) {
  const u = props.upload;
  const [answering, setAnswering] = useState(false);
  const step = STEPS.indexOf(u.status);

  async function answer(value: string) {
    setAnswering(true);
    try {
      await api(`/company/uploads/${u.id}/answer`, {
        method: "POST",
        tenant: props.tenant,
        body: { question_id: u.question!.id, answer: value },
      });
      await props.onChange();
    } finally {
      setAnswering(false);
    }
  }

  return (
    <div className="upload-body">
      <div className="upload-head">
        <div>
          <b>{u.filename}</b>
          <div className="small">
            {u.kind ? KIND_WORDS[u.kind] ?? u.kind : "Working out what this file is"}
            {u.row_count != null && ` · ${u.row_count.toLocaleString("en-GB")} rows`}
            {u.data_as_of && ` · data true as of ${new Date(u.data_as_of).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}`}
          </div>
        </div>
        <span className={`pill ${u.status === "ready" ? "ok" : u.status === "failed" ? "warn" : ""}`}>
          {STEP_WORDS[u.status] ?? u.status}
        </span>
      </div>
      {u.status !== "failed" && (
        <ol className="steps" aria-label="Progress">
          {STEPS.map((s, i) => (
            <li key={s} className={i < step ? "done" : i === step ? "now" : ""}>
              {STEP_WORDS[s]}
            </li>
          ))}
        </ol>
      )}
      {u.message && !u.question && <p className={`small ${u.status === "failed" ? "warn-text" : ""}`}>{u.message}</p>}
      {u.question && (
        <div className="question">
          <p>
            <b>{u.question.prompt}</b>
          </p>
          <div className="checks">
            {u.question.options.map((o) => (
              <button key={o.value} disabled={answering} onClick={() => void answer(o.value)}>
                {o.label}
              </button>
            ))}
          </div>
          <p className="small">We save your answer, so the same file is not asked about again.</p>
        </div>
      )}
      {u.needs_mapping && !props.mapping && (
        <button className="primary" onClick={props.onMap}>
          Choose what each column is
        </button>
      )}
      {props.mapping && <MappingForm upload={u} tenant={props.tenant} onDone={props.onMapped} />}
    </div>
  );
}

function MappingForm({ upload, tenant, onDone }: { upload: Upload; tenant: string; onDone: () => Promise<void> }) {
  const [info, setInfo] = useState<MappingInfo | null>(null);
  const [kind, setKind] = useState("finance");
  const { error, busy, onSubmit } = useSubmit(async (data) => {
    const columns = info!.columns
      .map((c, i) => ({ column: c.name, field: String(data.get(`field-${i}`) ?? ""), date_format: null }))
      .filter((c) => c.field && c.field !== "ignore");
    await api(`/company/uploads/${upload.id}/mapping`, { method: "PUT", tenant, body: { kind, columns } });
    await onDone();
  });

  useEffect(() => {
    void api<MappingInfo>(`/company/uploads/${upload.id}/mapping`, { tenant }).then(setInfo);
  }, [upload.id, tenant]);

  if (!info) return <p className="muted">Loading the columns</p>;
  return (
    <form onSubmit={onSubmit} className="mapping">
      <label className="field">
        <span>What is this file?</span>
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          {Object.keys(info.kinds).map((k) => (
            <option key={k} value={k}>
              {KIND_WORDS[k]}
            </option>
          ))}
        </select>
      </label>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="label">Column</th>
              <th className="label">Examples</th>
              <th className="label">Use as</th>
            </tr>
          </thead>
          <tbody>
            {info.columns.map((c, i) => (
              <tr key={c.name}>
                <td>{c.name}</td>
                <td className="small">{c.examples.join(", ")}</td>
                <td>
                  <select name={`field-${i}`} defaultValue="ignore" aria-label={`Use ${c.name} as`}>
                    <option value="ignore">Not needed</option>
                    {info.kinds[kind].map((f) => (
                      <option key={f.key} value={f.key}>
                        {f.label}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {error && <p className="notice err">{error}</p>}
      <button className="primary" disabled={busy}>
        Use these columns
      </button>
    </form>
  );
}

export function FiguresSection({ tenant, onSaved }: { tenant: string; onSaved: () => void }) {
  const [figures, setFigures] = useState<Figure[]>([]);
  const load = useCallback(async () => setFigures(await api<Figure[]>("/company/figures", { tenant })), [tenant]);
  const { error, busy: saving, onSubmit } = useSubmit(async (data, form) => {
    await api("/company/figures", {
      method: "POST",
      tenant,
      body: {
        metric: data.get("metric"),
        period: data.get("period"),
        value: data.get("value"),
        kind: data.get("kind"),
      },
    });
    form.reset();
    await load();
    onSaved();
  });

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="card">
      <h2>Enter a figure by hand</h2>
      <p className="muted">
        For a forecast, a target or a figure no file holds. It is labelled with your name and the date, and is not
        checked against data.
      </p>
      <form onSubmit={onSubmit} className="inline-form">
        <label className="field">
          <span>Measure</span>
          <select name="metric" required>
            {Object.entries(METRICS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Month</span>
          <input name="period" type="month" required />
        </label>
        <label className="field">
          <span>Value</span>
          <input name="value" inputMode="decimal" required placeholder="80000" />
        </label>
        <label className="field">
          <span>Type</span>
          <select name="kind" defaultValue="target">
            <option value="actual">Actual</option>
            <option value="forecast">Forecast</option>
            <option value="target">Target</option>
          </select>
        </label>
        <button disabled={saving}>Save figure</button>
      </form>
      {error && <p className="notice err">{error}</p>}
      {figures.length > 0 && (
        <div className="table-wrap">
          <table>
            <tbody>
              {figures.map((f) => (
                <tr key={f.id}>
                  <td>
                    {METRICS[f.metric] ?? f.metric}, {f.period}
                    <div className="small">{f.label}</div>
                  </td>
                  <td className="small">{f.kind}</td>
                  <td className="num">{Number(f.value).toLocaleString("en-GB")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
