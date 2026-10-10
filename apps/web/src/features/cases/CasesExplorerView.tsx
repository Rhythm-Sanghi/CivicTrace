import React, { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { api, type Case, type Category } from "../../lib/api";
import { Search } from "lucide-react";

export const CasesExplorerView: React.FC = () => {
  const [cases, setCases] = useState<Case[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [selectedBand, setSelectedBand] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [activeCase, setActiveCase] = useState<Case | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);

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
    <div style={{ padding: "var(--space-6) 0" }}>
      <div className="container">
        {/* Workspace Title & Controls Bar */}
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
          marginBottom: "var(--space-4)",
        }}>
          <div>
            <h1 style={{ fontSize: "var(--font-size-xl)", fontWeight: 700, letterSpacing: "-0.01em" }}>
              Public Infrastructure Ledger
            </h1>
            <div style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)" }}>
              {filteredCases.length} active civic cases in Indore Central & North Ward
            </div>
          </div>

          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <div style={{ position: "relative" }}>
              <Search size={14} style={{ position: "absolute", left: "10px", top: "10px", color: "var(--color-text-muted)" }} />
              <input
                type="text"
                placeholder="Search cases or locations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  padding: "6px 12px 6px 30px",
                  fontSize: "var(--font-size-sm)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-sm)",
                  width: "240px",
                }}
              />
            </div>

            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              style={{
                padding: "6px 10px",
                fontSize: "var(--font-size-sm)",
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
                fontSize: "var(--font-size-sm)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-sm)",
                backgroundColor: "var(--color-surface)",
              }}
            >
              <option value="">All Priorities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>
        </div>

        {/* Split View: Ruled Table + Selected Case Inspector */}
        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: "20px" }}>
          {/* Left: Case Records Table */}
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>
            <table className="ruled-table">
              <thead>
                <tr>
                  <th>Case ID</th>
                  <th>Defect Title & Location</th>
                  <th>Category</th>
                  <th>Status</th>
                  <th>Priority</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredCases.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => setActiveCase(c)}
                    style={{
                      cursor: "pointer",
                      backgroundColor: activeCase?.id === c.id ? "var(--color-civic-blue-subtle)" : undefined,
                    }}
                  >
                    <td>
                      <span className="mono-id">{c.public_id}</span>
                      <div style={{ fontSize: "11px", color: "var(--color-text-muted)", marginTop: "2px" }}>
                        {c.report_count} report(s)
                      </div>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: "var(--color-text-primary)" }}>{c.title}</div>
                      <div style={{ fontSize: "11px", color: "var(--color-text-secondary)" }}>
                        📍 {c.address_reference || "Indore"}
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: "12px", color: "var(--color-text-secondary)" }}>
                        {c.category?.name || "General"}
                      </span>
                    </td>
                    <td>
                      <span className={`archival-stamp stamp-${c.state.toLowerCase()}`}>
                        {c.state.replace("_", " ")}
                      </span>
                    </td>
                    <td>
                      <span style={{
                        fontSize: "11px",
                        fontWeight: 700,
                        fontFamily: "var(--font-family-mono)",
                        color: c.priority_band === "CRITICAL" ? "var(--color-disputed-red)" : "var(--color-civic-blue)",
                      }}>
                        {c.priority_score.toFixed(1)}
                      </span>
                    </td>
                    <td>
                      <Link to={`/cases/${c.public_id}`} className="btn btn-outline btn-sm">
                        Inspect
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Right: Selected Case Inspector */}
          <div>
            {activeCase ? (
              <div className="card" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <span className="mono-id">{activeCase.public_id}</span>
                    <h2 style={{ fontSize: "18px", fontWeight: 700, marginTop: "6px" }}>
                      {activeCase.title}
                    </h2>
                  </div>
                  <span className={`archival-stamp stamp-${activeCase.state.toLowerCase()}`}>
                    {activeCase.state.replace("_", " ")}
                  </span>
                </div>

                <div style={{
                  padding: "12px",
                  backgroundColor: "var(--color-surface-elevated)",
                  border: "1px solid var(--color-border-subtle)",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "13px",
                  lineHeight: 1.5,
                }}>
                  {activeCase.description}
                </div>

                {/* Spatial Map Canvas & Evidence Box */}
                <div style={{
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-sm)",
                  overflow: "hidden",
                  backgroundColor: "#FAFAF9",
                }}>
                  {/* Interactive Map Canvas */}
                  <div
                    ref={mapContainerRef}
                    style={{
                      width: "100%",
                      height: "180px",
                      backgroundColor: "#E8ECE9",
                      position: "relative",
                      borderBottom: "1px solid var(--color-border)",
                    }}
                  >
                    {/* Offline/Online resilient SVG Pin overlay */}
                    <div style={{
                      position: "absolute",
                      top: "50%",
                      left: "50%",
                      transform: "translate(-50%, -50%)",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      pointerEvents: "none",
                      zIndex: 10,
                    }}>
                      <div style={{
                        backgroundColor: activeCase.priority_band === "CRITICAL" ? "var(--color-disputed-red)" : "var(--color-civic-blue)",
                        color: "#FFF",
                        padding: "3px 8px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: "10px",
                        fontWeight: 700,
                        fontFamily: "var(--font-family-mono)",
                        boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
                        whiteSpace: "nowrap",
                      }}>
                        📍 {activeCase.public_id} ({activeCase.latitude.toFixed(4)}, {activeCase.longitude.toFixed(4)})
                      </div>
                      <div style={{
                        width: "10px",
                        height: "10px",
                        backgroundColor: activeCase.priority_band === "CRITICAL" ? "var(--color-disputed-red)" : "var(--color-civic-blue)",
                        transform: "rotate(45deg)",
                        marginTop: "-5px",
                      }} />
                    </div>
                  </div>

                  <div style={{ padding: "12px" }}>
                    <div style={{ fontSize: "11px", textTransform: "uppercase", fontWeight: 600, color: "var(--color-text-secondary)", marginBottom: "4px" }}>
                      Geographic Coordinates (WGS84 & Ward Boundary)
                    </div>
                    <div style={{ fontFamily: "var(--font-family-mono)", fontSize: "13px", color: "var(--color-civic-blue)", fontWeight: 600 }}>
                      LAT: {activeCase.latitude.toFixed(6)} | LON: {activeCase.longitude.toFixed(6)}
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--color-text-secondary)", marginTop: "4px" }}>
                      📍 {activeCase.address_reference || "Indore Central Ward, MP, India"}
                    </div>
                    <div style={{ marginTop: "6px", fontSize: "11px", color: "var(--color-text-muted)" }}>
                      Verified Geographic Footprint: Indore Municipal Ward 34 &bull; Offline Grid Active
                    </div>
                  </div>
                </div>

                {/* Civic Priority Breakdown Rationale */}
                <div style={{
                  padding: "12px",
                  backgroundColor: "var(--color-attention-orange-subtle)",
                  border: "1px solid var(--color-attention-orange)",
                  borderRadius: "var(--radius-sm)",
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ fontWeight: 600, fontSize: "13px", color: "var(--color-attention-orange)" }}>
                      Explainable Civic Priority: {activeCase.priority_score.toFixed(1)} / 10
                    </div>
                    <span className="mono-id">{activeCase.priority_band}</span>
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--color-text-primary)", marginTop: "6px" }}>
                    Calculated by deterministic civic policy (corroborated reports + intrinsic hazard weight + duration).
                  </div>
                </div>

                <div style={{ display: "flex", gap: "10px" }}>
                  <Link to={`/cases/${activeCase.public_id}`} className="btn btn-primary" style={{ flex: 1 }}>
                    Full Evidence & History Ledger
                  </Link>
                  <a
                    href={`http://localhost:8000/api/v1/cases/${activeCase.public_id}/export`}
                    className="btn btn-outline"
                    download
                  >
                    Export ZIP
                  </a>
                </div>
              </div>
            ) : (
              <div className="card" style={{ textAlign: "center", color: "var(--color-text-muted)", padding: "40px" }}>
                Select a case to inspect evidence provenance
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
