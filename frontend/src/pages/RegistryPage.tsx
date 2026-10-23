import React, { useEffect, useState } from "react";
import { Cpu, ShieldCheck, AlertCircle, FileCode, Hash, Calendar } from "lucide-react";
import { api } from "../api/client";
import { ModelDetail } from "../types/api";
import { Badge } from "../components/ui/Badge";
import { Alert } from "../components/ui/Alert";

export const RegistryPage: React.FC = () => {
  const [models, setModels] = useState<ModelDetail[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [filterTab, setFilterTab] = useState<"ALL" | "SERVING" | "CV">("SERVING");

  useEffect(() => {
    const fetchModels = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const list = await api.listModels();
        setModels(list);
      } catch (err: any) {
        setError(err.message || "Failed to load model registry.");
      } finally {
        setIsLoading(false);
      }
    };
    fetchModels();
  }, []);

  const servingReadyCount = models.filter((m) => m.serving_status === "SERVING_READY").length;
  const cvCount = models.filter((m) => m.serving_status !== "SERVING_READY").length;

  const filteredModels = models.filter((m) => {
    if (filterTab === "SERVING") return m.serving_status === "SERVING_READY";
    if (filterTab === "CV") return m.serving_status !== "SERVING_READY";
    return true;
  });

  return (
    <div className="page-wrapper">
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "1.85rem", marginBottom: "0.35rem" }}>Model Registry &amp; Telemetry</h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
          Inventory of registered model artifacts, cryptographic SHA-256 integrity hashes, and serving authorizations.
        </p>
      </div>

      {error && <Alert type="error">{error}</Alert>}

      {/* Tabs */}
      <div className="nav-tabs">
        <button
          className={`nav-tab ${filterTab === "SERVING" ? "active" : ""}`}
          onClick={() => setFilterTab("SERVING")}
        >
          Serving Ready Candidates ({servingReadyCount})
        </button>
        <button
          className={`nav-tab ${filterTab === "ALL" ? "active" : ""}`}
          onClick={() => setFilterTab("ALL")}
        >
          All Registered Artifacts ({models.length})
        </button>
        <button
          className={`nav-tab ${filterTab === "CV" ? "active" : ""}`}
          onClick={() => setFilterTab("CV")}
        >
          CV Training Artifacts ({cvCount})
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "1.5rem" }}>
        {filteredModels.map((m) => {
          const roleLabel = m.artifact_role || m.model_role || "CV_ARTIFACT";
          const shaChecksum = m.artifact_checksum || m.artifact_sha256 || "N/A";
          const horizonsDisplay =
            m.supported_horizons && m.supported_horizons.length > 0
              ? m.supported_horizons.map((h) => `H=${h}`).join(", ")
              : "Not Serving (CV Model)";

          return (
            <div key={m.model_id} className="glass-panel" style={{ padding: "1.75rem" }}>
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  gap: "1rem",
                  marginBottom: "1rem",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.35rem" }}>
                    <h3 style={{ fontSize: "1.2rem" }}>{m.model_name}</h3>
                    <Badge status={m.serving_status} />
                    <span className="badge badge-neutral">v{m.model_version || "1.0.0"}</span>
                    {m.cohort && <span className="badge badge-neutral">{m.cohort}</span>}
                  </div>
                  <div style={{ fontSize: "0.85rem", color: "var(--primary-500)", fontWeight: 600 }}>
                    Role: {roleLabel} {m.fold_id ? `(CV Fold ${m.fold_id})` : ""}
                  </div>
                </div>

                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", textTransform: "uppercase" }}>
                    Algorithm Family
                  </div>
                  <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{m.algorithm_family || m.framework || "N/A"}</div>
                </div>
              </div>

              {/* Grid Attributes */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(4, 1fr)",
                  gap: "1rem",
                  background: "rgba(15, 23, 42, 0.6)",
                  padding: "1rem 1.25rem",
                  borderRadius: "var(--radius-md)",
                  marginBottom: "1rem",
                  fontSize: "0.825rem",
                }}
              >
                <div>
                  <div style={{ color: "var(--text-dim)", marginBottom: "0.2rem" }}>Supported Horizons</div>
                  <div style={{ fontWeight: 600 }}>{horizonsDisplay}</div>
                </div>
                <div>
                  <div style={{ color: "var(--text-dim)", marginBottom: "0.2rem" }}>Training Cutoff</div>
                  <div style={{ fontWeight: 600, fontFamily: "var(--font-mono)" }}>
                    {m.training_cutoff || "2011-10-03"}
                  </div>
                </div>
                <div>
                  <div style={{ color: "var(--text-dim)", marginBottom: "0.2rem" }}>Objective / Metric</div>
                  <div style={{ fontWeight: 600 }}>{m.objective || "MAE"}</div>
                </div>
                <div>
                  <div style={{ color: "var(--text-dim)", marginBottom: "0.2rem" }}>Best Iteration</div>
                  <div style={{ fontWeight: 600 }}>{m.best_iteration ? `${m.best_iteration} trees` : "N/A"}</div>
                </div>
              </div>

              {/* Cryptographic SHA-256 */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  fontSize: "0.75rem",
                  color: "var(--text-dim)",
                  fontFamily: "var(--font-mono)",
                  background: "rgba(0, 0, 0, 0.25)",
                  padding: "0.5rem 0.75rem",
                  borderRadius: "var(--radius-sm)",
                  overflowX: "auto",
                }}
              >
                <Hash size={13} color="var(--status-info)" style={{ flexShrink: 0 }} />
                <span>SHA-256: {shaChecksum}</span>
              </div>

              {/* Readiness Reasons / Blockers if not ready */}
              {m.readiness_reasons && m.readiness_reasons.length > 0 && (
                <div style={{ marginTop: "1rem", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  <span style={{ fontWeight: 600, color: "var(--status-warning)" }}>Serving Notes: </span>
                  {m.readiness_reasons.join("; ")}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

