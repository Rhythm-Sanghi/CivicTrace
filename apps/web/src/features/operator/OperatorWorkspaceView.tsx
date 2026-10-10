import React, { useEffect, useState } from "react";
import { api, type Case } from "../../lib/api";
import { PageHeading, SectionHeader, StatusStamp } from "../../components/FieldPrimitives";

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
    <>
      <PageHeading
        index="06"
        title="Operator terminal"
        description="Active Work Orders & Resolution Claims · Log repair operations and file completion evidence. Claims remain in Awaiting Community Verification until verified by the public."
      />

      <div className="workspace">
        {statusMsg && (
          <div
            role="status"
            style={{
              padding: "var(--space-2) var(--space-3)",
              borderLeft: `2px solid ${statusMsg.includes("Error") ? "var(--danger)" : "var(--success)"}`,
              background: "var(--surface)",
              color: statusMsg.includes("Error") ? "var(--danger)" : "var(--success)",
              marginBottom: "var(--space-4)",
            }}
          >
            {statusMsg}
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "minmax(300px, 1.2fr) minmax(400px, 1.8fr)", gap: "var(--space-5)" }}>
          {/* Work Orders List */}
          <div>
            <SectionHeader index="01" title={`Work Order Queue (${assignedCases.length})`} />

            <div style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              {assignedCases.length === 0 ? (
                <p className="empty" style={{ padding: "var(--space-4)" }}>No pending work orders assigned to this terminal.</p>
              ) : (
                assignedCases.map((c) => {
                  const isSelected = selectedCase?.id === c.id;
                  return (
                    <div
                      key={c.id}
                      onClick={() => setSelectedCase(c)}
                      style={{
                        padding: "var(--space-3)",
                        borderBottom: "1px solid var(--border)",
                        cursor: "pointer",
                        background: isSelected ? "var(--selection)" : "transparent",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                        <code style={{ fontWeight: 600 }}>{c.public_id}</code>
                        <StatusStamp state={c.state} size="sm" />
                      </div>
                      <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
                        {c.title}
                      </div>
                      <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px" }}>
                        {c.address_reference} · Priority: {c.priority_score.toFixed(1)}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Resolution Claim Form */}
          <div>
            <SectionHeader index="02" title="Resolution claim station" />

            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "var(--space-4)" }}>
              {selectedCase ? (
                <form onSubmit={handleClaimSubmit} style={{ margin: 0 }}>
                  <div style={{ marginBottom: "var(--space-3)", paddingBottom: "var(--space-2)", borderBottom: "1px solid var(--border)" }}>
                    <span className="muted" style={{ fontSize: "11px" }}>Selected Case</span>
                    <h3 style={{ margin: "2px 0 0", fontSize: "14px" }}>
                      <code>{selectedCase.public_id}</code> — {selectedCase.title}
                    </h3>
                  </div>

                  <div style={{ marginBottom: "var(--space-3)" }}>
                    <label htmlFor="summary-input">Work summary</label>
                    <input
                      id="summary-input"
                      type="text"
                      placeholder="e.g. Cleared storm debris and patched asphalt cavity"
                      value={workSummary}
                      onChange={(e) => setWorkSummary(e.target.value)}
                      required
                      style={{ width: "100%" }}
                    />
                  </div>

                  <div style={{ marginBottom: "var(--space-3)" }}>
                    <label htmlFor="actions-textarea">Actions taken & technical specifications</label>
                    <textarea
                      id="actions-textarea"
                      rows={4}
                      placeholder="Specify materials applied, measurements, equipment used, and operator crew details..."
                      value={actionsTaken}
                      onChange={(e) => setActionsTaken(e.target.value)}
                      required
                      style={{ width: "100%" }}
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={submitting}
                    className="button-primary"
                    style={{ width: "100%" }}
                  >
                    {submitting ? "Submitting claim..." : "File Resolution Claim"}
                  </button>
                </form>
              ) : (
                <p className="empty">Select a work order from the queue to file resolution evidence.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
