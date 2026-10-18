import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { api, Me, Membership } from "../api";
import { month, TraceView } from "./Metrics";
import { UpdatesFeed } from "./Updates";

// "The Full Picture", the board pack from mockup v5.7. The company and its investors see the
// same pack; investors see what was shared and can only comment and tag.

interface Figure {
  update_id: string;
  figure_id: string;
  metric: string;
  label: string;
  unit: string;
  department: string;
  period: string;
  display: string;
  previous_period: string | null;
  previous_display: string | null;
  risk: "high" | "medium" | "low" | null;
  source_line: string;
  edited_by_name: string | null;
  shared: boolean;
}

interface Section {
  id: string;
  kind: string;
  text: string | null;
  status: string;
  label: string;
  unmatched: string[];
}

interface Pack {
  company_name: string;
  data_as_of: string | null;
  includes_unshared: boolean;
  figures: Figure[];
  series: { metric: string; label: string; points: { period: string; value: string; display: string }[] }[];
  targets: { metric: string; label: string; actual: string; actual_display: string; target: string; target_display: string }[];
  commentary: { department: string; update_id: string; shared: boolean; sections: Section[] }[];
  commentary_waiting: boolean;
}

const TABS: [string, string][] = [
  ["overview", "Overview"],
  ["cashflow", "Cashflow"],
  ["market", "Market validation"],
  ["updates", "Updates"],
  ["roadmap", "Roadmap"],
  ["product", "Product"],
  ["people", "People"],
];
const PHASE_2: Record<string, string> = {
  roadmap: "Delivery against plan, from a Jira or Monday export.",
  product: "Product delivery figures, from your project tool's export.",
  people: "Headcount against plan, from an HR export such as HiBob. Pay is never kept.",
};
const RISK_WORDS = { high: "High risk", medium: "Medium risk", low: "Low risk" };
const RISK_CLASS = { high: "risk-high", medium: "risk-medium", low: "risk-low" };

function longDay(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
}

export function Hub({ tenant, me, membership, canEdit }: { tenant: string; me: Me; membership: Membership; canEdit: boolean }) {
  const { page = "overview" } = useParams();
  const navigate = useNavigate();
  const investor = membership.role === "investor";
  const [pack, setPack] = useState<Pack | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    void api<Pack>("/company/pack", { tenant }).then(setPack);
  }, [tenant, version]);

  if (!pack) return <p className="muted">Loading the board pack</p>;
  const backed = me.memberships.filter((m) => m.role === "investor");
  const fig = (metric: string) => pack.figures.find((f) => f.metric === metric);
  const words = (department: string) => pack.commentary.find((c) => c.department === department);
  const go = (tab: string) => navigate(`/c/${tenant}/pack/${tab}`);

  return (
    <div className="hub">
      <div className="hubtop">
        {investor && backed.length > 1 && (
          <select aria-label="Company" value={tenant} onChange={(e) => navigate(`/c/${e.target.value}/pack`)}>
            {backed.map((m) => (
              <option key={m.tenant_id} value={m.tenant_id}>
                {m.tenant_name}
              </option>
            ))}
          </select>
        )}
        <span className="small muted">
          {investor ? "Read-only · shared updates only · you can comment and tag" : canEdit ? "You can edit this pack" : "You can view this pack"}
        </span>
        <span className="sp" />
        {investor ? (
          <span className="pill appr">Read-only</span>
        ) : pack.includes_unshared ? (
          <button className="pill warn as-pill" onClick={() => go("updates")}>
            Includes an update awaiting approval
          </button>
        ) : (
          <span className="pill appr">All shared</span>
        )}
      </div>

      <div className="tabs" role="tablist" aria-label="Board pack">
        {TABS.map(([id, name]) => (
          <button key={id} className="tab" role="tab" aria-selected={page === id} aria-current={page === id ? "page" : undefined} onClick={() => go(id)}>
            {name}
          </button>
        ))}
      </div>

      {page === "overview" && (
        <div className="sec">
          <div className="card hero2">
            <span className="eyebrow">
              {pack.company_name} · {investor ? "Investor dashboard" : "Board pack"}
            </span>
            <h1 className="hero-title">The Full Picture</h1>
            <p className="muted">
              Confidential · {pack.data_as_of ? `data true as of ${longDay(pack.data_as_of)}` : "no data shared yet"}
            </p>
          </div>

          <div className="grid g3">
            <SectionCard title="Cashflow" onOpen={() => go("cashflow")} body="Cash, burn, runway and revenue, calculated from the finance files." chips={[fig("cash_balance") && `${fig("cash_balance")!.display} cash`, fig("runway") && `${fig("runway")!.display} runway`]} />
            <SectionCard title="Market validation" onOpen={() => go("market")} body="Pipeline, coverage and win rate, from the CRM export." chips={[fig("pipeline") && `${fig("pipeline")!.display} pipeline`, fig("coverage") && `${fig("coverage")!.display} coverage`]} />
            <SectionCard title="Updates" onOpen={() => go("updates")} body="Every update, who added it, its commentary and the thread with investors." chips={[pack.data_as_of && `As of ${month(pack.data_as_of.slice(0, 7))}`]} />
            <SectionCard title="Roadmap" onOpen={() => go("roadmap")} body={PHASE_2.roadmap} chips={["Coming in phase 2"]} />
            <SectionCard title="Product" onOpen={() => go("product")} body={PHASE_2.product} chips={["Coming in phase 2"]} />
            <SectionCard title="People" onOpen={() => go("people")} body={PHASE_2.people} chips={["Coming in phase 2"]} />
          </div>

          <PlanCard pack={pack} />

          <div className="tiles">
            {["revenue", "cash_balance", "runway", "net_burn"].map((m) => {
              const f = fig(m);
              const target = m === "revenue" ? pack.targets.find((t) => t.metric === "revenue") : undefined;
              return (
                <div key={m} className="tile static">
                  <span className="k">{f?.label ?? m.replace("_", " ")}</span>
                  <span className={f ? "v" : "v muted-value"}>{f?.display ?? "Not shared yet"}</span>
                  <span className={`d ${target && Number(target.actual) < Number(target.target) ? "bad" : ""}`}>
                    {target
                      ? `${Math.round((Number(target.actual) / Number(target.target)) * 1000) / 10}% of ${target.target_display} plan`
                      : f
                        ? f.risk
                          ? RISK_WORDS[f.risk]
                          : month(f.period)
                        : ""}
                  </span>
                </div>
              );
            })}
          </div>

          {pack.commentary_waiting && (
            <div className="question">
              <p>
                <b>Part of the commentary is waiting for you.</b> Claude's draft did not pass the number check, so a person
                writes it.
              </p>
              <div className="checks">
                <button className="small" onClick={() => go("updates")}>
                  Write it in Updates
                </button>
              </div>
            </div>
          )}
          {pack.commentary.length > 0 && (
            <>
              <h2 className="h-section">Founder update · {pack.data_as_of ? month(pack.data_as_of.slice(0, 7)) : ""}</h2>
              <Commentary sections={pack.commentary[0].sections} />
            </>
          )}
        </div>
      )}

      {page === "cashflow" && (
        <Department
          pack={pack}
          tenant={tenant}
          department="finance"
          metrics={["cash_balance", "revenue", "runway", "net_burn", "gross_margin", "revenue_growth", "revenue_vs_plan"]}
          empty="Add a profit and loss report or a bank export to see cashflow."
          words={words("finance")}
        >
          <MonthlyChart pack={pack} />
        </Department>
      )}

      {page === "market" && (
        <Department
          pack={pack}
          tenant={tenant}
          department="sales"
          metrics={["pipeline", "weighted_pipeline", "coverage", "win_rate", "avg_deal_size", "stalled_deals"]}
          empty="Add a deals list from your CRM to see the pipeline."
          words={words("sales")}
        />
      )}

      {page === "updates" && (
        <UpdatesFeed tenant={tenant} companyName={pack.company_name} version={version} investor={investor} onChanged={() => setVersion((v) => v + 1)} />
      )}

      {PHASE_2[page] && (
        <div className="card">
          <span className="pill">Coming in phase 2</span>
          <p>{PHASE_2[page]}</p>
          <p className="small muted">Files like these can already be added. Their figures appear here when this part is switched on.</p>
        </div>
      )}
      {!investor && (
        <p className="small muted">
          Investors see this same pack, read-only, once updates are approved. <Link to={`/c/${tenant}/team`}>Who can approve</Link>
        </p>
      )}
    </div>
  );
}

function SectionCard({ title, body, chips, onOpen }: { title: string; body: string; chips: (string | false | null | undefined)[]; onOpen: () => void }) {
  return (
    <button className="card section-card" onClick={onOpen}>
      <h3>{title}</h3>
      <p className="small muted">{body}</p>
      <span className="chips">
        {chips.filter(Boolean).map((c) => (
          <span key={c as string} className="tag">
            {c}
          </span>
        ))}
      </span>
    </button>
  );
}

function PlanCard({ pack }: { pack: Pack }) {
  const sources = Array.from(new Set(pack.figures.map((f) => f.source_line.split(",")[0])));
  return (
    <div className="card">
      <h3>Progress to plan</h3>
      {pack.targets.length === 0 ? (
        <p className="small muted">Set a target in setup, or add a budget file, to see progress against plan here.</p>
      ) : (
        <>
          <p className="small muted">Where the latest month landed against its target</p>
          {pack.targets.map((t) => {
            const share = Number(t.actual) / Number(t.target);
            return (
              <div key={t.metric} className="srow">
                <span>
                  {t.label}, target {t.target_display}
                </span>
                <span className="track">
                  <span className={`bar ${share < 1 ? "off" : ""}`} style={{ width: `${Math.min(share, 1) * 100}%` }} />
                </span>
                <span className="amt">{t.actual_display}</span>
              </div>
            );
          })}
          {sources.length > 0 && <p className="small muted">Sources: {sources.join(", ")}. Every figure is calculated by code.</p>}
        </>
      )}
    </div>
  );
}

export function Commentary({ sections }: { sections: Section[] }) {
  return (
    <div className="comm">
      <span className="chips">
        {sections.some((s) => s.status === "drafted") && <span className="tag claude">◆ Drafted by Claude</span>}
        {sections.every((s) => s.status === "drafted") && <span className="tag ok">Number check: passed</span>}
      </span>
      {sections.map((s) => (
        <p key={s.id} className={s.kind === "headline" ? "comm-headline" : ""}>
          {s.text}
        </p>
      ))}
      {sections.some((s) => s.status !== "drafted") && (
        <p className="small muted">{sections.map((s) => s.label).filter((v, i, a) => a.indexOf(v) === i).join(" · ")}</p>
      )}
    </div>
  );
}

function Department({
  pack,
  tenant,
  department,
  metrics,
  empty,
  words,
  children,
}: {
  pack: Pack;
  tenant: string;
  department: string;
  metrics: string[];
  empty: string;
  words: Pack["commentary"][number] | undefined;
  children?: React.ReactNode;
}) {
  const [open, setOpen] = useState<Figure | null>(null);
  const figures = metrics.map((m) => pack.figures.find((f) => f.metric === m)).filter((f): f is Figure => !!f);
  if (figures.length === 0) return <p className="muted card">{empty}</p>;
  return (
    <div className="sec">
      {words && <Commentary sections={words.sections} />}
      <div className="tiles">
        {figures.map((f) => (
          <button key={f.figure_id} className={`tile ${open?.figure_id === f.figure_id ? "open" : ""}`} onClick={() => setOpen(open?.figure_id === f.figure_id ? null : f)} aria-expanded={open?.figure_id === f.figure_id}>
            <span className="k">{f.label}</span>
            <span className="v">{f.display}</span>
            <span className="d">
              {month(f.period)}
              {f.previous_display && f.previous_period && ` · ${month(f.previous_period)}: ${f.previous_display}`}
            </span>
            <span className="tile-foot">
              {f.risk && <span className={`pill ${RISK_CLASS[f.risk]}`}>{RISK_WORDS[f.risk]}</span>}
              {!f.shared && <span className="pill warn">Awaiting approval</span>}
              {f.edited_by_name && <span className="pill warn">Changed by {f.edited_by_name}</span>}
            </span>
          </button>
        ))}
      </div>
      {open && (
        <TraceView key={open.figure_id} tenant={tenant} id={open.figure_id} canManage={false} onChanged={async () => undefined} path={`/company/updates/${open.update_id}/figures/${open.figure_id}`} />
      )}
      {children}
      {department === "finance" && null}
    </div>
  );
}

function MonthlyChart({ pack }: { pack: Pack }) {
  const revenue = pack.series.find((s) => s.metric === "revenue")?.points ?? [];
  const burn = pack.series.find((s) => s.metric === "net_burn")?.points ?? [];
  const periods = revenue.map((p) => p.period).filter((p) => burn.some((b) => b.period === p)).slice(-6);
  if (periods.length === 0) return null;
  const rows = periods.map((p) => ({
    p,
    r: revenue.find((x) => x.period === p)!,
    b: burn.find((x) => x.period === p)!,
  }));
  const max = Math.max(...rows.flatMap((x) => [Number(x.r.value), Math.abs(Number(x.b.value))]), 1);
  const W = 640,
    H = 210,
    base = 190,
    group = W / rows.length,
    bar = Math.min(44, group / 3);
  return (
    <div className="card">
      <h3>Monthly revenue and net burn</h3>
      <p className="small muted">Each month as calculated from the finance file. Values as shown in the pack.</p>
      <svg className="chart" viewBox={`0 0 ${W} ${H + 16}`} role="img" aria-label="Monthly revenue and net burn">
        <line x1="0" x2={W} y1={base} y2={base} className="axis" />
        {rows.map((x, i) => {
          const cx = group * i + group / 2;
          const rh = (Number(x.r.value) / max) * 160;
          const bh = (Math.abs(Number(x.b.value)) / max) * 160;
          return (
            <g key={x.p}>
              <rect x={cx - bar - 2} y={base - rh} width={bar} height={rh} className="bar-in" />
              <rect x={cx + 2} y={base - bh} width={bar} height={bh} className="bar-out" />
              <text x={cx - bar / 2 - 2} y={base - rh - 6} textAnchor="middle" className="chart-label">
                {x.r.display}
              </text>
              <text x={cx + bar / 2 + 2} y={base - bh - 6} textAnchor="middle" className="chart-label">
                {x.b.display}
              </text>
              <text x={cx} y={base + 18} textAnchor="middle" className="chart-axis">
                {month(x.p).split(" ")[0]}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="small">
        <span className="key key-in" /> Revenue <span className="key key-out" /> Net burn
      </p>
    </div>
  );
}
