import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Category } from "../../lib/api";
import { PageHeading, SectionHeader } from "../../components/FieldPrimitives";

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
    <>
      <PageHeading
        index="04"
        title="Report issue"
        description="Report an Infrastructure Defect. Submit an individual public observation. CivicTrace will automatically compute duplicate similarity against existing cases and initiate cryptographic evidence tracking."
      />

      <div className="workspace">
        {successResult ? (
          <div style={{
            maxWidth: "680px",
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderLeft: "3px solid var(--success)",
            padding: "var(--space-5)",
          }}>
            <h2 style={{ fontSize: "16px", fontWeight: 600, color: "var(--success)", margin: "0 0 var(--space-2)" }}>
              Observation Successfully Registered
            </h2>

            <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "var(--space-4)", lineHeight: 1.5 }}>
              Your field observation has been registered into the append-only ledger and submitted to the deterministic correlation engine.
            </p>

            <div style={{
              background: "var(--surface-muted)",
              padding: "var(--space-3) var(--space-4)",
              marginBottom: "var(--space-4)",
              fontSize: "12px",
              display: "flex",
              flexDirection: "column",
              gap: "4px",
            }}>
              <div><strong>Report Reference:</strong> <code>{successResult.public_id}</code></div>
              <div><strong>Hazard:</strong> {successResult.title}</div>
              <div><strong>Coordinates:</strong> <code className="numeric">{successResult.latitude.toFixed(5)}, {successResult.longitude.toFixed(5)}</code></div>
            </div>

            <div className="action-group">
              <button
                onClick={() => navigate("/explorer")}
                className="button-primary"
              >
                View in Public Cases Explorer
              </button>
              <button
                onClick={() => {
                  setSuccessResult(null);
                  setTitle("");
                  setDescription("");
                  setAddressRef("");
                }}
                className="btn-outline"
              >
                Submit another observation
              </button>
            </div>
          </div>
        ) : (
          <div style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1.6fr) minmax(300px, 1fr)",
            gap: "var(--space-5)",
            alignItems: "start",
          }}>
            {/* Form Card */}
            <div>
              <SectionHeader index="01" title="Defect intake form" />

              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "var(--space-4)" }}>
                {errorMsg && (
                  <div role="alert" style={{ marginBottom: "var(--space-3)" }}>
                    {errorMsg}
                  </div>
                )}

                <form onSubmit={handleSubmit} style={{ margin: 0 }}>
                  <div style={{ marginBottom: "var(--space-3)" }}>
                    <label htmlFor="cat-select">Hazard category</label>
                    <select
                      id="cat-select"
                      value={categoryId}
                      onChange={(e) => setCategoryId(e.target.value)}
                      required
                      style={{ width: "100%" }}
                    >
                      {categories.map((cat) => (
                        <option key={cat.id} value={cat.id}>{cat.name}</option>
                      ))}
                    </select>
                  </div>

                  <div style={{ marginBottom: "var(--space-3)" }}>
                    <label htmlFor="title-input">Brief summary / title</label>
                    <input
                      id="title-input"
                      type="text"
                      placeholder="e.g. Deep pothole on MG Road near Rajwada intersection"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      required
                      style={{ width: "100%" }}
                    />
                  </div>

                  <div style={{ marginBottom: "var(--space-3)" }}>
                    <label htmlFor="desc-input">Observed details & severity</label>
                    <textarea
                      id="desc-input"
                      rows={4}
                      placeholder="Detail what you observed, physical depth, hazards to pedestrians, water leaks, or safety risks..."
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      required
                      style={{ width: "100%", lineHeight: 1.5 }}
                    />
                  </div>

                  {/* Location Picker Box */}
                  <div style={{
                    background: "var(--surface-muted)",
                    padding: "var(--space-3)",
                    border: "1px solid var(--border)",
                    marginBottom: "var(--space-3)",
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)" }}>
                      <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-secondary)" }}>
                        Geographic coordinates
                      </span>
                      <button
                        type="button"
                        onClick={handleUseBrowserLocation}
                        className="btn-outline btn-sm"
                      >
                        Use GPS location
                      </button>
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                      <div>
                        <label htmlFor="lat-input" style={{ fontSize: "11px" }}>Latitude</label>
                        <input
                          id="lat-input"
                          type="number"
                          step="0.000001"
                          value={latitude}
                          onChange={(e) => setLatitude(parseFloat(e.target.value))}
                          required
                          style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: "12px" }}
                        />
                      </div>
                      <div>
                        <label htmlFor="lon-input" style={{ fontSize: "11px" }}>Longitude</label>
                        <input
                          id="lon-input"
                          type="number"
                          step="0.000001"
                          value={longitude}
                          onChange={(e) => setLongitude(parseFloat(e.target.value))}
                          required
                          style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: "12px" }}
                        />
                      </div>
                    </div>

                    <div>
                      <label htmlFor="addr-input" style={{ fontSize: "11px" }}>Street / Landmark reference</label>
                      <input
                        id="addr-input"
                        type="text"
                        placeholder="e.g. Near Rajwada Palace, MG Road intersection"
                        value={addressRef}
                        onChange={(e) => setAddressRef(e.target.value)}
                        style={{ width: "100%" }}
                      />
                    </div>
                  </div>

                  {/* Reporter Pseudonym */}
                  <div style={{ marginBottom: "var(--space-3)" }}>
                    <label htmlFor="name-input">Observer name or pseudonym</label>
                    <input
                      id="name-input"
                      type="text"
                      placeholder="e.g. Aarav M. or Local Commuter"
                      value={pseudonym}
                      onChange={(e) => setPseudonym(e.target.value)}
                      style={{ width: "100%" }}
                    />
                  </div>

                  {/* Evidence File */}
                  <div style={{ marginBottom: "var(--space-4)" }}>
                    <label htmlFor="file-input">Attach site photographic evidence (optional)</label>
                    <input
                      id="file-input"
                      type="file"
                      accept="image/*,.pdf"
                      onChange={(e) => setEvidenceFile(e.target.files ? e.target.files[0] : null)}
                      style={{ width: "100%" }}
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="button-primary"
                    style={{ width: "100%" }}
                  >
                    {loading ? "Recording observation..." : "Submit public defect observation"}
                  </button>
                </form>
              </div>
            </div>

            {/* Right Column: Evidentiary Standards */}
            <div>
              <SectionHeader index="02" title="Evidentiary standard" />

              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "var(--space-4)", fontSize: "12px" }}>
                <h3 style={{ fontSize: "13px", margin: "0 0 var(--space-2)" }}>Corroboration protocol</h3>
                <p style={{ color: "var(--text-secondary)", lineHeight: 1.5, margin: "0 0 var(--space-3)" }}>
                  CivicTrace uses geographic proximity clustering and category matching to correlate reports into shared investigation cases.
                </p>

                <h3 style={{ fontSize: "13px", margin: "0 0 var(--space-2)" }}>Cryptographic accountability</h3>
                <p style={{ color: "var(--text-secondary)", lineHeight: 1.5, margin: "0 0 var(--space-3)" }}>
                  Each submitted observation is hashed into an immutable append-only audit log. Operator actions must withstand independent community verification before closure.
                </p>

                <div style={{ borderTop: "1px solid var(--border)", paddingTop: "var(--space-2)", color: "var(--text-muted)", fontSize: "11px" }}>
                  Demonstration Area: Indore Ward 34 · AB Road & MG Road corridors
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
};
