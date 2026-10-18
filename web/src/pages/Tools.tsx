import { useCallback, useEffect, useState } from "react";

import { api, DEPARTMENT_NAMES } from "../api";

export interface Tool {
  key: string;
  name: string;
  department: string;
  sends: string;
  state: "connected" | "failed" | "available" | "coming_soon" | "phase_2";
  connected_by_name: string | null;
  connected_at: string | null;
  last_synced_at: string | null;
  last_error: string | null;
}

const STATE_WORDS: Record<Tool["state"], string> = {
  connected: "Connected",
  failed: "Needs attention",
  available: "Not connected",
  coming_soon: "Coming soon",
  phase_2: "Phase 2",
};
const STATE_CLASS: Record<Tool["state"], string> = {
  connected: "pill ok",
  failed: "pill warn",
  available: "pill",
  coming_soon: "pill",
  phase_2: "pill",
};

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

// The company's tools: connect one and its data arrives with no export, checked and
// calculated exactly as a file is. Pulled again once a day.
export function ToolsSection({ tenant, onPulled }: { tenant: string; onPulled: () => void }) {
  const [tools, setTools] = useState<Tool[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => setTools(await api<Tool[]>("/company/connections", { tenant })), [tenant]);
  useEffect(() => {
    void load();
  }, [load]);

  async function act(key: string, path: string, method: string) {
    setBusy(key);
    setError(null);
    try {
      await api(path, { method, tenant });
      await load();
      onPulled();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (!tools) return null;
  return (
    <section className="card tools" aria-labelledby="tools-title">
      <h2 id="tools-title">Your tools</h2>
      <p className="muted">
        Connect a tool and its data arrives on its own, every day, with nothing to export. It is read the same way as a file, and
        pay is never kept.
      </p>
      {error && <p className="notice err">{error}</p>}
      <ul className="tool-list">
        {tools.map((t) => {
          const linked = t.state === "connected" || t.state === "failed";
          return (
            <li key={t.key} className="tool">
              <div className="tool-main">
                <div className="tool-name">
                  <b>{t.name}</b>
                  <span className={STATE_CLASS[t.state]}>{STATE_WORDS[t.state]}</span>
                </div>
                <div className="small muted">
                  {DEPARTMENT_NAMES[t.department] ?? t.department}: {t.sends}
                </div>
                {linked && (
                  <div className="small">
                    Connected by {t.connected_by_name}
                    {t.last_synced_at && `. Last pulled ${when(t.last_synced_at)}`}
                  </div>
                )}
                {t.last_error && <p className="small warn-text">{t.last_error}</p>}
              </div>
              <div className="tool-actions">
                {t.state === "available" && (
                  <button className="primary small" disabled={busy !== null} onClick={() => void act(t.key, `/company/connections/${t.key}`, "POST")}>
                    {busy === t.key ? "Connecting" : `Connect ${t.name}`}
                  </button>
                )}
                {linked && (
                  <>
                    <button className="small" disabled={busy !== null} onClick={() => void act(t.key, `/company/connections/${t.key}/sync`, "POST")}>
                      {busy === t.key ? "Pulling" : "Pull now"}
                    </button>
                    <button className="link small" disabled={busy !== null} onClick={() => void act(t.key, `/company/connections/${t.key}`, "DELETE")}>
                      Disconnect
                    </button>
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      <p className="small muted">Until a tool is connected, an export from it works just as well.</p>
    </section>
  );
}
