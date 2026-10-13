import React, { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { api, type Case, type Category } from "../../lib/api";
import { PageHeading, StatusStamp, SectionHeader } from "../../components/FieldPrimitives";

type SortField = "public_id" | "title" | "priority_score" | "updated_at";
type SortDirection = "asc" | "desc";

export const CasesExplorerView: React.FC = () => {
  const [cases, setCases] = useState<Case[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [selectedBand, setSelectedBand] = useState<string>("");
  const [selectedState, setSelectedState] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [activeCase, setActiveCase] = useState<Case | null>(null);
  const [isInspectorOpen, setIsInspectorOpen] = useState<boolean>(true);
  const [sortField, setSortField] = useState<SortField>("priority_score");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 15;

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

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  const filteredAndSortedCases = useMemo(() => {
    const filtered = cases.filter((c) => {
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

    return filtered.sort((a, b) => {
      let comparison = 0;
      if (sortField === "public_id") {
        comparison = a.public_id.localeCompare(b.public_id);
      } else if (sortField === "title") {
        comparison = a.title.localeCompare(b.title);
      } else if (sortField === "priority_score") {
        comparison = a.priority_score - b.priority_score;
      } else if (sortField === "updated_at") {
        const timeA = new Date(a.updated_at || a.created_at).getTime();
        const timeB = new Date(b.updated_at || b.created_at).getTime();
        comparison = timeA - timeB;
      }
      return sortDirection === "asc" ? comparison : -comparison;
    });
  }, [cases, selectedCategory, selectedBand, selectedState, searchQuery, sortField, sortDirection]);

  const totalPages = Math.max(1, Math.ceil(filteredAndSortedCases.length / pageSize));
  const paginatedCases = useMemo(() => {
    const startIndex = (currentPage - 1) * pageSize;
    return filteredAndSortedCases.slice(startIndex, startIndex + pageSize);
  }, [filteredAndSortedCases, currentPage, pageSize]);

  // Keyboard navigation support
  const handleKeyDown = (e: React.KeyboardEvent, c: Case) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setActiveCase(c);
      setIsInspectorOpen(true);
    }
  };

  return (
    <>
      <PageHeading
        index="02"
        title="Cases"
        description="Public infrastructure records and local problem reports. Filter by status, search by road or neighborhood, and review public evidence dossiers."
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
              style={{ width: "100%" }}
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

            {activeCase && (
              <button
                type="button"
                onClick={() => setIsInspectorOpen((prev) => !prev)}
                className="btn-outline btn-sm"
                title={isInspectorOpen ? "Hide case details pane" : "Show case details pane"}
              >
                {isInspectorOpen ? "Hide inspector" : "Show inspector"}
              </button>
            )}
          </div>
        </div>

        {/* Split View with Flat Table & Inspector */}
        <div className={`split ${isInspectorOpen && activeCase ? "inspecting" : ""}`}>
          <div style={{ minWidth: 0, overflowX: "auto" }}>
            <SectionHeader
              index="01"
              title="Public infrastructure records"
              actionText={`${filteredAndSortedCases.length} records`}
            />

            <table>
              <thead>
                <tr>
                  <th
                    style={{ width: "115px" }}
                    className="sortable"
                    onClick={() => handleSort("public_id")}
                    title="Sort by reference ID"
                  >
                    Reference {sortField === "public_id" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                  </th>
                  <th
                    style={{ minWidth: "220px", width: isInspectorOpen ? "32%" : "40%" }}
                    className="sortable"
                    onClick={() => handleSort("title")}
                    title="Sort by issue title"
                  >
                    Infrastructure issue {sortField === "title" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                  </th>
                  <th style={{ width: isInspectorOpen ? "18%" : "22%" }}>Location</th>
                  <th style={{ width: isInspectorOpen ? "14%" : "16%" }}>Category</th>
                  <th style={{ width: "120px" }}>Status</th>
                  <th
                    className="numeric sortable"
                    style={{ width: "75px" }}
                    onClick={() => handleSort("priority_score")}
                    title="Sort by priority score"
                  >
                    Priority {sortField === "priority_score" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                  </th>
                  <th
                    className="numeric sortable"
                    style={{ width: "85px" }}
                    onClick={() => handleSort("updated_at")}
                    title="Sort by date"
                  >
                    Updated {sortField === "updated_at" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredAndSortedCases.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: "center", padding: "var(--space-5)", color: "var(--text-secondary)" }}>
                      No infrastructure cases match the selected filter criteria.
                    </td>
                  </tr>
                ) : (
                  paginatedCases.map((c) => {
                    const isSelected = activeCase?.id === c.id;
                    return (
                      <tr
                        key={c.id}
                        className={isSelected ? "selected" : ""}
                        onClick={() => {
                          setActiveCase(c);
                          setIsInspectorOpen(true);
                        }}
                        onKeyDown={(e) => handleKeyDown(e, c)}
                        tabIndex={0}
                        aria-selected={isSelected}
                        style={{ cursor: "pointer" }}
                      >
                        <td>
                          <code style={{ fontWeight: 600 }}>{c.public_id}</code>
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
                          <div className="table-text-ellipsis" style={{ color: "var(--text-secondary)", fontSize: "12px" }} title={c.address_reference}>
                            {c.address_reference}
                          </div>
                        </td>
                        <td>
                          <div className="table-text-ellipsis" style={{ color: "var(--text-secondary)", fontSize: "12px" }} title={c.category?.name}>
                            {c.category?.name}
                          </div>
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
                  })
                )}
              </tbody>
            </table>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "var(--space-3) var(--space-4)",
                  borderTop: "1px solid var(--border)",
                  fontSize: "12px",
                  color: "var(--text-secondary)",
                }}
              >
                <div>
                  Showing {Math.min((currentPage - 1) * pageSize + 1, filteredAndSortedCases.length)}–
                  {Math.min(currentPage * pageSize, filteredAndSortedCases.length)} of {filteredAndSortedCases.length} cases
                </div>
                <div style={{ display: "flex", gap: "var(--space-2)" }}>
                  <button
                    type="button"
                    className="button-subtle"
                    disabled={currentPage <= 1}
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    style={{ padding: "4px 10px", fontSize: "12px" }}
                  >
                    Previous
                  </button>
                  <span style={{ display: "flex", alignItems: "center", padding: "0 4px" }}>
                    Page {currentPage} of {totalPages}
                  </span>
                  <button
                    type="button"
                    className="button-subtle"
                    disabled={currentPage >= totalPages}
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    style={{ padding: "4px 10px", fontSize: "12px" }}
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Inspector Pane */}
          {isInspectorOpen && activeCase && (
            <aside className="inspector" aria-label="Case inspector">
              <div className="inspector-header">
                <div>
                  <span className="section-index" style={{ marginRight: "6px" }}>02 /</span>
                  <code style={{ fontSize: "13px", fontWeight: 600 }}>{activeCase.public_id}</code>
                </div>
                <button
                  className="inspector-close"
                  onClick={() => setIsInspectorOpen(false)}
                  title="Close inspector"
                  aria-label="Close inspector"
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

              <div className="inspector-row">
                <label>Last activity</label>
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
      </div>
    </>
  );
};
