import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, getCurrentUser, type Case, type CaseEvent } from "../../lib/api";
import {
  ShieldCheck,
  History,
  FileCheck,
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
    return <div className="workspace-container" style={{ padding: "40px 0" }}>Loading case evidence ledger...</div>;
  }

  if (!caseItem) {
    return <div className="workspace-container" style={{ padding: "40px 0" }}>Case not found.</div>;
  }

  return (
    <div style={{ padding: "var(--space-6) 0 var(--space-12)" }}>
      <div className="workspace-container">
        
        {/* Document Breadcrumb & Action Bar */}
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
          paddingBottom: "var(--space-3)",
          borderBottom: "1px solid var(--color-border)",
          marginBottom: "var(--space-5)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Link to="/explorer" style={{ color: "var(--color-text-secondary)", textDecoration: "none", fontSize: "13px" }}>
              &larr; Back to Cases
            </Link>
            <span style={{ color: "var(--color-border-strong)" }}>/</span>
            <span className="mono-id">{caseItem.public_id}</span>
            <span className={`archival-stamp stamp-${caseItem.state.toLowerCase()}`}>
              {caseItem.state.replace("_", " ")}
            </span>
          </div>

          <a
            href={`http://localhost:8000/api/v1/cases/${caseItem.public_id}/export`}
            className="btn btn-outline btn-sm"
            download
          >
            <Download size={13} /> Export Cryptographic Evidence Package (ZIP)
          </a>
        </div>

        {/* Master Case Header Banner */}
        <div style={{
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          padding: "24px",
          marginBottom: "var(--space-6)",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "20px" }}>
            <div style={{ flex: "1 1 650px" }}>
              <div style={{ fontSize: "12px", color: "var(--color-civic-blue)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "4px" }}>
                {caseItem.category?.name} &bull; INDORE MUNICIPAL WARD 34
              </div>
              <h1 style={{ fontSize: "clamp(22px, 2vw, 30px)", fontWeight: 700, color: "var(--color-text-primary)", lineHeight: 1.25 }}>
                {caseItem.title}
              </h1>
              <p style={{ marginTop: "10px", fontSize: "14px", color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
                {caseItem.description}
              </p>
            </div>

            <div style={{
              backgroundColor: "var(--color-surface-elevated)",
              border: "1px solid var(--color-border)",
              padding: "16px 20px",
              borderRadius: "var(--radius-sm)",
              minWidth: "220px",
              textAlign: "right",
            }}>
              <div style={{ fontSize: "11px", textTransform: "uppercase", fontWeight: 600, color: "var(--color-text-secondary)" }}>
                CIVIC PRIORITY SCORE
              </div>
              <div style={{ fontSize: "28px", fontWeight: 700, color: "var(--color-civic-blue)", fontFamily: "var(--font-family-mono)", marginTop: "2px" }}>
                {caseItem.priority_score.toFixed(1)} <span style={{ fontSize: "15px", color: "var(--color-text-muted)" }}>/ 10</span>
              </div>
              <div style={{ marginTop: "4px" }}>
                <span className="mono-id">BAND: {caseItem.priority_band}</span>
              </div>
            </div>
          </div>

          {/* Contextual Role Operations Dock */}
          {user && (user.role === "REVIEWER" || user.role === "ADMINISTRATOR" || user.role === "OPERATOR") && (
            <div style={{
              marginTop: "18px",
              padding: "12px 16px",
              backgroundColor: "var(--color-surface-elevated)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "12px",
            }}>
              <div style={{ fontSize: "13px" }}>
                <strong>Role Action Dock ({user.role}):</strong> Current case state is <span className="mono-id">{caseItem.state}</span>
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
                  <>
                    <button
                      onClick={async () => {
                        await api.transitionCase(caseItem.id, "IN_PROGRESS", "Dispute sustained; ordered department rework");
                        loadData();
                      }}
                      className="btn btn-primary btn-sm"
                    >
                      Order Department Rework (In Progress)
                    </button>
                    <button
                      onClick={async () => {
                        await api.transitionCase(caseItem.id, "REOPENED", "Case reopened following community dispute");
                        loadData();
                      }}
                      className="btn btn-outline btn-sm"
                    >
                      Reopen Case
                    </button>
                  </>
                )}

                {(user.role === "REVIEWER" || user.role === "ADMINISTRATOR") && caseItem.state === "RESOLVED" && (
                  <button
                    onClick={async () => {
                      await api.transitionCase(caseItem.id, "REOPENED", "Reviewer reopening case due to renewed community reports");
                      loadData();
                    }}
                    className="btn btn-outline btn-sm"
                  >
                    Reopen Case
                  </button>
                )}

                {(user.role === "OPERATOR" || user.role === "ADMINISTRATOR") && (caseItem.state === "ASSIGNED" || caseItem.state === "IN_PROGRESS") && (
                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    {caseItem.state === "ASSIGNED" && (
                      <button
                        onClick={async () => {
                          await api.transitionCase(caseItem.id, "IN_PROGRESS", "Field repair operations underway");
                          loadData();
                        }}
                        className="btn btn-primary btn-sm"
                      >
                        Start Work (In Progress)
                      </button>
                    )}
                    <button
                      onClick={async () => {
                        const summary = window.prompt("Work Summary:", "Completed required repair operations and electrical verification.");
                        if (!summary) return;
                        const actions = window.prompt("Actions Taken:", "Replaced hardware, tested electrical load, cleared site debris.");
                        if (!actions) return;
                        try {
                          await api.submitResolutionClaim(caseItem.id, {
                            work_summary: summary,
                            actions_taken: actions,
                          });
                          loadData();
                        } catch (err: any) {
                          alert(`Error claiming resolution: ${err.message}`);
                        }
                      }}
                      className="btn btn-outline btn-sm"
                      style={{ borderColor: "var(--color-attention-orange)", color: "var(--color-attention-orange)" }}
                    >
                      File Resolution Claim &rarr;
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Cryptographic Ledger Health Strip */}
        {ledgerValidation && (
          <div style={{
            backgroundColor: ledgerValidation.is_valid ? "var(--color-verified-green-subtle)" : "var(--color-disputed-red-subtle)",
            border: `1px solid ${ledgerValidation.is_valid ? "var(--color-verified-green)" : "var(--color-disputed-red)"}`,
            padding: "14px 20px",
            borderRadius: "var(--radius-sm)",
            marginBottom: "var(--space-6)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "12px",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              {ledgerValidation.is_valid ? (
                <ShieldCheck size={22} color="var(--color-verified-green)" />
              ) : (
                <ShieldAlert size={22} color="var(--color-disputed-red)" />
              )}
              <div>
                <div style={{ fontWeight: 600, fontSize: "14px", color: ledgerValidation.is_valid ? "var(--color-verified-green)" : "var(--color-disputed-red)" }}>
                  {ledgerValidation.is_valid ? "Cryptographic Ledger Verified Intact" : "Ledger Tamper Detected!"}
                </div>
                <div style={{ fontSize: "12px", color: "var(--color-text-secondary)" }}>
                  {ledgerValidation.is_valid
                    ? `All ${ledgerValidation.total_events} events verify in strict sequential SHA-256 hash chaining.`
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

        {/* Studio Utility 3-Column Dossier Workspace on Desktop:
            Col 1 (25%): Evidence Provenance & Location
            Col 2 (45%): Append-Only Chronological Timeline
            Col 3 (30%): Independent Verification & Claim Station
        */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "minmax(280px, 1fr) minmax(380px, 1.8fr) minmax(320px, 1.2fr)",
          gap: "24px",
          alignItems: "start",
        }}>
          {/* COLUMN 1: EVIDENCE PROVENANCE & LOCAL CONTEXT */}
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div style={{
              backgroundColor: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              padding: "18px",
            }}>
              <div className="grid-header" style={{ margin: "-18px -18px 14px", borderRadius: "var(--radius-sm) var(--radius-sm) 0 0" }}>
                <span>Geographic Provenance</span>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "12px", fontSize: "13px" }}>
                <div>
                  <span style={{ color: "var(--color-text-muted)", fontSize: "11px", textTransform: "uppercase", fontWeight: 600 }}>Location</span>
                  <div style={{ fontWeight: 600, marginTop: "2px" }}>{caseItem.address_reference || "Indore Central Ward"}</div>
                </div>

                <div>
                  <span style={{ color: "var(--color-text-muted)", fontSize: "11px", textTransform: "uppercase", fontWeight: 600 }}>Coordinates (WGS84)</span>
                  <div style={{ fontFamily: "var(--font-family-mono)", fontSize: "12px", marginTop: "2px" }}>
                    LAT: {caseItem.latitude.toFixed(5)}<br />LON: {caseItem.longitude.toFixed(5)}
                  </div>
                </div>

                <div>
                  <span style={{ color: "var(--color-text-muted)", fontSize: "11px", textTransform: "uppercase", fontWeight: 600 }}>Corroborated Reports</span>
                  <div style={{ fontWeight: 600, marginTop: "2px" }}>{caseItem.report_count} independent submission(s)</div>
                </div>

                <div>
                  <span style={{ color: "var(--color-text-muted)", fontSize: "11px", textTransform: "uppercase", fontWeight: 600 }}>Submitted On</span>
                  <div style={{ marginTop: "2px" }}>{new Date(caseItem.created_at).toLocaleDateString()}</div>
                </div>

                <div>
                  <span style={{ color: "var(--color-text-muted)", fontSize: "11px", textTransform: "uppercase", fontWeight: 600 }}>Resolution Integrity</span>
                  <div style={{ fontWeight: 600, marginTop: "2px", color: caseItem.state === "RESOLVED" ? "var(--color-verified-green)" : caseItem.state === "DISPUTED" ? "var(--color-disputed-red)" : "var(--color-attention-orange)" }}>
                    {caseItem.state === "RESOLVED" ? "Independently Verified Fixed" : caseItem.state === "DISPUTED" ? "Claim Disputed by Public" : "Pending Community Verification"}
                  </div>
                </div>
              </div>
            </div>

            <div style={{
              backgroundColor: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              padding: "16px",
            }}>
              <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--color-text-secondary)", marginBottom: "6px" }}>
                Verification Protocol
              </div>
              <div style={{ fontSize: "12px", color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
                CivicTrace requires 2 independent citizen confirmations or administrative audit to auto-resolve. Any dispute observation immediately halts resolution and escalates to DISPUTED.
              </div>
            </div>
          </div>

          {/* COLUMN 2: APPEND-ONLY CHRONOLOGICAL ACTIVITY TIMELINE */}
          <div>
            <div className="grid-header" style={{
              backgroundColor: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderBottom: "none",
              borderRadius: "var(--radius-sm) var(--radius-sm) 0 0",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <History size={14} />
                <span>Append-Only Accountability Timeline ({events.length} Events)</span>
              </div>
            </div>

            <div style={{
              backgroundColor: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: "0 0 var(--radius-sm) var(--radius-sm)",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "14px",
            }}>
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
                      border: "1px solid var(--color-border)",
                      borderLeft: `4px solid ${borderAccent}`,
                      borderRadius: "var(--radius-sm)",
                      padding: "14px",
                      backgroundColor: "var(--color-surface-elevated)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                      <span className="mono-id">EVENT #{evt.event_index}</span>
                      <span style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>
                        {new Date(evt.created_at).toLocaleString()}
                      </span>
                    </div>

                    <div style={{ fontWeight: 600, fontSize: "14px", color: "var(--color-text-primary)", marginTop: "2px" }}>
                      {evt.event_type.replace(/_/g, " ")}
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--color-text-secondary)", marginBottom: "8px" }}>
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
                      marginTop: "8px",
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
            padding: "20px",
          }}>
            <div className="grid-header" style={{ margin: "-20px -20px 16px", borderRadius: "var(--radius-sm) var(--radius-sm) 0 0" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <FileCheck size={14} color="var(--color-verified-green)" />
                <span>Independent Citizen Verification</span>
              </div>
            </div>

            <div style={{ fontSize: "13px", color: "var(--color-text-secondary)", marginBottom: "14px", lineHeight: 1.5 }}>
              Have you inspected this location? In CivicTrace, public works claims do not automatically close a case. Citizen verification confirms whether the defect is genuinely repaired or still persists.
            </div>

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
                    padding: "8px",
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
                    padding: "8px",
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
                    padding: "8px",
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
                style={{ width: "100%" }}
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
