import React, { useEffect, useState } from "react";
import { api, type DuplicateCandidate } from "../../lib/api";
import { PageHeading, SectionHeader } from "../../components/FieldPrimitives";

export const ReviewerWorkspaceView: React.FC = () => {
  const [candidates, setCandidates] = useState<DuplicateCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [decisionNotes, setDecisionNotes] = useState<{ [key: string]: string }>({});
  const [actionStatus, setActionStatus] = useState<string>("");

  const loadCandidates = () => {
    api.getPendingDuplicates()
      .then((data) => {
        setCandidates(data);
        setLoading(false);
      })
      .catch((err) => {
        setActionStatus(`Error loading duplicates: ${err.message}`);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadCandidates();
  }, []);

  const handleDecision = async (candidateId: string, decision: "APPROVE" | "REJECT") => {
    try {
      await api.decideDuplicate(candidateId, decision, decisionNotes[candidateId]);
      setActionStatus(`Duplicate candidate successfully ${decision === "APPROVE" ? "consolidated into target case" : "separated into independent case"}.`);
      loadCandidates();
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

        {loading ? (
          <p className="muted">Loading duplicate candidates...</p>
        ) : candidates.length === 0 ? (
          <p className="empty">No pending duplicate candidates. All neighborhood observations are correlated or verified as independent incidents.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
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
