import { useCallback, useEffect, useState } from "react";

import { api, download, ROLE_NAMES, Role } from "../api";
import { useSubmit } from "./Auth";
import { month, TraceView } from "./Metrics";

interface Figure {
  figure_id: string;
  metric: string;
  label: string;
  unit: string;
  period: string;
  display: string;
  source_line: string;
  risk: string | null;
  calculated_display: string | null;
  edited_by_name: string | null;
  edited_at: string | null;
}

interface Section {
  id: string;
  kind: "headline" | "note" | "questions";
  department: string | null;
  text: string | null;
  status: "drafted" | "needs_person" | "written" | "edited";
  label: string;
  reason: string | null;
  unmatched: string[];
}

interface Comment {
  id: string;
  author_name: string;
  author_role: Role;
  body: string;
  created_at: string;
  mine: boolean;
}

interface Update {
  id: string;
  headline: string;
  detail: string;
  department: string;
  data_as_of: string;
  status: "awaiting_approval" | "shared";
  created_at: string;
  approved_by_name: string | null;
  approved_at: string | null;
  last_edited_by_name: string | null;
  last_edited_at: string | null;
  figures: Figure[];
  sections: Section[];
  comments: Comment[];
  can_edit: boolean;
  can_approve: boolean;
}

function day(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function when(iso: string): string {
  const d = new Date(iso);
  return `${d.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}, ${d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`;
}

// Each addition of data is an update: a dated line, its figures and a comment thread (FRD ch. 6).
export function UpdatesFeed({
  tenant,
  companyName,
  version,
  investor,
}: {
  tenant: string;
  companyName: string;
  version: number;
  investor: boolean;
}) {
  const [updates, setUpdates] = useState<Update[] | null>(null);

  const load = useCallback(async () => {
    const list = await api<Update[]>("/company/updates", { tenant });
    setUpdates(list);
    return list.length;
  }, [tenant]);

  useEffect(() => {
    void load().then(() => {
      // Opened from the investor overview: go straight to the latest update (FR-7.4).
      if (window.location.hash === "#updates") document.getElementById("updates")?.scrollIntoView();
    });
  }, [load]);

  // A finished upload becomes an update in the background: check until it arrives.
  useEffect(() => {
    if (version === 0) return;
    let cancelled = false;
    void (async () => {
      const before = updates?.length ?? 0;
      for (let i = 0; i < 10 && !cancelled; i++) {
        if ((await load()) !== before) return;
        await new Promise((r) => setTimeout(r, 1000));
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version]);

  if (!updates) return null;
  const replace = (u: Update) => setUpdates((list) => (list ?? []).map((x) => (x.id === u.id ? u : x)));
  return (
    <section className="card" id="updates">
      <h2>Updates</h2>
      {updates.length === 0 && (
        <p className="muted">
          {investor
            ? `Every update ${companyName} shares appears here, with the source of each figure.`
            : "Each file you add becomes an update here. Investors see it once it is approved."}
        </p>
      )}
      <div className="updates">
        {updates.map((u) => (
          <UpdateCard key={u.id} tenant={tenant} companyName={companyName} update={u} investor={investor} onChange={replace} />
        ))}
      </div>
    </section>
  );
}

function UpdateCard({
  tenant,
  companyName,
  update: u,
  investor,
  onChange,
}: {
  tenant: string;
  companyName: string;
  update: Update;
  investor: boolean;
  onChange: (u: Update) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function act(path: string, method: string, body?: unknown) {
    setBusy(true);
    setError(null);
    try {
      onChange(await api<Update>(path, { method, tenant, body }));
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "That did not work.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  const comment = useSubmit(async (data, form) => {
    const body = String(data.get("body") ?? "").trim();
    if (!body) return;
    if (await act(`/company/updates/${u.id}/comments`, "POST", { body })) form.reset();
  });

  const shared = u.status === "shared";
  return (
    <article className="update" aria-label={u.headline}>
      <div className="update-head">
        <div>
          <div className="update-line">{u.headline}</div>
          <div className="small">{u.detail}</div>
        </div>
        {!investor && <span className={`pill ${shared ? "ok" : "warn"}`}>{shared ? "Shared" : "Awaiting approval"}</span>}
      </div>
      {(u.approved_by_name || u.last_edited_at) && (
        <p className="small update-labels">
          {u.approved_by_name && u.approved_at && <span>Approved by {u.approved_by_name}, {day(u.approved_at)}</span>}
          {u.last_edited_at && (
            <span className="warn-text">
              Last edited {day(u.last_edited_at)}
              {u.last_edited_by_name && ` by ${u.last_edited_by_name}`}
            </span>
          )}
        </p>
      )}
      {u.can_approve && (
        <div className="question">
          <p>
            <b>Investors see this update once it is approved.</b> Check the figures, then share it.
          </p>
          <div className="checks">
            <button className="primary" disabled={busy} onClick={() => void act(`/company/updates/${u.id}/approve`, "POST")}>
              Approve and share
            </button>
          </div>
        </div>
      )}

      <Commentary update={u} busy={busy} act={act} />

      {u.figures.length > 0 ? (
        <div className="update-figures">
          {u.figures.map((f) => (
            <div key={f.figure_id} className={`update-figure ${open === f.figure_id ? "open" : ""}`}>
              <span className="label">{f.label}</span>
              <span className="figure">{f.display}</span>
              <span className="small">{month(f.period)}</span>
              {f.calculated_display && (
                <span className="small warn-text">
                  Changed by {f.edited_by_name}. Calculated: {f.calculated_display}
                </span>
              )}
              {editing === f.figure_id ? (
                <FigureEdit
                  figure={f}
                  busy={busy}
                  onSave={async (value) => {
                    if (await act(`/company/updates/${u.id}/figures/${f.figure_id}`, "PUT", { value })) setEditing(null);
                  }}
                  onCancel={() => setEditing(null)}
                />
              ) : (
                <span className="figure-actions">
                  <button
                    className="link small"
                    aria-expanded={open === f.figure_id}
                    onClick={() => setOpen(open === f.figure_id ? null : f.figure_id)}
                  >
                    {open === f.figure_id ? "▾" : "▸"} Source
                  </button>
                  {u.can_edit && (
                    <button className="link small" onClick={() => setEditing(f.figure_id)}>
                      Change
                    </button>
                  )}
                </span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="small muted">This file added no figures that can be shown yet.</p>
      )}
      {open && (
        <TraceView
          key={open}
          tenant={tenant}
          id={open}
          canManage={false}
          onChanged={async () => undefined}
          path={`/company/updates/${u.id}/figures/${open}`}
        />
      )}

      <div className="comments">
        {u.comments.map((c) => (
          <div key={c.id} className="comment">
            <b>{c.author_role === "investor" ? c.author_name : `${ROLE_NAMES[c.author_role]} ${c.author_name}`}</b>{" "}
            <span className="small">
              {c.author_role === "investor" ? "Investor · " : ""}
              {when(c.created_at)}
            </span>
            <p>{c.body}</p>
          </div>
        ))}
        {(shared || !investor) && (
          <form onSubmit={comment.onSubmit} className="answer-row">
            <input name="body" aria-label="Add a comment" placeholder="Add a comment" maxLength={2000} autoComplete="off" disabled={busy} />
            <button className="primary" disabled={busy}>
              Send
            </button>
          </form>
        )}
        {!shared && !investor && u.comments.length === 0 && (
          <p className="small muted">Investors see this thread, and every comment in it, once the update is shared.</p>
        )}
      </div>
      {error && <p className="notice err">{error}</p>}
      <div className="checks">
        <button
          className="small"
          onClick={() =>
            void download(`/company/updates/${u.id}/pdf`, tenant, `${companyName} update ${u.data_as_of}.pdf`).catch((e) =>
              setError(e instanceof Error ? e.message : "The PDF could not be made."),
            )
          }
        >
          Download PDF
        </button>
      </div>
    </article>
  );
}

function FigureEdit({
  figure,
  busy,
  onSave,
  onCancel,
}: {
  figure: Figure;
  busy: boolean;
  onSave: (value: string | null) => Promise<void>;
  onCancel: () => void;
}) {
  return (
    <form
      className="figure-edit"
      onSubmit={(e) => {
        e.preventDefault();
        void onSave(String(new FormData(e.currentTarget).get("value") ?? "").trim());
      }}
    >
      <label className="field">
        <span>New figure, as a plain number</span>
        <input name="value" inputMode="decimal" required autoFocus placeholder="For example 80000" />
      </label>
      <div className="checks">
        <button className="primary small" disabled={busy}>
          Save
        </button>
        {figure.calculated_display && (
          <button type="button" className="small" disabled={busy} onClick={() => void onSave(null)}>
            Put back {figure.calculated_display}
          </button>
        )}
        <button type="button" className="link small" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

const SECTION_WORDS: Record<string, string> = { headline: "Headline", note: "Note", questions: "Likely board questions" };

// The headline and notes investors read, and the board questions for the company only.
// Each says who wrote it (FR-6.4). A part Claude could not get past the number check waits
// for a person (FR-5.5).
function Commentary({
  update: u,
  busy,
  act,
}: {
  update: Update;
  busy: boolean;
  act: (path: string, method: string, body?: unknown) => Promise<boolean>;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  if (u.sections.length === 0) return null;
  const waiting = u.sections.some((s) => s.status === "needs_person");
  return (
    <div className="commentary">
      {u.sections.map((s) =>
        editing === s.id ? (
          <SectionEdit
            key={s.id}
            section={s}
            busy={busy}
            onSave={async (text) => {
              if (await act(`/company/updates/${u.id}/sections/${s.id}`, "PUT", { text })) setEditing(null);
            }}
            onCancel={() => setEditing(null)}
          />
        ) : (
          <div key={s.id} className={`section section-${s.kind} ${s.status === "needs_person" ? "waiting" : ""}`}>
            {s.kind === "questions" && <span className="label">Likely board questions, for you only</span>}
            {s.status === "needs_person" ? (
              <p className="small">
                <b>{SECTION_WORDS[s.kind]}:</b> {s.reason} Write it yourself, or leave it out.
              </p>
            ) : s.text ? (
              s.kind === "questions" ? (
                <ul>
                  {s.text.split("\n").map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
              ) : (
                <p>{s.text}</p>
              )
            ) : (
              <p className="small muted">Left out of this update.</p>
            )}
            {s.unmatched.length > 0 && s.status !== "needs_person" && (
              <p className="small warn-text">
                These figures match nothing calculated: {s.unmatched.join(", ")}. Investors will see them as written.
              </p>
            )}
            <span className="small section-foot">
              {s.status !== "needs_person" && <span className="muted">{s.label}</span>}
              {u.can_edit && (
                <button className="link small" onClick={() => setEditing(s.id)}>
                  {s.status === "needs_person" ? "Write it" : "Edit"}
                </button>
              )}
            </span>
          </div>
        ),
      )}
      {u.can_edit && (
        <div className="checks">
          <button className="small" disabled={busy} onClick={() => void act(`/company/updates/${u.id}/redraft`, "POST")}>
            {waiting ? "Ask Claude to try again" : "Redraft with Claude"}
          </button>
        </div>
      )}
    </div>
  );
}

function SectionEdit({
  section,
  busy,
  onSave,
  onCancel,
}: {
  section: Section;
  busy: boolean;
  onSave: (text: string) => Promise<void>;
  onCancel: () => void;
}) {
  return (
    <form
      className="section-edit"
      onSubmit={(e) => {
        e.preventDefault();
        void onSave(String(new FormData(e.currentTarget).get("text") ?? ""));
      }}
    >
      <label className="field">
        <span>{SECTION_WORDS[section.kind]}</span>
        <textarea name="text" rows={section.kind === "headline" ? 2 : 4} maxLength={4000} defaultValue={section.text ?? ""} autoFocus />
      </label>
      <p className="small muted">Write figures as they appear above, or rounded. Leave it empty to leave this part out.</p>
      <div className="checks">
        <button className="primary small" disabled={busy}>
          Save
        </button>
        <button type="button" className="link small" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
