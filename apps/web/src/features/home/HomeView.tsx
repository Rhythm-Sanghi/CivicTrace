import React, { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { api, type Case, type NeighborhoodStats, type Category } from "../../lib/api";
import { PageHeading, MetricStrip, StatusStamp, SectionHeader } from "../../components/FieldPrimitives";

export const HomeView: React.FC = () => {
  const [stats, setStats] = useState<NeighborhoodStats | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [activeCase, setActiveCase] = useState<Case | null>(null);
  const [isInspectorOpen, setIsInspectorOpen] = useState<boolean>(true);
  const [isMapExpanded, setIsMapExpanded] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Map viewport pan & zoom state
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [panOffset, setPanOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  const fetchData = () => {
    setLoading(true);
    setErrorMsg(null);
    return Promise.all([
      api.getNeighborhoodStats(),
      api.getCases(),
      api.getCategories(),
    ])
      .then(([s, cList, cats]) => {
        setStats(s);
        setCases(cList);
        setCategories(cats);
        if (cList.length > 0) setActiveCase(cList[0]);
        setLoading(false);
      })
      .catch((err) => {
        setErrorMsg(err.message || "Failed to connect to CivicTrace API.");
        setLoading(false);
      });
  };

  useEffect(() => {
    Promise.all([
      api.getNeighborhoodStats(),
      api.getCases(),
      api.getCategories(),
    ])
      .then(([s, cList, cats]) => {
        setStats(s);
        setCases(cList);
        setCategories(cats);
        if (cList.length > 0) setActiveCase(cList[0]);
        setLoading(false);
      })
      .catch((err) => {
        setErrorMsg(err.message || "Failed to connect to CivicTrace API.");
        setLoading(false);
      });
  }, []);

  const filteredCases = useMemo(() => {
    return cases.filter((c) => {
      if (selectedCategory && c.category_id !== selectedCategory) return false;
      return true;
    });
  }, [cases, selectedCategory]);

  const handleFitToVisible = () => {
    setZoomLevel(1);
    setPanOffset({ x: 0, y: 0 });
  };

  const handleZoomIn = () => {
    setZoomLevel((prev) => Math.min(2.5, +(prev + 0.25).toFixed(2)));
  };

  const handleZoomOut = () => {
    setZoomLevel((prev) => Math.max(0.75, +(prev - 0.25).toFixed(2)));
  };

  const handlePan = (dx: number, dy: number) => {
    setPanOffset((prev) => ({ x: prev.x + dx, y: prev.y + dy }));
  };

  // Declutter marker layout with vertical and horizontal alternation
  const renderedMarkers = useMemo(() => {
    const minLat = 22.710, maxLat = 22.735;
    const minLon = 75.845, maxLon = 75.885;

    return filteredCases.map((c, index) => {
      const baseX = Math.max(45, Math.min(555, ((c.longitude - minLon) / (maxLon - minLon)) * 510 + 35));
      const baseY = Math.max(30, Math.min(325, (1 - (c.latitude - minLat) / (maxLat - minLat)) * 295 + 25));
      const isSelected = activeCase?.id === c.id;

      const labelYOffset = index % 2 === 0 ? -12 : 16;
      const labelXOffset = index % 3 === 0 ? -32 : 8;

      const pinColor =
        c.state === "DISPUTED"
          ? "var(--danger)"
          : c.state === "RESOLVED"
          ? "var(--success)"
          : c.state === "AWAITING_VERIFICATION"
          ? "var(--warning)"
          : "var(--accent)";

      return {
        c,
        baseX,
        baseY,
        isSelected,
        pinColor,
        labelXOffset,
        labelYOffset,
      };
    });
  }, [filteredCases, activeCase]);

  return (
    <>
      <PageHeading
        title="Overview"
        description="The state of your neighborhood. Follow infrastructure reports, track repairs, and verify completed work."
      >
        <Link to="/report" className="button-primary">
          Report issue
        </Link>
        <Link to="/explorer" className="btn-outline">
          Browse cases
        </Link>
      </PageHeading>

      <div className="workspace">
        {loading ? (
          <p className="muted" style={{ padding: "var(--space-4) 0" }}>Loading neighborhood cases and metrics...</p>
        ) : errorMsg ? (
          <div style={{
            background: "var(--surface)",
            border: "1px solid var(--danger)",
            borderLeft: "3px solid var(--danger)",
            padding: "var(--space-4)",
            marginBottom: "var(--space-4)",
          }}>
            <h3 style={{ fontSize: "14px", color: "var(--danger)", margin: "0 0 6px" }}>Unable to load cases</h3>
            <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: "0 0 var(--space-3)" }}>{errorMsg}</p>
            <button onClick={fetchData} className="button-primary btn-sm">
              Retry
            </button>
          </div>
        ) : cases.length === 0 ? (
          <div style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            padding: "var(--space-6)",
            textAlign: "center",
            maxWidth: "600px",
            margin: "var(--space-5) auto",
          }}>
            <h3 style={{ fontSize: "16px", margin: "0 0 var(--space-2)" }}>No cases recorded yet</h3>
            <p style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: 1.5, margin: "0 0 var(--space-4)" }}>
              No infrastructure reports have been registered for this service area. You can submit the first issue to establish public tracking.
            </p>
            <Link to="/report" className="button-primary">
              Report an issue
            </Link>
          </div>
        ) : (
          <>
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
                  value: stats && stats.median_resolution_days > 0 ? `${stats.median_resolution_days}d` : "—",
                },
              ]}
            />

            <div className={`split ${isInspectorOpen && activeCase ? "inspecting" : ""}`}>
              <div style={{ minWidth: 0 }}>
                {/* Issue Map Section */}
                <SectionHeader
                  title="Issue map"
                  actionText={`Ward 34 · ${filteredCases.length} plotted cases`}
                >
                  <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center", flexWrap: "wrap" }}>
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

                    <button
                      type="button"
                      onClick={() => setIsMapExpanded((prev) => !prev)}
                      className="btn-outline btn-sm"
                      title={isMapExpanded ? "Collapse map" : "Expand map"}
                    >
                      {isMapExpanded ? "Hide map" : "Show map"}
                    </button>

                    {activeCase && (
                      <button
                        type="button"
                        onClick={() => setIsInspectorOpen((prev) => !prev)}
                        className="btn-outline btn-sm"
                      >
                        {isInspectorOpen ? "Hide inspector" : "Show inspector"}
                      </button>
                    )}
                  </div>
                </SectionHeader>

                {isMapExpanded && (
                  <div style={{
                    position: "relative",
                    height: "360px",
                    background: "var(--surface-muted)",
                    border: "1px solid var(--border)",
                    marginBottom: "var(--space-5)",
                    overflow: "hidden",
                  }}>
                    {/* Map Controls */}
                    <div style={{
                      position: "absolute",
                      top: "8px",
                      right: "8px",
                      zIndex: 10,
                      display: "flex",
                      flexDirection: "column",
                      gap: "3px",
                      background: "var(--surface)",
                      border: "1px solid var(--border)",
                      padding: "4px",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
                    }}>
                      <button
                        type="button"
                        onClick={handleZoomIn}
                        className="btn-outline btn-sm"
                        style={{ minWidth: "26px", height: "26px", padding: 0 }}
                        title="Zoom in"
                        aria-label="Zoom in"
                      >
                        +
                      </button>
                      <button
                        type="button"
                        onClick={handleZoomOut}
                        className="btn-outline btn-sm"
                        style={{ minWidth: "26px", height: "26px", padding: 0 }}
                        title="Zoom out"
                        aria-label="Zoom out"
                      >
                        -
                      </button>
                      <button
                        type="button"
                        onClick={handleFitToVisible}
                        className="btn-outline btn-sm"
                        style={{ fontSize: "10px", padding: "2px 4px", minHeight: "22px" }}
                        title="Fit to visible cases"
                      >
                        Fit
                      </button>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2px" }}>
                        <button
                          type="button"
                          onClick={() => handlePan(20, 0)}
                          className="btn-outline btn-sm"
                          style={{ padding: 0, height: "20px", minHeight: "20px", fontSize: "10px" }}
                          title="Pan left"
                        >
                          ◀
                        </button>
                        <button
                          type="button"
                          onClick={() => handlePan(-20, 0)}
                          className="btn-outline btn-sm"
                          style={{ padding: 0, height: "20px", minHeight: "20px", fontSize: "10px" }}
                          title="Pan right"
                        >
                          ▶
                        </button>
                      </div>
                    </div>

                    {/* SVG Schematic Canvas */}
                    <svg style={{ width: "100%", height: "100%" }} viewBox="0 0 600 360">
                      <defs>
                        <pattern id="benchGrid" width="24" height="24" patternUnits="userSpaceOnUse">
                          <path d="M 24 0 L 0 0 0 24" fill="none" stroke="var(--border)" strokeWidth="0.75" />
                        </pattern>
                      </defs>
                      <rect width="100%" height="100%" fill="url(#benchGrid)" />

                      <g transform={`translate(${panOffset.x}, ${panOffset.y}) scale(${zoomLevel})`}>
                        {/* Ward Perimeter */}
                        <polygon
                          points="30,20 570,15 580,335 25,340"
                          fill="rgba(121, 95, 47, 0.03)"
                          stroke="var(--border-strong)"
                          strokeWidth="1"
                          strokeDasharray="4 3"
                        />

                        {/* Arterial Corridors (Schematic Reference Lines) */}
                        <line x1="25" y1="180" x2="575" y2="175" stroke="var(--border-strong)" strokeWidth="3" />
                        <text x="35" y="170" fill="var(--text-secondary)" fontSize="9" fontFamily="var(--font-mono)">
                          MG ROAD CORRIDOR
                        </text>

                        <line x1="310" y1="15" x2="325" y2="335" stroke="var(--border-strong)" strokeWidth="3" />
                        <text x="335" y="32" fill="var(--text-secondary)" fontSize="9" fontFamily="var(--font-mono)">
                          AB ROAD AXIS
                        </text>

                        {/* Plotted Live Case Markers */}
                        {renderedMarkers.map(({ c, baseX, baseY, isSelected, pinColor, labelXOffset, labelYOffset }) => (
                          <g
                            key={c.id}
                            onClick={() => {
                              setActiveCase(c);
                              setIsInspectorOpen(true);
                            }}
                            style={{ cursor: "pointer" }}
                          >
                            <circle cx={baseX} cy={baseY} r="18" fill="transparent" />

                            {isSelected && (
                              <>
                                <circle cx={baseX} cy={baseY} r="14" fill="none" stroke={pinColor} strokeWidth="2.5" opacity="0.4" />
                                <circle cx={baseX} cy={baseY} r="20" fill="none" stroke="var(--accent)" strokeWidth="1" strokeDasharray="3 2" />
                              </>
                            )}
                            <circle
                              cx={baseX}
                              cy={baseY}
                              r={isSelected ? "7" : "5"}
                              fill={pinColor}
                              stroke="#FFF"
                              strokeWidth={isSelected ? "2" : "1.5"}
                            />

                            <g transform={`translate(${baseX + labelXOffset}, ${baseY + labelYOffset})`}>
                              <rect
                                x="-2"
                                y="-9"
                                width="78"
                                height="13"
                                fill="var(--surface)"
                                stroke={isSelected ? "var(--accent)" : "var(--border)"}
                                strokeWidth={isSelected ? "1" : "0.5"}
                                rx="2"
                              />
                              <text
                                x="2"
                                y="1"
                                fill={isSelected ? "var(--accent)" : "var(--text-primary)"}
                                fontSize="9"
                                fontWeight={isSelected ? "700" : "600"}
                                fontFamily="var(--font-mono)"
                              >
                                {c.public_id}
                              </text>
                            </g>
                          </g>
                        ))}
                      </g>
                    </svg>

                    {/* Schematic Disclaimer Footer */}
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
                      alignItems: "center",
                      fontSize: "10px",
                      color: "var(--text-secondary)",
                      fontFamily: "var(--font-mono)",
                    }}>
                      <span>Schematic layout — not real street geometry</span>
                      <span>Zoom: {zoomLevel.toFixed(2)}x · Indore Ward 34</span>
                    </div>
                  </div>
                )}

                {/* Recent Cases Section */}
                <SectionHeader
                  title="Recent cases"
                  actionText="View all cases"
                  actionHref="/explorer"
                />

                <div className="table-shell">
                  <table>
                    <thead>
                      <tr>
                        <th style={{ width: "120px" }}>Reference</th>
                        <th style={{ minWidth: "180px", width: isInspectorOpen ? "34%" : "42%" }}>Issue</th>
                        <th style={{ minWidth: "140px", width: isInspectorOpen ? "22%" : "26%" }}>Location</th>
                        <th style={{ width: "120px" }}>Status</th>
                        <th className="numeric" style={{ width: "75px" }}>Priority</th>
                        <th className="numeric" style={{ width: "85px" }}>Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cases.slice(0, 8).map((c) => {
                        const isSelected = activeCase?.id === c.id;
                        return (
                          <tr
                            key={c.id}
                            className={isSelected ? "selected" : ""}
                            onClick={() => {
                              setActiveCase(c);
                              setIsInspectorOpen(true);
                            }}
                            tabIndex={0}
                            aria-selected={isSelected}
                            style={{ cursor: "pointer" }}
                          >
                            <td>
                              <code style={{ color: "var(--text-primary)", fontWeight: 600 }}>{c.public_id}</code>
                            </td>
                            <td>
                              <div className="table-title-clamp" title={c.title}>
                                <Link
                                  to={`/cases/${c.public_id}`}
                                  style={{ fontWeight: 600, color: "var(--text-primary)" }}
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  {c.title}
                                </Link>
                              </div>
                            </td>
                            <td>
                              <div className="table-text-ellipsis" style={{ fontSize: "12px", color: "var(--text-secondary)" }} title={c.address_reference}>
                                {c.address_reference}
                              </div>
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
              </div>

              {/* Inspector Pane */}
              {isInspectorOpen && activeCase && (
                <aside className="inspector" aria-label="Case inspector">
                  <div className="inspector-header">
                    <div>
                      <code style={{ fontSize: "13px", fontWeight: 600 }}>{activeCase.public_id}</code>
                    </div>
                    <button
                      className="inspector-close"
                      onClick={() => setIsInspectorOpen(false)}
                      title="Close inspector"
                      aria-label="Close case inspector"
                    >
                      &times;
                    </button>
                  </div>

                  <div style={{ marginBottom: "var(--space-3)" }}>
                    <h3 style={{ fontSize: "14px", fontWeight: 600, margin: "0 0 6px", lineHeight: 1.35 }}>
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
                    <label>Location</label>
                    <span>{activeCase.address_reference}</span>
                  </div>

                  <div className="inspector-row">
                    <label>Coordinates</label>
                    <code className="numeric">
                      {activeCase.latitude.toFixed(5)}, {activeCase.longitude.toFixed(5)}
                    </code>
                  </div>

                  <div className="inspector-row">
                    <label>Priority</label>
                    <span style={{ fontWeight: 600, color: "var(--accent)" }}>
                      {activeCase.priority_score.toFixed(1)} / 10 · {activeCase.priority_band}
                    </span>
                  </div>

                  <div className="inspector-row">
                    <label>Corroborated reports</label>
                    <span>{activeCase.report_count} citizen report(s)</span>
                  </div>

                  <div className="inspector-row">
                    <label>Last updated</label>
                    <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                      {new Date(activeCase.updated_at || activeCase.created_at).toLocaleString()}
                    </span>
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
          </>
        )}
      </div>
    </>
  );
};
