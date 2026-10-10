import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Case, type NeighborhoodStats } from "../../lib/api";
import { ArrowRight, ShieldCheck, Layers, FileSearch } from "lucide-react";

export const HomeView: React.FC = () => {
  const [stats, setStats] = useState<NeighborhoodStats | null>(null);
  const [criticalCases, setCriticalCases] = useState<Case[]>([]);

  useEffect(() => {
    Promise.all([
      api.getNeighborhoodStats().catch(() => null),
      api.getCases({ priority_band: "CRITICAL" }).catch(() => []),
    ]).then(([s, c]) => {
      setStats(s);
      setCriticalCases(c.slice(0, 4));
    });
  }, []);

  return (
    <div style={{ padding: "var(--space-8) 0" }}>
      <div className="container">
        {/* Core Guiding Principle Banner */}
        <div style={{
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderLeft: "4px solid var(--color-civic-blue)",
          padding: "var(--space-6)",
          marginBottom: "var(--space-8)",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
            <div style={{ maxWidth: "780px" }}>
              <div style={{
                fontFamily: "var(--font-family-mono)",
                fontSize: "var(--font-size-xs)",
                color: "var(--color-civic-blue)",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                fontWeight: 600,
                marginBottom: "6px",
              }}>
                Evidence-Oriented Civic Accountability
              </div>
              <h1 style={{ fontSize: "var(--font-size-2xl)", fontWeight: 700, letterSpacing: "-0.02em", color: "var(--color-text-primary)", marginBottom: "8px" }}>
                A complaint should not disappear simply because someone changes its status to resolved.
              </h1>
              <p style={{ color: "var(--color-text-secondary)", fontSize: "var(--font-size-base)", lineHeight: 1.6 }}>
                CivicTrace is not an opaque ticketing box. It maintains an append-only cryptographic ledger of civic infrastructure defects, correlates duplicate reports, and requires independent citizen verification before cases are marked resolved.
              </p>
            </div>
            <div style={{ display: "flex", gap: "12px", alignSelf: "center" }}>
              <Link to="/report" className="btn btn-primary">
                Report Infrastructure Defect
              </Link>
              <Link to="/explorer" className="btn btn-outline">
                Explore Cases <ArrowRight size={14} />
              </Link>
            </div>
          </div>
        </div>

        {/* Live Metrics Gridline Bar */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "16px",
          marginBottom: "var(--space-8)",
        }}>
          <div className="card">
            <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", textTransform: "uppercase", fontWeight: 600 }}>
              Live Open Issues
            </div>
            <div style={{ fontSize: "28px", fontWeight: 700, color: "var(--color-text-primary)", marginTop: "4px" }}>
              {stats ? stats.open_cases : "..."}
            </div>
            <div style={{ fontSize: "11px", color: "var(--color-text-muted)", marginTop: "4px" }}>
              Active investigation or repair
            </div>
          </div>

          <div className="card">
            <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", textTransform: "uppercase", fontWeight: 600 }}>
              Independently Verified
            </div>
            <div style={{ fontSize: "28px", fontWeight: 700, color: "var(--color-verified-green)", marginTop: "4px" }}>
              {stats ? stats.verified_resolutions : "..."}
            </div>
            <div style={{ fontSize: "11px", color: "var(--color-text-muted)", marginTop: "4px" }}>
              Confirmed by independent citizens
            </div>
          </div>

          <div className="card">
            <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", textTransform: "uppercase", fontWeight: 600 }}>
              Disputed Claims
            </div>
            <div style={{ fontSize: "28px", fontWeight: 700, color: "var(--color-disputed-red)", marginTop: "4px" }}>
              {stats ? stats.disputed_resolutions : "..."}
            </div>
            <div style={{ fontSize: "11px", color: "var(--color-text-muted)", marginTop: "4px" }}>
              Work claimed but rejected by public
            </div>
          </div>

          <div className="card">
            <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", textTransform: "uppercase", fontWeight: 600 }}>
              Median Resolution
            </div>
            <div style={{ fontSize: "28px", fontWeight: 700, color: "var(--color-civic-blue)", marginTop: "4px" }}>
              {stats ? `${stats.median_resolution_days}d` : "..."}
            </div>
            <div style={{ fontSize: "11px", color: "var(--color-text-muted)", marginTop: "4px" }}>
              From submission to verified fix
            </div>
          </div>
        </div>

        {/* Studio Utility Columns: High Priority Issues & How CivicTrace Works */}
        <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: "24px" }}>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <h2 style={{ fontSize: "var(--font-size-lg)", fontWeight: 700 }}>
                High Priority Infrastructure Concerns
              </h2>
              <Link to="/explorer" style={{ fontSize: "var(--font-size-sm)", color: "var(--color-civic-blue)", textDecoration: "none" }}>
                View all cases &rarr;
              </Link>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {criticalCases.map((c) => (
                <div key={c.id} className="card" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span className="mono-id">{c.public_id}</span>
                      <span className={`archival-stamp stamp-${c.state.toLowerCase()}`}>
                        {c.state.replace("_", " ")}
                      </span>
                    </div>
                    <span style={{
                      backgroundColor: "var(--color-disputed-red-subtle)",
                      color: "var(--color-disputed-red)",
                      fontSize: "11px",
                      fontWeight: 700,
                      padding: "2px 6px",
                      borderRadius: "2px",
                      fontFamily: "var(--font-family-mono)",
                    }}>
                      PRIORITY: {c.priority_score.toFixed(1)} / 10
                    </span>
                  </div>

                  <Link to={`/cases/${c.public_id}`} style={{ textDecoration: "none", color: "inherit" }}>
                    <h3 style={{ fontSize: "15px", fontWeight: 600, color: "var(--color-text-primary)", lineHeight: 1.4 }}>
                      {c.title}
                    </h3>
                  </Link>

                  <div style={{ fontSize: "12px", color: "var(--color-text-secondary)" }}>
                    📍 {c.address_reference || "Indore Central Ward"} &bull; {c.report_count} corroborated report(s)
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h2 style={{ fontSize: "var(--font-size-lg)", fontWeight: 700, marginBottom: "12px" }}>
              CivicTrace Workflow Standard
            </h2>
            <div className="card" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                <Layers size={20} color="var(--color-civic-blue)" style={{ marginTop: "2px", flexShrink: 0 }} />
                <div>
                  <div style={{ fontWeight: 600, fontSize: "14px" }}>Deterministic Duplicate Engine</div>
                  <div style={{ fontSize: "12px", color: "var(--color-text-secondary)", marginTop: "2px" }}>
                    Correlates separate citizen reports via Haversine spatial proximity, token similarity, and temporal clustering into unified public cases.
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                <FileSearch size={20} color="var(--color-civic-blue)" style={{ marginTop: "2px", flexShrink: 0 }} />
                <div>
                  <div style={{ fontWeight: 600, fontSize: "14px" }}>Cryptographic Hash Chain</div>
                  <div style={{ fontSize: "12px", color: "var(--color-text-secondary)", marginTop: "2px" }}>
                    Every transition, assignment, and observation is signed into an append-only SHA-256 ledger. Tampering is mathematically detectable.
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                <ShieldCheck size={20} color="var(--color-verified-green)" style={{ marginTop: "2px", flexShrink: 0 }} />
                <div>
                  <div style={{ fontWeight: 600, fontSize: "14px" }}>Independent Verification Gate</div>
                  <div style={{ fontSize: "12px", color: "var(--color-text-secondary)", marginTop: "2px" }}>
                    Department repair claims remain pending until local citizens independently inspect and verify that the problem is truly fixed.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
