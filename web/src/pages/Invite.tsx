import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";

import { api, saveSession, signedIn, Tokens } from "../api";
import { AuthFrame, Field, useSubmit } from "./Auth";

export function InvitePage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const [existing, setExisting] = useState(signedIn());

  const accept = useSubmit(async () => {
    const r = await api<{ tenant_id: string }>("/invitations/accept", {
      method: "POST",
      body: { token },
    });
    navigate(`/c/${r.tenant_id}`);
  });

  const join = useSubmit(async (data) => {
    const tokens = await api<Tokens>("/auth/signup", {
      method: "POST",
      body: {
        name: data.get("name"),
        email: data.get("email"),
        password: data.get("password"),
        invite_token: token,
      },
    });
    saveSession(tokens);
    navigate(tokens.tenant_id ? `/c/${tokens.tenant_id}` : "/");
  });

  if (!token) {
    return (
      <AuthFrame title="This link is missing its invitation">
        <p>Open the link from your invitation email again, or ask for a new invitation.</p>
      </AuthFrame>
    );
  }

  if (existing) {
    return (
      <AuthFrame title="Accept your invitation">
        <p>The invitation is added to the account you are signed in with. It must be the email the invitation was sent to.</p>
        <form onSubmit={accept.onSubmit}>
          {accept.error && <p className="notice err">{accept.error}</p>}
          <button className="primary" disabled={accept.busy}>
            Accept invitation
          </button>
        </form>
        <button className="small" onClick={() => setExisting(false)}>
          Use a new account instead
        </button>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame title="Accept your invitation">
      <p className="muted">Create your account with the email the invitation was sent to.</p>
      <form onSubmit={join.onSubmit}>
        <Field label="Your name" name="name" autoComplete="name" />
        <Field label="Email" name="email" type="email" autoComplete="email" />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          hint="At least 12 characters."
        />
        {join.error && <p className="notice err">{join.error}</p>}
        <button className="primary" disabled={join.busy}>
          Accept and create account
        </button>
      </form>
      <p className="small">
        Already have an account?{" "}
        <Link to="/signin" onClick={() => sessionStorage.setItem("boardroom.invite", token)}>
          Sign in to accept
        </Link>
      </p>
    </AuthFrame>
  );
}
