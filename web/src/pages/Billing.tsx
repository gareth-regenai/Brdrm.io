import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import { api, LIMIT_EVENT } from "../api";

interface Line {
  key: string;
  label: string;
  limit: number | null;
  used: number | null;
}

interface PlanOption {
  key: string;
  name: string;
  lines: Line[];
  current: boolean;
  can_buy: boolean;
}

interface Billing {
  plan_name: string | null;
  status: string | null;
  behaviour: "warn" | "block";
  payment_ready: boolean;
  has_account: boolean;
  current_period_end: string | null;
  lines: Line[];
  plans: PlanOption[];
}

const STATUS_WORDS: Record<string, string> = {
  active: "Paid",
  trialing: "Trial",
  past_due: "Payment overdue",
  canceled: "Ended",
  incomplete: "Waiting for payment",
  incomplete_expired: "Payment not completed",
  unpaid: "Unpaid",
  paused: "Paused",
};

function amount(line: Line): string {
  if (line.limit === null) return "No limit";
  return line.key === "max_file_mb" ? `${line.limit} MB` : String(line.limit);
}

// The company's plan, what it uses against each limit, and the way to change it (FRD ch. 9).
// Prices and limits come from the plans BoardRoom sets, never from this page.
export function BillingSection({ tenant }: { tenant: string }) {
  const [billing, setBilling] = useState<Billing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [params] = useSearchParams();
  const outcome = params.get("billing");

  const load = useCallback(() => {
    api<Billing>("/company/billing", { tenant }).then(setBilling, (e: Error) => setError(e.message));
  }, [tenant]);

  useEffect(() => {
    load();
    // Stripe confirms a payment by webhook, a moment after it sends the person back.
    if (outcome === "done") {
      const again = setTimeout(load, 3000);
      return () => clearTimeout(again);
    }
  }, [load, outcome]);

  async function go(path: string, body?: unknown) {
    setBusy(true);
    setError(null);
    try {
      const { url } = await api<{ url: string }>(path, { method: "POST", tenant, body });
      window.location.assign(url);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  if (!billing) return error ? <p className="notice err">{error}</p> : <p className="muted">Loading</p>;

  const status = billing.status ? (STATUS_WORDS[billing.status] ?? billing.status) : null;
  const buyable = billing.plans.filter((p) => !p.current && p.can_buy);

  return (
    <section className="card billing" aria-labelledby="billing-title">
      <div className="billing-head">
        <div>
          <span className="label">Plan</span>
          <h2 id="billing-title">{billing.plan_name ?? "No plan chosen"}</h2>
          {status && (
            <p className="small muted">
              {status}
              {billing.current_period_end &&
                billing.status !== "canceled" &&
                `, renews ${new Date(billing.current_period_end).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}`}
            </p>
          )}
        </div>
        {billing.has_account && billing.payment_ready && (
          <button className="small" disabled={busy} onClick={() => go("/company/billing/portal")}>
            Manage billing
          </button>
        )}
      </div>
      {outcome === "done" && <p className="notice ok">Stripe has the payment. The plan shows here once Stripe confirms it.</p>}
      {outcome === "cancelled" && <p className="notice">Nothing was paid. The plan has not changed.</p>}
      {error && <p className="notice err">{error}</p>}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="label">Limit</th>
              <th className="label num">Used</th>
              <th className="label num">Plan allows</th>
            </tr>
          </thead>
          <tbody>
            {billing.lines.map((line) => {
              const over = line.limit !== null && line.used !== null && line.used > line.limit;
              return (
                <tr key={line.key}>
                  <td>{line.label}</td>
                  <td className="num">{line.used ?? ""}</td>
                  <td className={over ? "num over" : "num"}>
                    {amount(line)}
                    {over && <span className="pill warn">Over</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="small muted">
        {billing.behaviour === "block"
          ? "At a limit, the action is refused until the plan changes."
          : "Past a limit, the action still goes through and the person is told."}{" "}
        Approving updates never depends on the plan.
      </p>

      {buyable.length > 0 && (
        <>
          <h3>Change plan</h3>
          <div className="plan-grid">
            {buyable.map((p) => (
              <div key={p.key} className="plan-option">
                <h4>{p.name}</h4>
                <ul className="small">
                  {p.lines.map((line) => (
                    <li key={line.key}>
                      {line.label}: {amount(line)}
                    </li>
                  ))}
                </ul>
                <button
                  className="primary small"
                  disabled={busy || !billing.payment_ready}
                  onClick={() => go("/company/billing/checkout", { plan: p.key })}
                >
                  Choose {p.name}
                </button>
              </div>
            ))}
          </div>
        </>
      )}
      {!billing.payment_ready && <p className="small muted">Payment is not set up yet.</p>}
    </section>
  );
}

// Shows a plan limit passed in warn mode, wherever the person was when it happened.
export function LimitNotice() {
  const [warning, setWarning] = useState<string | null>(null);

  useEffect(() => {
    const show = (e: Event) => setWarning((e as CustomEvent<string>).detail);
    window.addEventListener(LIMIT_EVENT, show);
    return () => window.removeEventListener(LIMIT_EVENT, show);
  }, []);

  if (!warning) return null;
  return (
    <div className="notice limit-notice" role="status">
      <span>{warning}</span>
      <button className="link small" onClick={() => setWarning(null)}>
        Dismiss
      </button>
    </div>
  );
}
