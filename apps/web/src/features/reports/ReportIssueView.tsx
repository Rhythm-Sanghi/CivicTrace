import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Category } from "../../lib/api";
import { PageHeading, SectionHeader } from "../../components/FieldPrimitives";

export const ReportIssueView: React.FC = () => {
  const navigate = useNavigate();
  const [categories, setCategories] = useState<Category[]>([]);

  // Form fields with draft local preservation
  const [categoryId, setCategoryId] = useState<string>(() => {
    return localStorage.getItem("civictrace_draft_cat") || "";
  });
  const [title, setTitle] = useState<string>(() => {
    return localStorage.getItem("civictrace_draft_title") || "";
  });
  const [description, setDescription] = useState<string>(() => {
    return localStorage.getItem("civictrace_draft_desc") || "";
  });
  const [latitude, setLatitude] = useState<number>(() => {
    const saved = localStorage.getItem("civictrace_draft_lat");
    return saved ? parseFloat(saved) : 22.7196; // Indore default
  });
  const [longitude, setLongitude] = useState<number>(() => {
    const saved = localStorage.getItem("civictrace_draft_lon");
    return saved ? parseFloat(saved) : 75.8577;
  });
  const [addressRef, setAddressRef] = useState<string>(() => {
    return localStorage.getItem("civictrace_draft_addr") || "";
  });
  const [pseudonym, setPseudonym] = useState<string>(() => {
    return localStorage.getItem("civictrace_draft_name") || "";
  });

  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);
  const [evidencePreviewUrl, setEvidencePreviewUrl] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [locationFeedback, setLocationFeedback] = useState<string>("");
  const [successResult, setSuccessResult] = useState<any | null>(null);

  // Auto-save drafts
  useEffect(() => {
    localStorage.setItem("civictrace_draft_cat", categoryId);
    localStorage.setItem("civictrace_draft_title", title);
    localStorage.setItem("civictrace_draft_desc", description);
    localStorage.setItem("civictrace_draft_lat", latitude.toString());
    localStorage.setItem("civictrace_draft_lon", longitude.toString());
    localStorage.setItem("civictrace_draft_addr", addressRef);
    localStorage.setItem("civictrace_draft_name", pseudonym);
  }, [categoryId, title, description, latitude, longitude, addressRef, pseudonym]);

  useEffect(() => {
    api.getCategories().then((cats) => {
      setCategories(cats);
      if (cats.length > 0) setCategoryId((prev) => prev || cats[0].id);
    });
  }, []);

  const clearDraft = () => {
    localStorage.removeItem("civictrace_draft_cat");
    localStorage.removeItem("civictrace_draft_title");
    localStorage.removeItem("civictrace_draft_desc");
    localStorage.removeItem("civictrace_draft_lat");
    localStorage.removeItem("civictrace_draft_lon");
    localStorage.removeItem("civictrace_draft_addr");
    localStorage.removeItem("civictrace_draft_name");
    setTitle("");
    setDescription("");
    setAddressRef("");
    setPseudonym("");
    setEvidenceFile(null);
    if (evidencePreviewUrl) URL.revokeObjectURL(evidencePreviewUrl);
    setEvidencePreviewUrl(null);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setErrorMsg("");
    const file = e.target.files ? e.target.files[0] : null;
    if (!file) {
      setEvidenceFile(null);
      if (evidencePreviewUrl) URL.revokeObjectURL(evidencePreviewUrl);
      setEvidencePreviewUrl(null);
      return;
    }

    const validTypes = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
    if (!validTypes.includes(file.type) && !file.name.match(/\.(jpe?g|png|webp|pdf)$/i)) {
      setErrorMsg("Invalid file type. Only JPG, PNG, WEBP, and PDF documents are permitted.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setErrorMsg("File size exceeds 10MB maximum evidentiary payload limit.");
      return;
    }

    setEvidenceFile(file);
    if (file.type.startsWith("image/")) {
      const url = URL.createObjectURL(file);
      setEvidencePreviewUrl(url);
    } else {
      setEvidencePreviewUrl(null);
    }
  };

  const handleUseBrowserLocation = () => {
    setLocationFeedback("");
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setLatitude(pos.coords.latitude);
          setLongitude(pos.coords.longitude);
          setLocationFeedback("Browser GPS coordinates acquired successfully.");
        },
        () => {
          setLocationFeedback("GPS lock unavailable. Manual Indore coordinates active.");
        }
      );
    } else {
      setLocationFeedback("Geolocation API unsupported by browser.");
    }
  };

  const isDescribeValid = title.trim().length >= 5 && description.trim().length >= 10;
  const isLocateValid = latitude !== 0 && longitude !== 0 && addressRef.trim().length >= 3;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isDescribeValid) {
      setErrorMsg("Please enter a valid issue title (at least 5 characters) and description (at least 10 characters).");
      return;
    }
    if (!isLocateValid) {
      setErrorMsg("Please provide a valid street or landmark location reference.");
      return;
    }

    setLoading(true);
    setErrorMsg("");

    try {
      const res = await api.submitReport({
        category_id: categoryId,
        title: title.trim(),
        description: description.trim(),
        latitude,
        longitude,
        address_reference: addressRef.trim(),
        guest_pseudonym: pseudonym.trim() || undefined,
      });

      let evidenceUploadFailed = false;
      let evidenceErrorMsg = "";
      if (evidenceFile) {
        try {
          await api.uploadEvidence(res.id, evidenceFile, "Initial observation photo evidence", res.upload_token);
        } catch (uploadErr: any) {
          evidenceUploadFailed = true;
          evidenceErrorMsg = uploadErr.message || "Failed to attach evidence file.";
          console.warn("Evidence attachment error:", uploadErr.message);
        }
      }

      clearDraft();
      setSuccessResult({
        ...res,
        evidenceFailed: evidenceUploadFailed,
        evidenceError: evidenceErrorMsg,
      });
      setLoading(false);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to submit report");
      setLoading(false);
    }
  };

  const selectedCategoryObj = categories.find((c) => c.id === categoryId);

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
              gap: "6px",
              border: "1px solid var(--border)",
            }}>
              <div><strong>Report Reference:</strong> <code style={{ fontWeight: 600 }}>{successResult.public_id}</code></div>
              <div><strong>Hazard Category:</strong> {selectedCategoryObj?.name || successResult.category?.name}</div>
              <div><strong>Title:</strong> {successResult.title}</div>
              <div><strong>Location:</strong> {successResult.address_reference}</div>
              <div><strong>Coordinates:</strong> <code className="numeric">{successResult.latitude.toFixed(5)}, {successResult.longitude.toFixed(5)}</code></div>
            </div>

            {successResult.evidenceFailed && (
              <div
                role="alert"
                style={{
                  background: "var(--surface)",
                  border: "1px solid var(--warning)",
                  borderLeft: "3px solid var(--warning)",
                  padding: "var(--space-3) var(--space-4)",
                  marginBottom: "var(--space-4)",
                  fontSize: "12px",
                }}
              >
                <strong style={{ color: "var(--warning)" }}>Notice on Attached Media:</strong>
                <p style={{ margin: "4px 0 0", color: "var(--text-secondary)" }}>
                  Your report was safely created as <code>{successResult.public_id}</code>, but the evidence attachment encountered an issue ({successResult.evidenceError}). You can add or re-upload evidence from the case detail view.
                </p>
              </div>
            )}

            <div className="action-group">
              <button
                onClick={() => navigate("/explorer")}
                className="button-primary"
              >
                View in Public Cases Explorer
              </button>
              <button
                onClick={() => setSuccessResult(null)}
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
            {/* Form Container */}
            <div>
              <SectionHeader index="01" title="Defect intake form" />

              {errorMsg && (
                <div role="alert" style={{
                  background: "#fbf1f0",
                  color: "var(--danger)",
                  border: "1px solid var(--danger)",
                  padding: "var(--space-2) var(--space-3)",
                  marginBottom: "var(--space-3)",
                  fontSize: "12px",
                }}>
                  {errorMsg}
                </div>
              )}

              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "var(--space-4)" }}>
                <form onSubmit={handleSubmit} style={{ margin: 0 }}>
                  {/* Stage 1: Describe Defect */}
                  <div style={{ marginBottom: "var(--space-4)" }}>
                    <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--accent)", marginBottom: "var(--space-2)" }}>
                      STAGE 1: DESCRIBE DEFECT
                    </div>

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
                      <label htmlFor="title-input">Brief summary / title *</label>
                      <input
                        id="title-input"
                        type="text"
                        placeholder="e.g. Deep pothole on MG Road near Rajwada intersection"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        required
                        style={{ width: "100%" }}
                      />
                      {title.length > 0 && title.length < 5 && (
                        <span style={{ fontSize: "11px", color: "var(--danger)" }}>Must be at least 5 characters.</span>
                      )}
                    </div>

                    <div style={{ marginBottom: "var(--space-3)" }}>
                      <label htmlFor="desc-input">Observed details & severity *</label>
                      <textarea
                        id="desc-input"
                        rows={3}
                        placeholder="Detail what you observed, physical depth, hazards to pedestrians, water leaks, or safety risks..."
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        required
                        style={{ width: "100%", lineHeight: 1.5 }}
                      />
                      {description.length > 0 && description.length < 10 && (
                        <span style={{ fontSize: "11px", color: "var(--danger)" }}>Must be at least 10 characters.</span>
                      )}
                    </div>
                  </div>

                  {/* Stage 2: Locate Defect */}
                  <div style={{
                    marginBottom: "var(--space-4)",
                    paddingTop: "var(--space-3)",
                    borderTop: "1px solid var(--border)",
                  }}>
                    <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--accent)", marginBottom: "var(--space-2)" }}>
                      STAGE 2: LOCATE DEFECT
                    </div>

                    <div style={{
                      background: "var(--surface-muted)",
                      padding: "var(--space-3)",
                      border: "1px solid var(--border)",
                      marginBottom: "var(--space-3)",
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)" }}>
                        <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-secondary)" }}>
                          WGS84 Coordinates
                        </span>
                        <button
                          type="button"
                          onClick={handleUseBrowserLocation}
                          className="btn-outline btn-sm"
                        >
                          Acquire browser GPS
                        </button>
                      </div>

                      {locationFeedback && (
                        <div style={{ fontSize: "11px", color: "var(--accent)", marginBottom: "var(--space-2)" }}>
                          {locationFeedback}
                        </div>
                      )}

                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                        <div>
                          <label htmlFor="lat-input" style={{ fontSize: "11px" }}>Latitude</label>
                          <input
                            id="lat-input"
                            type="number"
                            step="0.000001"
                            value={latitude}
                            onChange={(e) => setLatitude(parseFloat(e.target.value) || 0)}
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
                            onChange={(e) => setLongitude(parseFloat(e.target.value) || 0)}
                            required
                            style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: "12px" }}
                          />
                        </div>
                      </div>
                    </div>

                    <div style={{ marginBottom: "var(--space-3)" }}>
                      <label htmlFor="addr-input">Street / Landmark reference *</label>
                      <input
                        id="addr-input"
                        type="text"
                        placeholder="e.g. Near Rajwada Palace, MG Road intersection"
                        value={addressRef}
                        onChange={(e) => setAddressRef(e.target.value)}
                        required
                        style={{ width: "100%" }}
                      />
                      {addressRef.length > 0 && addressRef.length < 3 && (
                        <span style={{ fontSize: "11px", color: "var(--danger)" }}>Please specify street or landmark.</span>
                      )}
                    </div>
                  </div>

                  {/* Stage 3: Evidentiary Attachments */}
                  <div style={{
                    marginBottom: "var(--space-4)",
                    paddingTop: "var(--space-3)",
                    borderTop: "1px solid var(--border)",
                  }}>
                    <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--accent)", marginBottom: "var(--space-2)" }}>
                      STAGE 3: EVIDENTIARY ATTACHMENTS & OBSERVER
                    </div>

                    <div style={{ marginBottom: "var(--space-3)" }}>
                      <label htmlFor="name-input">Observer pseudonym / display name (optional)</label>
                      <input
                        id="name-input"
                        type="text"
                        placeholder="e.g. Aarav M. or Local Resident (leave blank for guest anonymous)"
                        value={pseudonym}
                        onChange={(e) => setPseudonym(e.target.value)}
                        style={{ width: "100%" }}
                      />
                    </div>

                    <div style={{ marginBottom: "var(--space-3)" }}>
                      <label htmlFor="file-input">Attach photographic evidence (optional, max 10MB)</label>
                      <input
                        id="file-input"
                        type="file"
                        accept="image/*,.pdf"
                        onChange={handleFileChange}
                        style={{ width: "100%" }}
                      />
                    </div>

                    {evidencePreviewUrl && (
                      <div style={{
                        marginBottom: "var(--space-3)",
                        border: "1px solid var(--border)",
                        padding: "var(--space-2)",
                        background: "var(--surface-muted)",
                      }}>
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "4px" }}>
                          Attached Preview: {evidenceFile?.name} ({(evidenceFile!.size / 1024).toFixed(0)} KB)
                        </div>
                        <img
                          src={evidencePreviewUrl}
                          alt="Evidence preview"
                          style={{ maxWidth: "100%", maxHeight: "160px", objectFit: "contain", border: "1px solid var(--border)" }}
                        />
                      </div>
                    )}
                  </div>

                  {/* Stage 4: Review Summary Box */}
                  <div style={{
                    marginBottom: "var(--space-4)",
                    padding: "var(--space-3)",
                    background: "var(--surface-muted)",
                    border: "1px solid var(--border)",
                  }}>
                    <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "var(--space-1)" }}>
                      STAGE 4: PRE-SUBMISSION VERIFICATION SUMMARY
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: 1.45 }}>
                      Category: <strong>{selectedCategoryObj?.name}</strong> · Location: <strong>{addressRef || "Pending location"}</strong>
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={loading || !isDescribeValid || !isLocateValid}
                    className="button-primary"
                    style={{ width: "100%" }}
                  >
                    {loading ? "Recording in ledger..." : "Submit public defect observation"}
                  </button>
                </form>
              </div>
            </div>

            {/* Right Column: Evidentiary Standards Panel */}
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
