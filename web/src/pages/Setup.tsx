import { useCallback, useEffect, useRef, useState } from "react";

import { api, apiBlob } from "../api";
import { useSubmit } from "./Auth";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  applied: { settings?: string[]; targets?: number; invites_waiting?: string[] };
}

interface Setup {
  status: "open" | "done" | "skipped" | null;
  messages: Message[];
  pending_invites: string[];
  summary: { label: string; value: string }[];
  has_files: boolean;
}

interface Profile {
  reporting_currency: string;
  business_description: string | null;
  website: string | null;
  revenue_lines: string[];
  display_band: number | null;
  voice: string;
  brand_colour: string | null;
  has_logo: boolean;
}

interface Target {
  metric: string;
  period: string;
  value: string;
  source: string;
  set_by_name: string;
}

const BANDS = ["Whole pounds", "£k, 1 decimal", "£m, 3 decimals", "£m, 2 decimals", "£m, 1 decimal"];

// A short interview, one question at a time, as in mockup/interview-example.
export function SetupChat({
  tenant,
  userName,
  onChanged,
  untilDone = false,
}: {
  tenant: string;
  userName: string;
  onChanged: () => void;
  // On the dashboard: show only while setup is still to do.
  untilDone?: boolean;
}) {
  const [setup, setSetup] = useState<Setup | null>(null);
  const [busy, setBusy] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const chat = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const firstName = userName.split(" ")[0] || "You";

  const load = useCallback(async () => setSetup(await api<Setup>("/company/setup", { tenant })), [tenant]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    chat.current?.scrollTo({ top: chat.current.scrollHeight });
    if (!busy) input.current?.focus({ preventScroll: true });
  }, [setup?.messages.length, busy]);

  async function act(path: string, method = "POST", body?: unknown) {
    setBusy(true);
    try {
      setSetup(await api<Setup>(path, { method, tenant, body }));
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  const { error, onSubmit } = useSubmit(async (data, form) => {
    const text = String(data.get("text") ?? "").trim();
    if (!text) return;
    form.reset();
    await act("/company/setup/messages", "POST", { text });
  });

  if (!setup) return null;
  const started = setup.status === "open" || setup.status === "done";

  if (untilDone && (setup.status === "done" || setup.status === "skipped")) return null;
  if (!started) {
    return (
      <section className="card setup">
        <div className="setup-head">
          <h2>{setup.status ? "Setup" : "Set up in a minute"}</h2>
          <button className="small" onClick={() => setShowSettings(!showSettings)}>
            {showSettings ? "Hide settings" : "Settings"}
          </button>
        </div>
        <p className="muted">
          {setup.status === "skipped"
            ? "You skipped setup. Defaults are in place."
            : setup.has_files
              ? "I have read your files and set most things up. A couple of quick questions will finish it."
              : "A couple of quick questions. Add a file first and I can work out the rest."}
        </p>
        <div className="checks">
          <button className="primary" disabled={busy} onClick={() => void act("/company/setup/start")}>
            {setup.status ? "Reopen setup" : "Start setup"}
          </button>
          {!setup.status && (
            <button disabled={busy} onClick={() => void act("/company/setup/skip")}>
              Skip for now
            </button>
          )}
        </div>
        {showSettings && <SettingsForm tenant={tenant} onSaved={onChanged} />}
      </section>
    );
  }

  const asking = setup.status === "open";
  return (
    <section className="card setup">
      <div className="setup-head">
        <h2>Setup</h2>
        <div className="checks">
          <button className="small" onClick={() => setShowSettings(!showSettings)}>
            {showSettings ? "Hide settings" : "Settings"}
          </button>
          {asking && (
            <button className="small" disabled={busy} onClick={() => void act("/company/setup/skip")}>
              Finish later
            </button>
          )}
        </div>
      </div>
      <div className="interview">
        <div className="chat" ref={chat} aria-live="polite">
          {setup.messages.map((m) => (
            <div key={m.id} className={`bubble ${m.role}`}>
              <span className="who">{m.role === "assistant" ? "BoardRoom" : firstName}</span>
              {m.content.split("\n\n").map((para, i) => (
                <p key={i}>{para}</p>
              ))}
            </div>
          ))}
          {busy && <p className="small muted">Writing a reply</p>}
        </div>
        <aside className="set-for-you" aria-label="Set up for you">
          <h3>Set up for you</h3>
          {setup.summary.map((r) => (
            <div key={r.label} className="set-row">
              <span>{r.label}</span>
              <span>{r.value}</span>
            </div>
          ))}
          <p className="small muted">Tell me in the chat to change any of this.</p>
          {!setup.has_files && (
            <button className="primary small" onClick={() => document.getElementById("files")?.scrollIntoView({ behavior: "smooth" })}>
              Add your first file
            </button>
          )}
        </aside>
      </div>
      {setup.pending_invites.length > 0 && (
        <div className="question">
          <p>
            <b>Invite {setup.pending_invites.join(", ")} as investors?</b> They will see every update you share.
          </p>
          <div className="checks">
            <button className="primary" disabled={busy} onClick={() => void act("/company/setup/invites")}>
              Send invitations
            </button>
            <button disabled={busy} onClick={() => void act("/company/setup/invites", "DELETE")}>
              Do not invite
            </button>
          </div>
        </div>
      )}
      <form onSubmit={onSubmit} className="answer-row">
        <input
          ref={input}
          name="text"
          aria-label="Your answer"
          autoComplete="off"
          placeholder={asking ? "Type your answer" : "Tell me anything to change"}
          disabled={busy}
        />
        <button className="primary" disabled={busy}>
          Send
        </button>
        {asking && (
          <button
            type="button"
            className="link"
            disabled={busy}
            onClick={() => void act("/company/setup/messages", "POST", { text: "Skip" })}
          >
            Skip
          </button>
        )}
      </form>
      {error && <p className="notice err">{error}</p>}
      {showSettings && <SettingsForm tenant={tenant} onSaved={onChanged} />}
    </section>
  );
}

function SettingsForm({ tenant, onSaved }: { tenant: string; onSaved: () => void }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    const [p, t] = await Promise.all([
      api<Profile>("/company/settings/profile", { tenant }),
      api<Target[]>("/company/settings/targets", { tenant }),
    ]);
    setProfile(p);
    setTargets(t);
  }, [tenant]);
  useEffect(() => {
    void load();
  }, [load]);

  const save = useSubmit(async (data) => {
    const band = String(data.get("band"));
    await api("/company/settings/profile", {
      method: "PUT",
      tenant,
      body: {
        reporting_currency: String(data.get("currency")).toUpperCase(),
        business_description: data.get("description"),
        website: data.get("website"),
        voice: data.get("voice"),
        brand_colour: String(data.get("brand_colour") ?? "").toUpperCase(),
        ...(band === "auto" ? { follow_revenue: true } : { display_band: Number(band) }),
      },
    });
    setSaved(true);
    onSaved();
  });

  const addTarget = useSubmit(async (data, form) => {
    await api("/company/settings/targets", {
      method: "PUT",
      tenant,
      body: [{ metric: data.get("metric"), period: data.get("period"), value: data.get("value") }],
    });
    form.reset();
    await load();
    onSaved();
  });

  if (!profile) return null;
  return (
    <div className="settings-panel">
      <form onSubmit={save.onSubmit} onChange={() => setSaved(false)}>
        <div className="inline-form">
          <label className="field">
            <span>Reporting currency</span>
            <input name="currency" defaultValue={profile.reporting_currency} maxLength={3} />
          </label>
          <label className="field">
            <span>Money shown as</span>
            <select name="band" defaultValue={profile.display_band === null ? "auto" : String(profile.display_band)}>
              <option value="auto">Set by annual revenue</option>
              {BANDS.map((b, i) => (
                <option key={b} value={i}>
                  {b}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Commentary voice</span>
            <select name="voice" defaultValue={profile.voice}>
              <option value="we">We</option>
              <option value="third_person">The company</option>
            </select>
          </label>
          <label className="field">
            <span>Colour on exports</span>
            <input name="brand_colour" type="color" defaultValue={profile.brand_colour ?? "#123C4A"} />
          </label>
        </div>
        <label className="field">
          <span>What the business does</span>
          <input name="description" defaultValue={profile.business_description ?? ""} maxLength={300} />
        </label>
        <label className="field">
          <span>Website</span>
          <input name="website" defaultValue={profile.website ?? ""} placeholder="northwind.co.uk" />
        </label>
        {save.error && <p className="notice err">{save.error}</p>}
        {saved && <p className="notice ok">Saved.</p>}
        <button disabled={save.busy}>Save settings</button>
      </form>
      <LogoSetting tenant={tenant} hasLogo={profile.has_logo} onChanged={(p) => setProfile(p)} />
      <h3>Targets</h3>
      {targets.length > 0 && (
        <div className="table-wrap">
          <table>
            <tbody>
              {targets.map((t) => (
                <tr key={t.metric + t.period}>
                  <td>{t.metric === "revenue" ? "Revenue" : "Closed-won sales"}</td>
                  <td>{t.period}</td>
                  <td className="num">£{Number(t.value).toLocaleString("en-GB")}</td>
                  <td className="small">
                    Set by {t.set_by_name} in {t.source === "chat" ? "setup" : "settings"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <form onSubmit={addTarget.onSubmit} className="inline-form">
        <label className="field">
          <span>Target for</span>
          <select name="metric">
            <option value="revenue">Revenue</option>
            <option value="closed_won">Closed-won sales</option>
          </select>
        </label>
        <label className="field">
          <span>Month</span>
          <input name="period" type="month" required />
        </label>
        <label className="field">
          <span>Amount</span>
          <input name="value" inputMode="decimal" required />
        </label>
        <button disabled={addTarget.busy}>Save target</button>
      </form>
      {addTarget.error && <p className="notice err">{addTarget.error}</p>}
    </div>
  );
}

// The logo on exported updates (FR-6.6). The server checks it and redraws it as a PNG.
function LogoSetting({ tenant, hasLogo, onChanged }: { tenant: string; hasLogo: boolean; onChanged: (p: Profile) => void }) {
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!hasLogo) {
      setPreview(null);
      return;
    }
    let url: string | null = null;
    void apiBlob("/company/settings/logo", tenant)
      .then((blob) => {
        url = URL.createObjectURL(blob);
        setPreview(url);
      })
      .catch(() => setPreview(null));
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [hasLogo, tenant]);

  async function choose(file: File) {
    setError(null);
    if (file.size > 512 * 1024) {
      setError("Use a logo under 512 KB.");
      return;
    }
    setBusy(true);
    try {
      const data_url = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(new Error("That file could not be read."));
        reader.readAsDataURL(file);
      });
      onChanged(await api<Profile>("/company/settings/logo", { method: "PUT", tenant, body: { data_url } }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "That logo could not be used.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="logo-setting">
      <h3>Logo on exports</h3>
      <div className="checks">
        {preview && <img src={preview} alt="Your logo" className="logo-preview" />}
        <label className="button-like small">
          {hasLogo ? "Replace logo" : "Add a logo"}
          <input
            type="file"
            accept="image/png,image/jpeg"
            hidden
            disabled={busy}
            onChange={(e) => {
              const file = e.currentTarget.files?.[0];
              e.currentTarget.value = "";
              if (file) void choose(file);
            }}
          />
        </label>
        {hasLogo && (
          <button
            className="small"
            disabled={busy}
            onClick={async () => onChanged(await api<Profile>("/company/settings/logo", { method: "DELETE", tenant }))}
          >
            Remove logo
          </button>
        )}
      </div>
      <p className="small muted">A PNG or JPEG under 512 KB. It appears on the PDF of each update.</p>
      {error && <p className="notice err">{error}</p>}
    </div>
  );
}
