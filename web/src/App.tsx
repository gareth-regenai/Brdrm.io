import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useNavigate, useParams } from "react-router";

import { api, Me, ROLE_NAMES, signedIn, signOut } from "./api";
import { CompanyPage } from "./pages/Company";
import { InvitePage } from "./pages/Invite";
import { PortfolioPage } from "./pages/Portfolio";
import { SignInPage, SignUpPage } from "./pages/Auth";

export function App() {
  return (
    <Routes>
      <Route path="/signin" element={<SignInPage />} />
      <Route path="/signup" element={<SignUpPage />} />
      <Route path="/invite" element={<InvitePage />} />
      <Route path="/*" element={<SignedIn />} />
    </Routes>
  );
}

function SignedIn() {
  const [me, setMe] = useState<Me | null>(null);
  const [failed, setFailed] = useState(false);

  const reload = useCallback(() => {
    api<Me>("/me").then(setMe, () => setFailed(true));
  }, []);

  useEffect(() => {
    if (signedIn()) reload();
  }, [reload]);

  if (!signedIn() || failed) return <Navigate to="/signin" replace />;
  if (!me) return <p className="narrow muted">Loading</p>;

  return (
    <>
      <TopBar me={me} />
      <Routes>
        <Route path="/" element={<Home me={me} />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/c/:tenantId" element={<CompanyRoute me={me} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

function Home({ me }: { me: Me }) {
  const company = me.memberships.find((m) => m.role !== "investor");
  if (company) return <Navigate to={`/c/${company.tenant_id}`} replace />;
  if (me.memberships.length) return <Navigate to="/portfolio" replace />;
  return (
    <main className="page">
      <div className="card">
        <h2>You are not in a company yet</h2>
        <p>Ask the company that invited you to send the invitation again, or create your own company.</p>
      </div>
    </main>
  );
}

function CompanyRoute({ me }: { me: Me }) {
  const { tenantId } = useParams();
  const membership = me.memberships.find((m) => m.tenant_id === tenantId);
  if (!membership) return <Navigate to="/" replace />;
  return <CompanyPage key={membership.tenant_id} me={me} membership={membership} />;
}

function TopBar({ me }: { me: Me }) {
  const navigate = useNavigate();
  const { tenantId } = useParams();
  const companies = me.memberships.filter((m) => m.role !== "investor");
  const backs = me.memberships.some((m) => m.role === "investor");
  const current = location.pathname.startsWith("/c/") ? location.pathname.split("/")[2] : tenantId;

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link to="/" className="wordmark">
          <img src="/boardroom-mark.svg" alt="" width={28} height={28} />
          <span>
            BoardRoom<span className="io">.io</span>
          </span>
        </Link>
        {backs && (
          <Link to="/portfolio" style={{ color: "inherit" }}>
            Portfolio
          </Link>
        )}
        <span className="spacer" />
        {companies.length > 1 && (
          <select
              aria-label="Company"
              value={companies.some((c) => c.tenant_id === current) ? current : ""}
              onChange={(e) => navigate(`/c/${e.target.value}`)}
            >
              <option value="" disabled>
                Choose a company
              </option>
              {companies.map((c) => (
                <option key={c.tenant_id} value={c.tenant_id}>
                  {c.tenant_name} ({ROLE_NAMES[c.role]})
                </option>
              ))}
          </select>
        )}
        <span className="small" style={{ color: "inherit" }}>
          {me.name}
        </span>
        <button
          className="small"
          onClick={async () => {
            await signOut();
            navigate("/signin");
          }}
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
