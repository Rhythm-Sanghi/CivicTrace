import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Case, type NeighborhoodStats, type Category } from "../../lib/api";
import { PageHeading, MetricStrip, StatusStamp, SectionHeader } from "../../components/FieldPrimitives";
import {
  ArrowRight,
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

  return (
    <div>
      {/* 1. EDITORIAL PAGE HEADING */}
      <PageHeading
        eyebrow="COMMUNITY AUDIT &bull; INDORE MUNICIPAL DEMONSTRATION"
        title="The state of your neighborhood."
        description="Follow infrastructure reports, see what action was taken, and check whether repairs were independently verified."
      >
        <Link to="/report" className="btn btn-primary">
          Report Issue
        </Link>
        <Link to="/explorer" className="btn btn-outline">
          Explore Cases <ArrowRight size={13} />
        </Link>
      </PageHeading>

      {/* 2. COMPACT FIELD METRIC STRIP */}
      <MetricStrip
        metrics={[
          {
            label: "Open Issues",
            value: stats ? stats.open_cases : "—",
            description: "Active investigation or field repair",
          },
          {
            label: "Verified Resolutions",
            value: stats ? stats.verified_resolutions : "—",
            description: "Confirmed fixed by local citizens",
            accentColor: "var(--color-verified-green)",
          },
          {
            label: "Disputed Claims",
            value: stats ? stats.disputed_resolutions : "—",
            description: "Premature closures rejected by public",
            accentColor: "var(--color-disputed-red)",
          },
          {
            label: "Median Resolution Duration",
            value: stats ? `${stats.median_resolution_days}d` : "—",
            description: "From submission to verified fix",
            accentColor: "var(--color-civic-blue)",
          },
        ]}
      />

      {/* 3. MAIN FIELD INVESTIGATION WORKSPACE (Two Columns: 68% Map & 32% Inspector) */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 1.8fr) minmax(360px, 1fr)",
        gap: "20px",
        marginBottom: "24px",
      }}>
        {/* Left Column: Geographic Investigation Surface */}
        <div style={{
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}>
          {/* Dark-Ink Section Header with Category Filter */}
          <SectionHeader title="Geographic Investigation Surface &bull; Ward 34 Grid">
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                style={{
                  fontSize: "11px",
                  padding: "2px 6px",
                  backgroundColor: "var(--color-ink-rail-hover)",
                  color: "#FFF",
                  border: "1px solid var(--color-ink-rail-border)",
                  borderRadius: "var(--radius-sm)",
                  fontFamily: "var(--font-family-mono)",
                }}
              >
                <option value="">All Categories ({cases.length})</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
          </SectionHeader>

          {/* Interactive Geographic Canvas */}
          <div style={{ position: "relative", height: "420px", backgroundColor: "#EBECE7" }}>
            <svg style={{ width: "100%", height: "100%" }} viewBox="0 0 600 420">
              <defs>
                <pattern id="ledgerGrid" width="30" height="30" patternUnits="userSpaceOnUse">
                  <path d="M 30 0 L 0 0 0 30" fill="none" stroke="#D8DDD6" strokeWidth="1" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#ledgerGrid)" />

              {/* Geographic Municipal Ward Perimeter */}
              <polygon
                points="40,30 560,20 580,390 30,400"
                fill="rgba(40, 94, 121, 0.04)"
                stroke="#B5BFB2"
                strokeWidth="1.5"
                strokeDasharray="6 3"
              />

              {/* Arterial Corridors */}
              <line x1="30" y1="210" x2="580" y2="200" stroke="#CAD2C8" strokeWidth="10" />
              <text x="45" y="195" fill="#7D897B" fontSize="10" fontFamily="IBM Plex Mono" fontWeight="600">
                MG ROAD ARTERIAL CORRIDOR
              </text>

              <line x1="310" y1="20" x2="330" y2="400" stroke="#CAD2C8" strokeWidth="8" />
              <text x="340" y="45" fill="#7D897B" fontSize="10" fontFamily="IBM Plex Mono" fontWeight="600">
                AB ROAD MAIN AXIS
              </text>

              {/* Plotted Live Case Markers */}
              {filteredCases.map((c) => {
                const minLat = 22.710, maxLat = 22.735;
                const minLon = 75.845, maxLon = 75.885;
                const x = Math.max(50, Math.min(550, ((c.longitude - minLon) / (maxLon - minLon)) * 500 + 40));
                const y = Math.max(40, Math.min(380, (1 - (c.latitude - minLat) / (maxLat - minLat)) * 340 + 35));
                const isSelected = activeCase?.id === c.id;

                const pinColor =
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
                      <circle cx={x} cy={y} r="15" fill="none" stroke={pinColor} strokeWidth="2.5" opacity="0.6" />
                    )}
                    <circle cx={x} cy={y} r={isSelected ? "9" : "6.5"} fill={pinColor} stroke="#FFF" strokeWidth="1.5" />
                    <rect
                      x={x + 12}
                      y={y - 8}
                      width="82"
                      height="16"
                      fill="var(--color-ink-rail)"
                      rx="2"
                    />
                    <text
                      x={x + 16}
                      y={y + 4}
                      fill="#FFF"
                      fontSize="9.5"
                      fontWeight="600"
                      fontFamily="IBM Plex Mono"
                    >
                      {c.public_id}
                    </text>
                  </g>
                );
              })}
            </svg>

            {/* Offline Schematic Disclaimer & Coordinate Bar */}
            <div style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              backgroundColor: "rgba(25, 30, 26, 0.9)",
              color: "#E5EAE4",
              padding: "6px 14px",
              display: "flex",
              justifyContent: "space-between",
              fontSize: "11px",
              fontFamily: "var(--font-family-mono)",
            }}>
              <span>OFFLINE SCHEMATIC GRID &bull; INDORE WARD 34</span>
              <span>WGS84: 22.7196° N, 75.8577° E</span>
            </div>
          </div>
        </div>

        {/* Right Column: High-Value Contextual Case Inspector */}
        <div style={{
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}>
          {/* Dark Header with Active Identifier */}
          <div style={{
            backgroundColor: "var(--color-ink-rail)",
            color: "#FFF",
            padding: "12px 18px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}>
            <div>
              <div style={{ fontSize: "10px", fontFamily: "var(--font-family-mono)", color: "var(--color-ink-rail-muted)" }}>
                ACTIVE INVESTIGATION DOSSIER
              </div>
              <div style={{ fontSize: "16px", fontWeight: 700, fontFamily: "var(--font-family-mono)", color: "#FFF", marginTop: "2px" }}>
                {activeCase ? activeCase.public_id : "NO SELECTION"}
              </div>
            </div>

            {activeCase && (
              <StatusStamp state={activeCase.state} size="sm" />
            )}
          </div>

          {/* Inspector Content Body */}
          {activeCase ? (
            <div style={{ padding: "18px", display: "flex", flexDirection: "column", gap: "14px", flex: 1 }}>
              <div>
                <h3 style={{ fontSize: "16px", fontWeight: 700, lineHeight: 1.3, color: "var(--color-text-primary)" }}>
                  {activeCase.title}
                </h3>
                <p style={{ fontSize: "13px", color: "var(--color-text-secondary)", marginTop: "6px", lineHeight: 1.5 }}>
                  {activeCase.description}
                </p>
              </div>

              {/* Forensic Details Grid */}
              <div style={{
                backgroundColor: "var(--color-surface-elevated)",
                border: "1px solid var(--color-border-subtle)",
                borderRadius: "var(--radius-sm)",
                padding: "12px 14px",
                display: "flex",
                flexDirection: "column",
                gap: "8px",
                fontSize: "12px",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--color-text-muted)" }}>Category:</span>
                  <span style={{ fontWeight: 600 }}>{activeCase.category?.name}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--color-text-muted)" }}>Location:</span>
                  <span style={{ fontWeight: 500 }}>{activeCase.address_reference}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--color-text-muted)" }}>Coordinates:</span>
                  <span style={{ fontFamily: "var(--font-family-mono)" }}>
                    {activeCase.latitude.toFixed(5)}, {activeCase.longitude.toFixed(5)}
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--color-text-muted)" }}>Civic Priority Score:</span>
                  <span style={{ fontWeight: 700, color: "var(--color-civic-blue)", fontFamily: "var(--font-family-mono)" }}>
                    {activeCase.priority_score.toFixed(1)} / 10 ({activeCase.priority_band})
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--color-text-muted)" }}>Corroborated Reports:</span>
                  <span style={{ fontWeight: 600 }}>{activeCase.report_count} citizen report(s)</span>
                </div>
              </div>

              {/* Direct Dossier Link Button */}
              <div style={{ marginTop: "auto" }}>
                <Link
                  to={`/cases/${activeCase.public_id}`}
                  className="btn btn-dark"
                  style={{ width: "100%", justifyContent: "center" }}
                >
                  Open Full Case Dossier & Chain &rarr;
                </Link>
              </div>
            </div>
          ) : (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--color-text-muted)", fontSize: "13px" }}>
              Select a marker on the map to inspect details.
            </div>
          )}
        </div>
      </div>

      {/* 4. REFINED INFORMATION-DENSE FIELD ACTIVITY LEDGER */}
      <div style={{
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-sm)",
        overflow: "hidden",
      }}>
        <SectionHeader title="Public Infrastructure Activity Ledger" actionText="View all cases" actionHref="/explorer" />

        <table className="ledger-table">
          <thead>
            <tr>
              <th style={{ width: "130px" }}>Reference</th>
              <th>Infrastructure Issue & Location</th>
              <th style={{ width: "170px" }}>Category</th>
              <th style={{ width: "140px" }}>Status</th>
              <th style={{ width: "90px", textAlign: "right" }}>Priority</th>
              <th style={{ width: "110px" }}>Date</th>
              <th style={{ width: "90px", textAlign: "right" }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {cases.slice(0, 7).map((c) => (
              <tr key={c.id}>
                <td>
                  <span className="mono-id">{c.public_id}</span>
                </td>
                <td>
                  <Link to={`/cases/${c.public_id}`} style={{ textDecoration: "none", color: "var(--color-text-primary)", fontWeight: 600 }}>
                    {c.title}
                  </Link>
                  <div style={{ fontSize: "12px", color: "var(--color-text-secondary)", marginTop: "2px" }}>
                    📍 {c.address_reference}
                  </div>
                </td>
                <td style={{ fontSize: "12px", color: "var(--color-text-secondary)" }}>
                  {c.category?.name}
                </td>
                <td>
                  <StatusStamp state={c.state} size="sm" />
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--font-family-mono)", fontSize: "12px", fontWeight: 700, color: "var(--color-civic-blue)" }}>
                  {c.priority_score.toFixed(1)}
                </td>
                <td style={{ fontSize: "12px", color: "var(--color-text-secondary)" }}>
                  {new Date(c.created_at).toLocaleDateString()}
                </td>
                <td style={{ textAlign: "right" }}>
                  <Link to={`/cases/${c.public_id}`} className="btn btn-outline btn-sm">
                    Inspect
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
