import { FormEvent, ReactNode, useState } from "react";
import { Link, useNavigate } from "react-router";

import { api, saveSession, Tokens } from "../api";

export function AuthFrame({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="narrow">
      <div className="card">
        <div className="wordmark">
          <img src="/boardroom-mark.svg" alt="" width={32} height={32} />
          <span>
            BoardRoom<span className="io muted">.io</span>
          </span>
        </div>
        <h2>{title}</h2>
        {children}
      </div>
    </main>
  );
}

export function Field(props: {
  label: string;
  name: string;
  type?: string;
  autoComplete?: string;
  defaultValue?: string;
  readOnly?: boolean;
  hint?: string;
}) {
  return (
    <label className="field">
      <span>{props.label}</span>
      <input
        name={props.name}
        type={props.type ?? "text"}
        autoComplete={props.autoComplete}
        defaultValue={props.defaultValue}
        readOnly={props.readOnly}
        required
      />
      {props.hint && <small className="muted">{props.hint}</small>}
    </label>
  );
}

export function useSubmit(run: (data: FormData, form: HTMLFormElement) => Promise<void>) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const form = e.currentTarget;
      await run(new FormData(form), form);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  };
  return { error, busy, onSubmit };
}

export function SignInPage() {
  const navigate = useNavigate();
  const { error, busy, onSubmit } = useSubmit(async (data) => {
    const tokens = await api<Tokens>("/auth/login", {
      method: "POST",
      body: { email: data.get("email"), password: data.get("password") },
    });
    saveSession(tokens);
    // Coming from an invitation link: go back to it to accept.
    const invite = sessionStorage.getItem("boardroom.invite");
    sessionStorage.removeItem("boardroom.invite");
    navigate(invite ? `/invite?token=${encodeURIComponent(invite)}` : "/");
  });
  return (
    <AuthFrame title="Sign in">
      <form onSubmit={onSubmit}>
        <Field label="Email" name="email" type="email" autoComplete="email" />
        <Field label="Password" name="password" type="password" autoComplete="current-password" />
        {error && <p className="notice err">{error}</p>}
        <button className="primary" disabled={busy}>
          Sign in
        </button>
      </form>
      <p className="small">
        New to BoardRoom.io? <Link to="/signup">Create your company</Link>
      </p>
    </AuthFrame>
  );
}

export function SignUpPage() {
  const navigate = useNavigate();
  const { error, busy, onSubmit } = useSubmit(async (data) => {
    const tokens = await api<Tokens>("/auth/signup", {
      method: "POST",
      body: {
        name: data.get("name"),
        email: data.get("email"),
        password: data.get("password"),
        company_name: data.get("company_name"),
      },
    });
    saveSession(tokens);
    navigate(tokens.tenant_id ? `/c/${tokens.tenant_id}` : "/");
  });
  return (
    <AuthFrame title="Create your company">
      <p className="muted">You become the company's Owner. You can invite your team and investors next.</p>
      <form onSubmit={onSubmit}>
        <Field label="Company name" name="company_name" autoComplete="organization" />
        <Field label="Your name" name="name" autoComplete="name" />
        <Field label="Work email" name="email" type="email" autoComplete="email" />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          hint="At least 12 characters."
        />
        {error && <p className="notice err">{error}</p>}
        <button className="primary" disabled={busy}>
          Create company
        </button>
      </form>
      <p className="small">
        Already have an account? <Link to="/signin">Sign in</Link>
      </p>
    </AuthFrame>
  );
}
