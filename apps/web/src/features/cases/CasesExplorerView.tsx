import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Case, type Category } from "../../lib/api";
import { Search } from "lucide-react";

export const CasesExplorerView: React.FC = () => {
  const [cases, setCases] = useState<Case[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [selectedBand, setSelectedBand] = useState<string>("");
  const [selectedState, setSelectedState] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [activeCase, setActiveCase] = useState<Case | null>(null);

  useEffect(() => {
    Promise.all([
      api.getCategories().catch(() => []),
      api.getCases().catch(() => []),
    ]).then(([cats, cList]) => {
      setCategories(cats);
      setCases(cList);
      if (cList.length > 0) setActiveCase(cList[0]);
    });
  }, []);

  const filteredCases = cases.filter((c) => {
    if (selectedCategory && c.category_id !== selectedCategory) return false;
    if (selectedBand && c.priority_band !== selectedBand) return false;
    if (selectedState && c.state !== selectedState) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        c.title.toLowerCase().includes(q) ||
        c.public_id.toLowerCase().includes(q) ||
        (c.address_reference && c.address_reference.toLowerCase().includes(q))
      );
    }
    return true;
  });

  return (
    <div style={{ padding: "var(--space-6) 0 var(--space-10)" }}>
      <div className="workspace-container">
        
        {/* Workspace Title & Controls Bar */}
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          flexWrap: "wrap",
          gap: "16px",
          paddingBottom: "var(--space-4)",
          borderBottom: "1px solid var(--color-border)",
          marginBottom: "var(--space-6)",
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
              PUBLIC INFRASTRUCTURE LEDGER
            </div>
            <h1 style={{ fontSize: "28px", fontWeight: 700, letterSpacing: "-0.02em", color: "var(--color-text-primary)" }}>
              Public Cases Explorer
            </h1>
            <div style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)", marginTop: "2px" }}>
              {filteredCases.length} public infrastructure dossiers recorded across Indore Central & North Ward
            </div>
          </div>

          {/* Filter Toolbar */}
          <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ position: "relative" }}>
              <Search size={14} style={{ position: "absolute", left: "10px", top: "9px", color: "var(--color-text-muted)" }} />
              <input
                type="text"
                placeholder="Search cases or locations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  padding: "6px 12px 6px 30px",
                  fontSize: "13px",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-sm)",
                  width: "240px",
                  backgroundColor: "var(--color-surface)",
                }}
              />
            </div>

            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              style={{
                padding: "6px 10px",
                fontSize: "13px",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-sm)",
                backgroundColor: "var(--color-surface)",
              }}
            >
              <option value="">All Categories</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>{cat.name}</option>
              ))}
            </select>

            <select
              value={selectedBand}
              onChange={(e) => setSelectedBand(e.target.value)}
              style={{
                padding: "6px 10px",
                fontSize: "13px",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-sm)",
                backgroundColor: "var(--color-surface)",
              }}
            >
              <option value="">All Priorities</option>
              <option value="CRITICAL">Critical Priority</option>
              <option value="HIGH">High Priority</option>
              <option value="MEDIUM">Medium Priority</option>
              <option value="LOW">Low Priority</option>
            </select>

            <select
              value={selectedState}
              onChange={(e) => setSelectedState(e.target.value)}
              style={{
                padding: "6px 10px",
                fontSize: "13px",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-sm)",
                backgroundColor: "var(--color-surface)",
              }}
            >
              <option value="">All Statuses</option>
              <option value="SUBMITTED">Submitted</option>
              <option value="ASSIGNED">Assigned</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="AWAITING_VERIFICATION">Awaiting Verification</option>
              <option value="DISPUTED">Disputed</option>
              <option value="RESOLVED">Resolved</option>
            </select>
          </div>
        </div>

        {/* Master-Detail Full-Width Workspace Grid (65% Table / 35% Inspector) */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.8fr) minmax(360px, 1fr)",
          gap: "24px",
          alignItems: "start",
        }}>
          {/* Main Dossier Ledger Table */}
          <div style={{
            backgroundColor: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            overflow: "hidden",
          }}>
            <table className="ruled-table">
              <thead>
                <tr>
                  <th style={{ width: "120px" }}>Case ID</th>
                  <th>Defect Title & Location</th>
                  <th style={{ width: "160px" }}>Category</th>
                  <th style={{ width: "150px" }}>Status</th>
                  <th style={{ width: "80px", textAlign: "right" }}>Priority</th>
                  <th style={{ width: "80px", textAlign: "center" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredCases.map((c) => {
                  const isSelected = activeCase?.id === c.id;
                  return (
                    <tr
                      key={c.id}
                      onClick={() => setActiveCase(c)}
                      style={{
                        backgroundColor: isSelected ? "var(--color-civic-blue-subtle)" : undefined,
                        cursor: "pointer",
                      }}
                    >
                      <td>
                        <span className="mono-id">{c.public_id}</span>
                        <div style={{ fontSize: "11px", color: "var(--color-text-muted)", marginTop: "2px" }}>
                          {c.report_count} report(s)
                        </div>
                      </td>
                      <td>
                        <div style={{ fontWeight: 600, color: "var(--color-text-primary)", fontSize: "14px" }}>
                          {c.title}
                        </div>
                        <div style={{ fontSize: "12px", color: "var(--color-text-secondary)", marginTop: "2px" }}>
                          📍 {c.address_reference || "Indore Municipal Ward"}
                        </div>
                      </td>
                      <td style={{ fontSize: "12px", color: "var(--color-text-secondary)" }}>
                        {c.category?.name}
                      </td>
                      <td>
                        <span className={`archival-stamp stamp-${c.state.toLowerCase()}`}>
                          {c.state.replace("_", " ")}
                        </span>
                      </td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-family-mono)", fontSize: "13px", fontWeight: 700, color: "var(--color-civic-blue)" }}>
                        {c.priority_score.toFixed(1)}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <Link
                          to={`/cases/${c.public_id}`}
                          className="btn btn-outline btn-sm"
                          style={{ padding: "3px 8px", fontSize: "11px" }}
                        >
                          Inspect
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Side Inspection Panel & Geographic Dossier */}
          {activeCase && (
            <div style={{
              backgroundColor: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              padding: "20px",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="mono-id">{activeCase.public_id}</span>
                <span className={`archival-stamp stamp-${activeCase.state.toLowerCase()}`}>
                  {activeCase.state.replace("_", " ")}
                </span>
              </div>

              <div>
                <h2 style={{ fontSize: "18px", fontWeight: 700, lineHeight: 1.3, color: "var(--color-text-primary)" }}>
                  {activeCase.title}
                </h2>
                <p style={{ fontSize: "13px", color: "var(--color-text-secondary)", marginTop: "8px", lineHeight: 1.5 }}>
                  {activeCase.description}
                </p>
              </div>

              {/* Geographic Footprint Schematic */}
              <div style={{
                backgroundColor: "#EBECE8",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-sm)",
                padding: "16px",
                position: "relative",
              }}>
                <div style={{
                  fontFamily: "var(--font-family-mono)",
                  fontSize: "11px",
                  color: "var(--color-text-secondary)",
                  textAlign: "center",
                  marginBottom: "8px",
                }}>
                  GEOGRAPHIC COORDINATES (WGS84 & WARD BOUNDARY)
                </div>
                <div style={{
                  fontSize: "13px",
                  fontWeight: 600,
                  fontFamily: "var(--font-family-mono)",
                  textAlign: "center",
                  color: "var(--color-civic-blue)",
                }}>
                  LAT: {activeCase.latitude.toFixed(6)} | LON: {activeCase.longitude.toFixed(6)}
                </div>
                <div style={{ fontSize: "12px", color: "var(--color-text-muted)", textAlign: "center", marginTop: "4px" }}>
                  📍 {activeCase.address_reference}
                </div>
                <div style={{ fontSize: "10px", color: "var(--color-text-muted)", textAlign: "center", marginTop: "2px" }}>
                  Verified Geographic Footprint: Indore Municipal Ward 34 &bull; Offline Grid Active
                </div>
              </div>

              {/* Priority Score Breakdown */}
              <div style={{
                backgroundColor: "var(--color-surface-elevated)",
                border: "1px solid var(--color-border)",
                padding: "12px 16px",
                borderRadius: "var(--radius-sm)",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--color-text-secondary)" }}>
                    Explainable Civic Priority: {activeCase.priority_score.toFixed(1)} / 10
                  </span>
                  <span className="mono-id">{activeCase.priority_band}</span>
                </div>
                <div style={{ fontSize: "11px", color: "var(--color-text-muted)", marginTop: "4px" }}>
                  Calculated by deterministic civic policy (corroborated reports + intrinsic hazard weight + duration).
                </div>
              </div>

              <Link to={`/cases/${activeCase.public_id}`} className="btn btn-primary" style={{ width: "100%" }}>
                Open Complete Forensic Dossier &rarr;
              </Link>
            </div>
          )}
        </div>

      </div>
    </div>
  );
};
