import React, { useState, useEffect } from "react";
import { Award, ShieldAlert, BarChart3, HelpCircle, Lock } from "lucide-react";
import { Badge } from "../components/ui/Badge";
import { BenchmarkMetric } from "../types/api";
import { api } from "../api/client";


const OOF_METRICS: BenchmarkMetric[] = [
  {
    model_family: "CatBoost MAE",
    model_id: "CatBoost__MAE",
    role: "Primary Production Candidate",
    protocol: "Rolling OOF (CV Folds 1-5)",
    horizon: "Pooled OOF (H=1..8)",
    wape: 66.16,
    mae: 19.51,
    rmse: 81.36,
    signed_bias: -39.26,
    status: "Champion (Primary)",
  },
  {
    model_family: "LightGBM Regression L1",
    model_id: "LightGBM__regression_l1",
    role: "Exploratory Tree Benchmark",
    protocol: "Rolling OOF (CV Folds 1-5)",
    horizon: "Pooled OOF (H=1..8)",
    wape: 66.29,
    mae: 19.55,
    rmse: 81.06,
    signed_bias: -41.47,
    status: "Research Benchmark",
  },
  {
    model_family: "TiDE Sequence v1",
    model_id: "TiDE_Sequence_v1",
    role: "Direct Multi-Horizon Sequence",
    protocol: "Rolling OOF (CV Folds 1-5)",
    horizon: "Pooled OOF (H=1..8)",
    wape: 67.71,
    mae: 19.97,
    rmse: 80.62,
    signed_bias: -36.79,
    status: "Sequence Benchmark",
  },
  {
    model_family: "Temporal Fusion Transformer (TFT)",
    model_id: "TFT_Sequence_v1",
    role: "Attention Deep Learning Benchmark",
    protocol: "Rolling OOF (CV Folds 1-5)",
    horizon: "Pooled OOF (H=1..8)",
    wape: 69.14,
    mae: 20.39,
    rmse: 82.10,
    signed_bias: -39.21,
    status: "Research Benchmark",
  },
  {
    model_family: "CatBoost Tweedie (p=1.5)",
    model_id: "CatBoost__Tweedie_p15",
    role: "Low-Aggregate-Bias Diagnostic",
    protocol: "Rolling OOF (CV Folds 1-5)",
    horizon: "Pooled OOF (H=1..8)",
    wape: 73.51,
    mae: 21.68,
    rmse: 77.73,
    signed_bias: -5.02,
    status: "Diagnostic (Low Bias)",
  },
  {
    model_family: "Moving Average (4-Week)",
    model_id: "MA_4",
    role: "Statistical Baseline",
    protocol: "Rolling OOF (CV Folds 1-5)",
    horizon: "Pooled OOF (H=1..8)",
    wape: 76.75,
    mae: 22.63,
    rmse: 82.78,
    signed_bias: -4.12,
    status: "Research Benchmark",
  },
  {
    model_family: "Naive (Last-Week Persistence)",
    model_id: "Naive_1",
    role: "Statistical Baseline",
    protocol: "Rolling OOF (CV Folds 1-5)",
    horizon: "Pooled OOF (H=1..8)",
    wape: 88.84,
    mae: 26.20,
    rmse: 102.85,
    signed_bias: -3.34,
    status: "Research Benchmark",
  },
];

const HOLDOUT_METRICS: BenchmarkMetric[] = [
  {
    model_family: "CatBoost MAE",
    model_id: "CatBoost__MAE",
    role: "Primary Production Candidate",
    protocol: "Fixed-Origin Final Holdout (8 Weeks)",
    horizon: "Cumulative H=4",
    wape: 65.57,
    mae: 22.21,
    rmse: 101.00,
    signed_bias: -30.87,
    status: "Champion (Primary)",
  },
  {
    model_family: "TiDE Sequence v1",
    model_id: "TiDE_Sequence_v1",
    role: "Direct Multi-Horizon Sequence",
    protocol: "Fixed-Origin Final Holdout (8 Weeks)",
    horizon: "Cumulative H=4",
    wape: 65.83,
    mae: 22.30,
    rmse: 99.27,
    signed_bias: -28.96,
    status: "Sequence Benchmark",
  },
  {
    model_family: "CatBoost Tweedie (p=1.5)",
    model_id: "CatBoost__Tweedie_p15",
    role: "Low-Aggregate-Bias Diagnostic",
    protocol: "Fixed-Origin Final Holdout (8 Weeks)",
    horizon: "Cumulative H=4",
    wape: 73.88,
    mae: 25.03,
    rmse: 96.26,
    signed_bias: 1.61,
    status: "Diagnostic (Low Bias)",
  },
  {
    model_family: "Moving Average (4-Week)",
    model_id: "MA_4",
    role: "Statistical Baseline",
    protocol: "Fixed-Origin Final Holdout (8 Weeks)",
    horizon: "Cumulative H=4",
    wape: 76.46,
    mae: 25.90,
    rmse: 99.55,
    signed_bias: 1.81,
    status: "Research Benchmark",
  },
  {
    model_family: "Naive (Last-Week Persistence)",
    model_id: "Naive_1",
    role: "Statistical Baseline",
    protocol: "Fixed-Origin Final Holdout (8 Weeks)",
    horizon: "Cumulative H=4",
    wape: 101.11,
    mae: 34.25,
    rmse: 146.41,
    signed_bias: 16.27,
    status: "Research Benchmark",
  },
];

export const EvaluationPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"OOF" | "HOLDOUT">("OOF");
  const [oofMetrics, setOofMetrics] = useState<BenchmarkMetric[]>(OOF_METRICS);
  const [holdoutMetrics, setHoldoutMetrics] = useState<BenchmarkMetric[]>(HOLDOUT_METRICS);

  useEffect(() => {
    const fetchLiveLeaderboard = async () => {
      try {
        const data = await api.getLeaderboard();
        if (data.oof_metrics && data.oof_metrics.length > 0) {
          setOofMetrics(data.oof_metrics);
        }
        if (data.holdout_metrics && data.holdout_metrics.length > 0) {
          setHoldoutMetrics(data.holdout_metrics);
        }
      } catch (err) {
        console.warn("Using physical fallback metrics for leaderboard:", err);
      }
    };
    fetchLiveLeaderboard();
  }, []);

  const currentMetrics = activeTab === "OOF" ? oofMetrics : holdoutMetrics;

  return (
    <div className="page-wrapper">
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "1.85rem", marginBottom: "0.35rem" }}>Model Evaluation &amp; Benchmarks</h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
          Published historical validation results across candidate model families under strictly audited protocols.
        </p>
      </div>

      {/* Governance Banner */}
      <div className="governance-banner">
        <Lock size={20} color="var(--primary-500)" style={{ flexShrink: 0, marginTop: "2px" }} />
        <div>
          <div className="governance-banner-title" style={{ color: "var(--primary-500)" }}>
            FROZEN RESEARCH BENCHMARK RECORD (NO DYNAMIC HOLD-OUT RESCORING)
          </div>
          <div className="governance-banner-text">
            The final holdout (2011-10-10 &ndash; 2011-11-28, 8 weeks, 22,280 predictions) has already been scored once in Phase 8.
            Under scientific research governance, <strong>the holdout is never rerun or tuned against</strong>.
            CatBoost MAE is the designated champion model based on the frozen Phase 7 Selection Protocol.
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="nav-tabs">
        <button
          className={`nav-tab ${activeTab === "OOF" ? "active" : ""}`}
          onClick={() => setActiveTab("OOF")}
        >
          Rolling OOF Validation (Folds 1&ndash;5, 96 Weeks)
        </button>
        <button
          className={`nav-tab ${activeTab === "HOLDOUT" ? "active" : ""}`}
          onClick={() => setActiveTab("HOLDOUT")}
        >
          Fixed-Origin Final Holdout (8 Weeks, 22,280 Predictions)
        </button>
      </div>

      {/* Leaderboard Table */}
      <div className="table-container" style={{ marginBottom: "2rem" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Model Candidate</th>
              <th>Evaluation Protocol</th>
              <th>Target Horizon</th>
              <th>WAPE (%)</th>
              <th>MAE (Units)</th>
              <th>RMSE</th>
              <th>Signed Bias</th>
              <th>Model Role</th>
            </tr>
          </thead>
          <tbody>
            {currentMetrics.map((m, idx) => (
              <tr key={idx}>
                <td>
                  <div style={{ fontWeight: 700, color: "var(--text-main)" }}>{m.model_family}</div>
                  <div style={{ fontSize: "0.725rem", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                    {m.model_id}
                  </div>
                </td>
                <td>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{m.protocol}</span>
                </td>
                <td>
                  <span className="badge badge-neutral">{m.horizon}</span>
                </td>
                <td style={{ fontWeight: 700, color: idx === 0 ? "var(--status-success)" : "var(--text-main)", fontSize: "0.95rem" }}>
                  {m.wape.toFixed(2)}%
                </td>
                <td style={{ fontWeight: 600 }}>{m.mae.toFixed(2)}</td>
                <td style={{ color: "var(--text-muted)" }}>{m.rmse.toFixed(2)}</td>
                <td style={{ color: Math.abs(m.signed_bias) <= 0.05 ? "var(--status-success)" : "var(--text-muted)" }}>
                  {m.signed_bias > 0 ? `+${m.signed_bias.toFixed(2)}` : m.signed_bias.toFixed(2)}
                </td>
                <td>
                  <span
                    className={`badge ${
                      m.status.includes("Champion")
                        ? "badge-success"
                        : m.status.includes("Diagnostic")
                        ? "badge-info"
                        : "badge-neutral"
                    }`}
                  >
                    {m.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* SHAP & Explainability Insights Card */}
      <div className="glass-panel" style={{ padding: "1.75rem" }}>
        <h3 style={{ fontSize: "1.1rem", marginBottom: "0.75rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <BarChart3 size={18} color="var(--primary-500)" />
          Feature Attribution &amp; Explainability (Phase 10 Forensic Audit)
        </h3>
        <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: "1rem", lineHeight: 1.5 }}>
          SHAP tree explainability analysis on CatBoost MAE reveals that demand forecasting accuracy is predominantly
          driven by autoregressive lag features and recent rolling statistics, rather than static catalog attributes:
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem", fontSize: "0.825rem" }}>
          <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "1rem", borderRadius: "var(--radius-md)" }}>
            <div style={{ fontWeight: 600, color: "var(--primary-500)", marginBottom: "0.25rem" }}>
              1. Lagged Demand (lag_1, lag_2)
            </div>
            <div style={{ color: "var(--text-dim)" }}>
              Represents 46.2% of mean absolute SHAP value. Recent observed velocity provides the strongest predictive signal.
            </div>
          </div>
          <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "1rem", borderRadius: "var(--radius-md)" }}>
            <div style={{ fontWeight: 600, color: "var(--primary-500)", marginBottom: "0.25rem" }}>
              2. Rolling Mean &amp; Std (4w, 12w)
            </div>
            <div style={{ color: "var(--text-dim)" }}>
              Captures recent volume trend and intermittency variance, mitigating single-week purchase spikes.
            </div>
          </div>
          <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "1rem", borderRadius: "var(--radius-md)" }}>
            <div style={{ fontWeight: 600, color: "var(--primary-500)", marginBottom: "0.25rem" }}>
              3. Calendar &amp; Month Sincos
            </div>
            <div style={{ color: "var(--text-dim)" }}>
              Accounts for strong Q4 holiday seasonality observed in the UK retail gift catalog in November and December.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
