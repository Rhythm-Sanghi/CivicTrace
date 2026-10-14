import React, { useEffect, useState } from "react";
import { api, type DuplicateCandidate, type Report } from "../../lib/api";
import { PageHeading, SectionHeader } from "../../components/FieldPrimitives";

export const ReviewerWorkspaceView: React.FC = () => {
  const [candidates, setCandidates] = useState<DuplicateCandidate[]>([]);
  const [pendingReports, setPendingReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [decisionNotes, setDecisionNotes] = useState<{ [key: string]: string }>({});
  const [actionStatus, setActionStatus] = useState<string>("");

  const loadData = () => {
    Promise.all([
      api.getPendingDuplicates().catch(() => []),
      api.getPendingReports().catch(() => []),
    ]).then(([dups, reports]) => {
      setCandidates(dups);
      setPendingReports(reports);
      setLoading(false);
    }).catch((err) => {
      setActionStatus(`Error loading reviewer data: ${err.message}`);
      setLoading(false);
    });
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleModerateReport = async (reportId: string, decision: "APPROVED" | "REJECTED") => {
    try {
      await api.moderateReport(reportId, decision);
      setActionStatus(`Report ${reportId} marked as ${decision}.`);
      loadData();
    } catch (err: any) {
      setActionStatus(`Error: ${err.message}`);
    }
  };

  const handleDecision = async (candidateId: string, decision: "APPROVE" | "REJECT") => {
    try {
      await api.decideDuplicate(candidateId, decision, decisionNotes[candidateId]);
      setActionStatus(
        decision === "APPROVE"
          ? "Duplicate report consolidated into target case."
          : "Report separated as an independent case."
      );
      loadData();
    } catch (err: any) {
      setActionStatus(`Error: ${err.message}`);
    }
  };

  return (
    <>
      <PageHeading
        title="Reviewer desk"
        description="Review candidate report pairs identified by the duplicate engine and moderate incoming citizen submissions."
      />

      <div className="workspace">
        {actionStatus && (
          <div
            role="status"
            style={{
              padding: "var(--space-2) var(--space-3)",
              borderLeft: `2px solid ${actionStatus.includes("Error") ? "var(--danger)" : "var(--success)"}`,
              background: "var(--surface)",
              color: actionStatus.includes("Error") ? "var(--danger)" : "var(--success)",
              marginBottom: "var(--space-4)",
            }}
          >
            {actionStatus}
          </div>
        )}

        {/* Pending Submissions Moderation Section */}
        <div style={{ marginBottom: "var(--space-6)" }}>
          <SectionHeader
            title="Citizen Moderation Queue"
            actionText={`${pendingReports.length} pending review`}
          />
          {pendingReports.length === 0 ? (
            <p className="empty" style={{ margin: "var(--space-3) 0" }}>
              No pending citizen reports requiring moderation.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", marginTop: "var(--space-3)" }}>
              {pendingReports.map((rpt) => (
                <div
                  key={rpt.id}
                  style={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    padding: "var(--space-3) var(--space-4)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)", flexWrap: "wrap", gap: "4px" }}>
                    <div>
                      <span className="mono" style={{ fontSize: "11px", color: "var(--accent)" }}>{rpt.public_id}</span>
                      <h4 style={{ margin: "2px 0", fontSize: "14px" }}>{rpt.title}</h4>
                    </div>
                    <span className="badge badge-warning" style={{ fontSize: "10px" }}>{rpt.moderation_status}</span>
                  </div>
                  <p className="muted" style={{ fontSize: "12px", margin: "4px 0" }}>{rpt.description}</p>
                  <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginBottom: "var(--space-3)" }}>
                    Location: {rpt.address_reference || `${rpt.latitude.toFixed(4)}, ${rpt.longitude.toFixed(4)}`} · Reporter: {rpt.guest_pseudonym || "Anonymous Resident"}
                  </div>
                  <div className="action-group">
                    <button
                      onClick={() => handleModerateReport(rpt.id, "APPROVED")}
                      className="button-primary btn-sm"
                    >
                      Approve Report
                    </button>
                    <button
                      onClick={() => handleModerateReport(rpt.id, "REJECTED")}
                      className="btn-outline btn-sm"
                    >
                      Reject Report
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Duplicate Correlation & Consolidation Section */}
        <SectionHeader
          title="Duplicate Correlation & Consolidation"
          actionText={`${candidates.length} candidate pairs`}
        />

        {loading ? (
          <p className="muted">Loading duplicate candidates...</p>
        ) : candidates.length === 0 ? (
          <p className="empty">No pending duplicate candidates. All reported observations are resolved or verified as distinct incidents.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", marginTop: "var(--space-3)" }}>
            {candidates.map((cand) => {
              // Extract genuine algorithm reasons from verified backend data
              let reasons: string[] = [];
              try {
                const parsed = JSON.parse(cand.explanation || "{}");
                if (Array.isArray(parsed.reasons)) {
                  reasons = parsed.reasons;
                }
              } catch {
                if (cand.explanation && typeof cand.explanation === "string" && !cand.explanation.startsWith("{")) {
                  reasons = [cand.explanation];
                }
              }

              // Fallback only to genuine attributes, NEVER inventing timeframe
              if (reasons.length === 0) {
                reasons.push(`Proximity: ${cand.distance_meters.toFixed(1)}m apart`);
                if (cand.category_score === 1.0) {
                  reasons.push("Identical infrastructure category");
                }
                if (cand.text_score > 0.15) {
                  reasons.push(`Text similarity: ${(cand.text_score * 100).toFixed(0)}%`);
                }
              }

              return (
                <div
                  key={cand.id}
                  style={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    padding: "var(--space-4)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)", flexWrap: "wrap", gap: "8px" }}>
                    <div style={{ fontWeight: 600, fontSize: "14px" }}>
                      Candidate Pair · {(cand.composite_score * 100).toFixed(0)}% Match
                    </div>
                    <div className="font-mono" style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                      Distance: {cand.distance_meters.toFixed(1)}m
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "var(--space-3)", marginBottom: "var(--space-3)" }}>
                    <div style={{ background: "var(--surface-muted)", padding: "var(--space-3)", border: "1px solid var(--border)" }}>
                      <span className="muted" style={{ fontSize: "11px", display: "block", marginBottom: "2px" }}>Incoming Citizen Report</span>
                      <code style={{ fontWeight: 600, fontSize: "12px" }}>{cand.report_id}</code>
                    </div>
                    <div style={{ background: "var(--surface-muted)", padding: "var(--space-3)", border: "1px solid var(--border)" }}>
                      <span className="muted" style={{ fontSize: "11px", display: "block", marginBottom: "2px" }}>Existing Case</span>
                      <code style={{ fontWeight: 600, fontSize: "12px" }}>{cand.target_case?.public_id || cand.target_case_id}</code>
                      {cand.target_case?.title && (
                        <div style={{ fontSize: "12px", marginTop: "2px" }}>{cand.target_case.title}</div>
                      )}
                    </div>
                  </div>

                  <div style={{
                    background: "var(--surface-muted)",
                    padding: "var(--space-3)",
                    marginBottom: "var(--space-3)",
                    fontSize: "12px",
                    border: "1px solid var(--border)",
                  }}>
                    <strong style={{ display: "block", marginBottom: "4px", fontSize: "11px", color: "var(--text-secondary)" }}>
                      Matching Evidence:
                    </strong>
                    <ul style={{ margin: 0, paddingLeft: "18px" }}>
                      {reasons.map((r, idx) => (
                        <li key={idx} style={{ marginBottom: "2px" }}>{r}</li>
                      ))}
                    </ul>
                  </div>

                  {/* Reviewer Adjudication Actions */}
                  <div className="action-group" style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
                    <input
                      type="text"
                      placeholder="Reviewer consolidation note..."
                      value={decisionNotes[cand.id] || ""}
                      onChange={(e) => setDecisionNotes({ ...decisionNotes, [cand.id]: e.target.value })}
                      style={{ flex: "1 1 220px", minWidth: "180px" }}
                    />

                    <button
                      onClick={() => handleDecision(cand.id, "APPROVE")}
                      className="button-primary btn-sm"
                    >
                      Consolidate into Case
                    </button>

                    <button
                      onClick={() => handleDecision(cand.id, "REJECT")}
                      className="btn-outline btn-sm"
                    >
                      Separate as Independent
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
};
