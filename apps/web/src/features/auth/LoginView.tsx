import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { SectionHeader } from "../../components/FieldPrimitives";
import { LogIn, Key, Shield } from "lucide-react";

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
    <div style={{ maxWidth: "520px", margin: "40px auto" }}>
      <div style={{
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-sm)",
        overflow: "hidden",
        marginBottom: "20px",
      }}>
        <SectionHeader title="CivicTrace Portal Sign-In" />

        <div style={{ padding: "24px" }}>
          {errorMsg && (
            <div style={{
              padding: "10px 14px",
              backgroundColor: "var(--color-disputed-red-subtle)",
              color: "var(--color-disputed-red)",
              borderRadius: "var(--radius-sm)",
              fontSize: "13px",
              marginBottom: "16px",
            }}>
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "4px" }}>
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
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "4px" }}>
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
              className="btn btn-dark"
              style={{ width: "100%", marginTop: "4px", padding: "8px 14px" }}
            >
              <LogIn size={14} /> {loading ? "Signing in..." : "Sign In to Field Ledger"}
            </button>
          </form>
        </div>
      </div>

      {/* Quick Demo Accounts Selection Box */}
      <div style={{
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-sm)",
        overflow: "hidden",
      }}>
        <div style={{
          padding: "10px 16px",
          backgroundColor: "var(--color-surface-elevated)",
          borderBottom: "1px solid var(--color-border)",
          fontSize: "11px",
          fontFamily: "var(--font-family-mono)",
          fontWeight: 600,
          color: "var(--color-text-secondary)",
          textTransform: "uppercase",
        }}>
          Seeded Local Demo Roles (One-Click Selection):
        </div>

        <div style={{ padding: "14px", display: "flex", flexDirection: "column", gap: "8px" }}>
          <button
            type="button"
            onClick={() => handleQuickDemoFill("reviewer@civictrace.local", "ReviewerPass2026!")}
            className="btn btn-outline btn-sm"
            style={{ justifyContent: "space-between", fontSize: "12px", padding: "8px 12px" }}
          >
            <span><strong>Community Reviewer:</strong> reviewer@civictrace.local</span>
            <Key size={13} color="var(--color-civic-blue)" />
          </button>

          <button
            type="button"
            onClick={() => handleQuickDemoFill("lighting.operator@civictrace.local", "OperatorPass2026!")}
            className="btn btn-outline btn-sm"
            style={{ justifyContent: "space-between", fontSize: "12px", padding: "8px 12px" }}
          >
            <span><strong>Public Works Operator:</strong> lighting.operator@civictrace.local</span>
            <Key size={13} color="var(--color-attention-orange)" />
          </button>

          <button
            type="button"
            onClick={() => handleQuickDemoFill("citizen.aarav@civictrace.local", "CitizenPass2026!")}
            className="btn btn-outline btn-sm"
            style={{ justifyContent: "space-between", fontSize: "12px", padding: "8px 12px" }}
          >
            <span><strong>Citizen Observer:</strong> citizen.aarav@civictrace.local</span>
            <Key size={13} color="var(--color-verified-green)" />
          </button>

          <button
            type="button"
            onClick={() => handleQuickDemoFill("admin@civictrace.local", "AdminPass2026!")}
            className="btn btn-outline btn-sm"
            style={{ justifyContent: "space-between", fontSize: "12px", padding: "8px 12px" }}
          >
            <span><strong>Administrator:</strong> admin@civictrace.local</span>
            <Shield size={13} color="var(--color-civic-blue)" />
          </button>
        </div>
      </div>
    </div>
  );
};
