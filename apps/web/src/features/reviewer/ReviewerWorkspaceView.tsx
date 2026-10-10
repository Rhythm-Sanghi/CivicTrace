import React, { useEffect, useState } from "react";
import { api, type DuplicateCandidate } from "../../lib/api";
import { Check, X } from "lucide-react";

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
    <div style={{ padding: "var(--space-6) 0" }}>
      <div className="container">
        <div style={{ marginBottom: "var(--space-6)" }}>
          <div style={{
            fontFamily: "var(--font-family-mono)",
            fontSize: "var(--font-size-xs)",
            color: "var(--color-civic-blue)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            fontWeight: 600,
          }}>
            Community Reviewer Desk
          </div>
          <h1 style={{ fontSize: "var(--font-size-xl)", fontWeight: 700 }}>
            Duplicate Correlation & Case Consolidation
          </h1>
          <p style={{ color: "var(--color-text-secondary)", fontSize: "var(--font-size-sm)" }}>
            Review candidate report pairs identified by the deterministic duplicate engine. Approving merges observations into one verified public case with full provenance.
          </p>
        </div>

        {actionStatus && (
          <div style={{
            padding: "10px 14px",
            backgroundColor: actionStatus.includes("Error") ? "var(--color-disputed-red-subtle)" : "var(--color-verified-green-subtle)",
            color: actionStatus.includes("Error") ? "var(--color-disputed-red)" : "var(--color-verified-green)",
            borderRadius: "var(--radius-sm)",
            fontSize: "13px",
            marginBottom: "16px",
          }}>
            {actionStatus}
          </div>
        )}

        {loading ? (
          <div>Loading duplicate candidates...</div>
        ) : candidates.length === 0 ? (
          <div className="card" style={{ textAlign: "center", padding: "40px", color: "var(--color-text-secondary)" }}>
            No pending duplicate candidates require human review. All submissions are correlated!
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {candidates.map((cand) => {
              const explanation = JSON.parse(cand.explanation || "{}");
              return (
                <div key={cand.id} className="card" style={{ borderLeft: "4px solid var(--color-civic-blue)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px", marginBottom: "12px" }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span className="mono-id">REPORT: {cand.report_id.substring(0, 8)}...</span>
                        <span>&rarr;</span>
                        <span className="mono-id">CASE: {cand.target_case_id.substring(0, 8)}...</span>
                      </div>
                      <h3 style={{ fontSize: "16px", fontWeight: 600, marginTop: "6px" }}>
                        Candidate Similarity: {(cand.composite_score * 100).toFixed(0)}% Match
                      </h3>
                    </div>

                    <div style={{ textAlign: "right", fontFamily: "var(--font-family-mono)", fontSize: "12px" }}>
                      <div>Distance: <strong>{cand.distance_meters.toFixed(1)}m</strong></div>
                      <div>Spatial: {(cand.spatial_score * 100).toFixed(0)}% | Text: {(cand.text_score * 100).toFixed(0)}%</div>
                    </div>
                  </div>

                  {/* Engine Explanation Bullets */}
                  <div style={{
                    backgroundColor: "var(--color-surface-elevated)",
                    padding: "10px 14px",
                    borderRadius: "var(--radius-sm)",
                    fontSize: "12px",
                    marginBottom: "14px",
                  }}>
                    <div style={{ fontWeight: 600, marginBottom: "4px", color: "var(--color-text-secondary)" }}>
                      Deterministic Algorithm Rationale:
                    </div>
                    <ul style={{ paddingLeft: "18px", color: "var(--color-text-primary)" }}>
                      {explanation.reasons?.map((r: string, idx: number) => (
                        <li key={idx}>{r}</li>
                      ))}
                    </ul>
                  </div>

                  {/* Reviewer Action Controls */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
                    <input
                      type="text"
                      placeholder="Add reviewer consolidation note..."
                      value={decisionNotes[cand.id] || ""}
                      onChange={(e) => setDecisionNotes({ ...decisionNotes, [cand.id]: e.target.value })}
                      style={{
                        padding: "6px 10px",
                        fontSize: "13px",
                        border: "1px solid var(--color-border)",
                        borderRadius: "var(--radius-sm)",
                        flex: 1,
                        minWidth: "220px",
                      }}
                    />

                    <div style={{ display: "flex", gap: "8px" }}>
                      <button
                        onClick={() => handleDecision(cand.id, "APPROVE")}
                        className="btn btn-primary btn-sm"
                      >
                        <Check size={13} /> Consolidate into Case
                      </button>
                      <button
                        onClick={() => handleDecision(cand.id, "REJECT")}
                        className="btn btn-outline btn-sm"
                      >
                        <X size={13} /> Separate as Independent
                      </button>
                    </div>
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
