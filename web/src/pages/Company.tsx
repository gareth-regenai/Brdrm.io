import { useCallback, useEffect, useState } from "react";

import {
  api,
  Approval,
  AuditEntry,
  DEPARTMENT_NAMES,
  DEPARTMENTS,
  Invitation,
  Me,
  Membership,
  Permissions,
  Person,
  Role,
  ROLE_NAMES,
} from "../api";
import { useSubmit } from "./Auth";
import { FiguresSection, UploadsSection } from "./Uploads";

interface Data {
  permissions: Permissions;
  team: Person[];
  investors: Person[];
  invitations: Invitation[];
  approval: Approval | null;
  audit: AuditEntry[];
}

export function CompanyPage({ me, membership }: { me: Me; membership: Membership }) {
  const tenant = membership.tenant_id;
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      // Opening the company is what counts as an investor view in the audit log.
      await api("/company", { tenant });
      const permissions = await api<Permissions>("/company/permissions", { tenant });
      const can = (action: string) => permissions.actions.includes(action);
      const [team, investors, invitations, approval, audit] = await Promise.all([
        can("view_team") ? api<Person[]>("/company/team", { tenant }) : Promise.resolve([]),
        api<Person[]>("/company/investors", { tenant }),
        can("invite_users") ? api<Invitation[]>("/company/invitations", { tenant }) : Promise.resolve([]),
        can("manage_settings") ? api<Approval>("/company/settings/approval", { tenant }) : Promise.resolve(null),
        can("view_audit") ? api<AuditEntry[]>("/company/audit", { tenant }) : Promise.resolve([]),
      ]);
      setData({ permissions, team, investors, invitations, approval, audit });
    } catch (e) {
      setError(e instanceof Error ? e.message : "This company could not be loaded.");
    }
  }, [tenant]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) return <main className="page"><p className="notice err">{error}</p></main>;
  if (!data) return <main className="page"><p className="muted">Loading</p></main>;

  const can = (action: string) => data.permissions.actions.includes(action);
  const isInvestor = membership.role === "investor";
  const names = new Map([...data.team, ...data.investors].map((p) => [p.user_id, p.name]));

  return (
    <main className="page">
      <div className="page-head">
        <span className="label">{ROLE_NAMES[membership.role]}</span>
        <h1>{membership.tenant_name}</h1>
        {data.permissions.can_approve && <p className="small">You can approve this company's updates.</p>}
      </div>

      {can("upload_files") ? (
        <div className="grid-2">
          <UploadsSection tenant={tenant} />
          <FiguresSection tenant={tenant} />
        </div>
      ) : (
        <section className="card">
          <h2>Updates</h2>
          <p className="muted">
            {isInvestor
              ? "Every update the company shares will appear here. You will be able to trace each figure to its source and comment."
              : "Your role does not add files. Updates appear here once they are shared."}
          </p>
        </section>
      )}

      <div className="grid-2">
        {can("view_team") && (
          <section className="card">
            <h2>Team</h2>
            <PeopleTable people={data.team} />
          </section>
        )}
        <section className="card">
          <h2>Investors</h2>
          {data.investors.length === 0 ? (
            <p className="muted">No investors yet.</p>
          ) : (
            <PeopleTable
              people={data.investors}
              onRemove={
                can("remove_investor")
                  ? async (p) => {
                      if (!confirm(`Remove ${p.name}? Their access stops straight away.`)) return;
                      await api(`/company/investors/${p.user_id}`, { method: "DELETE", tenant });
                      await load();
                    }
                  : undefined
              }
            />
          )}
        </section>
      </div>

      {can("invite_users") && (
        <div className="grid-2">
          <InviteForm tenant={tenant} onDone={load} />
          <section className="card">
            <h2>Open invitations</h2>
            {data.invitations.length === 0 ? (
              <p className="muted">No open invitations.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th className="label">Email</th>
                      <th className="label">Role</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {data.invitations.map((i) => (
                      <tr key={i.id}>
                        <td>{i.email}</td>
                        <td>{ROLE_NAMES[i.role]}</td>
                        <td>
                          <button
                            className="small danger"
                            onClick={async () => {
                              await api(`/company/invitations/${i.id}`, { method: "DELETE", tenant });
                              await load();
                            }}
                          >
                            Cancel invitation
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}

      {data.approval && (
        <ApprovalForm tenant={tenant} approval={data.approval} team={data.team} onDone={load} />
      )}

      {can("view_audit") && (
        <section className="card">
          <h2>Activity</h2>
          <p className="muted">Every sign-in, invitation, change of setting and investor view, newest first.</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="label">When</th>
                  <th className="label">Who</th>
                  <th className="label">What</th>
                </tr>
              </thead>
              <tbody>
                {data.audit.map((e) => (
                  <tr key={e.id}>
                    <td className="small">{new Date(e.created_at).toLocaleString("en-GB")}</td>
                    <td>{e.actor_user_id ? (names.get(e.actor_user_id) ?? (e.actor_user_id === me.id ? me.name : "Former member")) : "BoardRoom.io"}</td>
                    <td>{describe(e)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}

const ACTIONS: Record<string, string> = {
  "company.created": "Created the company",
  "company.deleted": "Closed the workspace",
  "invitation.created": "Sent an invitation",
  "invitation.sent": "Emailed an invitation",
  "invitation.revoked": "Cancelled an invitation",
  "invitation.accepted": "Accepted an invitation",
  "investor.removed": "Removed an investor",
  "investor.viewed": "Viewed the company",
  "settings.approval_changed": "Changed who can approve updates",
  "upload.started": "Started adding a file",
  "upload.added": "Added a file",
  "upload.status_changed": "File moved to the next step",
  "upload.question_answered": "Answered a question about a file",
  "upload.mapped_by_hand": "Chose a file's columns by hand",
  "figure.entered": "Entered a figure by hand",
};

function describe(e: AuditEntry): string {
  const base = ACTIONS[e.action] ?? e.action;
  const role = e.details.role;
  return typeof role === "string" && role in ROLE_NAMES ? `${base} as ${ROLE_NAMES[role as Role]}` : base;
}

function PeopleTable({ people, onRemove }: { people: Person[]; onRemove?: (p: Person) => Promise<void> }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th className="label">Name</th>
            <th className="label">Role</th>
            {onRemove && <th />}
          </tr>
        </thead>
        <tbody>
          {people.map((p) => (
            <tr key={p.user_id}>
              <td>
                {p.name}
                {p.email && <div className="small">{p.email}</div>}
              </td>
              <td>
                {ROLE_NAMES[p.role]}
                {p.departments.length > 0 && (
                  <div className="small">{p.departments.map((d) => DEPARTMENT_NAMES[d] ?? d).join(", ")}</div>
                )}
              </td>
              {onRemove && (
                <td>
                  <button className="small danger" onClick={() => void onRemove(p)}>
                    Remove investor
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function InviteForm({ tenant, onDone }: { tenant: string; onDone: () => Promise<void> }) {
  const [role, setRole] = useState<Role>("investor");
  const [sent, setSent] = useState<string | null>(null);
  const { error, busy, onSubmit } = useSubmit(async (data, form) => {
    setSent(null);
    const email = String(data.get("email"));
    await api("/company/invitations", {
      method: "POST",
      tenant,
      body: { email, role, departments: data.getAll("departments") },
    });
    setSent(email);
    form.reset();
    await onDone();
  });
  const needsDepartments = role === "department_lead" || role === "contributor";

  return (
    <section className="card">
      <h2>Invite someone</h2>
      <p className="muted">
        An investor sees every update you share from now on, with no further step. Team members see this company only.
      </p>
      <form onSubmit={onSubmit}>
        <label className="field">
          <span>Email</span>
          <input name="email" type="email" required />
        </label>
        <label className="field">
          <span>Role</span>
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            <option value="investor">Investor</option>
            <option value="ceo">CEO</option>
            <option value="department_lead">Department lead</option>
            <option value="contributor">Contributor</option>
          </select>
        </label>
        {needsDepartments && (
          <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
            <span>{role === "contributor" ? "Department (choose one)" : "Departments"}</span>
            <div className="checks">
              {DEPARTMENTS.map((d) => (
                <label key={d}>
                  <input type={role === "contributor" ? "radio" : "checkbox"} name="departments" value={d} />
                  {DEPARTMENT_NAMES[d]}
                </label>
              ))}
            </div>
          </fieldset>
        )}
        {error && <p className="notice err">{error}</p>}
        {sent && <p className="notice ok">Invitation sent to {sent}.</p>}
        <button className="primary" disabled={busy}>
          Send invitation
        </button>
      </form>
    </section>
  );
}

function ApprovalForm({
  tenant,
  approval,
  team,
  onDone,
}: {
  tenant: string;
  approval: Approval;
  team: Person[];
  onDone: () => Promise<void>;
}) {
  const leads = team.filter((p) => p.role === "department_lead" || p.role === "ceo");
  const [saved, setSaved] = useState(false);
  const { error, busy, onSubmit } = useSubmit(async (data) => {
    await api("/company/settings/approval", {
      method: "PUT",
      tenant,
      body: { roles: data.getAll("roles"), user_ids: data.getAll("user_ids") },
    });
    setSaved(true);
    await onDone();
  });
  return (
    <section className="card">
      <h2>Who can approve updates</h2>
      <p className="muted">An update reaches investors once one of these people approves it. The Owner can always approve.</p>
      <form onSubmit={onSubmit} onChange={() => setSaved(false)}>
        <div className="checks">
          <label>
            <input type="checkbox" name="roles" value="ceo" defaultChecked={approval.roles.includes("ceo")} />
            The CEO
          </label>
          <label>
            <input
              type="checkbox"
              name="roles"
              value="department_lead"
              defaultChecked={approval.roles.includes("department_lead")}
            />
            Every department lead
          </label>
        </div>
        {leads.length > 0 && (
          <div className="field">
            <span>Named people</span>
            <div className="checks">
              {leads.map((p) => (
                <label key={p.user_id}>
                  <input
                    type="checkbox"
                    name="user_ids"
                    value={p.user_id}
                    defaultChecked={approval.user_ids.includes(p.user_id)}
                  />
                  {p.name}
                </label>
              ))}
            </div>
          </div>
        )}
        {error && <p className="notice err">{error}</p>}
        {saved && <p className="notice ok">Saved.</p>}
        <button disabled={busy}>Save approvers</button>
      </form>
    </section>
  );
}
