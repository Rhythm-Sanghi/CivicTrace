import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Case, type Category } from "../../lib/api";
import { PageHeading, StatusStamp, SectionHeader } from "../../components/FieldPrimitives";
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
    <div>
      <PageHeading
        eyebrow="PUBLIC INFRASTRUCTURE LEDGER &bull; INDORE MUNICIPAL REGISTRY"
        title="Public Cases Explorer"
        description={`${filteredCases.length} public infrastructure dossiers recorded across Indore Central & North Ward.`}
      >
        <Link to="/report" className="btn btn-primary">
          Report New Issue
        </Link>
      </PageHeading>

      {/* Filter Toolbar */}
      <div style={{
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-sm)",
        padding: "10px 14px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: "10px",
        marginBottom: "16px",
      }}>
        <div style={{ position: "relative", flex: "1 1 240px", maxWidth: "340px" }}>
          <Search size={14} style={{ position: "absolute", left: "10px", top: "9px", color: "var(--color-text-muted)" }} />
          <input
            type="text"
            placeholder="Search reference, keyword, or street..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: "100%",
              padding: "6px 10px 6px 30px",
              fontSize: "13px",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              backgroundColor: "var(--color-surface-elevated)",
            }}
          />
        </div>

        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            style={{
              padding: "6px 10px",
              fontSize: "12px",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              backgroundColor: "var(--color-surface-elevated)",
            }}
          >
            <option value="">All Categories ({categories.length})</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>

          <select
            value={selectedBand}
            onChange={(e) => setSelectedBand(e.target.value)}
            style={{
              padding: "6px 10px",
              fontSize: "12px",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              backgroundColor: "var(--color-surface-elevated)",
            }}
          >
            <option value="">All Priorities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>

          <select
            value={selectedState}
            onChange={(e) => setSelectedState(e.target.value)}
            style={{
              padding: "6px 10px",
              fontSize: "12px",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              backgroundColor: "var(--color-surface-elevated)",
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

      {/* Master-Detail Investigation Workspace (65% Table / 35% Inspector) */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 1.8fr) minmax(360px, 1fr)",
        gap: "20px",
        alignItems: "start",
      }}>
        {/* Main Dossier Ledger Table */}
        <div style={{
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          overflow: "hidden",
        }}>
          <SectionHeader title="Public Infrastructure Ledger" />

          <table className="ledger-table">
            <thead>
              <tr>
                <th style={{ width: "130px" }}>Reference</th>
                <th>Defect Title & Location</th>
                <th style={{ width: "160px" }}>Category</th>
                <th style={{ width: "140px" }}>Status</th>
                <th style={{ width: "80px", textAlign: "right" }}>Priority</th>
                <th style={{ width: "70px", textAlign: "center" }}>Action</th>
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
                        {c.report_count} observation(s)
                      </div>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: "var(--color-text-primary)", fontSize: "13px" }}>
                        {c.title}
                      </div>
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
                    <td style={{ textAlign: "center" }}>
                      <Link to={`/cases/${c.public_id}`} className="btn btn-outline btn-sm" style={{ padding: "2px 8px" }}>
                        Inspect
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Side Forensic Inspector */}
        {activeCase && (
          <div style={{
            backgroundColor: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
          }}>
            {/* Dark Inspector Header */}
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
                  INSPECTOR PANEL
                </div>
                <div style={{ fontSize: "15px", fontWeight: 700, fontFamily: "var(--font-family-mono)", color: "#FFF" }}>
                  {activeCase.public_id}
                </div>
              </div>
              <StatusStamp state={activeCase.state} size="sm" />
            </div>

            <div style={{ padding: "18px", display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <h3 style={{ fontSize: "16px", fontWeight: 700, lineHeight: 1.3, color: "var(--color-text-primary)" }}>
                  {activeCase.title}
                </h3>
                <p style={{ fontSize: "13px", color: "var(--color-text-secondary)", marginTop: "6px", lineHeight: 1.5 }}>
                  {activeCase.description}
                </p>
              </div>

              {/* Geographic Footprint Schematic */}
              <div style={{
                backgroundColor: "#EBECE7",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-sm)",
                padding: "12px 14px",
              }}>
                <div style={{ fontSize: "10px", fontFamily: "var(--font-family-mono)", color: "var(--color-text-secondary)", textTransform: "uppercase" }}>
                  WGS84 Coordinates &bull; Offline Grid
                </div>
                <div style={{ fontSize: "13px", fontFamily: "var(--font-family-mono)", fontWeight: 600, color: "var(--color-civic-blue)", marginTop: "2px" }}>
                  LAT: {activeCase.latitude.toFixed(6)} | LON: {activeCase.longitude.toFixed(6)}
                </div>
                <div style={{ fontSize: "12px", color: "var(--color-text-secondary)", marginTop: "2px" }}>
                  📍 {activeCase.address_reference}
                </div>
              </div>

              {/* Explainable Civic Priority */}
              <div style={{
                backgroundColor: "var(--color-surface-elevated)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-sm)",
                padding: "12px 14px",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "12px", fontWeight: 600 }}>
                    Priority: {activeCase.priority_score.toFixed(1)} / 10
                  </span>
                  <span className="mono-id">{activeCase.priority_band}</span>
                </div>
                <div style={{ fontSize: "11px", color: "var(--color-text-muted)", marginTop: "4px" }}>
                  Deterministic civic policy (hazard category + {activeCase.report_count} observations + duration).
                </div>
              </div>

              <Link to={`/cases/${activeCase.public_id}`} className="btn btn-dark" style={{ width: "100%", justifyContent: "center" }}>
                Open Complete Forensic Dossier &rarr;
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
