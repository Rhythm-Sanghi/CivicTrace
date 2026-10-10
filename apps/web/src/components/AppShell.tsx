import React, { useState } from "react";
import { Link, NavLink, useNavigate, useLocation } from "react-router-dom";
import { getCurrentUser, clearAuthToken, type User } from "../lib/api";
import {
  TrendingUp,
  PlusCircle,
  Shield,
  Layers,
  Wrench,
  LogOut,
  LogIn,
  Database,
  ChevronRight,
  Activity
} from "lucide-react";

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState<User | null>(getCurrentUser());

  const handleLogout = () => {
    clearAuthToken();
    setUser(null);
    navigate("/");
  };

  // Determine current section for utility header breadcrumb
  const getSectionTitle = () => {
    const path = location.pathname;
    if (path === "/") return "Overview & Community Investigation";
    if (path.startsWith("/explorer")) return "Public Cases Explorer";
    if (path.startsWith("/cases")) return "Forensic Case Dossier";
    if (path.startsWith("/neighborhood")) return "Neighborhood Telemetry & Scorecards";
    if (path.startsWith("/report")) return "Civic Intake Portal";
    if (path.startsWith("/reviewer")) return "Community Reviewer Desk";
    if (path.startsWith("/operator")) return "Public Works Dispatch Terminal";
    if (path.startsWith("/login")) return "Access & Authentication Gate";
    return "Public Investigation Workspace";
  };

  return (
    <div className="field-shell">
      {/* 1. DARK-INK INDUSTRIAL NAVIGATION RAIL */}
      <aside className="nav-rail">
        {/* Brand Header */}
        <div className="nav-rail-header">
          <Link to="/" className="nav-rail-brand">
            <div className="nav-rail-logo">CT</div>
            <div>
              <div className="nav-rail-title">CivicTrace</div>
              <div className="nav-rail-subtitle">Field Ledger Standard</div>
            </div>
          </Link>
        </div>

        {/* Primary Navigation Routes */}
        <div className="nav-rail-group">
          <div className="nav-rail-label">Public Investigation</div>
          
          <NavLink to="/" end className={({ isActive }) => `nav-rail-link ${isActive ? "active" : ""}`}>
            <Activity size={15} />
            <span>Overview</span>
          </NavLink>

          <NavLink to="/explorer" className={({ isActive }) => `nav-rail-link ${isActive ? "active" : ""}`}>
            <Database size={15} />
            <span>Case Explorer</span>
            <span className="nav-rail-badge">Indore</span>
          </NavLink>

          <NavLink to="/neighborhood" className={({ isActive }) => `nav-rail-link ${isActive ? "active" : ""}`}>
            <TrendingUp size={15} />
            <span>Intelligence</span>
          </NavLink>
        </div>

        {/* Citizen Intake Action */}
        <div className="nav-rail-group" style={{ paddingTop: "6px" }}>
          <div className="nav-rail-label">Citizen Intake</div>
          <NavLink to="/report" className={({ isActive }) => `nav-rail-link ${isActive ? "active" : ""}`} style={{ color: "var(--color-ink-rail-text)" }}>
            <PlusCircle size={15} color="#9BC0D6" />
            <span>Report Issue</span>
          </NavLink>
        </div>

        {/* Role-Specific Workspaces (Contextual) */}
        {user && (user.role === "REVIEWER" || user.role === "OPERATOR" || user.role === "ADMINISTRATOR") && (
          <div className="nav-rail-group" style={{ paddingTop: "6px" }}>
            <div className="nav-rail-label">Operational Desks</div>

            {(user.role === "REVIEWER" || user.role === "ADMINISTRATOR") && (
              <NavLink to="/reviewer" className={({ isActive }) => `nav-rail-link ${isActive ? "active" : ""}`}>
                <Layers size={15} />
                <span>Reviewer Desk</span>
              </NavLink>
            )}

            {(user.role === "OPERATOR" || user.role === "ADMINISTRATOR") && (
              <NavLink to="/operator" className={({ isActive }) => `nav-rail-link ${isActive ? "active" : ""}`}>
                <Wrench size={15} />
                <span>Operator Terminal</span>
              </NavLink>
            )}
          </div>
        )}

        {/* Account & Session Control Footer */}
        <div className="nav-rail-footer">
          {user ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", overflow: "hidden" }}>
                <Shield size={14} color="var(--color-civic-blue)" style={{ flexShrink: 0 }} />
                <div style={{ overflow: "hidden" }}>
                  <div style={{ fontSize: "12px", fontWeight: 600, color: "#FFF", whiteSpace: "nowrap", textOverflow: "ellipsis" }}>
                    {user.display_name}
                  </div>
                  <div style={{ fontSize: "10px", fontFamily: "var(--font-family-mono)", color: "var(--color-ink-rail-muted)" }}>
                    {user.role}
                  </div>
                </div>
              </div>

              <button
                onClick={handleLogout}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--color-ink-rail-muted)",
                  cursor: "pointer",
                  padding: "4px",
                }}
                title="Sign out"
              >
                <LogOut size={14} />
              </button>
            </div>
          ) : (
            <Link
              to="/login"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                color: "var(--color-ink-rail-text)",
                textDecoration: "none",
                fontSize: "12px",
                fontWeight: 500,
                width: "100%",
                justifyContent: "center",
                padding: "4px 0",
              }}
            >
              <LogIn size={14} /> Sign In to Portal
            </Link>
          )}
        </div>
      </aside>

      {/* 2. MAIN WORKING CANVAS */}
      <div className="field-canvas">
        {/* Slim Utility Header */}
        <header className="utility-header">
          <div className="utility-breadcrumb">
            <span style={{ color: "var(--color-text-muted)" }}>CIVICTRACE</span>
            <ChevronRight size={12} color="var(--color-text-muted)" />
            <span style={{ fontWeight: 600, color: "var(--color-text-primary)" }}>{getSectionTitle()}</span>
          </div>

          <div className="utility-telemetry">
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span className="pulse-indicator" />
              <span>SHA-256 LEDGER LIVE</span>
            </div>
            <span style={{ color: "var(--color-border-strong)" }}>|</span>
            <span>WARD 34 &bull; INDORE</span>
          </div>
        </header>

        {/* Fluid Content Canvas */}
        <main className="field-content">
          {children}
        </main>
      </div>
    </div>
  );
};
