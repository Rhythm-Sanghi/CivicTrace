import React, { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { api, getCurrentUser, clearAuthToken, type User } from "../lib/api";

function CivicBeacon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 32 32" width="22" height="22">
      <path
        d="M6 9l10-5 10 5v9c0 6-10 11-10 11S6 23 6 18V9z"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path d="M16 8v14M11 15h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(getCurrentUser());

  React.useEffect(() => {
    // Validate session against backend /auth/me to maintain reactive synchronization
    api.getMe()
      .then((serverUser) => {
        setUser(serverUser);
      })
      .catch(() => {
        // If cookie is expired or unauthorized, reset state
        setUser(null);
      });
  }, []);

  const handleLogout = async () => {
    await clearAuthToken();
    setUser(null);
    navigate("/");
  };

  const navItems = [
    { name: "Overview", path: "/" },
    { name: "Cases", path: "/explorer" },
    { name: "Intelligence", path: "/neighborhood" },
    { name: "Report issue", path: "/report" },
  ];

  if (user && (user.role === "REVIEWER" || user.role === "ADMINISTRATOR")) {
    navItems.push({
      name: "Reviewer desk",
      path: "/reviewer",
    });
  }
  if (user && (user.role === "OPERATOR" || user.role === "ADMINISTRATOR")) {
    navItems.push({
      name: "Work orders",
      path: "/operator",
    });
  }

  return (
    <div className="application">
      <a className="skip-link" href="#main-workspace">
        Skip to workspace
      </a>

      {/* CivicTrace Sidebar */}
      <aside className="app-sidebar">
        <Link to="/" className="brand">
          <CivicBeacon />
          <strong>CivicTrace</strong>
        </Link>

        <nav aria-label="Main navigation">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              <span>{item.name}</span>
            </NavLink>
          ))}
        </nav>

        {/* Workspace Session Status */}
        <div className="local-note">
          <span className="local-marker" aria-hidden="true" />
          {user ? user.display_name : "Local workspace"}
          <p>
            {user ? `${user.role} session active` : "Indore Ward 34 service area"}
            <br />
            {user ? (
              <button
                onClick={handleLogout}
                className="button-quiet"
                style={{ padding: 0, fontSize: "11px", color: "var(--accent)", cursor: "pointer" }}
              >
                Sign out
              </button>
            ) : (
              <Link to="/login" style={{ fontSize: "11px", color: "var(--accent)" }}>
                Sign in to portal
              </Link>
            )}
          </p>
        </div>
      </aside>

      {/* Main Viewport */}
      <main className="main-viewport" id="main-workspace" tabIndex={-1}>
        {children}
      </main>

      {/* CivicTrace Application Status Bar */}
      <footer className="app-status-bar">
        <span className="status-context">CivicTrace</span>
        <span role="status">
          Public Infrastructure Accountability Ledger
        </span>
        <span className="status-version">
          v1.0.0
        </span>
      </footer>
    </div>
  );
};
