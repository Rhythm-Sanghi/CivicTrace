import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, getCurrentUser, type Case, type CaseEvent } from "../../lib/api";
import { StatusStamp, SectionHeader } from "../../components/FieldPrimitives";
import {
  ShieldCheck,
  Download,
  ShieldAlert,
  Send,
} from "lucide-react";

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

  const loadData = () => {
    if (!id) return;
    Promise.all([
      api.getCase(id),
      api.getCaseEvents(id),
      api.verifyLedger(id),
    ])
      .then(([c, evts, val]) => {
        setCaseItem(c);
        setEvents(evts);
        setLedgerValidation(val);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
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
    return <div style={{ padding: "40px 0" }}>Loading case evidence ledger...</div>;
  }

  if (!caseItem) {
    return <div style={{ padding: "40px 0" }}>Case not found.</div>;
  }

  return (
    <div>
      {/* 1. SIGNATURE SCREEN: DISTINCTIVE DARK-INK CASE DOSSIER HEADER */}
      <div style={{
        backgroundColor: "var(--color-ink-rail)",
        color: "#FFF",
        borderRadius: "var(--radius-sm)",
        border: "1px solid var(--color-ink-rail-border)",
        padding: "20px 24px",
        marginBottom: "20px",
      }}>
        {/* Top Reference & Quick Export Bar */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "10px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{
              fontFamily: "var(--font-family-mono)",
              fontSize: "13px",
              backgroundColor: "rgba(255, 255, 255, 0.1)",
              padding: "2px 8px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid rgba(255, 255, 255, 0.2)",
              color: "#FFF",
            }}>
              {caseItem.public_id}
            </span>
            <StatusStamp state={caseItem.state} />
            <span style={{ color: "var(--color-ink-rail-muted)", fontSize: "12px" }}>
              Category: <strong style={{ color: "#FFF" }}>{caseItem.category?.name}</strong>
            </span>
          </div>

          <a
            href={`http://localhost:8000/api/v1/cases/${caseItem.public_id}/export`}
            className="btn btn-outline btn-sm"
            style={{ backgroundColor: "rgba(255, 255, 255, 0.08)", color: "#FFF", borderColor: "rgba(255, 255, 255, 0.2)" }}
            download
          >
            <Download size={13} /> Export Cryptographic Evidence Package (ZIP)
          </a>
        </div>

        {/* Master Case Title & Description */}
        <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#FFF", lineHeight: 1.25, letterSpacing: "-0.01em" }}>
          {caseItem.title}
        </h1>
        <p style={{ marginTop: "8px", fontSize: "14px", color: "#C6CEC5", lineHeight: 1.55, maxWidth: "1000px" }}>
          {caseItem.description}
        </p>

        {/* Dense Technical Metadata Strip */}
        <div style={{
          marginTop: "16px",
          paddingTop: "14px",
          borderTop: "1px solid rgba(255, 255, 255, 0.12)",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "14px",
          fontSize: "12px",
        }}>
          <div>
            <span style={{ color: "var(--color-ink-rail-muted)", display: "block", fontSize: "11px", textTransform: "uppercase" }}>Location Reference</span>
            <span style={{ color: "#FFF", fontWeight: 500 }}>{caseItem.address_reference}</span>
          </div>

          <div>
            <span style={{ color: "var(--color-ink-rail-muted)", display: "block", fontSize: "11px", textTransform: "uppercase" }}>WGS84 Coordinates</span>
            <span style={{ color: "#FFF", fontFamily: "var(--font-family-mono)" }}>
              {caseItem.latitude.toFixed(5)}, {caseItem.longitude.toFixed(5)}
            </span>
          </div>

          <div>
            <span style={{ color: "var(--color-ink-rail-muted)", display: "block", fontSize: "11px", textTransform: "uppercase" }}>Corroborated Reports</span>
            <span style={{ color: "#FFF", fontWeight: 600 }}>{caseItem.report_count} citizen observation(s)</span>
          </div>

          <div>
            <span style={{ color: "var(--color-ink-rail-muted)", display: "block", fontSize: "11px", textTransform: "uppercase" }}>Civic Priority Score</span>
            <span style={{ color: "#9BC0D6", fontWeight: 700, fontFamily: "var(--font-family-mono)" }}>
              {caseItem.priority_score.toFixed(1)} / 10 ({caseItem.priority_band})
            </span>
          </div>
        </div>

        {/* Contextual Role Operations Panel */}
        {user && (user.role === "REVIEWER" || user.role === "ADMINISTRATOR" || user.role === "OPERATOR") && (
          <div style={{
            marginTop: "14px",
            padding: "10px 14px",
            backgroundColor: "rgba(0, 0, 0, 0.3)",
            borderRadius: "var(--radius-sm)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "10px",
            border: "1px solid rgba(255, 255, 255, 0.1)",
          }}>
            <div style={{ fontSize: "12px", color: "#C6CEC5" }}>
              <strong>Operational Dock ({user.role}):</strong> State is <span className="mono-id" style={{ backgroundColor: "#000", color: "#FFF", borderColor: "#444" }}>{caseItem.state.replace(/_/g, " ")}</span>
            </div>

            <div style={{ display: "flex", gap: "8px" }}>
              {(user.role === "REVIEWER" || user.role === "ADMINISTRATOR") && caseItem.state === "SUBMITTED" && (
                <button
                  onClick={async () => {
                    await api.transitionCase(caseItem.id, "VERIFIED", "Reviewer ground corroboration complete");
                    loadData();
                  }}
                  className="btn btn-primary btn-sm"
                >
                  Verify Case &rarr;
                </button>
              )}

              {(user.role === "REVIEWER" || user.role === "ADMINISTRATOR") && caseItem.state === "DISPUTED" && (
                <button
                  onClick={async () => {
                    try {
                      const updated = await api.transitionCase(caseItem.id, "IN_PROGRESS", "Dispute sustained; ordered department rework");
                      setCaseItem(updated);
                      await loadData();
                    } catch (err: any) {
                      alert(`Error: ${err.message}`);
                    }
                  }}
                  className="btn btn-primary btn-sm"
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
                  className="btn btn-sm"
                  style={{ backgroundColor: "var(--color-attention-orange)", color: "#FFF" }}
                >
                  File Resolution Claim &rarr;
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 2. CRYPTOGRAPHIC LEDGER HEALTH STATUS */}
      {ledgerValidation && (
        <div style={{
          backgroundColor: ledgerValidation.is_valid ? "var(--color-verified-green-subtle)" : "var(--color-disputed-red-subtle)",
          border: `1px solid ${ledgerValidation.is_valid ? "var(--color-verified-green)" : "var(--color-disputed-red)"}`,
          padding: "12px 18px",
          borderRadius: "var(--radius-sm)",
          marginBottom: "20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "10px",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            {ledgerValidation.is_valid ? (
              <ShieldCheck size={20} color="var(--color-verified-green)" />
            ) : (
              <ShieldAlert size={20} color="var(--color-disputed-red)" />
            )}
            <div>
              <div style={{ fontWeight: 600, fontSize: "13px", color: ledgerValidation.is_valid ? "var(--color-verified-green)" : "var(--color-disputed-red)" }}>
                {ledgerValidation.is_valid ? "Cryptographic Ledger Verified Intact" : "Ledger Tamper Detected!"}
              </div>
              <div style={{ fontSize: "12px", color: "var(--color-text-secondary)" }}>
                {ledgerValidation.is_valid
                  ? `All ${ledgerValidation.total_events} sequential events verify with zero breaks in SHA-256 hash chaining.`
                  : ledgerValidation.error_message}
              </div>
            </div>
          </div>

          {ledgerValidation.latest_event_hash && (
            <div style={{ fontFamily: "var(--font-family-mono)", fontSize: "11px", color: "var(--color-text-secondary)" }}>
              HEAD HASH: {ledgerValidation.latest_event_hash.substring(0, 24)}...
            </div>
          )}
        </div>
      )}

      {/* 3. RESPONSIVE TECHNICAL INVESTIGATION WORKSPACE (3 Columns: Narrative/Provenance | Chronological Timeline | Verification Inspector) */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "minmax(280px, 1fr) minmax(380px, 1.8fr) minmax(320px, 1.2fr)",
        gap: "20px",
        alignItems: "start",
      }}>
        {/* COLUMN 1: NARRATIVE & PROVENANCE LEDGER */}
        <div style={{
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          overflow: "hidden",
        }}>
          <SectionHeader title="Geographic Provenance" />

          <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "14px", fontSize: "13px" }}>
            <div>
              <span style={{ fontSize: "11px", textTransform: "uppercase", fontWeight: 600, color: "var(--color-text-muted)" }}>
                Physical Location
              </span>
              <div style={{ fontWeight: 600, marginTop: "2px" }}>{caseItem.address_reference}</div>
            </div>

            <div>
              <span style={{ fontSize: "11px", textTransform: "uppercase", fontWeight: 600, color: "var(--color-text-muted)" }}>
                WGS84 Coordinates
              </span>
              <div style={{ fontFamily: "var(--font-family-mono)", fontSize: "12px", marginTop: "2px" }}>
                LAT: {caseItem.latitude.toFixed(6)}<br />
                LON: {caseItem.longitude.toFixed(6)}
              </div>
            </div>

            <div>
              <span style={{ fontSize: "11px", textTransform: "uppercase", fontWeight: 600, color: "var(--color-text-muted)" }}>
                Independent Submissions
              </span>
              <div style={{ fontWeight: 600, marginTop: "2px" }}>{caseItem.report_count} verified citizen report(s)</div>
            </div>

            <div>
              <span style={{ fontSize: "11px", textTransform: "uppercase", fontWeight: 600, color: "var(--color-text-muted)" }}>
                First Reported Date
              </span>
              <div style={{ marginTop: "2px" }}>{new Date(caseItem.created_at).toLocaleString()}</div>
            </div>

            <div style={{ borderTop: "1px solid var(--color-border-subtle)", paddingTop: "12px" }}>
              <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--color-text-secondary)", textTransform: "uppercase" }}>
                Verification Protocol
              </div>
              <p style={{ fontSize: "12px", color: "var(--color-text-secondary)", marginTop: "4px", lineHeight: 1.5 }}>
                CivicTrace requires 2 distinct citizen accounts or reviewer audit to close an uncontested case. Any adverse citizen inspection immediately sets status to DISPUTED.
              </p>
            </div>
          </div>
        </div>

        {/* COLUMN 2: APPEND-ONLY CHRONOLOGICAL ACTIVITY TIMELINE */}
        <div style={{
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          overflow: "hidden",
        }}>
          <SectionHeader title={`Append-Only Accountability Timeline (${events.length} Events)`} />

          <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
            {events.map((evt) => {
              const payload = JSON.parse(evt.payload_json || "{}");
              const borderAccent =
                evt.event_type.includes("DISPUTE")
                  ? "var(--color-disputed-red)"
                  : evt.event_type.includes("VERIFIED") || evt.event_type.includes("RESOLVED")
                  ? "var(--color-verified-green)"
                  : evt.event_type.includes("CLAIM")
                  ? "var(--color-attention-orange)"
                  : evt.event_type.includes("ASSIGN") || evt.event_type.includes("IN_PROGRESS")
                  ? "var(--color-civic-blue)"
                  : "var(--color-border-strong)";

              return (
                <div
                  key={evt.id}
                  style={{
                    backgroundColor: "var(--color-surface-elevated)",
                    border: "1px solid var(--color-border)",
                    borderLeft: `4px solid ${borderAccent}`,
                    borderRadius: "var(--radius-sm)",
                    padding: "12px 14px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                    <span className="mono-id">EVENT #{evt.event_index}</span>
                    <span style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>
                      {new Date(evt.created_at).toLocaleString()}
                    </span>
                  </div>

                  <div style={{ fontWeight: 600, fontSize: "13px", color: "var(--color-text-primary)" }}>
                    {evt.event_type.replace(/_/g, " ")}
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--color-text-secondary)", marginBottom: "6px" }}>
                    Recorded by: <strong>{evt.public_actor_label}</strong>
                  </div>

                  {/* Formatted Event Details */}
                  <div style={{
                    backgroundColor: "#FFF",
                    border: "1px solid var(--color-border-subtle)",
                    padding: "8px 10px",
                    borderRadius: "var(--radius-sm)",
                    fontSize: "12px",
                    fontFamily: "var(--font-family-mono)",
                    color: "var(--color-text-primary)",
                    overflowX: "auto",
                  }}>
                    {Object.entries(payload).map(([k, v]) => (
                      <div key={k}>
                        <strong>{k}:</strong> {typeof v === "object" ? JSON.stringify(v) : String(v)}
                      </div>
                    ))}
                  </div>

                  {/* Hash Link Stamp */}
                  <div style={{
                    marginTop: "6px",
                    fontSize: "10px",
                    color: "var(--color-text-muted)",
                    fontFamily: "var(--font-family-mono)",
                    display: "flex",
                    justifyContent: "space-between",
                  }}>
                    <span>PREV: {evt.previous_event_hash.substring(0, 16)}...</span>
                    <span>HASH: {evt.current_event_hash.substring(0, 16)}...</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* COLUMN 3: INDEPENDENT CITIZEN VERIFICATION STATION */}
        <div style={{
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          overflow: "hidden",
        }}>
          <SectionHeader title="Independent Citizen Verification" />

          <div style={{ padding: "16px" }}>
            <p style={{ fontSize: "13px", color: "var(--color-text-secondary)", lineHeight: 1.5, marginBottom: "14px" }}>
              Have you inspected this location? In CivicTrace, operator claims do not close a case. Citizen verification confirms whether the defect is genuinely repaired.
            </p>

            {feedbackMsg && (
              <div style={{
                padding: "10px",
                borderRadius: "var(--radius-sm)",
                fontSize: "12px",
                marginBottom: "12px",
                backgroundColor: feedbackMsg.includes("Error") ? "var(--color-disputed-red-subtle)" : "var(--color-verified-green-subtle)",
                color: feedbackMsg.includes("Error") ? "var(--color-disputed-red)" : "var(--color-verified-green)",
              }}>
                {feedbackMsg}
              </div>
            )}

            <form onSubmit={handleVerificationSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                  Observation Outcome
                </label>
                <select
                  value={verificationOutcome}
                  onChange={(e) => setVerificationOutcome(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "7px 10px",
                    fontSize: "13px",
                    border: "1px solid var(--color-border)",
                    borderRadius: "var(--radius-sm)",
                    backgroundColor: "var(--color-surface)",
                  }}
                >
                  <option value="CONFIRMED_FIXED">Confirmed Fixed (Repaired satisfactorily)</option>
                  <option value="STILL_UNRESOLVED">Still Unresolved (Defect persists)</option>
                  <option value="PARTIALLY_FIXED">Partially Fixed (Substandard repair)</option>
                  <option value="UNABLE_TO_VERIFY">Unable to Verify (Inaccessible)</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                  Inspector Pseudonym or Reference
                </label>
                <input
                  type="text"
                  placeholder="e.g. Local Resident, Daily Commuter"
                  value={verifierName}
                  onChange={(e) => setVerifierName(e.target.value)}
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
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                  Evidence Notes & Inspection Details
                </label>
                <textarea
                  rows={3}
                  placeholder="Describe what you observed on site..."
                  value={verificationNotes}
                  onChange={(e) => setVerificationNotes(e.target.value)}
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

              <button
                type="submit"
                disabled={verificationSubmitting}
                className="btn btn-primary"
                style={{ width: "100%", marginTop: "2px" }}
              >
                <Send size={13} /> {verificationSubmitting ? "Submitting..." : "Submit Verification Observation"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
