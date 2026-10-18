import { useCallback, useEffect, useState } from "react";

import { api } from "../api";

interface Tile {
  id: string;
  metric: string;
  label: string;
  period: string;
  display: string;
  status: string;
  unit: string;
  risk: string | null;
  custom: boolean;
  source_line: string;
  previous_period: string | null;
  previous_display: string | null;
}

interface Source {
  filename: string;
  dataset_version: number;
  fields: string[];
  row_count: number;
  selections: { row_set: string; source: string; reason: string }[];
  rows: Record<string, string | number>[];
}

interface Trace {
  id: string;
  metric: string;
  label: string;
  period: string;
  value: string | null;
  display: string;
  formula: string;
  formula_version: string;
  method: string;
  custom: boolean;
  method_note: string | null;
  inputs: Record<string, string>;
  extra: Record<string, unknown>;
  sources: Source[];
  entered_by_hand: { entered_by: string; entered_at: string; kind: string }[];
  moves: string[];
  risk: string | null;
  thresholds: { high: string; medium: string; direction: string } | null;
}

const RISK_WORDS: Record<string, string> = { high: "High risk", medium: "Medium risk", low: "Low risk" };
const RISK_CLASS: Record<string, string> = { high: "risk-high", medium: "risk-medium", low: "risk-low" };

function month(period: string): string {
  const [y, m] = period.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-GB", { month: "short", year: "numeric" });
}

function words(key: string): string {
  return key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function MetricsGrid({ tenant, version, canManage }: { tenant: string; version: number; canManage: boolean }) {
  const [tiles, setTiles] = useState<Tile[] | null>(null);
  const [calculatedAt, setCalculatedAt] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(async () => {
    const r = await api<{ calculated_at: string | null; tiles: Tile[] }>("/company/metrics", { tenant });
    setTiles(r.tiles);
    setCalculatedAt(r.calculated_at);
    return r.calculated_at;
  }, [tenant]);

  useEffect(() => {
    void load();
  }, [load]);

  // After new data, figures are recalculated in the background: check until they arrive.
  useEffect(() => {
    if (version === 0) return;
    let cancelled = false;
    const before = calculatedAt;
    void (async () => {
      for (let i = 0; i < 15 && !cancelled; i++) {
        if ((await load()) !== before) return;
        await new Promise((r) => setTimeout(r, 1000));
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version]);

  if (!tiles) return null;
  return (
    <section className="card">
      <h2>Figures</h2>
      {tiles.length === 0 ? (
        <p className="muted">Add a finance export or a deals list and your figures appear here.</p>
      ) : (
        <p className="muted">Calculated by code from your files. Choose a figure to see its exact value and source.</p>
      )}
      <div className="tiles">
        {tiles.map((t) => (
          <button
            key={t.id}
            className={`tile ${open === t.id ? "open" : ""}`}
            onClick={() => setOpen(open === t.id ? null : t.id)}
            aria-expanded={open === t.id}
          >
            <span className="label">{t.label}</span>
            <span className={`figure ${t.status !== "ok" ? "muted-figure" : ""}`}>{t.display}</span>
            <span className="small">
              {month(t.period)}
              {t.previous_display && t.previous_period && ` · ${month(t.previous_period)}: ${t.previous_display}`}
            </span>
            <span className="tile-foot">
              {t.risk && <span className={`pill ${RISK_CLASS[t.risk]}`}>{RISK_WORDS[t.risk]}</span>}
              {t.custom && <span className="pill warn">Custom method</span>}
            </span>
            <span className="source-line">Source: {t.source_line}</span>
          </button>
        ))}
      </div>
      {open && <TraceView key={open} tenant={tenant} id={open} canManage={canManage} onChanged={load} />}
    </section>
  );
}

function TraceView({ tenant, id, canManage, onChanged }: { tenant: string; id: string; canManage: boolean; onChanged: () => Promise<unknown> }) {
  const [trace, setTrace] = useState<Trace | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => setTrace(await api<Trace>(`/company/metrics/${id}`, { tenant })), [id, tenant]);
  useEffect(() => {
    void load();
  }, [load]);

  async function change(body: Record<string, unknown>) {
    setError(null);
    try {
      await api(`/company/metrics/settings/${trace!.metric}`, { method: "PUT", tenant, body });
      await Promise.all([load(), onChanged()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "That did not save.");
    }
  }

  if (!trace) return <p className="muted">Loading the source</p>;
  return (
    <div className="trace" aria-live="polite">
      <div className="trace-head">
        <div>
          <span className="label">
            {trace.label}, {month(trace.period)}
          </span>
          <div className="figure">{trace.display}</div>
          {trace.value && <div className="small">Exact value: {trace.value}</div>}
        </div>
        {trace.risk && <span className={`pill ${RISK_CLASS[trace.risk]}`}>{RISK_WORDS[trace.risk]}</span>}
      </div>
      <dl className="trace-list">
        <dt>Formula</dt>
        <dd>
          {trace.formula} <span className="small">(version {trace.formula_version})</span>
        </dd>
        {trace.method_note && (
          <>
            <dt>Method</dt>
            <dd className="warn-text">{trace.method_note}</dd>
          </>
        )}
        {Object.keys(trace.inputs).length > 0 && (
          <>
            <dt>Inputs</dt>
            <dd>
              {Object.entries(trace.inputs)
                .map(([k, v]) => `${words(k)} ${v}`)
                .join(", ")}
            </dd>
          </>
        )}
        {trace.moves.length > 0 && (
          <>
            <dt>What it moves</dt>
            <dd>{trace.moves.join(", ")}</dd>
          </>
        )}
        {trace.thresholds && (
          <>
            <dt>Warning lines</dt>
            <dd>
              High risk {trace.thresholds.direction === "below" ? "below" : "above"} {trace.thresholds.high}, medium risk{" "}
              {trace.thresholds.direction === "below" ? "below" : "above"} {trace.thresholds.medium}
            </dd>
          </>
        )}
        <dt>Check</dt>
        <dd>The number check runs on commentary, which arrives in a later release.</dd>
      </dl>
      {trace.entered_by_hand.map((m) => (
        <p key={m.entered_at} className="small">
          Entered by {m.entered_by}, {new Date(m.entered_at).toLocaleDateString("en-GB")}. Not checked against data.
        </p>
      ))}
      {trace.sources.map((s) => (
        <div key={s.filename + s.dataset_version} className="trace-source">
          <p>
            <b>{s.filename}</b>{" "}
            <span className="small">
              version {s.dataset_version}, {s.row_count} row{s.row_count === 1 ? "" : "s"} used
            </span>
          </p>
          {s.selections.map((sel) => (
            <p key={sel.row_set} className="small">
              {words(sel.row_set)}: {sel.source === "ai" ? `chosen by Claude. ${sel.reason}` : "standard selection"}
            </p>
          ))}
          {s.rows.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {Object.keys(s.rows[0]).map((k) => (
                      <th key={k} className="label">
                        {words(k)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {s.rows.map((r, i) => (
                    <tr key={i}>
                      {Object.values(r).map((v, j) => (
                        <td key={j} className={typeof v === "number" || /^-?\d/.test(String(v)) ? "num" : ""}>
                          {String(v)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}
      {canManage && (
        <div className="trace-settings">
          <span className="label">Your view</span>
          <div className="checks">
            <button className="small" onClick={() => void change({ band_offset: -1 })}>
              Show more detail
            </button>
            <button className="small" onClick={() => void change({ band_offset: 1 })}>
              Show less detail
            </button>
            <button className="small" onClick={() => void change({ band_offset: 0 })}>
              Default detail
            </button>
            <button className="small" onClick={() => void change({ hidden: true })}>
              Hide this figure
            </button>
          </div>
          {trace.thresholds && (
            <form
              className="inline-form"
              onSubmit={(e) => {
                e.preventDefault();
                const data = new FormData(e.currentTarget);
                void change({ high: data.get("high"), medium: data.get("medium") });
              }}
            >
              <label className="field">
                <span>High risk line</span>
                <input name="high" defaultValue={trace.thresholds.high} inputMode="decimal" />
              </label>
              <label className="field">
                <span>Medium risk line</span>
                <input name="medium" defaultValue={trace.thresholds.medium} inputMode="decimal" />
              </label>
              <button className="small">Save warning lines</button>
            </form>
          )}
          {error && <p className="notice err">{error}</p>}
        </div>
      )}
    </div>
  );
}
