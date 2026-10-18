import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router";

import { api, Me, signedIn, signOut } from "./api";
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
      <Masthead me={me} />
      <Routes>
        <Route path="/" element={<Home me={me} />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/c/:tenantId/*" element={<CompanyRoute me={me} />} />
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

// Company users get the sidebar from v5.7, which carries the logo and who they are.
// Investors, and anyone outside a company, get this light masthead instead.
function Masthead({ me }: { me: Me }) {
  const navigate = useNavigate();
  const location = useLocation();
  const inCompany = location.pathname.startsWith("/c/") ? location.pathname.split("/")[2] : null;
  const membership = me.memberships.find((m) => m.tenant_id === inCompany);
  if (membership && membership.role !== "investor") return null;
  const backs = me.memberships.some((m) => m.role === "investor");

  return (
    <header className="masthead">
      <Link to="/" className="wordmark">
        <img src="/boardroom-mark.svg" alt="" width={28} height={28} />
        <span>
          BoardRoom<span className="io">.io</span>
        </span>
      </Link>
      <span className="spacer" />
      {backs && (
        <Link to="/portfolio" className="masthead-link" aria-current={location.pathname === "/portfolio" ? "page" : undefined}>
          Portfolio
        </Link>
      )}
      <span className="small muted">
        {me.name}
        {backs && " · Investor · read-only"}
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
    </header>
  );
}
