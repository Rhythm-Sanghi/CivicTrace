import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { LogIn } from "lucide-react";

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
      window.location.reload();
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
    <div style={{ padding: "var(--space-10) 0" }}>
      <div className="container" style={{ maxWidth: "480px" }}>
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <h1 style={{ fontSize: "22px", fontWeight: 700 }}>CivicTrace Portal Sign-In</h1>
          <p style={{ fontSize: "13px", color: "var(--color-text-secondary)", marginTop: "4px" }}>
            Sign in to access reviewer correlation desk or operator work orders
          </p>
        </div>

        <div className="card" style={{ marginBottom: "20px" }}>
          {errorMsg && (
            <div style={{
              padding: "10px",
              backgroundColor: "var(--color-disputed-red-subtle)",
              color: "var(--color-disputed-red)",
              borderRadius: "var(--radius-sm)",
              fontSize: "13px",
              marginBottom: "14px",
            }}>
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  fontSize: "13px",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-sm)",
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  fontSize: "13px",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-sm)",
                }}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary"
              style={{ marginTop: "6px" }}
            >
              <LogIn size={14} /> {loading ? "Signing in..." : "Sign In"}
            </button>
          </form>
        </div>

        {/* Quick Demo Accounts Selection Box */}
        <div className="card" style={{ backgroundColor: "var(--color-surface-elevated)" }}>
          <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--color-text-secondary)", marginBottom: "8px" }}>
            Seeded Local Demo Roles (One-Click Selection):
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <button
              type="button"
              onClick={() => handleQuickDemoFill("reviewer@civictrace.local", "ReviewerPass2026!")}
              className="btn btn-outline btn-sm"
              style={{ justifyContent: "flex-start", fontSize: "11px" }}
            >
              <strong>Community Reviewer:</strong> reviewer@civictrace.local
            </button>

            <button
              type="button"
              onClick={() => handleQuickDemoFill("lighting.operator@civictrace.local", "OperatorPass2026!")}
              className="btn btn-outline btn-sm"
              style={{ justifyContent: "flex-start", fontSize: "11px" }}
            >
              <strong>Public Works Operator:</strong> lighting.operator@civictrace.local
            </button>

            <button
              type="button"
              onClick={() => handleQuickDemoFill("citizen.aarav@civictrace.local", "CitizenPass2026!")}
              className="btn btn-outline btn-sm"
              style={{ justifyContent: "flex-start", fontSize: "11px" }}
            >
              <strong>Citizen Observer:</strong> citizen.aarav@civictrace.local
            </button>

            <button
              type="button"
              onClick={() => handleQuickDemoFill("admin@civictrace.local", "AdminPass2026!")}
              className="btn btn-outline btn-sm"
              style={{ justifyContent: "flex-start", fontSize: "11px" }}
            >
              <strong>Administrator:</strong> admin@civictrace.local
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
