import React, { useEffect, useState } from "react";
import {
  History,
  Download,
  FileSpreadsheet,
  Eye,
  X,
  ChevronLeft,
  ChevronRight,
  User,
} from "lucide-react";
import { api } from "../api/client";
import {
  ExportFormat,
  ForecastRecordResponse,
  ForecastRunSummary,
} from "../types/api";
import { Badge } from "../components/ui/Badge";
import { Alert } from "../components/ui/Alert";
import { useAuth } from "../context/AuthContext";

export const HistoryPage: React.FC = () => {
  const { user } = useAuth();
  const [runs, setRuns] = useState<ForecastRunSummary[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const pageSize = 15;

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Drilldown run details
  const [selectedRun, setSelectedRun] = useState<ForecastRunSummary | null>(null);
  const [runRecords, setRunRecords] = useState<ForecastRecordResponse[]>([]);
  const [recordsTotal, setRecordsTotal] = useState<number>(0);
  const [isLoadingRecords, setIsLoadingRecords] = useState<boolean>(false);
  const [isExporting, setIsExporting] = useState<boolean>(false);

  const loadRuns = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await api.listForecastRuns({ page, page_size: pageSize });
      setRuns(resp.items);
      setTotal(resp.total);
    } catch (err: any) {
      setError(err.message || "Failed to load forecast execution history.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadRuns();
  }, [page]);

  const handleInspectRun = async (run: ForecastRunSummary) => {
    setSelectedRun(run);
    setIsLoadingRecords(true);
    try {
      const resp = await api.getForecastRunResults(run.forecast_run_id, 1, 50);
      setRunRecords(resp.items);
      setRecordsTotal(resp.total);
    } catch (err: any) {
      alert(`Failed to load predictions: ${err.message}`);
    } finally {
      setIsLoadingRecords(false);
    }
  };

  const handleExport = async (runId: string, format: ExportFormat) => {
    setIsExporting(true);
    try {
      const exp = await api.createExport(runId, format);
      const url = api.getDownloadUrl(runId, exp.export_id);
      window.open(url, "_blank");
    } catch (err: any) {
      alert(`Export generation failed: ${err.message}`);
    } finally {
      setIsExporting(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="page-wrapper">
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "1.85rem", marginBottom: "0.35rem" }}>Execution History &amp; Exports</h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
          Audit trail of completed forecasting runs, user attribution, and downloadable CSV/XLSX artifacts.
        </p>
      </div>

      {error && <Alert type="error">{error}</Alert>}

      {/* Runs Table */}
      <div className="table-container" style={{ marginBottom: "1.5rem" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Run Identifier</th>
              <th>Status</th>
              <th>Model Name</th>
              <th>Cutoff Date</th>
              <th>Horizon</th>
              <th>Requested SKUs</th>
              <th>Predictions</th>
              <th>Initiated By</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={9} style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                  Loading execution runs...
                </td>
              </tr>
            ) : runs.length === 0 ? (
              <tr>
                <td colSpan={9} style={{ textAlign: "center", padding: "3rem", color: "var(--text-dim)" }}>
                  No forecast executions found in database.
                </td>
              </tr>
            ) : (
              runs.map((r) => (
                <tr key={r.forecast_run_id}>
                  <td style={{ fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--primary-500)" }}>
                    {r.forecast_run_id}
                  </td>
                  <td>
                    <Badge status={r.status} />
                  </td>
                  <td style={{ fontSize: "0.825rem", fontWeight: 500 }}>{r.model_id}</td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{r.forecast_origin}</td>
                  <td>
                    <span className="badge badge-neutral">H={r.horizon_weeks}</span>
                  </td>
                  <td>{r.requested_sku_count}</td>
                  <td style={{ fontWeight: 600 }}>{r.prediction_count}</td>
                  <td>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      <User size={12} />
                      {r.user_id || "System"}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: "0.4rem" }}>
                      <button
                        className="btn btn-secondary"
                        style={{ padding: "0.3rem 0.6rem", fontSize: "0.75rem" }}
                        onClick={() => handleInspectRun(r)}
                        title="View Predictions"
                      >
                        <Eye size={13} />
                        View
                      </button>
                      {r.status === "SUCCEEDED" && (
                        <>
                          <button
                            className="btn btn-secondary"
                            style={{ padding: "0.3rem 0.6rem", fontSize: "0.75rem" }}
                            onClick={() => handleExport(r.forecast_run_id, "CSV")}
                            disabled={isExporting}
                            title="Download CSV"
                          >
                            <Download size={13} />
                            CSV
                          </button>
                          <button
                            className="btn btn-secondary"
                            style={{ padding: "0.3rem 0.6rem", fontSize: "0.75rem" }}
                            onClick={() => handleExport(r.forecast_run_id, "XLSX")}
                            disabled={isExporting}
                            title="Download Excel"
                          >
                            <FileSpreadsheet size={13} />
                            Excel
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: "0.825rem", color: "var(--text-muted)" }}>
          Showing {runs.length > 0 ? (page - 1) * pageSize + 1 : 0} &ndash;{" "}
          {Math.min(page * pageSize, total)} of {total} runs
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            className="btn btn-secondary"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            style={{ padding: "0.4rem 0.75rem", fontSize: "0.8rem" }}
          >
            <ChevronLeft size={16} /> Prev
          </button>
          <span
            style={{
              display: "flex",
              alignItems: "center",
              padding: "0 0.85rem",
              fontSize: "0.825rem",
              color: "var(--text-muted)",
              background: "var(--bg-card)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            Page {page} / {totalPages}
          </span>
          <button
            className="btn btn-secondary"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            style={{ padding: "0.4rem 0.75rem", fontSize: "0.8rem" }}
          >
            Next <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* Drill-down Modal */}
      {selectedRun && (
        <div className="modal-overlay" onClick={() => setSelectedRun(null)}>
          <div className="modal-content" style={{ maxWidth: "880px" }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.25rem" }}>
              <div>
                <h2 style={{ fontSize: "1.25rem", fontFamily: "var(--font-mono)", marginBottom: "0.2rem" }}>
                  Run Details: {selectedRun.forecast_run_id}
                </h2>
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  Model: <strong>{selectedRun.model_id}</strong> &bull; Cutoff: {selectedRun.forecast_origin} &bull; Created by: {selectedRun.user_id || "System"}
                </div>
              </div>
              <button className="btn btn-ghost" onClick={() => setSelectedRun(null)} style={{ padding: "0.4rem" }}>
                <X size={20} />
              </button>
            </div>

            {isLoadingRecords ? (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
                Loading prediction records...
              </div>
            ) : (
              <div className="table-container" style={{ maxHeight: "400px", overflowY: "auto" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>SKU ID</th>
                      <th>Target Week</th>
                      <th>Step</th>
                      <th>Prediction (Units)</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runRecords.map((r, i) => (
                      <tr key={i}>
                        <td style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{r.sku_id}</td>
                        <td style={{ fontFamily: "var(--font-mono)" }}>{r.target_week}</td>
                        <td>+{r.horizon_step}</td>
                        <td style={{ fontWeight: 700, color: "var(--primary-500)" }}>{r.prediction.toFixed(2)}</td>
                        <td>
                          <Badge status={r.prediction_status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
