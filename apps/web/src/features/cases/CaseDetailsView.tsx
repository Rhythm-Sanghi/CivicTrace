import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, type Case, type CaseEvent } from "../../lib/api";
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
    return <div className="container" style={{ padding: "40px 0" }}>Loading case evidence ledger...</div>;
  }

  if (!caseItem) {
    return <div className="container" style={{ padding: "40px 0" }}>Case not found.</div>;
  }

  return (
    <div style={{ padding: "var(--space-6) 0" }}>
      <div className="container">
        {/* Breadcrumb / Document Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Link to="/explorer" style={{ color: "var(--color-text-secondary)", textDecoration: "none", fontSize: "13px" }}>
              &larr; Back to Cases
            </Link>
            <span style={{ color: "var(--color-border-strong)" }}>/</span>
            <span className="mono-id">{caseItem.public_id}</span>
          </div>

          <a
            href={`http://localhost:8000/api/v1/cases/${caseItem.public_id}/export`}
            className="btn btn-outline btn-sm"
            download
          >
            <Download size={13} /> Export Cryptographic Evidence Package (ZIP)
          </a>
        </div>

        {/* Case Dossier Main Card */}
        <div className="card" style={{ marginBottom: "24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
            <div style={{ maxWidth: "800px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                <span className={`archival-stamp stamp-${caseItem.state.toLowerCase()}`}>
                  {caseItem.state.replace("_", " ")}
                </span>
                <span style={{ fontSize: "12px", color: "var(--color-text-secondary)" }}>
                  Category: <strong>{caseItem.category?.name}</strong>
                </span>
              </div>
              <h1 style={{ fontSize: "22px", fontWeight: 700, color: "var(--color-text-primary)" }}>
                {caseItem.title}
              </h1>
              <p style={{ marginTop: "10px", fontSize: "14px", color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
                {caseItem.description}
              </p>
            </div>

            <div style={{
              backgroundColor: "var(--color-surface-elevated)",
              border: "1px solid var(--color-border)",
              padding: "12px 16px",
              borderRadius: "var(--radius-sm)",
              textAlign: "right",
            }}>
              <div style={{ fontSize: "11px", textTransform: "uppercase", fontWeight: 600, color: "var(--color-text-secondary)" }}>
                Civic Priority Score
              </div>
              <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--color-civic-blue)", fontFamily: "var(--font-family-mono)" }}>
                {caseItem.priority_score.toFixed(1)} <span style={{ fontSize: "14px" }}>/ 10</span>
              </div>
              <span className="mono-id" style={{ marginTop: "4px" }}>
                BAND: {caseItem.priority_band}
              </span>
            </div>
          </div>

          {/* Metadata Grid */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "16px",
            marginTop: "20px",
            paddingTop: "16px",
            borderTop: "1px solid var(--color-border-subtle)",
            fontSize: "13px",
          }}>
            <div>
              <span style={{ color: "var(--color-text-muted)" }}>Location:</span>
              <div style={{ fontWeight: 500 }}>{caseItem.address_reference || "Indore Central Ward"}</div>
              <div style={{ fontFamily: "var(--font-family-mono)", fontSize: "11px", color: "var(--color-text-secondary)" }}>
                {caseItem.latitude.toFixed(5)}, {caseItem.longitude.toFixed(5)}
              </div>
            </div>
            <div>
              <span style={{ color: "var(--color-text-muted)" }}>Corroborated Reports:</span>
              <div style={{ fontWeight: 500 }}>{caseItem.report_count} independent submissions</div>
            </div>
            <div>
              <span style={{ color: "var(--color-text-muted)" }}>Submitted On:</span>
              <div style={{ fontWeight: 500 }}>{new Date(caseItem.created_at).toLocaleDateString()}</div>
            </div>
            <div>
              <span style={{ color: "var(--color-text-muted)" }}>Verification Status:</span>
              <div style={{ fontWeight: 600, color: caseItem.state === "RESOLVED" ? "var(--color-verified-green)" : caseItem.state === "DISPUTED" ? "var(--color-disputed-red)" : "var(--color-attention-orange)" }}>
                {caseItem.state === "RESOLVED" ? "Independently Verified Fixed" : caseItem.state === "DISPUTED" ? "Claim Disputed by Public" : "Pending Community Verification"}
              </div>
            </div>
          </div>
        </div>

        {/* Cryptographic Ledger Health Box */}
        {ledgerValidation && (
          <div style={{
            backgroundColor: ledgerValidation.is_valid ? "var(--color-verified-green-subtle)" : "var(--color-disputed-red-subtle)",
            border: `1px solid ${ledgerValidation.is_valid ? "var(--color-verified-green)" : "var(--color-disputed-red)"}`,
            padding: "14px 18px",
            borderRadius: "var(--radius-sm)",
            marginBottom: "24px",
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

        {/* Two-Column Grid: Timeline Ledger (Left) and Citizen Verification Station (Right) */}
        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: "24px" }}>
          {/* Append-only Event Timeline */}
          <div>
            <h2 style={{ fontSize: "18px", fontWeight: 700, marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
              <History size={18} /> Append-Only Accountability Timeline
            </h2>

            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              {events.map((evt) => {
                const payload = JSON.parse(evt.payload_json || "{}");
                return (
                  <div
                    key={evt.id}
                    className="card"
                    style={{
                      borderLeft: "3px solid var(--color-civic-blue)",
                      padding: "14px",
                      position: "relative",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                      <span className="mono-id">EVENT #{evt.event_index}</span>
                      <span style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>
                        {new Date(evt.created_at).toLocaleString()}
                      </span>
                    </div>

                    <div style={{ fontWeight: 600, fontSize: "14px", color: "var(--color-text-primary)" }}>
                      {evt.event_type.replace(/_/g, " ")}
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--color-text-secondary)", marginBottom: "8px" }}>
                      Recorded by: <strong>{evt.public_actor_label}</strong>
                    </div>

                    {/* Formatted Event Details */}
                    <div style={{
                      backgroundColor: "var(--color-surface-elevated)",
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

                    {/* Hash link stamp */}
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

          {/* Right Column: Independent Resolution Verification Station */}
          <div>
            <h2 style={{ fontSize: "18px", fontWeight: 700, marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
              <FileCheck size={18} /> Independent Citizen Verification
            </h2>

            <div className="card" style={{ marginBottom: "20px" }}>
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
                  style={{ alignSelf: "flex-start" }}
                >
                  <Send size={13} /> {verificationSubmitting ? "Submitting..." : "Submit Verification Observation"}
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
