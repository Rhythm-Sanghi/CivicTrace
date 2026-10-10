import React, { useEffect, useState } from "react";
import { api, type DuplicateCandidate } from "../../lib/api";
import { PageHeading, SectionHeader } from "../../components/FieldPrimitives";
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
    <div>
      <PageHeading
        eyebrow="COMMUNITY REVIEWER DESK &bull; DUPLICATE CORRELATION"
        title="Duplicate Correlation & Case Consolidation"
        description="Review candidate report pairs identified by the deterministic duplicate engine. Approving merges observations into one verified public case with full provenance."
      />

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
                  borderRadius: "var(--radius-sm)",
                  overflow: "hidden",
                }}
              >
                <SectionHeader title={`Candidate Pair &bull; ${(cand.composite_score * 100).toFixed(0)}% Similarity Match`}>
                  <span style={{ fontSize: "11px", color: "#9BC0D6" }}>
                    Distance: {cand.distance_meters.toFixed(1)}m
                  </span>
                </SectionHeader>

                <div style={{ padding: "18px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "10px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span className="mono-id">REPORT: {cand.report_id.substring(0, 8)}...</span>
                      <span>&rarr;</span>
                      <span className="mono-id">CASE: {cand.target_case_id.substring(0, 8)}...</span>
                    </div>

                    <div style={{ fontFamily: "var(--font-family-mono)", fontSize: "11px", color: "var(--color-text-secondary)" }}>
                      Spatial: {(cand.spatial_score * 100).toFixed(0)}% | Text: {(cand.text_score * 100).toFixed(0)}%
                    </div>
                  </div>

                  {/* Decision Rationale */}
                  <div style={{
                    backgroundColor: "var(--color-surface-elevated)",
                    border: "1px solid var(--color-border-subtle)",
                    padding: "10px 14px",
                    borderRadius: "var(--radius-sm)",
                    marginBottom: "14px",
                    fontSize: "12px",
                  }}>
                    <strong style={{ display: "block", marginBottom: "4px", textTransform: "uppercase", fontSize: "10px", color: "var(--color-text-secondary)" }}>
                      Deterministic Algorithm Rationale:
                    </strong>
                    <ul style={{ margin: 0, paddingLeft: "16px", display: "flex", flexDirection: "column", gap: "3px" }}>
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
                  <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                    <input
                      type="text"
                      placeholder="Add reviewer consolidation note..."
                      value={decisionNotes[cand.id] || ""}
                      onChange={(e) => setDecisionNotes({ ...decisionNotes, [cand.id]: e.target.value })}
                      style={{
                        flex: 1,
                        minWidth: "240px",
                        padding: "6px 10px",
                        fontSize: "13px",
                        border: "1px solid var(--color-border)",
                        borderRadius: "var(--radius-sm)",
                      }}
                    />

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
  );
};
