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
      setActionStatus(`Duplicate candidate successfully ${decision === "APPROVE" ? "consolidated into target case" : "separated into independent case"}.`);
      loadData();
    } catch (err: any) {
      setActionStatus(`Error: ${err.message}`);
    }
  };

  return (
    <>
      <PageHeading
        index="05"
        title="Reviewer desk"
        description="Duplicate Correlation & Case Consolidation · Review candidate report pairs identified by the deterministic duplicate engine. Approving merges observations into one verified public case with full provenance."
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
            index="01"
            title={`Citizen Moderation Queue · ${pendingReports.length} Pending Review`}
            actionText="Pending Citizen Observations"
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
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)" }}>
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

        <SectionHeader
          index="02"
          title={`Duplicate Correlation & Consolidation · ${candidates.length} Pairs`}
          actionText="Deterministic Match Engine"
        />

        {loading ? (
          <p className="muted">Loading duplicate candidates...</p>
        ) : candidates.length === 0 ? (
          <p className="empty">No pending duplicate candidates. All neighborhood observations are correlated or verified as independent incidents.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", marginTop: "var(--space-3)" }}>
            {candidates.map((cand) => {
              const explanation = JSON.parse(cand.explanation || "{}");
              return (
                <div
                  key={cand.id}
                  style={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    padding: "var(--space-4)",
                  }}
                >
                  <SectionHeader
                    index="01"
                    title={`Candidate Pair · ${(cand.composite_score * 100).toFixed(0)}% Similarity Match`}
                    actionText={`Distance: ${cand.distance_meters.toFixed(1)}m`}
                  />

                  <div style={{ display: "flex", justifyContent: "space-between", margin: "var(--space-3) 0", flexWrap: "wrap", gap: "var(--space-2)" }}>
                    <div>
                      <span className="muted" style={{ fontSize: "11px", display: "block" }}>Incoming Citizen Report</span>
                      <code style={{ fontWeight: 600 }}>{cand.report_id}</code>
                    </div>
                    <div>
                      <span className="muted" style={{ fontSize: "11px", display: "block" }}>Target Incident Dossier</span>
                      <code style={{ fontWeight: 600 }}>{cand.target_case?.public_id}</code>: {cand.target_case?.title}
                    </div>
                  </div>

                  <div style={{
                    background: "var(--surface-muted)",
                    padding: "var(--space-3)",
                    marginBottom: "var(--space-3)",
                    fontSize: "12px",
                  }}>
                    <strong style={{ display: "block", marginBottom: "4px", fontSize: "11px", color: "var(--text-secondary)" }}>
                      Deterministic Algorithm Rationale:
                    </strong>
                    <ul style={{ margin: 0, paddingLeft: "16px" }}>
                      {explanation.reasons ? (
                        explanation.reasons.map((r: string, idx: number) => (
                          <li key={idx}>{r}</li>
                        ))
                      ) : (
                        <>
                          <li>Within neighborhood vicinity ({cand.distance_meters.toFixed(1)}m away)</li>
                          <li>Identical infrastructure category</li>
                          <li>Concurrent timeframe (0.0 days apart)</li>
                        </>
                      )}
                    </ul>
                  </div>

                  {/* Actions Bar */}
                  <div className="action-group">
                    <input
                      type="text"
                      placeholder="Add reviewer consolidation note..."
                      value={decisionNotes[cand.id] || ""}
                      onChange={(e) => setDecisionNotes({ ...decisionNotes, [cand.id]: e.target.value })}
                      style={{ flex: 1, minWidth: "240px" }}
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
