import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Category } from "../../lib/api";
import { MapPin, CheckCircle, Send, ArrowRight, ShieldAlert } from "lucide-react";

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

      // If citizen selected an evidence file, upload it immediately attached to this report
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
    <div style={{ padding: "var(--space-6) 0 var(--space-12)" }}>
      <div className="workspace-container">
        
        {/* Workspace Breadcrumb & Header */}
        <div style={{
          borderBottom: "1px solid var(--color-border)",
          paddingBottom: "var(--space-4)",
          marginBottom: "var(--space-6)",
        }}>
          <div style={{
            fontFamily: "var(--font-family-mono)",
            fontSize: "var(--font-size-2xs)",
            color: "var(--color-civic-blue)",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            fontWeight: 600,
            marginBottom: "4px",
          }}>
            CIVIC INTAKE PORTAL &bull; INDORE MUNICIPAL WARD 34
          </div>
          <h1 style={{ fontSize: "28px", fontWeight: 700, letterSpacing: "-0.02em", color: "var(--color-text-primary)" }}>
            Report an Infrastructure Defect
          </h1>
          <p style={{ color: "var(--color-text-secondary)", fontSize: "14px", marginTop: "2px" }}>
            Submit an individual public observation. CivicTrace will automatically compute duplicate similarity against existing cases and initiate cryptographic evidence tracking.
          </p>
        </div>

        {successResult ? (
          <div style={{
            maxWidth: "780px",
            backgroundColor: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderLeft: "4px solid var(--color-verified-green)",
            borderRadius: "var(--radius-sm)",
            padding: "24px",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
              <CheckCircle size={24} color="var(--color-verified-green)" />
              <h2 style={{ fontSize: "18px", fontWeight: 700, color: "var(--color-verified-green)" }}>
                Observation Successfully Registered
              </h2>
            </div>

            <p style={{ fontSize: "14px", color: "var(--color-text-secondary)", marginBottom: "16px", lineHeight: 1.5 }}>
              Your field observation has been recorded and submitted to the deterministic correlation engine.
            </p>

            <div style={{
              backgroundColor: "var(--color-surface-elevated)",
              border: "1px solid var(--color-border-subtle)",
              padding: "14px 18px",
              borderRadius: "var(--radius-sm)",
              fontSize: "13px",
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              marginBottom: "20px",
            }}>
              <div><strong>Report Reference:</strong> <span className="mono-id">{successResult.public_id}</span></div>
              <div><strong>Infrastructure Hazard:</strong> {successResult.title}</div>
              <div><strong>Location Coordinates:</strong> {successResult.latitude.toFixed(5)}, {successResult.longitude.toFixed(5)}</div>
            </div>

            <div style={{ display: "flex", gap: "12px" }}>
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
            gap: "28px",
            alignItems: "start",
          }}>
            {/* Primary Intake Form Card */}
            <div style={{
              backgroundColor: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              padding: "24px",
            }}>
              {errorMsg && (
                <div style={{
                  padding: "12px 14px",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "13px",
                  marginBottom: "16px",
                  backgroundColor: "var(--color-disputed-red-subtle)",
                  color: "var(--color-disputed-red)",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}>
                  <ShieldAlert size={16} /> {errorMsg}
                </div>
              )}

              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
                    Infrastructure Hazard Category
                  </label>
                  <select
                    value={categoryId}
                    onChange={(e) => setCategoryId(e.target.value)}
                    required
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      fontSize: "14px",
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
                  <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
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
                      padding: "8px 12px",
                      fontSize: "14px",
                      border: "1px solid var(--color-border)",
                      borderRadius: "var(--radius-sm)",
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
                    Observed Problem Details & Physical Severity
                  </label>
                  <textarea
                    rows={4}
                    placeholder="Detail what you observed, physical depth, hazards to pedestrians, water leaks, or safety risks..."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    required
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      fontSize: "14px",
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
                  padding: "16px",
                  borderRadius: "var(--radius-sm)",
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                    <span style={{ fontSize: "13px", fontWeight: 600 }}>Geographic Location (Indore Grid)</span>
                    <button
                      type="button"
                      onClick={handleUseBrowserLocation}
                      className="btn btn-outline btn-sm"
                    >
                      <MapPin size={13} /> Use Device GPS
                    </button>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "10px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "11px", color: "var(--color-text-secondary)", marginBottom: "4px" }}>Latitude</label>
                      <input
                        type="number"
                        step="any"
                        value={latitude}
                        onChange={(e) => setLatitude(parseFloat(e.target.value))}
                        required
                        style={{
                          width: "100%",
                          padding: "6px 10px",
                          fontSize: "13px",
                          fontFamily: "var(--font-family-mono)",
                          border: "1px solid var(--color-border)",
                          borderRadius: "var(--radius-sm)",
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "11px", color: "var(--color-text-secondary)", marginBottom: "4px" }}>Longitude</label>
                      <input
                        type="number"
                        step="any"
                        value={longitude}
                        onChange={(e) => setLongitude(parseFloat(e.target.value))}
                        required
                        style={{
                          width: "100%",
                          padding: "6px 10px",
                          fontSize: "13px",
                          fontFamily: "var(--font-family-mono)",
                          border: "1px solid var(--color-border)",
                          borderRadius: "var(--radius-sm)",
                        }}
                      />
                    </div>
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "11px", color: "var(--color-text-secondary)", marginBottom: "4px" }}>Street / Landmark Reference</label>
                    <input
                      type="text"
                      placeholder="e.g. Near Rajwada Palace, MG Road crossing"
                      value={addressRef}
                      onChange={(e) => setAddressRef(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "6px 10px",
                        fontSize: "13px",
                        border: "1px solid var(--color-border)",
                        borderRadius: "var(--radius-sm)",
                      }}
                    />
                  </div>
                </div>

                {/* Evidence Photo Upload */}
                <div>
                  <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "4px" }}>
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
                    style={{
                      fontSize: "13px",
                      color: "var(--color-text-secondary)",
                    }}
                  />
                  <div style={{ fontSize: "11px", color: "var(--color-text-muted)", marginTop: "4px" }}>
                    Files are validated for MIME type, byte integrity, and hashed into the public evidence archive.
                  </div>
                </div>

                {/* Submitter Pseudonym */}
                <div>
                  <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "4px" }}>
                    Observer Pseudonym / Attribution (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Ward 34 Resident, Commuter"
                    value={pseudonym}
                    onChange={(e) => setPseudonym(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      fontSize: "14px",
                      border: "1px solid var(--color-border)",
                      borderRadius: "var(--radius-sm)",
                    }}
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="btn btn-primary"
                  style={{ alignSelf: "flex-start", marginTop: "6px" }}
                >
                  <Send size={14} /> {loading ? "Registering Observation..." : "Submit Observation to Ledger"}
                </button>
              </form>
            </div>

            {/* Explanatory Sidebar Card */}
            <div style={{
              backgroundColor: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              padding: "20px",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}>
              <div className="grid-header" style={{ margin: "-20px -20px 0", borderRadius: "var(--radius-sm) var(--radius-sm) 0 0" }}>
                <span>Accountability Standards</span>
              </div>

              <div>
                <h3 style={{ fontSize: "14px", fontWeight: 600, marginBottom: "6px" }}>
                  1. Automatic Duplicate Correlation
                </h3>
                <p style={{ fontSize: "12px", color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
                  If other citizens have reported the same issue nearby, CivicTrace calculates Haversine proximity and text token similarity to consolidate evidence rather than creating disconnected tickets.
                </p>
              </div>

              <div>
                <h3 style={{ fontSize: "14px", fontWeight: 600, marginBottom: "6px" }}>
                  2. Transparent Civic Priority
                </h3>
                <p style={{ fontSize: "12px", color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
                  Reports automatically receive an explainable priority score based on intrinsic hazard severity and corroboration count.
                </p>
              </div>

              <div>
                <h3 style={{ fontSize: "14px", fontWeight: 600, marginBottom: "6px" }}>
                  3. Append-Only Provenance
                </h3>
                <p style={{ fontSize: "12px", color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
                  Every observation creates an immutable audit event on a sequential SHA-256 ledger. No administrator can delete a report without invalidating the chain.
                </p>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};
