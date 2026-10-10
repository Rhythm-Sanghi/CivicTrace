import React, { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { getCurrentUser, clearAuthToken, type User } from "../lib/api";
import { LogOut, LogIn, Menu, X, Shield, PlusCircle } from "lucide-react";

export const Header: React.FC = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(getCurrentUser());
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

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
      <div className="workspace-container" style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        height: "56px",
      }}>
        {/* Brand / Wordmark */}
        <div style={{ display: "flex", alignItems: "center", gap: "24px" }}>
          <Link to="/" style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            textDecoration: "none",
            color: "var(--color-text-primary)",
          }}>
            <div style={{
              width: "28px",
              height: "28px",
              backgroundColor: "var(--color-civic-blue)",
              color: "#FFF",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 700,
              borderRadius: "var(--radius-sm)",
              fontFamily: "var(--font-family-mono)",
              fontSize: "13px",
            }}>
              CT
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: "15px", letterSpacing: "-0.02em", lineHeight: 1.1 }}>
                CivicTrace
              </div>
              <div style={{ fontSize: "11px", color: "var(--color-text-secondary)", letterSpacing: "0.02em" }}>
                Public Evidence Ledger
              </div>
            </div>
          </Link>

          {/* Navigation Links - Desktop */}
          <nav style={{ display: "flex", alignItems: "center", gap: "4px" }} className="desktop-nav">
            <NavLink
              to="/"
              end
              style={({ isActive }) => ({
                textDecoration: "none",
                fontSize: "var(--font-size-sm)",
                fontWeight: 500,
                color: isActive ? "var(--color-civic-blue)" : "var(--color-text-secondary)",
                padding: "6px 12px",
                borderRadius: "var(--radius-sm)",
                backgroundColor: isActive ? "var(--color-civic-blue-subtle)" : "transparent",
              })}
            >
              Overview
            </NavLink>

            <NavLink
              to="/explorer"
              style={({ isActive }) => ({
                textDecoration: "none",
                fontSize: "var(--font-size-sm)",
                fontWeight: 500,
                color: isActive ? "var(--color-civic-blue)" : "var(--color-text-secondary)",
                padding: "6px 12px",
                borderRadius: "var(--radius-sm)",
                backgroundColor: isActive ? "var(--color-civic-blue-subtle)" : "transparent",
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
                padding: "6px 12px",
                borderRadius: "var(--radius-sm)",
                backgroundColor: isActive ? "var(--color-civic-blue-subtle)" : "transparent",
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
                  padding: "6px 12px",
                  borderRadius: "var(--radius-sm)",
                  backgroundColor: isActive ? "var(--color-civic-blue-subtle)" : "transparent",
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
                  padding: "6px 12px",
                  borderRadius: "var(--radius-sm)",
                  backgroundColor: isActive ? "var(--color-civic-blue-subtle)" : "transparent",
                })}
              >
                Operator Workspace
              </NavLink>
            )}
          </nav>
        </div>

        {/* Right Section: Actions & Contextual Auth */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Link to="/report" className="btn btn-primary btn-sm">
            <PlusCircle size={14} /> Report Issue
          </Link>

          {user ? (
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span className="mono-id" title={`Signed in as ${user.email}`} style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                <Shield size={12} color="var(--color-civic-blue)" />
                {user.role}:{user.display_name.split(" ")[0]}
              </span>
              <button onClick={handleLogout} className="btn btn-outline btn-sm" title="Sign out">
                <LogOut size={13} />
              </button>
            </div>
          ) : (
            <Link to="/login" className="btn btn-outline btn-sm">
              <LogIn size={13} /> Sign In
            </Link>
          )}

          {/* Mobile hamburger button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="btn btn-outline btn-sm mobile-menu-toggle"
            style={{ display: "none" }}
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X size={16} /> : <Menu size={16} />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div style={{
          borderTop: "1px solid var(--color-border)",
          backgroundColor: "var(--color-surface)",
          padding: "12px 20px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
        }}>
          <Link to="/" onClick={() => setMobileMenuOpen(false)} style={{ padding: "8px 0", color: "inherit", textDecoration: "none", fontSize: "14px" }}>
            Overview
          </Link>
          <Link to="/explorer" onClick={() => setMobileMenuOpen(false)} style={{ padding: "8px 0", color: "inherit", textDecoration: "none", fontSize: "14px" }}>
            Public Cases
          </Link>
          <Link to="/neighborhood" onClick={() => setMobileMenuOpen(false)} style={{ padding: "8px 0", color: "inherit", textDecoration: "none", fontSize: "14px" }}>
            Intelligence & Metrics
          </Link>
          {user && (user.role === "REVIEWER" || user.role === "ADMINISTRATOR") && (
            <Link to="/reviewer" onClick={() => setMobileMenuOpen(false)} style={{ padding: "8px 0", color: "inherit", textDecoration: "none", fontSize: "14px" }}>
              Reviewer Workspace
            </Link>
          )}
          {user && (user.role === "OPERATOR" || user.role === "ADMINISTRATOR") && (
            <Link to="/operator" onClick={() => setMobileMenuOpen(false)} style={{ padding: "8px 0", color: "inherit", textDecoration: "none", fontSize: "14px" }}>
              Operator Workspace
            </Link>
          )}
        </div>
      )}
    </header>
  );
};
