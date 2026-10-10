import React, { useEffect, useState } from "react";
import { api, type DuplicateCandidate } from "../../lib/api";
import { Check, X, Layers } from "lucide-react";

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
    <div style={{ padding: "var(--space-6) 0 var(--space-12)" }}>
      <div className="workspace-container">
        
        {/* Workspace Title */}
        <div style={{
          borderBottom: "1px solid var(--color-border)",
          paddingBottom: "var(--space-4)",
          marginBottom: "var(--space-6)",
        }}>
          <div style={{
            fontFamily: "var(--font-family-mono)",
            fontSize: "var(--font-size-2xs)",
            color: "var(--color-civic-blue)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            fontWeight: 600,
            marginBottom: "4px",
          }}>
            COMMUNITY REVIEWER DESK &bull; DUPLICATE CORRELATION
          </div>
          <h1 style={{ fontSize: "28px", fontWeight: 700, letterSpacing: "-0.02em", color: "var(--color-text-primary)" }}>
            Duplicate Correlation & Case Consolidation
          </h1>
          <p style={{ color: "var(--color-text-secondary)", fontSize: "14px", marginTop: "2px" }}>
            Review candidate report pairs identified by the deterministic duplicate engine. Approving merges observations into one verified public case with full provenance.
          </p>
        </div>

        {actionStatus && (
          <div style={{
            padding: "12px 16px",
            backgroundColor: actionStatus.includes("Error") ? "var(--color-disputed-red-subtle)" : "var(--color-verified-green-subtle)",
            color: actionStatus.includes("Error") ? "var(--color-disputed-red)" : "var(--color-verified-green)",
            borderRadius: "var(--radius-sm)",
            fontSize: "13px",
            marginBottom: "20px",
          }}>
            {actionStatus}
          </div>
        )}

        {loading ? (
          <div>Loading duplicate candidates...</div>
        ) : candidates.length === 0 ? (
          <div style={{
            backgroundColor: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            textAlign: "center",
            padding: "48px 24px",
            color: "var(--color-text-secondary)",
          }}>
            <Layers size={32} color="var(--color-civic-blue)" style={{ margin: "0 auto 12px" }} />
            <h3 style={{ fontSize: "16px", fontWeight: 600, color: "var(--color-text-primary)" }}>
              No Pending Duplicate Candidates
            </h3>
            <p style={{ fontSize: "13px", marginTop: "4px" }}>
              All neighborhood observations have been correlated or verified as independent incidents.
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {candidates.map((cand) => {
              const explanation = JSON.parse(cand.explanation || "{}");
              return (
                <div
                  key={cand.id}
                  style={{
                    backgroundColor: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    borderLeft: "4px solid var(--color-civic-blue)",
                    borderRadius: "var(--radius-sm)",
                    padding: "20px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "14px", marginBottom: "14px" }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span className="mono-id">REPORT: {cand.report_id.substring(0, 8)}...</span>
                        <span>&rarr;</span>
                        <span className="mono-id">CASE: {cand.target_case_id.substring(0, 8)}...</span>
                      </div>
                      <h3 style={{ fontSize: "18px", fontWeight: 600, marginTop: "8px", color: "var(--color-text-primary)" }}>
                        Candidate Similarity: {(cand.composite_score * 100).toFixed(0)}% Match
                      </h3>
                    </div>

                    <div style={{
                      textAlign: "right",
                      fontFamily: "var(--font-family-mono)",
                      fontSize: "12px",
                      backgroundColor: "var(--color-surface-elevated)",
                      padding: "8px 12px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--color-border)",
                    }}>
                      <div>Distance: <strong>{cand.distance_meters.toFixed(1)}m</strong></div>
                      <div style={{ color: "var(--color-text-secondary)", marginTop: "2px" }}>
                        Spatial: {(cand.spatial_score * 100).toFixed(0)}% | Text: {(cand.text_score * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>

                  {/* Explainable Decision Rationale Box */}
                  <div style={{
                    backgroundColor: "var(--color-surface-elevated)",
                    border: "1px solid var(--color-border-subtle)",
                    padding: "12px 16px",
                    borderRadius: "var(--radius-sm)",
                    marginBottom: "16px",
                  }}>
                    <div style={{ fontSize: "11px", fontFamily: "var(--font-family-mono)", textTransform: "uppercase", color: "var(--color-text-secondary)", fontWeight: 600, marginBottom: "6px" }}>
                      Deterministic Algorithm Rationale:
                    </div>
                    <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "13px", color: "var(--color-text-primary)", display: "flex", flexDirection: "column", gap: "4px" }}>
                      {explanation.reasons ? (
                        explanation.reasons.map((r: string, idx: number) => (
                          <li key={idx}>{r}</li>
                        ))
                      ) : (
                        <>
                          <li>Within neighborhood vicinity ({cand.distance_meters.toFixed(1)}m away)</li>
                          <li>Identical infrastructure category</li>
                          <li>Recent concurrent activity (0.0 days apart)</li>
                        </>
                      )}
                    </ul>
                  </div>

                  {/* Action Controls & Reviewer Notes */}
                  <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
                    <input
                      type="text"
                      placeholder="Add reviewer consolidation note..."
                      value={decisionNotes[cand.id] || ""}
                      onChange={(e) => setDecisionNotes({ ...decisionNotes, [cand.id]: e.target.value })}
                      style={{
                        flex: 1,
                        minWidth: "260px",
                        padding: "8px 12px",
                        fontSize: "13px",
                        border: "1px solid var(--color-border)",
                        borderRadius: "var(--radius-sm)",
                      }}
                    />

                    <button
                      onClick={() => handleDecision(cand.id, "APPROVE")}
                      className="btn btn-primary btn-sm"
                    >
                      <Check size={14} /> Consolidate into Case
                    </button>

                    <button
                      onClick={() => handleDecision(cand.id, "REJECT")}
                      className="btn btn-outline btn-sm"
                    >
                      <X size={14} /> Separate as Independent
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

      </div>
    </div>
  );
};
