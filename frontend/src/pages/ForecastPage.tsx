import React, { useEffect, useState } from "react";
import {
  TrendingUp,
  Download,
  AlertCircle,
  Cpu,
  Layers,
  CheckCircle,
  FileSpreadsheet,
  Clock,
  Sparkles,
} from "lucide-react";
import { api } from "../api/client";
import {
  ExportFormat,
  ForecastResponse,
  ModelDetail,
  SKUForecastRecord,
} from "../types/api";
import { SvgChart, DataPoint } from "../components/ui/SvgChart";
import { Badge } from "../components/ui/Badge";
import { Alert } from "../components/ui/Alert";
import { useAuth } from "../context/AuthContext";

export const ForecastPage: React.FC = () => {
  const { user } = useAuth();
  const [models, setModels] = useState<ModelDetail[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("CatBoost__MAE");
  const [skuInput, setSkuInput] = useState<string>("10002, 20713, 85123A");
  const [forecastOrigin, setForecastOrigin] = useState<string>("2011-10-03");
  const [horizonWeeks, setHorizonWeeks] = useState<number>(4);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ForecastResponse | null>(null);

  useEffect(() => {
    const loadModels = async () => {
      try {
        const list = await api.listModels();
        // Filter to SERVING_READY models
        const readyModels = list.filter((m) => m.serving_status === "SERVING_READY");
        setModels(readyModels.length > 0 ? readyModels : list);
        if (readyModels.length > 0) {
          setSelectedModel(readyModels[0].model_id);
        }
      } catch (err: any) {
        setError("Failed to fetch registered models from API.");
      }
    };
    loadModels();
  }, []);

  const handleRunForecast = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    const skuList = skuInput
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);

    if (skuList.length === 0) {
      setError("Please specify at least one valid SKU identifier.");
      setIsLoading(false);
      return;
    }

    try {
      const resp = await api.createForecast({
        model_id: selectedModel,
        sku_ids: skuList,
        forecast_origin: forecastOrigin,
        horizon_weeks: Number(horizonWeeks),
      });
      setResult(resp);
    } catch (err: any) {
      setError(err.message || "Failed to generate demand forecast.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateExport = async (format: ExportFormat) => {
    if (!result) return;
    setIsExporting(true);
    try {
      const exp = await api.createExport(result.forecast_run_id, format);
      const downloadUrl = api.getDownloadUrl(result.forecast_run_id, exp.export_id);
      window.open(downloadUrl, "_blank");
    } catch (err: any) {
      alert(`Export failed: ${err.message}`);
    } finally {
      setIsExporting(false);
    }
  };

  // Prepare chart data from predictions (grouped by target_week)
  const chartData: DataPoint[] = [];
  if (result && result.predictions) {
    const weekMap: Record<string, number> = {};
    result.predictions.forEach((p) => {
      weekMap[p.target_week] = (weekMap[p.target_week] || 0) + p.prediction;
    });
    Object.keys(weekMap)
      .sort()
      .forEach((w) => {
        chartData.push({
          label: w,
          forecast: weekMap[w],
        });
      });
  }

  return (
    <div className="page-wrapper">
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "1.85rem", marginBottom: "0.35rem" }}>Demand Forecasting</h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
          Generate multi-horizon SKU-week predictions using verified production candidate models.
        </p>
      </div>

      {user?.role === "viewer" && (
        <Alert type="warning" title="Viewer Access Level">
          Your account has the <strong>Viewer</strong> role. You can explore existing forecast runs, but initiating new
          inferences requires <strong>Analyst</strong>, <strong>Planner</strong>, or <strong>Admin</strong> privileges.
        </Alert>
      )}

      {error && <Alert type="error" title="Forecasting Error">{error}</Alert>}

      {/* Forecast Configuration Form */}
      <div className="glass-panel" style={{ padding: "1.75rem", marginBottom: "2rem" }}>
        <form onSubmit={handleRunForecast}>
          <div style={{ display: "grid", gridTemplateColumns: "1.5fr 2fr 1fr 1fr", gap: "1.25rem", alignItems: "flex-end" }}>
            {/* Model Selector */}
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Production Model</label>
              <select
                className="form-select"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                disabled={isLoading}
              >
                {models.map((m) => (
                  <option key={m.model_id} value={m.model_id}>
                    {m.model_name} ({m.model_role})
                  </option>
                ))}
              </select>
            </div>

            {/* SKU Input */}
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Target SKUs (comma-separated)</label>
              <input
                type="text"
                className="form-input"
                value={skuInput}
                onChange={(e) => setSkuInput(e.target.value)}
                disabled={isLoading}
                placeholder="e.g. 10002, 20713, 85123A"
              />
            </div>

            {/* Forecast Origin */}
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Cutoff Origin</label>
              <input
                type="date"
                className="form-input"
                value={forecastOrigin}
                max="2011-10-03"
                onChange={(e) => setForecastOrigin(e.target.value)}
                disabled={isLoading}
              />
            </div>

            {/* Horizon Weeks */}
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Horizon (Weeks)</label>
              <select
                className="form-select"
                value={horizonWeeks}
                onChange={(e) => setHorizonWeeks(Number(e.target.value))}
                disabled={isLoading}
              >
                <option value={1}>H=1 (1 week)</option>
                <option value={2}>H=2 (2 weeks)</option>
                <option value={3}>H=3 (3 weeks)</option>
                <option value={4}>H=4 (4 weeks - Principal Champion Horizon)</option>
              </select>
            </div>
          </div>

          <div style={{ marginTop: "1.5rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: "0.775rem", color: "var(--text-dim)" }}>
              Historical development pool cutoff: <code>2011-10-03</code>. Holdout is preserved and not rescored.
            </div>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isLoading || user?.role === "viewer"}
              style={{ minWidth: "160px" }}
            >
              <Sparkles size={16} />
              {isLoading ? "Running Inference..." : "Generate Predictions"}
            </button>
          </div>
        </form>
      </div>

      {/* Results Section */}
      {result && (
        <div>
          {/* Metadata Header Bar */}
          <div
            className="glass-panel"
            style={{
              padding: "1.25rem 1.5rem",
              marginBottom: "1.5rem",
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "1rem",
            }}
          >
            <div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                Execution ID
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--primary-500)", fontSize: "0.95rem" }}>
                {result.forecast_run_id}
              </div>
            </div>

            <div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                Model &amp; Version
              </div>
              <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>
                {result.model_id} (v{result.model_version})
              </div>
            </div>

            <div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                Horizon &amp; Records
              </div>
              <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>
                {result.horizon_weeks} weeks ({result.predictions.length} records)
              </div>
            </div>

            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                className="btn btn-secondary"
                onClick={() => handleCreateExport("CSV")}
                disabled={isExporting}
                style={{ fontSize: "0.8rem", padding: "0.5rem 0.85rem" }}
              >
                <Download size={14} />
                Export CSV
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => handleCreateExport("XLSX")}
                disabled={isExporting}
                style={{ fontSize: "0.8rem", padding: "0.5rem 0.85rem" }}
              >
                <FileSpreadsheet size={14} />
                Export Excel
              </button>
            </div>
          </div>

          {/* Interactive Chart */}
          <div style={{ marginBottom: "2rem" }}>
            <SvgChart
              data={chartData}
              title="Aggregated Predicted Demand Across Forecast Horizon"
              subtitle={`Total expected sales volume for ${result.predictions.length / result.horizon_weeks} requested SKUs.`}
              height={280}
              forecastLabel="Predicted Units"
            />
          </div>

          {/* Predictions Table */}
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>SKU Code</th>
                  <th>Target Week (Monday)</th>
                  <th>Horizon Step</th>
                  <th>Predicted Demand (Units)</th>
                  <th>Inference Status</th>
                </tr>
              </thead>
              <tbody>
                {result.predictions.map((p, idx) => (
                  <tr key={`${p.sku_id}-${p.target_week}-${idx}`}>
                    <td style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{p.sku_id}</td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>{p.target_week}</td>
                    <td>
                      <span className="badge badge-neutral">Step +{p.horizon_step}</span>
                    </td>
                    <td style={{ fontWeight: 700, color: "var(--primary-500)", fontSize: "0.95rem" }}>
                      {p.prediction.toFixed(2)}
                    </td>
                    <td>
                      <Badge status={p.prediction_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
