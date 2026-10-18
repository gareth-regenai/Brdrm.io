import { useEffect, useState } from "react";
import { Link } from "react-router";

import { api } from "../api";

interface PortfolioCompany {
  id: string;
  name: string;
}

export function PortfolioPage() {
  const [companies, setCompanies] = useState<PortfolioCompany[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<PortfolioCompany[]>("/portfolio").then(setCompanies, (e: Error) => setError(e.message));
  }, []);

  return (
    <main className="page">
      <div className="page-head">
        <span className="label">Portfolio</span>
        <h1>Companies you back</h1>
        <p className="muted">
          Each company that invites you appears here. Figures and risk levels arrive with the overview in a later
          release.
        </p>
      </div>
      {error && <p className="notice err">{error}</p>}
      {companies && (
        <ul className="list">
          {companies.map((c) => (
            <li key={c.id}>
              <Link to={`/c/${c.id}`} className="card company-card">
                <h3>{c.name}</h3>
                <span className="small">Open company</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
