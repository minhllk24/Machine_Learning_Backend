import React, { useEffect, useState } from "react";
import {
  Database,
  Calendar,
  Cpu,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";
import { api } from "../api/client";
import { DashboardSummary, ForecastRunSummary, ModelDetail } from "../types/api";
import { Badge } from "../components/ui/Badge";
import { Alert } from "../components/ui/Alert";

interface DashboardPageProps {
  onNavigate: (path: string) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigate }) => {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [models, setModels] = useState<ModelDetail[]>([]);
  const [recentRuns, setRecentRuns] = useState<ForecastRunSummary[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [sumData, modelsData, runsData] = await Promise.all([
          api.getDashboardSummary(),
          api.listModels(),
          api.listForecastRuns({ page: 1, page_size: 5 }),
        ]);
        setSummary(sumData);
        setModels(modelsData);
        setRecentRuns(runsData.items);
      } catch (err: any) {
        setError(err.message || "Failed to load dashboard data from backend API.");
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  if (isLoading) {
    return (
      <div className="page-wrapper" style={{ textAlign: "center", padding: "4rem 0" }}>
        <div style={{ fontSize: "1.1rem", color: "var(--text-muted)" }}>Loading telemetry & dashboard summaries...</div>
      </div>
    );
  }

  return (
    <div className="page-wrapper">
      {/* Page Title & Subtitle */}
      <div style={{ marginBottom: "2rem", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 style={{ fontSize: "1.85rem", marginBottom: "0.35rem" }}>System Dashboard</h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
            Real-time status, dataset lineage, registered model candidates, and execution history.
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => onNavigate("/forecast")}
          style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}
        >
          <TrendingUp size={16} />
          New Forecast Run
        </button>
      </div>

      {error && <Alert type="error" title="Backend Synchronization Error">{error}</Alert>}

      {/* Governance Banner */}
      <div className="governance-banner">
        <AlertTriangle size={20} color="var(--status-warning)" style={{ flexShrink: 0, marginTop: "2px" }} />
        <div>
          <div className="governance-banner-title">ACADEMIC RESEARCH & HISTORICAL AUDIT NOTICE</div>
          <div className="governance-banner-text">
            This system evaluates historical retail transactions from the <strong>UCI Online Retail II</strong> dataset
            (December 2009 &ndash; December 2011). Because retail dynamics have structurally changed over time,
            current-market applicability has not been established (<code>current_market_applicability_assessed = FALSE</code>).
            All forecasts are computed using genuine frozen model artifacts.
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      {summary && (
        <div className="kpi-grid">
          <div className="glass-panel kpi-card">
            <div className="kpi-title">
              <span>Qualified Panel SKUs</span>
              <ShieldCheck size={16} color="var(--status-success)" />
            </div>
            <div className="kpi-value">{summary.catalog.total_skus.toLocaleString()}</div>
            <div className="kpi-subtitle">
              {summary.catalog.primary_cohort_skus} Causal Mature &bull; {summary.catalog.secondary_cohort_skus} Late Maturing
            </div>
          </div>

          <div className="glass-panel kpi-card">
            <div className="kpi-title">
              <span>Development Weeks</span>
              <Calendar size={16} color="var(--primary-500)" />
            </div>
            <div className="kpi-value">{summary.timeline.development_weeks_count}</div>
            <div className="kpi-subtitle">
              Start: {summary.timeline.dataset_start_week} &bull; Cutoff: {summary.timeline.training_cutoff}
            </div>
          </div>

          <div className="glass-panel kpi-card">
            <div className="kpi-title">
              <span>Final Holdout Weeks</span>
              <Calendar size={16} color="var(--status-info)" />
            </div>
            <div className="kpi-value">{summary.timeline.holdout_weeks_count}</div>
            <div className="kpi-subtitle">
              {summary.timeline.holdout_start_week} &rarr; {summary.timeline.holdout_end_week}
            </div>
          </div>

          <div className="glass-panel kpi-card">
            <div className="kpi-title">
              <span>Serving-Ready Models</span>
              <Cpu size={16} color="var(--status-warning)" />
            </div>
            <div className="kpi-value">
              {summary.candidate_models.filter((m) => m.serving_status === "SERVING_READY").length}
            </div>
            <div className="kpi-subtitle">
              CatBoost MAE, Tweedie &amp; TiDE Sequence
            </div>
          </div>
        </div>
      )}

      {/* Two Column Layout: Model Registry & Recent Executions */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.75rem", marginBottom: "2rem" }}>
        {/* Serving Models Card */}
        <div className="glass-panel" style={{ padding: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
            <h3 style={{ fontSize: "1.1rem" }}>Registered Model Artifacts</h3>
            <button className="btn btn-ghost" style={{ fontSize: "0.8rem", padding: "0.3rem 0.6rem" }} onClick={() => onNavigate("/registry")}>
              View All <ArrowRight size={14} />
            </button>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
            {[...models]
              .sort((a, b) => (b.serving_status === "SERVING_READY" ? 1 : 0) - (a.serving_status === "SERVING_READY" ? 1 : 0))
              .slice(0, 4)
              .map((m) => {
                const maxH = m.supported_horizons && m.supported_horizons.length > 0 ? Math.max(...m.supported_horizons) : 0;
                const horizonLabel = maxH > 0 ? `H=1..${maxH}` : "Not Serving";
                const roleLabel = m.artifact_role || m.model_role || "CV_ARTIFACT";

                return (
                  <div
                    key={m.model_id}
                    style={{
                      background: "rgba(15, 23, 42, 0.6)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "var(--radius-md)",
                      padding: "0.85rem 1rem",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: "0.875rem", color: "var(--text-main)", marginBottom: "0.2rem" }}>
                        {m.model_name}
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                        Role: {roleLabel} &bull; Horizons: {horizonLabel}
                      </div>
                    </div>
                    <Badge status={m.serving_status} />
                  </div>
                );
              })}
          </div>
        </div>

        {/* Recent Executions Card */}
        <div className="glass-panel" style={{ padding: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
            <h3 style={{ fontSize: "1.1rem" }}>Recent Forecast Runs</h3>
            <button className="btn btn-ghost" style={{ fontSize: "0.8rem", padding: "0.3rem 0.6rem" }} onClick={() => onNavigate("/history")}>
              View All <ArrowRight size={14} />
            </button>
          </div>

          {recentRuns.length === 0 ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-dim)", fontSize: "0.85rem" }}>
              No forecast runs executed yet in this session.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
              {recentRuns.map((run) => (
                <div
                  key={run.forecast_run_id}
                  style={{
                    background: "rgba(15, 23, 42, 0.6)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-md)",
                    padding: "0.85rem 1rem",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.825rem", color: "var(--primary-500)", fontWeight: 600 }}>
                      {run.forecast_run_id}
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                      {run.model_id} &bull; Cutoff: {run.forecast_origin} &bull; H={run.horizon_weeks}
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {run.prediction_count} records
                    </span>
                    <Badge status={run.status} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
