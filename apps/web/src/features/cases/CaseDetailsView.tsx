import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, getCurrentUser, type Case, type CaseEvent } from "../../lib/api";
import { PageHeading, StatusStamp, MetricStrip, SectionHeader } from "../../components/FieldPrimitives";

export const CaseDetailsView: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [caseItem, setCaseItem] = useState<Case | null>(null);
  const [events, setEvents] = useState<CaseEvent[]>([]);
  const user = getCurrentUser();
  const [ledgerValidation, setLedgerValidation] = useState<{
    is_valid: boolean;
    total_events: number;
    error_message?: string;
    latest_event_hash?: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  // In-page operator claim dialog state (replaces prompt/alert)
  const [showClaimModal, setShowClaimModal] = useState(false);
  const [claimWorkSummary, setClaimWorkSummary] = useState("Completed required repair operations.");
  const [claimActionsTaken, setClaimActionsTaken] = useState("Repaired defect, cleared debris.");
  const [claimSubmitting, setClaimSubmitting] = useState(false);
  const [claimError, setClaimError] = useState("");

  // In-page reviewer rework state
  const [showReworkModal, setShowReworkModal] = useState(false);
  const [reworkNotes, setReworkNotes] = useState("Dispute sustained; ordered department rework.");
  const [reworkSubmitting, setReworkSubmitting] = useState(false);
  const [reworkError, setReworkError] = useState("");

  // Verification observation form state
  const [verificationOutcome, setVerificationOutcome] = useState<string>("CONFIRMED_FIXED");
  const [verificationNotes, setVerificationNotes] = useState<string>("");
  const [verifierName, setVerifierName] = useState<string>("");
  const [verificationSubmitting, setVerificationSubmitting] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<string>("");

  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const loadData = () => setRefreshTrigger((prev) => prev + 1);

  useEffect(() => {
    if (!id) return;
    let isCancelled = false;

    const fetchData = async () => {
      try {
        const c = await api.getCase(id);
        if (isCancelled) return;
        setCaseItem(c);
        try {
          const evts = await api.getCaseEvents(id);
          if (!isCancelled) setEvents(evts);
        } catch (e) {
          console.error("Events error", e);
        }
        try {
          const val = await api.verifyLedger(id);
          if (!isCancelled) setLedgerValidation(val);
        } catch (e) {
          console.error("Ledger validation error", e);
        }
      } catch (err: any) {
        console.error("Failed to load case", err);
      } finally {
        if (!isCancelled) setLoading(false);
      }
    };

    fetchData();
    return () => {
      isCancelled = true;
    };
  }, [id, refreshTrigger]);

  const handleVerificationSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!caseItem) return;
    setVerificationSubmitting(true);
    setFeedbackMsg("");

    try {
      await api.submitVerification(caseItem.id, {
        outcome: verificationOutcome,
        notes: verificationNotes,
        guest_pseudonym: verifierName || undefined,
      });
      setVerificationNotes("");
      setFeedbackMsg("Verification observation successfully submitted to append-only ledger!");
      loadData();
    } catch (err: any) {
      setFeedbackMsg(`Error: ${err.message}`);
    } finally {
      setVerificationSubmitting(false);
    }
  };

  const handleClaimSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!caseItem) return;
    setClaimSubmitting(true);
    setClaimError("");

    try {
      await api.submitResolutionClaim(caseItem.id, {
        work_summary: claimWorkSummary,
        actions_taken: claimActionsTaken,
      });
      setShowClaimModal(false);
      loadData();
    } catch (err: any) {
      setClaimError(err.message || "Failed to submit resolution claim.");
    } finally {
      setClaimSubmitting(false);
    }
  };

  const handleReworkSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!caseItem) return;
    setReworkSubmitting(true);
    setReworkError("");

    try {
      const updated = await api.transitionCase(caseItem.id, "IN_PROGRESS", reworkNotes);
      setCaseItem(updated);
      setShowReworkModal(false);
      loadData();
    } catch (err: any) {
      setReworkError(err.message || "Failed to order department rework.");
    } finally {
      setReworkSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="workspace">
        <p className="muted">Opening case dossier...</p>
      </div>
    );
  }

  if (!caseItem) {
    return (
      <div className="workspace">
        <p className="empty">Case not found.</p>
      </div>
    );
  }

  const isVerificationEligible =
    (caseItem.state === "AWAITING_VERIFICATION" || caseItem.state === "DISPUTED") &&
    user?.role !== "OPERATOR";

  return (
    <>
      <PageHeading
        title={caseItem.public_id}
        description={`${caseItem.title} · ${caseItem.address_reference}`}
      >
        <a
          href={`/api/v1/cases/${caseItem.public_id}/export`}
          className="button-primary"
          download
        >
          Export evidence package
        </a>
      </PageHeading>

      <div className="workspace">
        <MetricStrip
          metrics={[
            {
              label: "Workflow state",
              value: caseItem.state.replace(/_/g, " "),
            },
            {
              label: "Category",
              value: caseItem.category?.name || "—",
            },
            {
              label: "Civic priority",
              value: `${caseItem.priority_score.toFixed(1)} / 10 · ${caseItem.priority_band}`,
              accentColor: "var(--accent)",
            },
            {
              label: "Corroborated reports",
              value: `${caseItem.report_count} observations`,
            },
          ]}
        />

        {/* Operational Dock (Authorized Roles) */}
        {user && (user.role === "REVIEWER" || user.role === "ADMINISTRATOR" || user.role === "OPERATOR") && (
          <div style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            padding: "var(--space-3) var(--space-4)",
            marginBottom: "var(--space-4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "var(--space-2)",
          }}>
            <div style={{ fontSize: "12px", color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: "8px" }}>
              <strong>Operational actions ({user.role}):</strong> Current state is{" "}
              <StatusStamp state={caseItem.state} />
            </div>

            <div className="action-group">
              {(user.role === "REVIEWER" || user.role === "ADMINISTRATOR") && caseItem.state === "SUBMITTED" && (
                <button
                  onClick={async () => {
                    await api.transitionCase(caseItem.id, "VERIFIED", "Reviewer ground corroboration complete");
                    loadData();
                  }}
                  className="button-primary btn-sm"
                >
                  Verify Case
                </button>
              )}

              {(user.role === "REVIEWER" || user.role === "ADMINISTRATOR") && (caseItem.state === "VERIFIED" || caseItem.state === "SUBMITTED") && (
                <button
                  onClick={async () => {
                    await api.transitionCase(caseItem.id, "ASSIGNED", "Dispatched to Line Crew");
                    loadData();
                  }}
                  className="button-primary btn-sm"
                >
                  Dispatch to Department
                </button>
              )}

              {(user.role === "REVIEWER" || user.role === "ADMINISTRATOR") && caseItem.state === "DISPUTED" && (
                <button
                  onClick={() => setShowReworkModal(true)}
                  className="button-primary btn-sm"
                >
                  Order Department Rework
                </button>
              )}

              {(user.role === "OPERATOR" || user.role === "ADMINISTRATOR") && (caseItem.state === "ASSIGNED" || caseItem.state === "IN_PROGRESS") && (
                <button
                  onClick={() => setShowClaimModal(true)}
                  className="button-primary btn-sm"
                >
                  File Resolution Claim
                </button>
              )}
            </div>
          </div>
        )}

        {/* In-Page Modal: Operator Resolution Claim */}
        {showClaimModal && (
          <div style={{
            background: "var(--surface)",
            border: "1px solid var(--accent)",
            borderLeft: "3px solid var(--accent)",
            padding: "var(--space-4)",
            marginBottom: "var(--space-4)",
          }}>
            <h3 style={{ fontSize: "14px", margin: "0 0 var(--space-2)" }}>File Resolution Claim</h3>
            {claimError && (
              <div role="alert" style={{ color: "var(--danger)", fontSize: "12px", marginBottom: "var(--space-2)" }}>
                {claimError}
              </div>
            )}
            <form onSubmit={handleClaimSubmit} style={{ margin: 0 }}>
              <div style={{ marginBottom: "var(--space-2)" }}>
                <label htmlFor="modal-work-summary" style={{ fontSize: "12px" }}>Work Summary</label>
                <input
                  id="modal-work-summary"
                  type="text"
                  value={claimWorkSummary}
                  onChange={(e) => setClaimWorkSummary(e.target.value)}
                  required
                  style={{ width: "100%" }}
                />
              </div>
              <div style={{ marginBottom: "var(--space-3)" }}>
                <label htmlFor="modal-actions-taken" style={{ fontSize: "12px" }}>Actions Taken</label>
                <textarea
                  id="modal-actions-taken"
                  rows={3}
                  value={claimActionsTaken}
                  onChange={(e) => setClaimActionsTaken(e.target.value)}
                  required
                  style={{ width: "100%" }}
                />
              </div>
              <div className="action-group">
                <button type="submit" disabled={claimSubmitting} className="button-primary btn-sm">
                  {claimSubmitting ? "Submitting..." : "Submit Claim"}
                </button>
                <button type="button" onClick={() => setShowClaimModal(false)} className="btn-outline btn-sm">
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* In-Page Modal: Reviewer Rework Order */}
        {showReworkModal && (
          <div style={{
            background: "var(--surface)",
            border: "1px solid var(--warning)",
            borderLeft: "3px solid var(--warning)",
            padding: "var(--space-4)",
            marginBottom: "var(--space-4)",
          }}>
            <h3 style={{ fontSize: "14px", margin: "0 0 var(--space-2)" }}>Order Department Rework</h3>
            {reworkError && (
              <div role="alert" style={{ color: "var(--danger)", fontSize: "12px", marginBottom: "var(--space-2)" }}>
                {reworkError}
              </div>
            )}
            <form onSubmit={handleReworkSubmit} style={{ margin: 0 }}>
              <div style={{ marginBottom: "var(--space-3)" }}>
                <label htmlFor="modal-rework-notes" style={{ fontSize: "12px" }}>Rework Instructions / Reason</label>
                <textarea
                  id="modal-rework-notes"
                  rows={2}
                  value={reworkNotes}
                  onChange={(e) => setReworkNotes(e.target.value)}
                  required
                  style={{ width: "100%" }}
                />
              </div>
              <div className="action-group">
                <button type="submit" disabled={reworkSubmitting} className="button-primary btn-sm">
                  {reworkSubmitting ? "Updating..." : "Confirm Rework Dispatch"}
                </button>
                <button type="button" onClick={() => setShowReworkModal(false)} className="btn-outline btn-sm">
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Cryptographic Ledger Health Verification */}
        {ledgerValidation && (
          <div
            role="status"
            style={{
              background: "var(--surface)",
              border: `1px solid var(--border)`,
              borderLeft: `3px solid ${ledgerValidation.is_valid ? "var(--success)" : "var(--danger)"}`,
              padding: "var(--space-3) var(--space-4)",
              marginBottom: "var(--space-5)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "8px",
            }}
          >
            <div>
              <div style={{ fontWeight: 600, fontSize: "13px", color: ledgerValidation.is_valid ? "var(--success)" : "var(--danger)" }}>
                {ledgerValidation.is_valid ? "Cryptographic Ledger Verified Intact" : "Ledger Tamper Detected!"}
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
                {ledgerValidation.is_valid
                  ? `All ${ledgerValidation.total_events} sequential events verify with zero breaks in SHA-256 hash chaining.`
                  : ledgerValidation.error_message}
              </div>
            </div>

            {ledgerValidation.latest_event_hash && (
              <div className="numeric" style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                HEAD HASH: {ledgerValidation.latest_event_hash.substring(0, 24)}...
              </div>
            )}
          </div>
        )}

        {/* Investigation Workspace Grid */}
        <div className="responsive-grid-3">
          {/* Column 1: Case Summary & Provenance */}
          <div>
            <SectionHeader title="Case details" />

            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "var(--space-4)" }}>
              <div style={{ marginBottom: "var(--space-3)" }}>
                <label>Location</label>
                <div style={{ fontWeight: 600 }}>{caseItem.address_reference}</div>
              </div>

              <div style={{ marginBottom: "var(--space-3)" }}>
                <label>Coordinates</label>
                <code className="numeric">
                  {caseItem.latitude.toFixed(6)}, {caseItem.longitude.toFixed(6)}
                </code>
              </div>

              <div style={{ marginBottom: "var(--space-3)" }}>
                <label>Reported observations</label>
                <div>{caseItem.report_count} verified citizen report(s)</div>
              </div>

              <div style={{ marginBottom: "var(--space-3)" }}>
                <label>First reported</label>
                <div className="numeric" style={{ fontSize: "12px" }}>
                  {new Date(caseItem.created_at).toLocaleString()}
                </div>
              </div>

              <div style={{ borderTop: "1px solid var(--border)", paddingTop: "var(--space-3)", marginTop: "var(--space-3)" }}>
                <label>Verification policy</label>
                <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: 0, lineHeight: 1.45 }}>
                  CivicTrace records all citizen observations directly into the append-only ledger. Under conservative identity policy, community observations provide public accountability, and formal automatic closure requires trusted identity credentials or authorized reviewer sign-off.
                </p>
              </div>
            </div>
          </div>

          {/* Column 2: Case History Timeline */}
          <div>
            <SectionHeader
              title={`Case history (${events.length} events)`}
            />

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
              {events.map((evt) => {
                let payload: Record<string, any> = {};
                try {
                  payload = typeof evt.payload_json === "string" ? JSON.parse(evt.payload_json || "{}") : (evt.payload_json || {});
                } catch {
                  payload = { raw: String(evt.payload_json) };
                }
                let borderAccent = "var(--border)";
                if (evt.event_type.includes("DISPUTE")) borderAccent = "var(--danger)";
                else if (evt.event_type.includes("VERIFIED") || evt.event_type.includes("RESOLVED")) borderAccent = "var(--success)";
                else if (evt.event_type.includes("CLAIM")) borderAccent = "var(--warning)";
                else if (evt.event_type.includes("ASSIGN") || evt.event_type.includes("IN_PROGRESS")) borderAccent = "var(--information)";

                const displayType = evt.event_type.replace(/_/g, " ");

                return (
                  <div
                    key={evt.id}
                    style={{
                      background: "var(--surface)",
                      border: "1px solid var(--border)",
                      borderLeft: `3px solid ${borderAccent}`,
                      padding: "var(--space-3) var(--space-4)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px", flexWrap: "wrap", gap: "4px" }}>
                      <code style={{ fontSize: "11px", fontWeight: 600 }}>EVENT #{evt.event_index}</code>
                      <span className="numeric" style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                        {new Date(evt.created_at).toLocaleString()}
                      </span>
                    </div>

                    <div style={{ fontWeight: 600, fontSize: "13px", color: "var(--text-primary)" }}>
                      {displayType}
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "4px" }}>
                      Recorded by: <strong>{evt.public_actor_label}</strong>
                    </div>

                    {(payload.work_summary || payload.notes || payload.outcome) && (
                      <div style={{ fontSize: "12px", color: "var(--text-primary)", marginBottom: "6px" }}>
                        {payload.work_summary && <div>{payload.work_summary}</div>}
                        {payload.actions_taken && <div className="muted">{payload.actions_taken}</div>}
                        {payload.notes && <div>{payload.notes}</div>}
                      </div>
                    )}

                    {/* Expandable Cryptographic Data Proofs */}
                    <details style={{ marginTop: "6px", fontSize: "11px", color: "var(--text-secondary)" }}>
                      <summary style={{ cursor: "pointer", fontWeight: 600 }}>
                        Technical verification data
                      </summary>
                      <div style={{
                        background: "var(--surface-muted)",
                        padding: "var(--space-2)",
                        marginTop: "4px",
                        border: "1px solid var(--border)",
                        fontFamily: "var(--font-mono)",
                        overflowX: "auto",
                        fontSize: "10px",
                      }}>
                        <div><strong>Schema:</strong> v{evt.schema_version} · <strong>Index:</strong> #{evt.event_index}</div>
                        <div><strong>Previous Hash:</strong> {evt.previous_event_hash}</div>
                        <div><strong>Event Hash:</strong> {evt.current_event_hash}</div>
                        <div style={{ marginTop: "4px" }}><strong>Payload JSON:</strong> {typeof evt.payload_json === "string" ? evt.payload_json : JSON.stringify(evt.payload_json)}</div>
                      </div>
                    </details>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Column 3: Check a Reported Repair (Citizen Verification) */}
          <div>
            <SectionHeader title="Check a reported repair" />

            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "var(--space-4)" }}>
              {isVerificationEligible ? (
                <>
                  <p style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: 1.45, marginBottom: "var(--space-3)" }}>
                    Have you inspected this location? In CivicTrace, operator claims do not automatically close a case. Independent citizen verification confirms whether the defect is genuinely fixed.
                  </p>

                  {feedbackMsg && (
                    <div style={{
                      padding: "var(--space-2) var(--space-3)",
                      fontSize: "12px",
                      marginBottom: "var(--space-3)",
                      borderLeft: `2px solid ${feedbackMsg.includes("Error") ? "var(--danger)" : "var(--success)"}`,
                      background: "var(--surface-muted)",
                      color: feedbackMsg.includes("Error") ? "var(--danger)" : "var(--success)",
                    }}>
                      {feedbackMsg}
                    </div>
                  )}

                  <form onSubmit={handleVerificationSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                    <div>
                      <label htmlFor="outcome-select">Observation outcome</label>
                      <select
                        id="outcome-select"
                        value={verificationOutcome}
                        onChange={(e) => setVerificationOutcome(e.target.value)}
                        style={{ width: "100%" }}
                      >
                        <option value="CONFIRMED_FIXED">Confirmed Fixed (Repaired satisfactorily)</option>
                        <option value="STILL_UNRESOLVED">Still Unresolved (Defect persists)</option>
                        <option value="PARTIALLY_FIXED">Partially Fixed (Substandard repair)</option>
                        <option value="UNABLE_TO_VERIFY">Unable to Verify (Inaccessible)</option>
                      </select>
                    </div>

                    <div>
                      <label htmlFor="pseudonym-input">Observer name or reference (optional)</label>
                      <input
                        id="pseudonym-input"
                        type="text"
                        placeholder="e.g. Local Resident, Daily Commuter"
                        value={verifierName}
                        onChange={(e) => setVerifierName(e.target.value)}
                        style={{ width: "100%" }}
                      />
                    </div>

                    <div>
                      <label htmlFor="notes-textarea">Inspection details & evidence notes *</label>
                      <textarea
                        id="notes-textarea"
                        rows={3}
                        placeholder="Describe what you observed on site..."
                        value={verificationNotes}
                        onChange={(e) => setVerificationNotes(e.target.value)}
                        required
                        style={{ width: "100%" }}
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={verificationSubmitting}
                      className="button-primary"
                      style={{ width: "100%" }}
                    >
                      {verificationSubmitting ? "Submitting..." : "Submit verification observation"}
                    </button>
                  </form>
                </>
              ) : (
                <div style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                  <div style={{ fontWeight: 600, color: "var(--text-primary)", marginBottom: "4px" }}>
                    {caseItem.state === "RESOLVED"
                      ? "Case Resolved"
                      : caseItem.state === "IN_PROGRESS" || caseItem.state === "ASSIGNED"
                      ? "Repair in Progress"
                      : user?.role === "OPERATOR"
                      ? "Operator Verification Restriction"
                      : "Awaiting Repair Dispatch"}
                  </div>
                  <p style={{ margin: "0 0 var(--space-3)" }}>
                    {caseItem.state === "RESOLVED"
                      ? "This infrastructure case has been verified and resolved. If the defect has recurred at this location, please submit a new report."
                      : caseItem.state === "IN_PROGRESS" || caseItem.state === "ASSIGNED"
                      ? "Crews are currently addressing this issue. Verification opens once public works operators file a resolution claim."
                      : user?.role === "OPERATOR"
                      ? "Department operators cannot verify their own resolution claims. Independent citizen verification is required."
                      : "This case is currently under review. Independent citizen verification opens after repair work is completed and claimed."}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
