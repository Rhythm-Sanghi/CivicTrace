import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { PageHeading, SectionHeader } from "../../components/FieldPrimitives";

export const RegisterView: React.FC = () => {
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");

    if (password.length < 8) {
      setErrorMsg("Password must be at least 8 characters long.");
      return;
    }
    if (password !== confirmPassword) {
      setErrorMsg("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      await api.register({
        display_name: displayName,
        email,
        password,
      });
      // Automatically log the new citizen in
      await api.login(email, password);
      navigate("/explorer");
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to register account.");
      setLoading(false);
    }
  };

  return (
    <>
      <PageHeading
        index="00"
        title="Citizen Registration"
        description="Create a citizen observer account to submit corroborated observations, participate in community resolution verification, and track civic infrastructure."
      />

      <div className="workspace">
        <div style={{ maxWidth: "480px", margin: "20px auto" }}>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "var(--space-5)" }}>
            <SectionHeader index="01" title="Register Citizen Identity" />

            {errorMsg && (
              <div role="alert" style={{ marginBottom: "var(--space-3)", color: "var(--danger)" }}>
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleRegister} style={{ margin: "var(--space-3) 0" }}>
              <div style={{ marginBottom: "var(--space-3)" }}>
                <label htmlFor="reg-name">Full Name / Public Display Pseudonym</label>
                <input
                  id="reg-name"
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="e.g. Aarav Sharma"
                  required
                  style={{ width: "100%" }}
                />
              </div>

              <div style={{ marginBottom: "var(--space-3)" }}>
                <label htmlFor="reg-email">Email Address</label>
                <input
                  id="reg-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@domain.local"
                  required
                  style={{ width: "100%" }}
                />
              </div>

              <div style={{ marginBottom: "var(--space-3)" }}>
                <label htmlFor="reg-password">Password (minimum 8 characters)</label>
                <input
                  id="reg-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  style={{ width: "100%" }}
                />
              </div>

              <div style={{ marginBottom: "var(--space-4)" }}>
                <label htmlFor="reg-confirm">Confirm Password</label>
                <input
                  id="reg-confirm"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
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
                {loading ? "Registering account..." : "Register Citizen Account"}
              </button>
            </form>

            <div style={{ borderTop: "1px solid var(--border)", paddingTop: "var(--space-3)", marginTop: "var(--space-4)", textAlign: "center" }}>
              <span className="muted" style={{ fontSize: "12px" }}>
                Already registered?{" "}
                <Link to="/login" style={{ color: "var(--accent)", fontWeight: 600 }}>
                  Sign in to portal
                </Link>
              </span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
