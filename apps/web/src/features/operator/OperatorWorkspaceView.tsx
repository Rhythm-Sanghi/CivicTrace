import React, { useEffect, useState } from "react";
import { api, type Case } from "../../lib/api";
import { PageHeading, SectionHeader, StatusStamp } from "../../components/FieldPrimitives";
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
    <div>
      <PageHeading
        eyebrow="PUBLIC WORKS OPERATOR TERMINAL &bull; INDORE DISPATCH"
        title="Active Work Orders & Resolution Claims"
        description="Log repair operations and file completion evidence. Claims remain in Awaiting Community Verification until verified by the public."
      />

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

      <div style={{ display: "grid", gridTemplateColumns: "minmax(320px, 1.2fr) minmax(420px, 1.8fr)", gap: "20px" }}>
        {/* Work Orders List */}
        <div style={{
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          overflow: "hidden",
        }}>
          <SectionHeader title={`Work Order Queue (${assignedCases.length})`} />

          <div style={{ display: "flex", flexDirection: "column" }}>
            {assignedCases.map((c) => (
              <div
                key={c.id}
                onClick={() => setSelectedCase(c)}
                style={{
                  padding: "12px 16px",
                  borderBottom: "1px solid var(--color-border-subtle)",
                  cursor: "pointer",
                  backgroundColor: selectedCase?.id === c.id ? "var(--color-civic-blue-subtle)" : undefined,
                  transition: "background-color 100ms",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <span className="mono-id">{c.public_id}</span>
                  <StatusStamp state={c.state} size="sm" />
                </div>
                <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--color-text-primary)", marginBottom: "2px" }}>
                  {c.title}
                </div>
                <div style={{ fontSize: "12px", color: "var(--color-text-secondary)" }}>
                  📍 {c.address_reference}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Claim Action Station */}
        {selectedCase ? (
          <div style={{
            backgroundColor: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            overflow: "hidden",
          }}>
            <div style={{
              backgroundColor: "var(--color-ink-rail)",
              color: "#FFF",
              padding: "12px 18px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}>
              <div>
                <span className="mono-id" style={{ backgroundColor: "rgba(255, 255, 255, 0.1)", color: "#FFF", borderColor: "rgba(255, 255, 255, 0.2)" }}>
                  {selectedCase.public_id}
                </span>
                <span style={{ marginLeft: "8px", fontSize: "12px", color: "var(--color-ink-rail-muted)" }}>
                  OPERATIONAL CLAIM
                </span>
              </div>
              <StatusStamp state={selectedCase.state} size="sm" />
            </div>

            <div style={{ padding: "20px" }}>
              <h2 style={{ fontSize: "18px", fontWeight: 700, color: "var(--color-text-primary)" }}>
                {selectedCase.title}
              </h2>
              <p style={{ fontSize: "13px", color: "var(--color-text-secondary)", marginTop: "4px", lineHeight: 1.5 }}>
                {selectedCase.description}
              </p>

              <div style={{
                margin: "14px 0",
                padding: "10px 14px",
                backgroundColor: "var(--color-surface-elevated)",
                border: "1px solid var(--color-border-subtle)",
                borderRadius: "var(--radius-sm)",
                fontSize: "12px",
                color: "var(--color-text-secondary)",
              }}>
                📍 Location: <strong>{selectedCase.address_reference}</strong> &bull; Lat: {selectedCase.latitude.toFixed(5)}, Lon: {selectedCase.longitude.toFixed(5)}
              </div>

              <form onSubmit={handleClaimSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: 600, textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "4px" }}>
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
                      padding: "7px 10px",
                      fontSize: "13px",
                      border: "1px solid var(--color-border)",
                      borderRadius: "var(--radius-sm)",
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: 600, textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "4px" }}>
                    Technical Actions Taken & Materials
                  </label>
                  <textarea
                    rows={4}
                    placeholder="Document specific engineering actions, crew details, materials applied..."
                    value={actionsTaken}
                    onChange={(e) => setActionsTaken(e.target.value)}
                    required
                    style={{
                      width: "100%",
                      padding: "7px 10px",
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
                  <Wrench size={13} /> {submitting ? "Submitting Claim..." : "File Resolution Claim"}
                </button>
              </form>
            </div>
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
  );
};
