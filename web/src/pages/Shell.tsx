import { useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router";

import { api, Me, Membership, ROLE_NAMES, signOut } from "../api";
import { SetupChat } from "./Setup";

// The app shell from mockup v5.7: a sidebar with the logo, the pages, and the company box.

const ICON = { width: 20, height: 20, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.5, "aria-hidden": true };

const PAGES: [string, string, JSX.Element][] = [
  [
    "",
    "Dashboard",
    <svg key="d" {...ICON}>
      <rect x="3.5" y="3.5" width="7" height="7" />
      <rect x="13.5" y="3.5" width="7" height="7" />
      <rect x="3.5" y="13.5" width="7" height="7" />
      <rect x="13.5" y="13.5" width="7" height="7" />
    </svg>,
  ],
  [
    "pack",
    "Board pack",
    <svg key="p" {...ICON}>
      <path d="M6 3.5h8l4 4v13H6z" />
      <path d="M9.5 17v-3M12 17v-6M14.5 17v-4.5" />
    </svg>,
  ],
  [
    "files",
    "Files",
    <svg key="f" {...ICON}>
      <path d="M12 15.5V4M7.5 8.5 12 4l4.5 4.5" />
      <path d="M4.5 15v4.5h15V15" />
    </svg>,
  ],
  [
    "team",
    "Team",
    <svg key="t" {...ICON}>
      <circle cx="9" cy="8.5" r="3" />
      <path d="M3.5 19.5c.6-3 2.8-4.5 5.5-4.5s4.9 1.5 5.5 4.5" />
      <circle cx="16.5" cy="9.5" r="2.3" />
      <path d="M16 14.6c2.3 0 4 1.3 4.5 3.9" />
    </svg>,
  ],
  [
    "settings",
    "Settings",
    <svg key="s" {...ICON}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3.5v2.5M12 18v2.5M3.5 12H6M18 12h2.5M6 6l1.8 1.8M16.2 16.2 18 18M6 18l1.8-1.8M16.2 7.8 18 6" />
    </svg>,
  ],
];

export function Sidebar({ me, membership }: { me: Me; membership: Membership }) {
  const navigate = useNavigate();
  const base = `/c/${membership.tenant_id}`;
  const companies = me.memberships.filter((m) => m.role !== "investor");
  const backs = me.memberships.some((m) => m.role === "investor");
  return (
    <nav className="side" aria-label="Company">
      <Link to={base} className="wordmark side-logo">
        <img src="/boardroom-mark.svg" alt="" width={28} height={28} />
        <span className="lt">
          BoardRoom<span className="io">.io</span>
        </span>
      </Link>
      {PAGES.map(([path, label, icon]) => (
        <NavLink key={label} to={path ? `${base}/${path}` : base} end={!path} className="side-item">
          {icon}
          <span>{label}</span>
        </NavLink>
      ))}
      <div className="co">
        <b>{membership.tenant_name}</b>
        <div className="small muted">
          You are {me.name.split(" ")[0]} ({ROLE_NAMES[membership.role]})
        </div>
        {companies.length > 1 && (
          <select aria-label="Company" value={membership.tenant_id} onChange={(e) => navigate(`/c/${e.target.value}`)}>
            {companies.map((c) => (
              <option key={c.tenant_id} value={c.tenant_id}>
                {c.tenant_name}
              </option>
            ))}
          </select>
        )}
        <div className="checks">
          {backs && (
            <Link to="/portfolio" className="small">
              Your portfolio
            </Link>
          )}
          <button
            className="link small"
            onClick={async () => {
              await signOut();
              navigate("/signin");
            }}
          >
            Sign out
          </button>
        </div>
      </div>
    </nav>
  );
}

interface UpdateRow {
  id: string;
  headline: string;
  data_as_of: string;
  status: "awaiting_approval" | "shared";
  can_approve: boolean;
  sections: { status: string }[];
}

interface UploadRow {
  id: string;
  filename: string;
  status: string;
  question: unknown;
  needs_mapping: boolean;
}

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

function day(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
}

export function Dashboard({
  tenant,
  firstName,
  canSetUp,
  onChanged,
  me,
}: {
  tenant: string;
  firstName: string;
  canSetUp: boolean;
  onChanged: () => void;
  me: Me;
}) {
  const [updates, setUpdates] = useState<UpdateRow[] | null>(null);
  const [uploads, setUploads] = useState<UploadRow[]>([]);

  useEffect(() => {
    void api<UpdateRow[]>("/company/updates", { tenant }).then(setUpdates);
    void api<UploadRow[]>("/company/uploads", { tenant }).then(setUploads, () => setUploads([]));
  }, [tenant]);

  // The newest data across updates, not the most recently added file.
  const latest = updates?.reduce<UpdateRow | undefined>((a, u) => (!a || u.data_as_of > a.data_as_of ? u : a), undefined);
  const attention: [string, string][] = [];
  for (const u of updates ?? []) {
    if (u.can_approve) attention.push([`"${u.headline}" is waiting for your approval.`, "pack/updates"]);
    if (u.sections.some((s) => s.status === "needs_person"))
      attention.push([`Commentary on "${u.headline}" needs a person to write part of it.`, "pack/updates"]);
  }
  for (const f of uploads) {
    if (f.question) attention.push([`${f.filename} has one question for you.`, "files"]);
    else if (f.needs_mapping) attention.push([`${f.filename} needs its columns chosen.`, "files"]);
    else if (f.status === "failed") attention.push([`${f.filename} could not be used.`, "files"]);
  }

  return (
    <>
      <div className="dash-head">
        <div>
          <h1>
            {greeting()}, {firstName}
          </h1>
          <p className="muted">
            {!updates ? "" : latest ? `Data true as of ${day(latest.data_as_of)}.` : "Add your first file to start your board pack."}
          </p>
        </div>
        <Link to="pack" className="button-primary">
          Open the board pack
        </Link>
      </div>
      {canSetUp && <SetupChat tenant={tenant} userName={me.name} onChanged={onChanged} untilDone />}
      <div className="grid-2">
        <section className="card">
          <h2>Updates</h2>
          {!updates ? (
            <p className="muted">Loading</p>
          ) : updates.length === 0 ? (
            <p className="muted">Each file you add becomes an update. Investors see it once it is approved.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <tbody>
                  {updates.slice(0, 5).map((u) => (
                    <tr key={u.id}>
                      <td>
                        {u.headline}
                        <div className="small">Data true as of {day(u.data_as_of)}</div>
                      </td>
                      <td>
                        <span className={`pill ${u.status === "shared" ? "appr" : "warn"}`}>
                          {u.status === "shared" ? "Shared" : "Awaiting approval"}
                        </span>
                      </td>
                      <td>
                        <Link to="pack/updates">View</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <section className="card">
          <h2>Needs attention</h2>
          {!updates ? (
            <p className="muted">Loading</p>
          ) : attention.length === 0 ? (
            <p className="muted">Nothing needs you right now.</p>
          ) : (
            <ul className="attention">
              {attention.map(([text, to]) => (
                <li key={text}>
                  <span className="ic" aria-hidden>
                    !
                  </span>
                  <Link to={to}>{text}</Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
