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
  const [latitude, setLatitude] = useState<string>(() => {
    return localStorage.getItem("civictrace_draft_lat") || "";
  });
  const [longitude, setLongitude] = useState<string>(() => {
    return localStorage.getItem("civictrace_draft_lon") || "";
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
  const [locationFeedbackType, setLocationFeedbackType] = useState<"info" | "warning" | "success">("info");
  const [successResult, setSuccessResult] = useState<any | null>(null);

  // Auto-save drafts
  useEffect(() => {
    localStorage.setItem("civictrace_draft_cat", categoryId);
    localStorage.setItem("civictrace_draft_title", title);
    localStorage.setItem("civictrace_draft_desc", description);
    localStorage.setItem("civictrace_draft_lat", latitude);
    localStorage.setItem("civictrace_draft_lon", longitude);
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
    setLatitude("");
    setLongitude("");
    setAddressRef("");
    setPseudonym("");
    setEvidenceFile(null);
    if (evidencePreviewUrl) URL.revokeObjectURL(evidencePreviewUrl);
    setEvidencePreviewUrl(null);
    setLocationFeedback("");
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
      setLocationFeedback("Requesting device location...");
      setLocationFeedbackType("info");

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setLatitude(pos.coords.latitude.toFixed(6));
          setLongitude(pos.coords.longitude.toFixed(6));
          const accuracy = Math.round(pos.coords.accuracy);
          setLocationFeedback(`GPS coordinates acquired (accuracy: ±${accuracy}m).`);
          setLocationFeedbackType("success");
        },
        (err) => {
          if (err.code === 1) {
            setLocationFeedback("Location access was denied. Please enter coordinates manually.");
          } else if (err.code === 2) {
            setLocationFeedback("Location signal unavailable. Please enter coordinates manually.");
          } else if (err.code === 3) {
            setLocationFeedback("Location request timed out. Please retry or enter coordinates manually.");
          } else {
            setLocationFeedback("Could not determine location. Please enter coordinates manually.");
          }
          setLocationFeedbackType("warning");
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
      );
    } else {
      setLocationFeedback("Geolocation is not supported by your browser. Please enter coordinates manually.");
      setLocationFeedbackType("warning");
    }
  };

  const handleUseSampleCoordinates = () => {
    setLatitude("22.719600");
    setLongitude("75.857700");
    setLocationFeedback("Loaded sample coordinates: Indore Ward 34 (Demonstration data).");
    setLocationFeedbackType("info");
  };

  const parsedLat = parseFloat(latitude);
  const parsedLon = parseFloat(longitude);
  const hasValidCoordinates =
    !isNaN(parsedLat) &&
    !isNaN(parsedLon) &&
    parsedLat >= -90 &&
    parsedLat <= 90 &&
    parsedLon >= -180 &&
    parsedLon <= 180 &&
    (parsedLat !== 0 || parsedLon !== 0);

  const isDescribeValid = title.trim().length >= 5 && description.trim().length >= 10;
  const isLocateValid = hasValidCoordinates && addressRef.trim().length >= 3;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isDescribeValid) {
      setErrorMsg("Please enter an issue title (at least 5 characters) and description (at least 10 characters).");
      return;
    }
    if (!hasValidCoordinates) {
      setErrorMsg("Please confirm location coordinates using GPS, manual entry, or sample data.");
      return;
    }
    if (addressRef.trim().length < 3) {
      setErrorMsg("Please provide a street or landmark reference (at least 3 characters).");
      return;
    }

    setLoading(true);
    setErrorMsg("");

    try {
      const res = await api.submitReport({
        category_id: categoryId,
        title: title.trim(),
        description: description.trim(),
        latitude: parsedLat,
        longitude: parsedLon,
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
        title="Report an issue"
        description="Submit an infrastructure issue for municipal repair and public tracking. Reports are checked for duplicates and logged to the public ledger."
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
              Issue Report Registered
            </h2>

            <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "var(--space-4)", lineHeight: 1.5 }}>
              Your report has been recorded into the public ledger. You can follow its progress, track operator work claims, and participate in resolution verification.
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
              <div><strong>Reference ID:</strong> <code style={{ fontWeight: 600 }}>{successResult.public_id}</code></div>
              <div><strong>Category:</strong> {selectedCategoryObj?.name || successResult.category?.name}</div>
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
                  Your report was created as <code>{successResult.public_id}</code>, but the evidence attachment encountered an issue ({successResult.evidenceError}).
                </p>
              </div>
            )}

            <div className="action-group">
              <button
                onClick={() => navigate("/explorer")}
                className="button-primary"
              >
                Browse all cases
              </button>
              <button
                onClick={() => setSuccessResult(null)}
                className="btn-outline"
              >
                Report another issue
              </button>
            </div>
          </div>
        ) : (
          <div className="responsive-grid-2" style={{ alignItems: "start" }}>
            {/* Form Container */}
            <div>
              <SectionHeader title="Report details" />

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
                  {/* Step 1: Issue details */}
                  <div style={{ marginBottom: "var(--space-4)" }}>
                    <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--accent)", marginBottom: "var(--space-2)" }}>
                      1. ISSUE DETAILS
                    </div>

                    <div style={{ marginBottom: "var(--space-3)" }}>
                      <label htmlFor="cat-select">Category *</label>
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
                      <label htmlFor="title-input">Title / Short summary *</label>
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
                      <label htmlFor="desc-input">Description & observed severity *</label>
                      <textarea
                        id="desc-input"
                        rows={3}
                        placeholder="Describe the defect, dimensions, potential hazards to pedestrians or vehicles..."
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

                  {/* Step 2: Location */}
                  <div style={{
                    marginBottom: "var(--space-4)",
                    paddingTop: "var(--space-3)",
                    borderTop: "1px solid var(--border)",
                  }}>
                    <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--accent)", marginBottom: "var(--space-2)" }}>
                      2. LOCATION
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
                        <span style={{ fontSize: "11px", color: "var(--danger)" }}>Please specify street or landmark (at least 3 characters).</span>
                      )}
                    </div>

                    <div style={{
                      background: "var(--surface-muted)",
                      padding: "var(--space-3)",
                      border: "1px solid var(--border)",
                      marginBottom: "var(--space-3)",
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)", flexWrap: "wrap", gap: "var(--space-2)" }}>
                        <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-secondary)" }}>
                          Coordinates (GPS or Manual)
                        </span>
                        <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                          <button
                            type="button"
                            onClick={handleUseBrowserLocation}
                            className="btn-outline btn-sm"
                          >
                            Acquire browser GPS
                          </button>
                          <button
                            type="button"
                            onClick={handleUseSampleCoordinates}
                            className="btn-outline btn-sm"
                            title="Load sample coordinates for testing"
                          >
                            Use sample location
                          </button>
                        </div>
                      </div>

                      {locationFeedback && (
                        <div
                          style={{
                            fontSize: "11px",
                            color:
                              locationFeedbackType === "success"
                                ? "var(--success)"
                                : locationFeedbackType === "warning"
                                ? "var(--danger)"
                                : "var(--accent)",
                            marginBottom: "var(--space-2)",
                          }}
                        >
                          {locationFeedback}
                        </div>
                      )}

                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-2)" }}>
                        <div>
                          <label htmlFor="lat-input" style={{ fontSize: "11px" }}>Latitude</label>
                          <input
                            id="lat-input"
                            type="number"
                            step="0.000001"
                            placeholder="e.g. 22.719600"
                            value={latitude}
                            onChange={(e) => setLatitude(e.target.value)}
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
                            placeholder="e.g. 75.857700"
                            value={longitude}
                            onChange={(e) => setLongitude(e.target.value)}
                            required
                            style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: "12px" }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Step 3: Optional evidence & observer */}
                  <div style={{
                    marginBottom: "var(--space-4)",
                    paddingTop: "var(--space-3)",
                    borderTop: "1px solid var(--border)",
                  }}>
                    <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--accent)", marginBottom: "var(--space-2)" }}>
                      3. EVIDENCE & OBSERVER (OPTIONAL)
                    </div>

                    <div style={{ marginBottom: "var(--space-3)" }}>
                      <label htmlFor="name-input">Observer name or pseudonym (optional)</label>
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
                      <label htmlFor="file-input">Attach photo or document (optional, max 10MB)</label>
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
                          Attached: {evidenceFile?.name} ({(evidenceFile!.size / 1024).toFixed(0)} KB)
                        </div>
                        <img
                          src={evidencePreviewUrl}
                          alt="Evidence preview"
                          style={{ maxWidth: "100%", maxHeight: "160px", objectFit: "contain", border: "1px solid var(--border)" }}
                        />
                      </div>
                    )}
                  </div>

                  <button
                    type="submit"
                    disabled={loading || !isDescribeValid || !isLocateValid}
                    className="button-primary"
                    style={{ width: "100%" }}
                  >
                    {loading ? "Submitting report..." : "Submit issue report"}
                  </button>
                </form>
              </div>
            </div>

            {/* Practical Reporting Guidance Sidebar */}
            <div>
              <SectionHeader title="Reporting guidance" />

              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "var(--space-4)", fontSize: "12px" }}>
                <h3 style={{ fontSize: "13px", margin: "0 0 var(--space-2)", fontWeight: 600 }}>What makes a useful report?</h3>
                <p style={{ color: "var(--text-secondary)", lineHeight: 1.5, margin: "0 0 var(--space-3)" }}>
                  Include clear details about the physical hazard: depth of potholes, width of cracks, active water flow, or obscured street signs.
                </p>

                <h3 style={{ fontSize: "13px", margin: "0 0 var(--space-2)", fontWeight: 600 }}>Location accuracy</h3>
                <p style={{ color: "var(--text-secondary)", lineHeight: 1.5, margin: "0 0 var(--space-3)" }}>
                  Use the browser GPS button when standing near the issue, or provide the nearest landmark intersection. Reports within 50 meters of existing issues are correlated to prevent duplicate tickets.
                </p>

                <h3 style={{ fontSize: "13px", margin: "0 0 var(--space-2)", fontWeight: 600 }}>Photographic evidence</h3>
                <p style={{ color: "var(--text-secondary)", lineHeight: 1.5, margin: "0 0 var(--space-3)" }}>
                  A clear photo helps reviewers triage priority accurately and enables community members to verify when the repair is completed.
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
