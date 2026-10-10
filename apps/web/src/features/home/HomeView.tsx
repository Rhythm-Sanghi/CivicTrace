import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Case, type NeighborhoodStats, type Category } from "../../lib/api";
import { PageHeading, MetricStrip, StatusStamp, SectionHeader } from "../../components/FieldPrimitives";

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
    <>
      {/* 1. BENCHLIGHT COMPACT PAGE HEADER */}
      <PageHeading
        index="01"
        title="Overview"
        description="The state of your neighborhood. Follow infrastructure reports, see what action was taken, and check whether repairs were independently verified."
      >
        <Link to="/report" className="button-primary">
          Report issue
        </Link>
        <Link to="/explorer" className="btn-outline">
          Browse cases
        </Link>
      </PageHeading>

      <div className="workspace">
        {/* 2. FLAT MEASUREMENT METRIC STRIP */}
        <MetricStrip
          metrics={[
            {
              label: "Open issues",
              value: stats ? stats.open_cases : "—",
            },
            {
              label: "Verified resolutions",
              value: stats ? stats.verified_resolutions : "—",
              accentColor: "var(--success)",
            },
            {
              label: "Disputed claims",
              value: stats ? stats.disputed_resolutions : "—",
              accentColor: "var(--danger)",
            },
            {
              label: "Median duration",
              value: stats ? `${stats.median_resolution_days}d` : "—",
            },
          ]}
        />

        {/* 3. BENCHLIGHT SPLIT WORKSPACE (Geographic Area + Inspector) */}
        <div className={`split ${activeCase ? "inspecting" : ""}`}>
          <div>
            {/* Section 01: Geographic Canvas */}
            <SectionHeader
              index="01"
              title="Geographic inspection canvas"
              actionText={`Ward 34 · ${filteredCases.length} plotted cases`}
            >
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                style={{ fontSize: "11px", padding: "2px 8px", height: "26px", minHeight: "26px" }}
                aria-label="Filter category"
              >
                <option value="">All categories ({cases.length})</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </SectionHeader>

            <div style={{
              position: "relative",
              height: "360px",
              background: "var(--surface-muted)",
              border: "1px solid var(--border)",
              marginBottom: "var(--space-5)",
              overflow: "hidden",
            }}>
              <svg style={{ width: "100%", height: "100%" }} viewBox="0 0 600 360">
                <defs>
                  <pattern id="benchGrid" width="24" height="24" patternUnits="userSpaceOnUse">
                    <path d="M 24 0 L 0 0 0 24" fill="none" stroke="var(--border)" strokeWidth="0.75" />
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#benchGrid)" />

                {/* Ward Perimeter */}
                <polygon
                  points="30,20 570,15 580,335 25,340"
                  fill="rgba(121, 95, 47, 0.03)"
                  stroke="var(--border-strong)"
                  strokeWidth="1"
                  strokeDasharray="4 3"
                />

                {/* Arterial Corridors */}
                <line x1="25" y1="180" x2="575" y2="175" stroke="var(--border-strong)" strokeWidth="4" />
                <text x="35" y="170" fill="var(--text-secondary)" fontSize="10" fontFamily="var(--font-mono)">
                  MG ROAD ARTERIAL CORRIDOR
                </text>

                <line x1="310" y1="15" x2="325" y2="340" stroke="var(--border-strong)" strokeWidth="4" />
                <text x="335" y="35" fill="var(--text-secondary)" fontSize="10" fontFamily="var(--font-mono)">
                  AB ROAD MAIN AXIS
                </text>

                {/* Plotted Live Case Markers */}
                {filteredCases.map((c) => {
                  const minLat = 22.710, maxLat = 22.735;
                  const minLon = 75.845, maxLon = 75.885;
                  const x = Math.max(45, Math.min(555, ((c.longitude - minLon) / (maxLon - minLon)) * 510 + 35));
                  const y = Math.max(30, Math.min(325, (1 - (c.latitude - minLat) / (maxLat - minLat)) * 295 + 25));
                  const isSelected = activeCase?.id === c.id;

                  const pinColor =
                    c.state === "DISPUTED"
                      ? "var(--danger)"
                      : c.state === "RESOLVED"
                      ? "var(--success)"
                      : c.state === "AWAITING_VERIFICATION"
                      ? "var(--warning)"
                      : "var(--accent)";

                  return (
                    <g
                      key={c.id}
                      onClick={() => setActiveCase(c)}
                      style={{ cursor: "pointer" }}
                    >
                      {isSelected && (
                        <circle cx={x} cy={y} r="13" fill="none" stroke={pinColor} strokeWidth="2" opacity="0.4" />
                      )}
                      <circle cx={x} cy={y} r={isSelected ? "7" : "5"} fill={pinColor} stroke="#FFF" strokeWidth="1.5" />
                      <text
                        x={x + 10}
                        y={y + 3.5}
                        fill="var(--text-primary)"
                        fontSize="10"
                        fontWeight="600"
                        fontFamily="var(--font-mono)"
                      >
                        {c.public_id}
                      </text>
                    </g>
                  );
                })}
              </svg>

              <div style={{
                position: "absolute",
                bottom: 0,
                left: 0,
                right: 0,
                background: "var(--surface)",
                borderTop: "1px solid var(--border)",
                padding: "4px 10px",
                display: "flex",
                justifyContent: "space-between",
                fontSize: "10px",
                color: "var(--text-secondary)",
                fontFamily: "var(--font-mono)",
              }}>
                <span>Offline schematic grid · Indore Ward 34</span>
                <span>WGS84: 22.7196° N, 75.8577° E</span>
              </div>
            </div>

            {/* Section 02: Flat Data Table */}
            <SectionHeader
              index="02"
              title="Public infrastructure activity ledger"
              actionText="View all cases"
              actionHref="/explorer"
            />

            <table>
              <thead>
                <tr>
                  <th style={{ width: "125px" }}>Reference</th>
                  <th>Infrastructure issue & location</th>
                  <th style={{ width: "175px" }}>Category</th>
                  <th style={{ width: "140px" }}>Status</th>
                  <th className="numeric" style={{ width: "80px" }}>Priority</th>
                  <th className="numeric" style={{ width: "100px" }}>Date</th>
                </tr>
              </thead>
              <tbody>
                {cases.slice(0, 8).map((c) => {
                  const isSelected = activeCase?.id === c.id;
                  return (
                    <tr
                      key={c.id}
                      className={isSelected ? "selected" : ""}
                      onClick={() => setActiveCase(c)}
                      style={{ cursor: "pointer" }}
                    >
                      <td>
                        <code style={{ color: "var(--text-primary)", fontWeight: 600 }}>{c.public_id}</code>
                      </td>
                      <td>
                        <Link to={`/cases/${c.public_id}`} style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                          {c.title}
                        </Link>
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px" }}>
                          {c.address_reference}
                        </div>
                      </td>
                      <td style={{ color: "var(--text-secondary)", fontSize: "12px" }}>
                        {c.category?.name}
                      </td>
                      <td>
                        <StatusStamp state={c.state} size="sm" />
                      </td>
                      <td className="numeric" style={{ fontWeight: 600, color: "var(--accent)" }}>
                        {c.priority_score.toFixed(1)}
                      </td>
                      <td className="numeric" style={{ color: "var(--text-secondary)", fontSize: "11px" }}>
                        {new Date(c.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Right Column: Benchlight Inspector Pane */}
          {activeCase && (
            <aside className="inspector" aria-label="Case inspector">
              <div className="inspector-header">
                <div>
                  <span className="section-index" style={{ marginRight: "6px" }}>02 /</span>
                  <code style={{ fontSize: "13px", fontWeight: 600 }}>{activeCase.public_id}</code>
                </div>
                <button
                  className="inspector-close"
                  onClick={() => setActiveCase(null)}
                  title="Close inspector"
                  aria-label="Close case inspector"
                >
                  &times;
                </button>
              </div>

              <div style={{ marginBottom: "var(--space-3)" }}>
                <h3 style={{ fontSize: "15px", fontWeight: 600, margin: "0 0 6px", lineHeight: 1.3 }}>
                  {activeCase.title}
                </h3>
                <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: 0, lineHeight: 1.45 }}>
                  {activeCase.description}
                </p>
              </div>

              <div className="inspector-row">
                <label>Status</label>
                <div>
                  <StatusStamp state={activeCase.state} />
                </div>
              </div>

              <div className="inspector-row">
                <label>Category</label>
                <span>{activeCase.category?.name}</span>
              </div>

              <div className="inspector-row">
                <label>Location reference</label>
                <span>{activeCase.address_reference}</span>
              </div>

              <div className="inspector-row">
                <label>WGS84 Coordinates</label>
                <code className="numeric">
                  {activeCase.latitude.toFixed(5)}, {activeCase.longitude.toFixed(5)}
                </code>
              </div>

              <div className="inspector-row">
                <label>Civic priority & band</label>
                <span style={{ fontWeight: 600, color: "var(--accent)" }}>
                  {activeCase.priority_score.toFixed(1)} / 10 · {activeCase.priority_band}
                </span>
              </div>

              <div className="inspector-row">
                <label>Corroborated observations</label>
                <span>{activeCase.report_count} citizen report(s)</span>
              </div>

              <div style={{ marginTop: "var(--space-4)", paddingTop: "var(--space-3)", borderTop: "1px solid var(--border)" }}>
                <Link
                  to={`/cases/${activeCase.public_id}`}
                  className="button-primary"
                  style={{ width: "100%", justifyContent: "center" }}
                >
                  Open full case dossier
                </Link>
              </div>
            </aside>
          )}
        </div>
      </div>
    </>
  );
};
