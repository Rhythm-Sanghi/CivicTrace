import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { PageHeading, SectionHeader } from "../../components/FieldPrimitives";

export const LoginView: React.FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");

    try {
      await api.login(email, password);
      navigate("/explorer");
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to authenticate");
      setLoading(false);
    }
  };

  const handleQuickDemoFill = (roleEmail: string, rolePass: string) => {
    setEmail(roleEmail);
    setPassword(rolePass);
  };

  return (
    <>
      <PageHeading
        index="00"
        title="Portal Sign-In"
        description="Authenticate with civic credentials or use demo identity keys. CivicTrace Portal Sign-In."
      />

      <div className="workspace">
        <div style={{ maxWidth: "480px", margin: "20px auto" }}>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "var(--space-5)" }}>
            <SectionHeader index="01" title="CivicTrace Portal Sign-In" />

            {errorMsg && (
              <div role="alert" style={{ marginBottom: "var(--space-3)" }}>
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleLogin} style={{ margin: "var(--space-3) 0" }}>
              <div style={{ marginBottom: "var(--space-3)" }}>
                <label htmlFor="login-email">Email Address</label>
                <input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  style={{ width: "100%" }}
                />
              </div>

              <div style={{ marginBottom: "var(--space-4)" }}>
                <label htmlFor="login-password">Password</label>
                <input
                  id="login-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  style={{ width: "100%" }}
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="button-primary"
                style={{ width: "100%", justifyContent: "center" }}
              >
                {loading ? "Authenticating..." : "Sign In to Portal"}
              </button>
            </form>

            <div style={{ borderTop: "1px solid var(--border)", paddingTop: "var(--space-3)", marginTop: "var(--space-4)" }}>
              <span className="muted" style={{ fontSize: "11px", display: "block", marginBottom: "var(--space-2)" }}>
                One-Click Seed Accounts:
              </span>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-2)" }}>
                <button
                  type="button"
                  onClick={() => handleQuickDemoFill("citizen.aarav@civictrace.local", "CitizenPass2026!")}
                  className="btn-outline btn-sm"
                >
                  Citizen (Aarav)
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickDemoFill("reviewer@civictrace.local", "ReviewerPass2026!")}
                  className="btn-outline btn-sm"
                >
                  Reviewer (Rajesh)
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickDemoFill("lighting.operator@civictrace.local", "OperatorPass2026!")}
                  className="btn-outline btn-sm"
                >
                  Operator (Kavita)
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickDemoFill("admin@civictrace.local", "AdminPass2026!")}
                  className="btn-outline btn-sm"
                >
                  Administrator
                </button>
              </div>
            </div>

            <div style={{ borderTop: "1px solid var(--border)", paddingTop: "var(--space-3)", marginTop: "var(--space-3)", textAlign: "center" }}>
              <span className="muted" style={{ fontSize: "12px" }}>
                New citizen?{" "}
                <Link to="/register" style={{ color: "var(--accent)", fontWeight: 600 }}>
                  Create an account
                </Link>
              </span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
