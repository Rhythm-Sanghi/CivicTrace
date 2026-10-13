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

  // Verification dispute / confirmation form state
  const [verificationOutcome, setVerificationOutcome] = useState<string>("CONFIRMED_FIXED");
  const [verificationNotes, setVerificationNotes] = useState<string>("");
  const [verifierName, setVerifierName] = useState<string>("");
  const [verificationSubmitting, setVerificationSubmitting] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<string>("");

  const loadData = async () => {
    if (!id) return;
    try {
      const c = await api.getCase(id);
      setCaseItem(c);
      try {
        const evts = await api.getCaseEvents(id);
        setEvents(evts);
      } catch (e) {
        console.error("Events error", e);
      }
      try {
        const val = await api.verifyLedger(id);
        setLedgerValidation(val);
      } catch (e) {
        console.error("Ledger validation error", e);
      }
    } catch (err: any) {
      console.error("Failed to load case", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [id]);

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

  if (loading) {
    return (
      <div className="workspace">
        <p className="muted">Opening local case dossier...</p>
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

  return (
    <>
      {/* 1. BENCHLIGHT COMPACT PAGE HEADER */}
      <PageHeading
        index="02"
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
        {/* 2. FLAT MEASUREMENT METRIC STRIP */}
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

        {/* 3. OPERATIONAL DOCK (Role Actions) */}
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
              <strong>Operational Dock ({user.role}):</strong> State is{" "}
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
                  onClick={async () => {
                    try {
                      const updated = await api.transitionCase(caseItem.id, "IN_PROGRESS", "Dispute sustained; ordered department rework");
                      setCaseItem(updated);
                      loadData();
                    } catch (err: any) {
                      alert(`Error: ${err.message}`);
                    }
                  }}
                  className="button-primary btn-sm"
                >
                  Order Department Rework
                </button>
              )}

              {(user.role === "OPERATOR" || user.role === "ADMINISTRATOR") && (caseItem.state === "ASSIGNED" || caseItem.state === "IN_PROGRESS") && (
                <button
                  onClick={async () => {
                    const summary = window.prompt("Work Summary:", "Completed required repair operations.");
                    if (!summary) return;
                    const actions = window.prompt("Actions Taken:", "Repaired defect, cleared debris.");
                    if (!actions) return;
                    try {
                      await api.submitResolutionClaim(caseItem.id, {
                        work_summary: summary,
                        actions_taken: actions,
                      });
                      loadData();
                    } catch (err: any) {
                      alert(`Error: ${err.message}`);
                    }
                  }}
                  className="button-primary btn-sm"
                >
                  File Resolution Claim
                </button>
              )}
            </div>
          </div>
        )}

        {/* 4. CRYPTOGRAPHIC LEDGER HEALTH STATUS */}
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

        {/* 5. INVESTIGATION WORKSPACE (3 Columns: Provenance | Timeline | Verification) */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "minmax(260px, 1fr) minmax(360px, 1.8fr) minmax(300px, 1.2fr)",
          gap: "var(--space-5)",
          alignItems: "start",
        }}>
          {/* COLUMN 1: CASE SUMMARY & PROVENANCE */}
          <div>
            <SectionHeader index="01" title="Case summary & provenance" />

            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "var(--space-4)" }}>
              <div style={{ marginBottom: "var(--space-3)" }}>
                <label>Physical location</label>
                <div style={{ fontWeight: 600 }}>{caseItem.address_reference}</div>
              </div>

              <div style={{ marginBottom: "var(--space-3)" }}>
                <label>WGS84 Coordinates</label>
                <code className="numeric">
                  LAT: {caseItem.latitude.toFixed(6)}<br />
                  LON: {caseItem.longitude.toFixed(6)}
                </code>
              </div>

              <div style={{ marginBottom: "var(--space-3)" }}>
                <label>Independent submissions</label>
                <div>{caseItem.report_count} verified citizen report(s)</div>
              </div>

              <div style={{ marginBottom: "var(--space-3)" }}>
                <label>First reported</label>
                <div className="numeric" style={{ fontSize: "12px" }}>
                  {new Date(caseItem.created_at).toLocaleString()}
                </div>
              </div>

              <div style={{ borderTop: "1px solid var(--border)", paddingTop: "var(--space-3)", marginTop: "var(--space-3)" }}>
                <label>Verification protocol</label>
                <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: 0, lineHeight: 1.45 }}>
                  CivicTrace requires 2 distinct citizen accounts or reviewer audit to close an uncontested case. Any adverse citizen inspection immediately sets status to DISPUTED.
                </p>
              </div>
            </div>
          </div>

          {/* COLUMN 2: TIMELINE */}
          <div>
            <SectionHeader
              index="02"
              title={`Append-Only Accountability Timeline (${events.length} Events)`}
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
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                      <code style={{ fontSize: "11px", fontWeight: 600 }}>EVENT #{evt.event_index}</code>
                      <span className="numeric" style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                        {new Date(evt.created_at).toLocaleString()}
                      </span>
                    </div>

                    <div style={{ fontWeight: 600, fontSize: "13px", color: "var(--text-primary)" }}>
                      {evt.event_type.replace(/_/g, " ")}
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "6px" }}>
                      Recorded by: <strong>{evt.public_actor_label}</strong>
                    </div>

                    <div style={{
                      background: "var(--surface-muted)",
                      padding: "6px var(--space-2)",
                      fontSize: "11px",
                      fontFamily: "var(--font-mono)",
                      color: "var(--text-primary)",
                      overflowX: "auto",
                      marginBottom: "6px",
                    }}>
                      {Object.entries(payload).map(([k, v]) => (
                        <div key={k}>
                          <strong>{k}:</strong> {typeof v === "object" ? JSON.stringify(v) : String(v)}
                        </div>
                      ))}
                    </div>

                    <div style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "10px",
                      color: "var(--text-muted)",
                      fontFamily: "var(--font-mono)",
                    }}>
                      <span>PREV: {evt.previous_event_hash.substring(0, 16)}...</span>
                      <span>HASH: {evt.current_event_hash.substring(0, 16)}...</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* COLUMN 3: CITIZEN VERIFICATION STATION */}
          <div>
            <SectionHeader index="03" title="Independent Citizen Verification" />

            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "var(--space-4)" }}>
              <p style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: 1.45, marginBottom: "var(--space-3)" }}>
                Have you inspected this location? In CivicTrace, operator claims do not close a case. Citizen verification confirms whether the defect is genuinely repaired.
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
                  <label htmlFor="outcome-select">Observation Outcome</label>
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
                  <label htmlFor="pseudonym-input">Inspector Pseudonym or Reference</label>
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
                  <label htmlFor="notes-textarea">Evidence Notes & Inspection Details</label>
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
                  {verificationSubmitting ? "Submitting..." : "Submit Verification Observation"}
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
