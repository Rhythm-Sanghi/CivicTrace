import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Case, type Category } from "../../lib/api";
import { PageHeading, StatusStamp, SectionHeader } from "../../components/FieldPrimitives";

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
    <>
      <PageHeading
        index="02"
        title="Cases"
        description="Public infrastructure records and case investigations. Public Cases Explorer · Public Infrastructure Ledger."
      >
        <Link to="/report" className="button-primary">
          Report issue
        </Link>
      </PageHeading>

      <div className="workspace">
        {/* Benchlight Work Toolbar */}
        <div className="toolbar work-toolbar">
          <div style={{ display: "flex", gap: "var(--space-2)", flex: 1, minWidth: "220px", maxWidth: "340px" }}>
            <input
              type="text"
              placeholder="Filter reference, issue, or street..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Filter cases"
            />
          </div>

          <div className="action-group">
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              aria-label="Filter by category"
            >
              <option value="">All categories ({categories.length})</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>

            <select
              value={selectedBand}
              onChange={(e) => setSelectedBand(e.target.value)}
              aria-label="Filter by priority"
            >
              <option value="">All priority bands</option>
              <option value="CRITICAL">Critical (&ge; 6.0)</option>
              <option value="HIGH">High (4.2 – 5.9)</option>
              <option value="MEDIUM">Medium (2.5 – 4.1)</option>
              <option value="LOW">Low (&lt; 2.5)</option>
            </select>

            <select
              value={selectedState}
              onChange={(e) => setSelectedState(e.target.value)}
              aria-label="Filter by state"
            >
              <option value="">All case states</option>
              <option value="SUBMITTED">Submitted</option>
              <option value="VERIFIED">Verified</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="AWAITING_VERIFICATION">Awaiting Verification</option>
              <option value="RESOLVED">Resolved</option>
              <option value="DISPUTED">Disputed</option>
            </select>
          </div>
        </div>

        {/* Split View with Flat Table & Inspector */}
        <div className={`split ${activeCase ? "inspecting" : ""}`}>
          <div>
            <SectionHeader
              index="01"
              title="Public infrastructure records"
              actionText={`${filteredCases.length} records`}
            />

            <table>
              <thead>
                <tr>
                  <th style={{ width: "125px" }}>Reference</th>
                  <th>Infrastructure issue</th>
                  <th style={{ width: "200px" }}>Location</th>
                  <th style={{ width: "160px" }}>Category</th>
                  <th style={{ width: "140px" }}>Status</th>
                  <th className="numeric" style={{ width: "75px" }}>Priority</th>
                  <th className="numeric" style={{ width: "85px" }}>Updated</th>
                </tr>
              </thead>
              <tbody>
                {filteredCases.map((c) => {
                  const isSelected = activeCase?.id === c.id;
                  return (
                    <tr
                      key={c.id}
                      className={isSelected ? "selected" : ""}
                      onClick={() => setActiveCase(c)}
                      style={{ cursor: "pointer" }}
                    >
                      <td>
                        <code style={{ fontWeight: 600 }}>{c.public_id}</code>
                      </td>
                      <td>
                        <Link to={`/cases/${c.public_id}`} style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                          {c.title}
                        </Link>
                      </td>
                      <td style={{ color: "var(--text-secondary)", fontSize: "12px" }}>
                        {c.address_reference}
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
                        {new Date(c.updated_at || c.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Inspector Pane */}
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
                  aria-label="Close inspector"
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
                <label>Workflow state</label>
                <div>
                  <StatusStamp state={activeCase.state} />
                </div>
              </div>

              <div className="inspector-row">
                <label>Category</label>
                <span>{activeCase.category?.name}</span>
              </div>

              <div className="inspector-row">
                <label>Physical location</label>
                <span>{activeCase.address_reference}</span>
              </div>

              <div className="inspector-row">
                <label>WGS84 Coordinates</label>
                <code className="numeric">
                  {activeCase.latitude.toFixed(5)}, {activeCase.longitude.toFixed(5)}
                </code>
              </div>

              <div className="inspector-row">
                <label>Civic priority</label>
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
