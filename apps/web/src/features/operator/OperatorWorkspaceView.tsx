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
            PUBLIC WORKS OPERATOR TERMINAL &bull; INDORE MUNICIPAL DISPATCH
          </div>
          <h1 style={{ fontSize: "28px", fontWeight: 700, letterSpacing: "-0.02em", color: "var(--color-text-primary)" }}>
            Active Work Orders & Resolution Claims
          </h1>
          <p style={{ color: "var(--color-text-secondary)", fontSize: "14px", marginTop: "2px" }}>
            Log repair operations and file completion evidence. Claims remain in Awaiting Community Verification until verified by the public.
          </p>
        </div>

        {statusMsg && (
          <div style={{
            padding: "12px 16px",
            backgroundColor: statusMsg.includes("Error") ? "var(--color-disputed-red-subtle)" : "var(--color-verified-green-subtle)",
            color: statusMsg.includes("Error") ? "var(--color-disputed-red)" : "var(--color-verified-green)",
            borderRadius: "var(--radius-sm)",
            fontSize: "13px",
            marginBottom: "20px",
          }}>
            {statusMsg}
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "minmax(320px, 1.2fr) minmax(420px, 1.8fr)", gap: "24px" }}>
          {/* Work Orders List (Left) */}
          <div style={{
            backgroundColor: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            overflow: "hidden",
          }}>
            <div className="grid-header">
              <span>Work Order Queue ({assignedCases.length})</span>
            </div>

            <div style={{ display: "flex", flexDirection: "column" }}>
              {assignedCases.map((c) => (
                <div
                  key={c.id}
                  onClick={() => setSelectedCase(c)}
                  style={{
                    padding: "14px 18px",
                    borderBottom: "1px solid var(--color-border-subtle)",
                    cursor: "pointer",
                    backgroundColor: selectedCase?.id === c.id ? "var(--color-civic-blue-subtle)" : undefined,
                    transition: "background-color 120ms",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                    <span className="mono-id">{c.public_id}</span>
                    <span className={`archival-stamp stamp-${c.state.toLowerCase()}`}>
                      {c.state.replace("_", " ")}
                    </span>
                  </div>
                  <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--color-text-primary)", marginBottom: "4px" }}>
                    {c.title}
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--color-text-secondary)" }}>
                    📍 {c.address_reference}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Claim Action Station (Right) */}
          {selectedCase ? (
            <div style={{
              backgroundColor: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              padding: "24px",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <span className="mono-id">{selectedCase.public_id}</span>
                <span className={`archival-stamp stamp-${selectedCase.state.toLowerCase()}`}>
                  {selectedCase.state.replace("_", " ")}
                </span>
              </div>

              <h2 style={{ fontSize: "20px", fontWeight: 700, color: "var(--color-text-primary)" }}>
                {selectedCase.title}
              </h2>
              <p style={{ fontSize: "13px", color: "var(--color-text-secondary)", marginTop: "6px", lineHeight: 1.5 }}>
                {selectedCase.description}
              </p>

              <div style={{
                margin: "18px 0",
                padding: "12px 16px",
                backgroundColor: "var(--color-surface-elevated)",
                border: "1px solid var(--color-border-subtle)",
                borderRadius: "var(--radius-sm)",
                fontSize: "12px",
                color: "var(--color-text-secondary)",
              }}>
                📍 Location: <strong>{selectedCase.address_reference}</strong> &bull; Lat: {selectedCase.latitude.toFixed(5)}, Lon: {selectedCase.longitude.toFixed(5)}
              </div>

              <form onSubmit={handleClaimSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
                    Work Summary / Repair Description
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Completed asphalt repaving and cold-mix patch compaction"
                    value={workSummary}
                    onChange={(e) => setWorkSummary(e.target.value)}
                    required
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      fontSize: "13px",
                      border: "1px solid var(--color-border)",
                      borderRadius: "var(--radius-sm)",
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
                    Technical Actions Taken & Materials Used
                  </label>
                  <textarea
                    rows={4}
                    placeholder="Document specific engineering actions, crew details, materials applied..."
                    value={actionsTaken}
                    onChange={(e) => setActionsTaken(e.target.value)}
                    required
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      fontSize: "13px",
                      border: "1px solid var(--color-border)",
                      borderRadius: "var(--radius-sm)",
                      lineHeight: 1.5,
                    }}
                  />
                </div>

                <div style={{ display: "flex", gap: "10px" }}>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="btn btn-primary"
                  >
                    <Wrench size={14} /> {submitting ? "Submitting Claim..." : "File Resolution Claim"}
                  </button>
                </div>
              </form>
            </div>
          ) : (
            <div style={{
              backgroundColor: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              padding: "40px",
              textAlign: "center",
              color: "var(--color-text-muted)",
            }}>
              Select a work order from the queue to log operations.
            </div>
          )}
        </div>

      </div>
    </div>
  );
};
