import { useEffect, useState } from "react";
import { Link } from "react-router";

import { api } from "../api";

interface Measure {
  key: string;
  label: string;
  display: string;
  risk: "high" | "medium" | "low" | null;
  period: string | null;
  available: boolean;
}

interface Card {
  tenant_id: string;
  name: string;
  risk: "high" | "medium" | "low" | null;
  measures: Measure[];
  latest_update_id: string | null;
}

const RISK_WORDS = { high: "High", medium: "Medium", low: "Low" };
const RISK_CLASS = { high: "risk-high", medium: "risk-medium", low: "risk-low" };

// The investor's overview: one card per company, highest risk first, on the same lines
// for every company (FRD ch. 7). Money is never added across companies.
export function PortfolioPage() {
  const [cards, setCards] = useState<Card[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Card[]>("/portfolio/overview").then(setCards, (e: Error) => setError(e.message));
  }, []);

  return (
    <main className="page">
      <div className="page-head">
        <span className="label">Portfolio</span>
        <h1>Companies you back</h1>
        <p className="muted">Highest risk first. Every company is measured on the same lines, from what it has shared.</p>
      </div>
      {error && <p className="notice err">{error}</p>}
      <div className="portfolio">
        {cards?.map((c) => (
          <Link key={c.tenant_id} to={`/c/${c.tenant_id}#updates`} className="card company-card" aria-label={`Open ${c.name}`}>
            <div className="company-head">
              <h2>{c.name}</h2>
              {c.risk ? (
                <span className={`pill ${RISK_CLASS[c.risk]}`}>{RISK_WORDS[c.risk]} risk</span>
              ) : (
                <span className="pill">Nothing shared yet</span>
              )}
            </div>
            <div className="measures">
              {c.measures.map((m) => (
                <div key={m.key} className="measure">
                  <span className="label">{m.label}</span>
                  <span className={m.available ? "measure-value" : "measure-value muted-value"}>{m.display}</span>
                  {m.risk && <span className={`pill ${RISK_CLASS[m.risk]}`}>{RISK_WORDS[m.risk]}</span>}
                </div>
              ))}
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}
