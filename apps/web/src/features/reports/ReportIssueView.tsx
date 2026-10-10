import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Category } from "../../lib/api";
import { PageHeading, SectionHeader } from "../../components/FieldPrimitives";
import { MapPin, CheckCircle, Send, ShieldAlert, ArrowRight } from "lucide-react";

export const ReportIssueView: React.FC = () => {
  const navigate = useNavigate();
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryId, setCategoryId] = useState<string>("");
  const [title, setTitle] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [latitude, setLatitude] = useState<number>(22.7196); // Indore default
  const [longitude, setLongitude] = useState<number>(75.8577);
  const [addressRef, setAddressRef] = useState<string>("");
  const [pseudonym, setPseudonym] = useState<string>("");
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [successResult, setSuccessResult] = useState<any | null>(null);

  useEffect(() => {
    api.getCategories().then((cats) => {
      setCategories(cats);
      if (cats.length > 0) setCategoryId(cats[0].id);
    });
  }, []);

  const handleUseBrowserLocation = () => {
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setLatitude(pos.coords.latitude);
          setLongitude(pos.coords.longitude);
        },
        () => {
          setErrorMsg("Could not retrieve browser GPS. Using manual coordinates.");
        }
      );
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");

    try {
      const res = await api.submitReport({
        category_id: categoryId,
        title,
        description,
        latitude,
        longitude,
        address_reference: addressRef,
        guest_pseudonym: pseudonym || undefined,
      });

      if (evidenceFile) {
        try {
          await api.uploadEvidence(res.id, evidenceFile, "Initial observation photo evidence");
        } catch (uploadErr: any) {
          console.warn("Evidence attachment error:", uploadErr.message);
        }
      }

      setSuccessResult(res);
      setLoading(false);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to submit report");
      setLoading(false);
    }
  };

  return (
    <div>
      <PageHeading
        eyebrow="CIVIC INTAKE PORTAL &bull; INDORE MUNICIPAL WARD 34"
        title="Report an Infrastructure Defect"
        description="Submit an individual public observation. CivicTrace will automatically compute duplicate similarity against existing cases and initiate cryptographic evidence tracking."
      />

      {successResult ? (
        <div style={{
          maxWidth: "760px",
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderLeft: "4px solid var(--color-verified-green)",
          borderRadius: "var(--radius-sm)",
          padding: "24px",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
            <CheckCircle size={22} color="var(--color-verified-green)" />
            <h2 style={{ fontSize: "18px", fontWeight: 700, color: "var(--color-verified-green)" }}>
              Observation Successfully Registered
            </h2>
          </div>

          <p style={{ fontSize: "14px", color: "var(--color-text-secondary)", marginBottom: "16px", lineHeight: 1.5 }}>
            Your field observation has been registered into the append-only ledger and submitted to the deterministic correlation engine.
          </p>

          <div style={{
            backgroundColor: "var(--color-surface-elevated)",
            border: "1px solid var(--color-border-subtle)",
            padding: "12px 16px",
            borderRadius: "var(--radius-sm)",
            fontSize: "13px",
            display: "flex",
            flexDirection: "column",
            gap: "6px",
            marginBottom: "18px",
          }}>
            <div><strong>Report Reference:</strong> <span className="mono-id">{successResult.public_id}</span></div>
            <div><strong>Hazard:</strong> {successResult.title}</div>
            <div><strong>Coordinates:</strong> {successResult.latitude.toFixed(5)}, {successResult.longitude.toFixed(5)}</div>
          </div>

          <div style={{ display: "flex", gap: "10px" }}>
            <button
              onClick={() => navigate("/explorer")}
              className="btn btn-primary"
            >
              View in Public Cases Explorer <ArrowRight size={14} />
            </button>
            <button
              onClick={() => {
                setSuccessResult(null);
                setTitle("");
                setDescription("");
                setAddressRef("");
              }}
              className="btn btn-outline"
            >
              Submit Another Observation
            </button>
          </div>
        </div>
      ) : (
        <div style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.6fr) minmax(320px, 1fr)",
          gap: "24px",
          alignItems: "start",
        }}>
          {/* Main Intake Form Card */}
          <div style={{
            backgroundColor: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            overflow: "hidden",
          }}>
            <SectionHeader title="Defect Intake Form" />

            <div style={{ padding: "20px" }}>
              {errorMsg && (
                <div style={{
                  padding: "10px 14px",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "13px",
                  marginBottom: "16px",
                  backgroundColor: "var(--color-disputed-red-subtle)",
                  color: "var(--color-disputed-red)",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}>
                  <ShieldAlert size={15} /> {errorMsg}
                </div>
              )}

              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: 600, textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "4px" }}>
                    Hazard Category
                  </label>
                  <select
                    value={categoryId}
                    onChange={(e) => setCategoryId(e.target.value)}
                    required
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      fontSize: "13px",
                      border: "1px solid var(--color-border)",
                      borderRadius: "var(--radius-sm)",
                      backgroundColor: "var(--color-surface)",
                    }}
                  >
                    {categories.map((cat) => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: 600, textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "4px" }}>
                    Brief Summary / Title
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Deep pothole on MG Road near Rajwada intersection"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    required
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
                  <label style={{ display: "block", fontSize: "12px", fontWeight: 600, textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "4px" }}>
                    Observed Details & Severity
                  </label>
                  <textarea
                    rows={4}
                    placeholder="Detail what you observed, physical depth, hazards to pedestrians, water leaks, or safety risks..."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    required
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

                {/* Location Picker Box */}
                <div style={{
                  backgroundColor: "var(--color-surface-elevated)",
                  border: "1px solid var(--color-border)",
                  padding: "14px",
                  borderRadius: "var(--radius-sm)",
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <span style={{ fontSize: "12px", fontWeight: 600, textTransform: "uppercase", color: "var(--color-text-secondary)" }}>
                      Geographic Location (Indore Grid)
                    </span>
                    <button
                      type="button"
                      onClick={handleUseBrowserLocation}
                      className="btn btn-outline btn-sm"
                    >
                      <MapPin size={12} /> Use GPS
                    </button>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "10px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "11px", color: "var(--color-text-secondary)", marginBottom: "2px" }}>Latitude</label>
                      <input
                        type="number"
                        step="any"
                        value={latitude}
                        onChange={(e) => setLatitude(parseFloat(e.target.value))}
                        required
                        style={{
                          width: "100%",
                          padding: "6px 8px",
                          fontSize: "12px",
                          fontFamily: "var(--font-family-mono)",
                          border: "1px solid var(--color-border)",
                          borderRadius: "var(--radius-sm)",
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "11px", color: "var(--color-text-secondary)", marginBottom: "2px" }}>Longitude</label>
                      <input
                        type="number"
                        step="any"
                        value={longitude}
                        onChange={(e) => setLongitude(parseFloat(e.target.value))}
                        required
                        style={{
                          width: "100%",
                          padding: "6px 8px",
                          fontSize: "12px",
                          fontFamily: "var(--font-family-mono)",
                          border: "1px solid var(--color-border)",
                          borderRadius: "var(--radius-sm)",
                        }}
                      />
                    </div>
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "11px", color: "var(--color-text-secondary)", marginBottom: "2px" }}>Street Reference</label>
                    <input
                      type="text"
                      placeholder="e.g. Near Rajwada Palace, MG Road crossing"
                      value={addressRef}
                      onChange={(e) => setAddressRef(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "6px 8px",
                        fontSize: "12px",
                        border: "1px solid var(--color-border)",
                        borderRadius: "var(--radius-sm)",
                      }}
                    />
                  </div>
                </div>

                {/* Photo Evidence Input */}
                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: 600, textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "4px" }}>
                    Attach Photo Evidence (Optional)
                  </label>
                  <input
                    type="file"
                    accept="image/png, image/jpeg, image/webp"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setEvidenceFile(e.target.files[0]);
                      }
                    }}
                    style={{ fontSize: "12px", color: "var(--color-text-secondary)" }}
                  />
                </div>

                {/* Submitter Pseudonym */}
                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: 600, textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "4px" }}>
                    Observer Attribution (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Ward 34 Resident, Commuter"
                    value={pseudonym}
                    onChange={(e) => setPseudonym(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      fontSize: "13px",
                      border: "1px solid var(--color-border)",
                      borderRadius: "var(--radius-sm)",
                    }}
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="btn btn-primary"
                  style={{ alignSelf: "flex-start", marginTop: "4px" }}
                >
                  <Send size={13} /> {loading ? "Registering..." : "Submit Observation to Ledger"}
                </button>
              </form>
            </div>
          </div>

          {/* Standards Sidebar */}
          <div style={{
            backgroundColor: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            overflow: "hidden",
          }}>
            <SectionHeader title="Verification Standards" />

            <div style={{ padding: "18px", display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <h4 style={{ fontSize: "13px", fontWeight: 600, color: "var(--color-text-primary)" }}>
                  1. Duplicate Correlation
                </h4>
                <p style={{ fontSize: "12px", color: "var(--color-text-secondary)", marginTop: "2px", lineHeight: 1.5 }}>
                  Submissions near an existing defect are correlated via Haversine distance and token similarity into a single case dossier.
                </p>
              </div>

              <div>
                <h4 style={{ fontSize: "13px", fontWeight: 600, color: "var(--color-text-primary)" }}>
                  2. Priority Scoring
                </h4>
                <p style={{ fontSize: "12px", color: "var(--color-text-secondary)", marginTop: "2px", lineHeight: 1.5 }}>
                  The priority engine ranks civic risk from 1 to 10 based on hazard class, corroborating reports, and unresolved days.
                </p>
              </div>

              <div>
                <h4 style={{ fontSize: "13px", fontWeight: 600, color: "var(--color-text-primary)" }}>
                  3. Verification Gate
                </h4>
                <p style={{ fontSize: "12px", color: "var(--color-text-secondary)", marginTop: "2px", lineHeight: 1.5 }}>
                  Public works repair claims do not close a case without independent citizen or reviewer inspection.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
