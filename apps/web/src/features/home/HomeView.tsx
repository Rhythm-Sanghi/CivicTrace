import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Case, type NeighborhoodStats, type Category } from "../../lib/api";
import {
  ArrowRight,
  AlertTriangle,
  MapPin,
} from "lucide-react";

export const HomeView: React.FC = () => {
  const [stats, setStats] = useState<NeighborhoodStats | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [activeCase, setActiveCase] = useState<Case | null>(null);

  useEffect(() => {
    Promise.all([
      api.getNeighborhoodStats().catch(() => null),
      api.getCases().catch(() => []),
      api.getCategories().catch(() => []),
    ]).then(([s, cList, cats]) => {
      setStats(s);
      setCases(cList);
      setCategories(cats);
      if (cList.length > 0) setActiveCase(cList[0]);
    });
  }, []);

  const filteredCases = cases.filter((c) => {
    if (selectedCategory && c.category_id !== selectedCategory) return false;
    return true;
  });

  // Actionable Attention Cases (Disputed, Older Unresolved, High Priority)
  const attentionCases = cases
    .filter((c) => c.state === "DISPUTED" || c.state === "AWAITING_VERIFICATION" || c.priority_score >= 4.0)
    .slice(0, 5);

  return (
    <div style={{ padding: "var(--space-6) 0 var(--space-10)" }}>
      <div className="workspace-container">
        
        {/* EDITORIAL HEADER (Left-aligned, restrained height, workshop tone) */}
        <div style={{
          borderBottom: "1px solid var(--color-border)",
          paddingBottom: "var(--space-5)",
          marginBottom: "var(--space-6)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          flexWrap: "wrap",
          gap: "16px",
        }}>
          <div>
            <div style={{
              fontFamily: "var(--font-family-mono)",
              fontSize: "var(--font-size-2xs)",
              color: "var(--color-civic-blue)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              fontWeight: 600,
              marginBottom: "4px",
            }}>
              PUBLIC ACCOUNTABILITY / INDORE DEMONSTRATION
            </div>
            <h1 style={{
              fontSize: "clamp(26px, 2.5vw, 36px)",
              fontWeight: 700,
              letterSpacing: "-0.02em",
              lineHeight: 1.15,
              color: "var(--color-text-primary)",
              marginBottom: "6px",
            }}>
              The state of your neighborhood.
            </h1>
            <p style={{
              color: "var(--color-text-secondary)",
              fontSize: "var(--font-size-base)",
              maxWidth: "840px",
              lineHeight: 1.45,
            }}>
              Follow infrastructure reports, see what action was taken, and check whether repairs were independently verified.
            </p>
          </div>

          <div style={{ display: "flex", gap: "10px" }}>
            <Link to="/report" className="btn btn-primary">
              Report an issue
            </Link>
            <Link to="/explorer" className="btn btn-outline">
              Explore cases <ArrowRight size={14} />
            </Link>
          </div>
        </div>

        {/* SECTION A: COMPACT METRICS HORIZONTAL STRIP (Ruled surface with clear columns) */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          marginBottom: "var(--space-6)",
          overflow: "hidden",
        }}>
          <div style={{ padding: "16px 20px", borderRight: "1px solid var(--color-border-subtle)" }}>
            <div style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--color-text-secondary)" }}>
              Open Issues
            </div>
            <div style={{ fontSize: "30px", fontWeight: 700, color: "var(--color-text-primary)", lineHeight: 1.2, marginTop: "2px" }}>
              {stats ? stats.open_cases : "—"}
            </div>
            <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)", marginTop: "2px" }}>
              Active investigation or work
            </div>
          </div>

          <div style={{ padding: "16px 20px", borderRight: "1px solid var(--color-border-subtle)" }}>
            <div style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--color-verified-green)" }}>
              Verified Resolutions
            </div>
            <div style={{ fontSize: "30px", fontWeight: 700, color: "var(--color-verified-green)", lineHeight: 1.2, marginTop: "2px" }}>
              {stats ? stats.verified_resolutions : "—"}
            </div>
            <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)", marginTop: "2px" }}>
              Confirmed fixed by citizens
            </div>
          </div>

          <div style={{ padding: "16px 20px", borderRight: "1px solid var(--color-border-subtle)" }}>
            <div style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--color-disputed-red)" }}>
              Disputed Claims
            </div>
            <div style={{ fontSize: "30px", fontWeight: 700, color: "var(--color-disputed-red)", lineHeight: 1.2, marginTop: "2px" }}>
              {stats ? stats.disputed_resolutions : "—"}
            </div>
            <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)", marginTop: "2px" }}>
              Work claimed but rejected by public
            </div>
          </div>

          <div style={{ padding: "16px 20px" }}>
            <div style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--color-civic-blue)" }}>
              Median Resolution Duration
            </div>
            <div style={{ fontSize: "30px", fontWeight: 700, color: "var(--color-civic-blue)", lineHeight: 1.2, marginTop: "2px" }}>
              {stats ? `${stats.median_resolution_days}d` : "—"}
            </div>
            <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)", marginTop: "2px" }}>
              From initial report to confirmed fix
            </div>
          </div>
        </div>

        {/* SECTION B: PRIMARY WORKSPACE (Two Columns: 68% Geographic Explorer, 32% Attention Ledger) */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.8fr) minmax(360px, 1fr)",
          gap: "24px",
          marginBottom: "var(--space-8)",
        }}>
          {/* Left Workspace: Interactive Geographic Case Explorer */}
          <div style={{
            backgroundColor: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            display: "flex",
            flexDirection: "column",
          }}>
            <div className="grid-header">
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <MapPin size={15} color="var(--color-civic-blue)" />
                <span>Geographic Case Explorer &bull; Ward 34 / Central</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  style={{
                    fontSize: "12px",
                    padding: "3px 8px",
                    border: "1px solid var(--color-border)",
                    borderRadius: "var(--radius-sm)",
                    backgroundColor: "var(--color-surface)",
                  }}
                >
                  <option value="">All Categories ({cases.length})</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                <Link to="/explorer" style={{ textDecoration: "none", color: "var(--color-civic-blue)", fontSize: "12px", fontWeight: 600 }}>
                  Expand Grid &rarr;
                </Link>
              </div>
            </div>

            {/* Split Explorer Workspace: Geographic Canvas + Case Selector */}
            <div style={{
              display: "grid",
              gridTemplateColumns: "1.1fr 1fr",
              minHeight: "440px",
            }}>
              {/* Geographic Schematic Map */}
              <div style={{
                position: "relative",
                backgroundColor: "#EBECE8",
                borderRight: "1px solid var(--color-border)",
                overflow: "hidden",
                display: "flex",
                flexDirection: "column",
              }}>
                {/* SVG Schematic Canvas with Coordinate Grid & Actual Points */}
                <svg
                  style={{ width: "100%", height: "100%", flex: 1, backgroundColor: "#EBECE8" }}
                  viewBox="0 0 500 400"
                >
                  <defs>
                    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#DDE0DC" strokeWidth="1" />
                    </pattern>
                  </defs>
                  <rect width="100%" height="100%" fill="url(#grid)" />

                  {/* Ward Boundary Outline */}
                  <polygon
                    points="30,40 460,30 480,360 40,380"
                    fill="rgba(40, 94, 121, 0.03)"
                    stroke="#C3CBC1"
                    strokeWidth="1.5"
                    strokeDasharray="4 2"
                  />

                  {/* Arterial Roads */}
                  <line x1="40" y1="200" x2="480" y2="190" stroke="#CAD1C9" strokeWidth="8" />
                  <text x="50" y="185" fill="#8F9992" fontSize="10" fontFamily="IBM Plex Mono">MG ROAD CORRIDOR</text>

                  <line x1="240" y1="30" x2="260" y2="380" stroke="#CAD1C9" strokeWidth="6" />
                  <text x="268" y="55" fill="#8F9992" fontSize="10" fontFamily="IBM Plex Mono">AB ROAD</text>

                  {/* Plot actual cases dynamically */}
                  {filteredCases.map((c) => {
                    // Normalize lat/lon to 500x400 SVG box around Indore center (22.71 to 22.73, 75.84 to 75.88)
                    const minLat = 22.710, maxLat = 22.735;
                    const minLon = 75.845, maxLon = 75.885;
                    const x = Math.max(30, Math.min(460, ((c.longitude - minLon) / (maxLon - minLon)) * 430 + 35));
                    const y = Math.max(40, Math.min(360, (1 - (c.latitude - minLat) / (maxLat - minLat)) * 320 + 40));
                    const isSelected = activeCase?.id === c.id;

                    const markerColor =
                      c.state === "DISPUTED"
                        ? "var(--color-disputed-red)"
                        : c.state === "RESOLVED"
                        ? "var(--color-verified-green)"
                        : c.state === "AWAITING_VERIFICATION"
                        ? "var(--color-attention-orange)"
                        : "var(--color-civic-blue)";

                    return (
                      <g
                        key={c.id}
                        onClick={() => setActiveCase(c)}
                        style={{ cursor: "pointer" }}
                      >
                        {isSelected && (
                          <circle cx={x} cy={y} r="14" fill="none" stroke={markerColor} strokeWidth="2" opacity="0.5" />
                        )}
                        <circle cx={x} cy={y} r={isSelected ? "8" : "6"} fill={markerColor} />
                        <text
                          x={x + 10}
                          y={y + 4}
                          fill="#202722"
                          fontSize="10"
                          fontWeight="600"
                          fontFamily="IBM Plex Mono"
                        >
                          {c.public_id.split("-").slice(1).join("-")}
                        </text>
                      </g>
                    );
                  })}
                </svg>

                {/* Map Control Bar & Coordinate Bar */}
                <div style={{
                  padding: "8px 14px",
                  borderTop: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-surface)",
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: "11px",
                  fontFamily: "var(--font-family-mono)",
                  color: "var(--color-text-secondary)",
                }}>
                  <div>INDORE WARD 34 (22.7196° N, 75.8577° E)</div>
                  <div>OFFLINE GEOMETRIC GRID</div>
                </div>
              </div>

              {/* Case Dossier Inspector (Active Pin Details) */}
              <div style={{ padding: "18px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                {activeCase ? (
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <span className="mono-id">{activeCase.public_id}</span>
                      <span className={`archival-stamp stamp-${activeCase.state.toLowerCase()}`}>
                        {activeCase.state.replace("_", " ")}
                      </span>
                    </div>

                    <h3 style={{ fontSize: "16px", fontWeight: 700, lineHeight: 1.3, marginBottom: "8px", color: "var(--color-text-primary)" }}>
                      {activeCase.title}
                    </h3>

                    <p style={{ fontSize: "13px", color: "var(--color-text-secondary)", lineHeight: 1.45, marginBottom: "14px" }}>
                      {activeCase.description}
                    </p>

                    <div style={{ display: "flex", flexDirection: "column", gap: "6px", fontSize: "12px", borderTop: "1px solid var(--color-border-subtle)", paddingTop: "10px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "var(--color-text-muted)" }}>Location:</span>
                        <span style={{ fontWeight: 500 }}>{activeCase.address_reference || "Indore Central"}</span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "var(--color-text-muted)" }}>Coordinates:</span>
                        <span style={{ fontFamily: "var(--font-family-mono)" }}>{activeCase.latitude.toFixed(4)}, {activeCase.longitude.toFixed(4)}</span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "var(--color-text-muted)" }}>Priority Score:</span>
                        <span style={{ fontWeight: 700, color: "var(--color-civic-blue)", fontFamily: "var(--font-family-mono)" }}>
                          {activeCase.priority_score.toFixed(1)} / 10 ({activeCase.priority_band})
                        </span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "var(--color-text-muted)" }}>Corroborated Reports:</span>
                        <span style={{ fontWeight: 600 }}>{activeCase.report_count} citizen report(s)</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div style={{ color: "var(--color-text-muted)", fontSize: "13px" }}>Select a pin on the map to inspect details.</div>
                )}

                {activeCase && (
                  <div style={{ marginTop: "16px", borderTop: "1px solid var(--color-border)", paddingTop: "12px" }}>
                    <Link to={`/cases/${activeCase.public_id}`} className="btn btn-primary btn-sm" style={{ width: "100%" }}>
                      Open Complete Dossier & Audit Log &rarr;
                    </Link>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Workspace: Needs Attention Dossier Queue */}
          <div style={{
            backgroundColor: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            display: "flex",
            flexDirection: "column",
          }}>
            <div className="grid-header">
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <AlertTriangle size={15} color="var(--color-attention-orange)" />
                <span>Needs Attention &bull; Pending Verification</span>
              </div>
              <span className="mono-id">{attentionCases.length} Cases</span>
            </div>

            <div style={{ display: "flex", flexDirection: "column" }}>
              {attentionCases.map((c) => {
                const borderLeft =
                  c.state === "DISPUTED"
                    ? "var(--color-disputed-red)"
                    : c.state === "AWAITING_VERIFICATION"
                    ? "var(--color-attention-orange)"
                    : "var(--color-civic-blue)";

                return (
                  <Link
                    key={c.id}
                    to={`/cases/${c.public_id}`}
                    style={{
                      display: "block",
                      padding: "14px 18px",
                      textDecoration: "none",
                      color: "inherit",
                      borderLeft: `4px solid ${borderLeft}`,
                      borderBottom: "1px solid var(--color-border-subtle)",
                      transition: "background-color 150ms",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "var(--color-surface-elevated)")}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                      <span className="mono-id">{c.public_id}</span>
                      <span className={`archival-stamp stamp-${c.state.toLowerCase()}`}>
                        {c.state.replace("_", " ")}
                      </span>
                    </div>

                    <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--color-text-primary)", lineHeight: 1.3, marginBottom: "4px" }}>
                      {c.title}
                    </div>

                    <div style={{ fontSize: "12px", color: "var(--color-text-secondary)", display: "flex", justifyContent: "space-between" }}>
                      <span>📍 {c.address_reference || "Indore Ward 34"}</span>
                      <span style={{ fontFamily: "var(--font-family-mono)", fontWeight: 600, color: "var(--color-civic-blue)" }}>
                        P: {c.priority_score.toFixed(1)}
                      </span>
                    </div>
                  </Link>
                );
              })}
            </div>

            <div style={{ padding: "12px 18px", backgroundColor: "var(--color-surface-elevated)", borderTop: "1px solid var(--color-border)", textAlign: "center", marginTop: "auto" }}>
              <Link to="/explorer" style={{ fontSize: "12px", color: "var(--color-civic-blue)", textDecoration: "none", fontWeight: 600 }}>
                View complete prioritized backlog &rarr;
              </Link>
            </div>
          </div>
        </div>

        {/* SECTION C: RECENT ACTIVITY LEDGER (Ruled table with actual API records) */}
        <div style={{
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          marginBottom: "var(--space-8)",
          overflow: "hidden",
        }}>
          <div className="grid-header">
            <span>Recent Public Ledger Activity</span>
            <Link to="/explorer" style={{ textDecoration: "none", color: "var(--color-civic-blue)", fontSize: "12px", fontWeight: 600 }}>
              View all records &rarr;
            </Link>
          </div>

          <table className="ruled-table">
            <thead>
              <tr>
                <th style={{ width: "120px" }}>Reference</th>
                <th>Infrastructure Issue</th>
                <th>Neighborhood</th>
                <th style={{ width: "160px" }}>Status</th>
                <th style={{ width: "100px" }}>Corroborated</th>
                <th style={{ width: "110px" }}>Date</th>
                <th style={{ width: "80px", textAlign: "right" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {cases.slice(0, 6).map((c) => (
                <tr key={c.id}>
                  <td>
                    <span className="mono-id">{c.public_id}</span>
                  </td>
                  <td>
                    <Link to={`/cases/${c.public_id}`} style={{ textDecoration: "none", color: "var(--color-text-primary)", fontWeight: 600 }}>
                      {c.title}
                    </Link>
                  </td>
                  <td style={{ color: "var(--color-text-secondary)", fontSize: "13px" }}>
                    {c.address_reference || "Indore Central Ward"}
                  </td>
                  <td>
                    <span className={`archival-stamp stamp-${c.state.toLowerCase()}`}>
                      {c.state.replace("_", " ")}
                    </span>
                  </td>
                  <td style={{ fontFamily: "var(--font-family-mono)", fontSize: "12px" }}>
                    {c.report_count} reports
                  </td>
                  <td style={{ fontSize: "12px", color: "var(--color-text-secondary)" }}>
                    {new Date(c.created_at).toLocaleDateString()}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <Link to={`/cases/${c.public_id}`} className="btn btn-outline btn-sm" style={{ padding: "2px 8px", fontSize: "11px" }}>
                      Inspect
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* SECTION D: ACCOUNTABILITY EXPLANATION (Disciplined editorial banner) */}
        <div style={{
          border: "1px solid var(--color-border)",
          backgroundColor: "var(--color-surface-elevated)",
          borderRadius: "var(--radius-sm)",
          padding: "20px 24px",
          display: "grid",
          gridTemplateColumns: "1fr 2fr",
          gap: "24px",
          alignItems: "center",
        }}>
          <div>
            <div style={{ fontFamily: "var(--font-family-mono)", fontSize: "11px", color: "var(--color-civic-blue)", textTransform: "uppercase", fontWeight: 600 }}>
              The Verification Principle
            </div>
            <h2 style={{ fontSize: "18px", fontWeight: 700, marginTop: "4px" }}>
              Reported. Actioned. Independently verified.
            </h2>
          </div>
          <div style={{ fontSize: "13px", color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
            A complaint should not disappear simply because someone changes its status to resolved. CivicTrace enforces role separation: public works operators log work orders and claim completion, but only corroborated field inspections by local citizens or reviewers can verify resolution.
          </div>
        </div>

      </div>
    </div>
  );
};
