import React from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { getCurrentUser, clearAuthToken, type User } from "../lib/api";
import { LogOut, LogIn } from "lucide-react";

export const Header: React.FC = () => {
  const navigate = useNavigate();
  const [user, setUser] = React.useState<User | null>(getCurrentUser());

  const handleLogout = () => {
    clearAuthToken();
    setUser(null);
    navigate("/");
  };

  return (
    <header style={{
      backgroundColor: "var(--color-surface)",
      borderBottom: "1px solid var(--color-border)",
      position: "sticky",
      top: 0,
      zIndex: 100,
    }}>
      <div className="container" style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        height: "64px",
      }}>
        {/* Brand / Logo */}
        <Link to="/" style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          textDecoration: "none",
          color: "var(--color-text-primary)",
        }}>
          <div style={{
            width: "32px",
            height: "32px",
            backgroundColor: "var(--color-civic-blue)",
            color: "#FFF",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 700,
            borderRadius: "var(--radius-sm)",
            fontFamily: "var(--font-family-mono)",
            fontSize: "14px",
          }}>
            CT
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: "16px", letterSpacing: "-0.01em" }}>
              CivicTrace
            </div>
            <div style={{ fontSize: "10px", color: "var(--color-text-secondary)", marginTop: "-2px" }}>
              Public Evidence Ledger
            </div>
          </div>
        </Link>

        {/* Primary Navigation */}
        <nav style={{ display: "flex", alignItems: "center", gap: "24px" }}>
          <NavLink
            to="/explorer"
            style={({ isActive }) => ({
              textDecoration: "none",
              fontSize: "var(--font-size-sm)",
              fontWeight: 500,
              color: isActive ? "var(--color-civic-blue)" : "var(--color-text-secondary)",
              borderBottom: isActive ? "2px solid var(--color-civic-blue)" : "2px solid transparent",
              padding: "20px 0",
            })}
          >
            Public Cases
          </NavLink>

          <NavLink
            to="/neighborhood"
            style={({ isActive }) => ({
              textDecoration: "none",
              fontSize: "var(--font-size-sm)",
              fontWeight: 500,
              color: isActive ? "var(--color-civic-blue)" : "var(--color-text-secondary)",
              borderBottom: isActive ? "2px solid var(--color-civic-blue)" : "2px solid transparent",
              padding: "20px 0",
            })}
          >
            Intelligence & Metrics
          </NavLink>

          {user && (user.role === "REVIEWER" || user.role === "ADMINISTRATOR") && (
            <NavLink
              to="/reviewer"
              style={({ isActive }) => ({
                textDecoration: "none",
                fontSize: "var(--font-size-sm)",
                fontWeight: 500,
                color: isActive ? "var(--color-civic-blue)" : "var(--color-text-secondary)",
                borderBottom: isActive ? "2px solid var(--color-civic-blue)" : "2px solid transparent",
                padding: "20px 0",
              })}
            >
              Reviewer Workspace
            </NavLink>
          )}

          {user && (user.role === "OPERATOR" || user.role === "ADMINISTRATOR") && (
            <NavLink
              to="/operator"
              style={({ isActive }) => ({
                textDecoration: "none",
                fontSize: "var(--font-size-sm)",
                fontWeight: 500,
                color: isActive ? "var(--color-civic-blue)" : "var(--color-text-secondary)",
                borderBottom: isActive ? "2px solid var(--color-civic-blue)" : "2px solid transparent",
                padding: "20px 0",
              })}
            >
              Operator Workspace
            </NavLink>
          )}
        </nav>

        {/* User Actions */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <Link to="/report" className="btn btn-primary btn-sm">
            Report Issue
          </Link>

          {user ? (
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span className="mono-id" title={`Signed in as ${user.email}`}>
                {user.role}:{user.display_name.split(" ")[0]}
              </span>
              <button onClick={handleLogout} className="btn btn-outline btn-sm" title="Sign out">
                <LogOut size={14} />
              </button>
            </div>
          ) : (
            <Link to="/login" className="btn btn-outline btn-sm">
              <LogIn size={14} /> Sign In
            </Link>
          )}
        </div>
      </div>
    </header>
  );
};
