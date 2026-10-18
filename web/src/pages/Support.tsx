import { useCallback, useEffect, useState } from "react";

import { api } from "../api";

interface SupportSession {
  staff_name: string;
  reason: string;
  started_at: string;
  expires_at: string;
}

function time(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

// Who from BoardRoom can see this company now, why and until when (FR-11.6). The Owner
// and CEO can end it at once. Support staff see that they are read-only.
export function SupportNotice({
  tenant,
  companyName,
  asSupport,
  canEnd,
}: {
  tenant: string;
  companyName: string;
  asSupport: boolean;
  canEnd: boolean;
}) {
  const [sessions, setSessions] = useState<SupportSession[]>([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setSessions(await api<SupportSession[]>("/company/support", { tenant }).catch(() => []));
  }, [tenant]);
  useEffect(() => {
    void load();
  }, [load]);

  if (asSupport) {
    const mine = sessions[0];
    return (
      <div className="notice support-notice" role="status">
        You are reading {companyName} as BoardRoom support. You can change nothing here, every page you open is in
        their audit log{mine ? `, and access ends at ${time(mine.expires_at)}` : ""}.
      </div>
    );
  }
  if (sessions.length === 0) return null;

  async function end() {
    setBusy(true);
    try {
      await api("/company/support", { method: "DELETE", tenant });
      await load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="notice support-notice" role="status">
      {sessions.map((s) => (
        <p key={s.started_at}>
          <b>{s.staff_name} from BoardRoom support</b> can see this company until {time(s.expires_at)}, read-only.
          Reason: {s.reason}
        </p>
      ))}
      {canEnd && (
        <button className="small" disabled={busy} onClick={() => void end()}>
          End support access now
        </button>
      )}
    </div>
  );
}
