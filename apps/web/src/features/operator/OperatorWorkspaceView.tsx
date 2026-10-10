import React, { useEffect, useState } from "react";
import { api, type Case } from "../../lib/api";
import { Wrench } from "lucide-react";

export const OperatorWorkspaceView: React.FC = () => {
  const [assignedCases, setAssignedCases] = useState<Case[]>([]);
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [workSummary, setWorkSummary] = useState<string>("");
  const [actionsTaken, setActionsTaken] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string>("");

  const loadCases = () => {
    api.getCases()
      .then((cases) => {
        const pending = cases.filter((c) =>
          ["ASSIGNED", "IN_PROGRESS", "AWAITING_VERIFICATION"].includes(c.state)
        );
        setAssignedCases(pending);
        if (pending.length > 0 && !selectedCase) setSelectedCase(pending[0]);
      })
      .catch((err) => setStatusMsg(`Error: ${err.message}`));
  };

  useEffect(() => {
    loadCases();
  }, []);

  const handleClaimSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCase) return;
    setSubmitting(true);
    setStatusMsg("");

    try {
      await api.submitResolutionClaim(selectedCase.id, {
        work_summary: workSummary,
        actions_taken: actionsTaken,
      });
      setStatusMsg("Resolution claim filed! Case status updated to Awaiting Verification.");
      setWorkSummary("");
      setActionsTaken("");
      loadCases();
    } catch (err: any) {
      setStatusMsg(`Error: ${err.message}`);
    } finally {
      setSubmitting(false);
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
            Public Works Operator Terminal
          </div>
          <h1 style={{ fontSize: "var(--font-size-xl)", fontWeight: 700 }}>
            Active Work Orders & Resolution Claims
          </h1>
          <p style={{ color: "var(--color-text-secondary)", fontSize: "var(--font-size-sm)" }}>
            Log repair operations and file completion evidence. Claims remain in Awaiting Community Verification until verified by the public.
          </p>
        </div>

        {statusMsg && (
          <div style={{
            padding: "10px 14px",
            backgroundColor: statusMsg.includes("Error") ? "var(--color-disputed-red-subtle)" : "var(--color-verified-green-subtle)",
            color: statusMsg.includes("Error") ? "var(--color-disputed-red)" : "var(--color-verified-green)",
            borderRadius: "var(--radius-sm)",
            fontSize: "13px",
            marginBottom: "16px",
          }}>
            {statusMsg}
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: "20px" }}>
          {/* Work Orders List */}
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>
            <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--color-border)", fontWeight: 600, fontSize: "14px" }}>
              Work Queue ({assignedCases.length})
            </div>
            {assignedCases.map((c) => (
              <div
                key={c.id}
                onClick={() => setSelectedCase(c)}
                style={{
                  padding: "12px 16px",
                  borderBottom: "1px solid var(--color-border-subtle)",
                  cursor: "pointer",
                  backgroundColor: selectedCase?.id === c.id ? "var(--color-civic-blue-subtle)" : undefined,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="mono-id">{c.public_id}</span>
                  <span className={`archival-stamp stamp-${c.state.toLowerCase()}`}>
                    {c.state.replace("_", " ")}
                  </span>
                </div>
                <div style={{ fontWeight: 600, fontSize: "14px", marginTop: "4px" }}>{c.title}</div>
                <div style={{ fontSize: "11px", color: "var(--color-text-secondary)" }}>
                  📍 {c.address_reference}
                </div>
              </div>
            ))}
          </div>

          {/* Claim Submission Station */}
          <div>
            {selectedCase ? (
              <div className="card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "14px" }}>
                  <div>
                    <span className="mono-id">{selectedCase.public_id}</span>
                    <h2 style={{ fontSize: "17px", fontWeight: 700, marginTop: "4px" }}>
                      {selectedCase.title}
                    </h2>
                  </div>
                  <span className={`archival-stamp stamp-${selectedCase.state.toLowerCase()}`}>
                    {selectedCase.state}
                  </span>
                </div>

                <div style={{
                  padding: "10px",
                  backgroundColor: "var(--color-surface-elevated)",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "13px",
                  marginBottom: "16px",
                }}>
                  {selectedCase.description}
                </div>

                <form onSubmit={handleClaimSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "4px" }}>
                      Summary of Work Completed
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Replaced 3 burned-out LED fixtures and reset circuit breaker"
                      value={workSummary}
                      onChange={(e) => setWorkSummary(e.target.value)}
                      required
                      minLength={10}
                      style={{
                        width: "100%",
                        padding: "8px 10px",
                        fontSize: "13px",
                        border: "1px solid var(--color-border)",
                        borderRadius: "var(--radius-sm)",
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "4px" }}>
                      Technical Actions & Materials Used
                    </label>
                    <textarea
                      rows={4}
                      placeholder="Detail specific technical measures, crew dispatched, test readings..."
                      value={actionsTaken}
                      onChange={(e) => setActionsTaken(e.target.value)}
                      required
                      minLength={10}
                      style={{
                        width: "100%",
                        padding: "8px 10px",
                        fontSize: "13px",
                        border: "1px solid var(--color-border)",
                        borderRadius: "var(--radius-sm)",
                        lineHeight: 1.5,
                      }}
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={submitting}
                    className="btn btn-primary"
                    style={{ alignSelf: "flex-start" }}
                  >
                    <Wrench size={14} /> {submitting ? "Recording Claim..." : "Submit Resolution Claim for Community Verification"}
                  </button>
                </form>
              </div>
            ) : (
              <div className="card" style={{ padding: "40px", textAlign: "center", color: "var(--color-text-muted)" }}>
                Select a case from the queue to record work actions
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
