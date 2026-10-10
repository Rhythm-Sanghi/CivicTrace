import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Category } from "../../lib/api";
import { MapPin, CheckCircle, Send } from "lucide-react";

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

      setSuccessResult(res);
      setLoading(false);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to submit report");
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "var(--space-8) 0" }}>
      <div className="container" style={{ maxWidth: "760px" }}>
        <div style={{ marginBottom: "var(--space-6)" }}>
          <div style={{
            fontFamily: "var(--font-family-mono)",
            fontSize: "var(--font-size-xs)",
            color: "var(--color-civic-blue)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            fontWeight: 600,
          }}>
            Civic Intake Portal
          </div>
          <h1 style={{ fontSize: "var(--font-size-2xl)", fontWeight: 700, letterSpacing: "-0.01em" }}>
            Report an Infrastructure Defect
          </h1>
          <p style={{ color: "var(--color-text-secondary)", fontSize: "var(--font-size-sm)", marginTop: "4px" }}>
            Submit an individual public observation. CivicTrace will automatically compute duplicate similarity against existing cases and initiate cryptographic evidence tracking.
          </p>
        </div>

        {successResult ? (
          <div className="card" style={{ borderLeft: "4px solid var(--color-verified-green)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
              <CheckCircle color="var(--color-verified-green)" size={24} />
              <h2 style={{ fontSize: "18px", fontWeight: 700 }}>Observation Successfully Registered</h2>
            </div>
            <p style={{ fontSize: "14px", color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
              Your report has been assigned public identifier <strong className="mono-id">{successResult.public_id}</strong>.
            </p>
            <div style={{ marginTop: "16px", display: "flex", gap: "10px" }}>
              <button onClick={() => navigate("/explorer")} className="btn btn-primary">
                View in Public Cases Explorer
              </button>
              <button
                onClick={() => {
                  setSuccessResult(null);
                  setTitle("");
                  setDescription("");
                }}
                className="btn btn-outline"
              >
                Submit Another Observation
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="card" style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
            {errorMsg && (
              <div style={{
                backgroundColor: "var(--color-disputed-red-subtle)",
                color: "var(--color-disputed-red)",
                padding: "10px 14px",
                borderRadius: "var(--radius-sm)",
                fontSize: "13px",
              }}>
                {errorMsg}
              </div>
            )}

            <div>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
                Infrastructure Category
              </label>
              <select
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                required
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  fontSize: "14px",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-sm)",
                  backgroundColor: "var(--color-surface)",
                }}
              >
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
                Brief Title
              </label>
              <input
                type="text"
                placeholder="e.g. Deep pothole on MG Road near Rajwada intersection"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                minLength={5}
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  fontSize: "14px",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-sm)",
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
                Observed Problem Details
              </label>
              <textarea
                rows={4}
                placeholder="Detail what you observed, physical depth, hazards to pedestrians, water leaks, or safety risks..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                required
                minLength={10}
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  fontSize: "14px",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-sm)",
                  lineHeight: 1.5,
                }}
              />
            </div>

            {/* Geographic Coordinates & Location */}
            <div style={{
              backgroundColor: "var(--color-surface-elevated)",
              padding: "16px",
              border: "1px solid var(--color-border-subtle)",
              borderRadius: "var(--radius-sm)",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <span style={{ fontWeight: 600, fontSize: "13px" }}>Geographic Location (Indore Area)</span>
                <button
                  type="button"
                  onClick={handleUseBrowserLocation}
                  className="btn btn-outline btn-sm"
                >
                  <MapPin size={12} /> Use GPS
                </button>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "12px" }}>
                <div>
                  <label style={{ fontSize: "11px", color: "var(--color-text-secondary)" }}>Latitude</label>
                  <input
                    type="number"
                    step="any"
                    value={latitude}
                    onChange={(e) => setLatitude(parseFloat(e.target.value))}
                    required
                    style={{
                      width: "100%",
                      padding: "6px 8px",
                      fontSize: "13px",
                      border: "1px solid var(--color-border)",
                      borderRadius: "var(--radius-sm)",
                      fontFamily: "var(--font-family-mono)",
                    }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: "11px", color: "var(--color-text-secondary)" }}>Longitude</label>
                  <input
                    type="number"
                    step="any"
                    value={longitude}
                    onChange={(e) => setLongitude(parseFloat(e.target.value))}
                    required
                    style={{
                      width: "100%",
                      padding: "6px 8px",
                      fontSize: "13px",
                      border: "1px solid var(--color-border)",
                      borderRadius: "var(--radius-sm)",
                      fontFamily: "var(--font-family-mono)",
                    }}
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: "11px", color: "var(--color-text-secondary)" }}>Street / Landmark Reference</label>
                <input
                  type="text"
                  placeholder="e.g. Near Rajwada Palace / Cloth Market Crossing"
                  value={addressRef}
                  onChange={(e) => setAddressRef(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "7px 10px",
                    fontSize: "13px",
                    border: "1px solid var(--color-border)",
                    borderRadius: "var(--radius-sm)",
                  }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
                Citizen Pseudonym (Privacy Preserving)
              </label>
              <input
                type="text"
                placeholder="e.g. Aarav Mehta (or leave blank for guest)"
                value={pseudonym}
                onChange={(e) => setPseudonym(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  fontSize: "13px",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-sm)",
                }}
              />
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "8px" }}>
              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary"
                style={{ padding: "10px 24px", fontSize: "14px" }}
              >
                <Send size={14} /> {loading ? "Recording Observation..." : "Submit to Public Record"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
