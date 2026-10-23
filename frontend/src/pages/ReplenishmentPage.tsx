import React, { useState } from "react";
import {
  Layers,
  Calculator,
  ShieldAlert,
  CheckCircle,
  HelpCircle,
  Info,
} from "lucide-react";
import { api } from "../api/client";
import { ReplenishmentSimulationResponse } from "../types/api";
import { Alert } from "../components/ui/Alert";
import { useAuth } from "../context/AuthContext";

export const ReplenishmentPage: React.FC = () => {
  const { user } = useAuth();
  const [skuId, setSkuId] = useState<string>("10002");
  const [forecastRunId, setForecastRunId] = useState<string>("");
  const [manualDemand, setManualDemand] = useState<string>("45.0");
  const [stockOnHand, setStockOnHand] = useState<string>("20.0");
  const [incomingStock, setIncomingStock] = useState<string>("10.0");
  const [leadTime, setLeadTime] = useState<number>(2);
  const [reviewPeriod, setReviewPeriod] = useState<number>(1);
  const [safetyStock, setSafetyStock] = useState<string>("15.0");

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [result, setResult] = useState<ReplenishmentSimulationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSimulate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const resp = await api.simulateReplenishment({
        sku_id: skuId.trim(),
        forecast_run_id: forecastRunId.trim() || undefined,
        manual_forecast_demand: !forecastRunId.trim() ? parseFloat(manualDemand) : undefined,
        stock_on_hand: parseFloat(stockOnHand) || 0,
        incoming_stock: parseFloat(incomingStock) || 0,
        lead_time_weeks: Number(leadTime),
        review_period_weeks: Number(reviewPeriod),
        safety_stock_units: parseFloat(safetyStock) || 0,
      });
      setResult(resp);
    } catch (err: any) {
      setError(err.message || "Replenishment calculation failed.");
    } finally {
      setIsLoading(false);
    }
  };

  const isAuthorized = user?.role === "planner" || user?.role === "admin";

  return (
    <div className="page-wrapper">
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "1.85rem", marginBottom: "0.35rem" }}>Replenishment Planning</h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
          Simulate periodic-review (R, S) purchase orders driven by forecast demand and explicit stock assumptions.
        </p>
      </div>

      {!isAuthorized && (
        <Alert type="warning" title="Planner or Admin Role Required">
          Executing replenishment simulations is restricted to <strong>Planner</strong> and <strong>Admin</strong> accounts.
          Your active role is <strong>{user?.role}</strong>.
        </Alert>
      )}

      {error && <Alert type="error" title="Simulation Error">{error}</Alert>}

      {/* Governance Banner */}
      <div className="governance-banner">
        <ShieldAlert size={20} color="var(--status-warning)" style={{ flexShrink: 0, marginTop: "2px" }} />
        <div>
          <div className="governance-banner-title">GOVERNANCE TAG: SIMULATION_BASED_ON_USER_ASSUMPTIONS</div>
          <div className="governance-banner-text">
            Outputs from this calculator are <strong>deterministic simulations</strong> based strictly on user-supplied
            safety stock and forecast point values. Safety stock has <strong>not been mathematically optimized</strong> or
            proven under stochastic lead-time and service-level constraints. Do not interpret as an optimal order guarantee.
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "2rem" }}>
        {/* Simulation Input Form */}
        <div className="glass-panel" style={{ padding: "1.75rem" }}>
          <h3 style={{ fontSize: "1.1rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Calculator size={18} color="var(--primary-500)" />
            Simulation Parameters
          </h3>

          <form onSubmit={handleSimulate}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div className="form-group">
                <label className="form-label">SKU Identifier</label>
                <input
                  type="text"
                  className="form-input"
                  value={skuId}
                  onChange={(e) => setSkuId(e.target.value)}
                  required
                  placeholder="e.g. 10002"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Persisted Run ID (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  value={forecastRunId}
                  onChange={(e) => setForecastRunId(e.target.value)}
                  placeholder="e.g. run_20261021_..."
                />
              </div>
            </div>

            {!forecastRunId && (
              <div className="form-group">
                <label className="form-label">Manual Forecast Demand (Protection Period)</label>
                <input
                  type="number"
                  step="any"
                  className="form-input"
                  value={manualDemand}
                  onChange={(e) => setManualDemand(e.target.value)}
                  placeholder="Total predicted units across L + R weeks"
                />
              </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div className="form-group">
                <label className="form-label">Stock on Hand (Units)</label>
                <input
                  type="number"
                  step="any"
                  className="form-input"
                  value={stockOnHand}
                  onChange={(e) => setStockOnHand(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Incoming / In-Transit Stock</label>
                <input
                  type="number"
                  step="any"
                  className="form-input"
                  value={incomingStock}
                  onChange={(e) => setIncomingStock(e.target.value)}
                  required
                />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
              <div className="form-group">
                <label className="form-label">Lead Time (L wks)</label>
                <select
                  className="form-select"
                  value={leadTime}
                  onChange={(e) => setLeadTime(Number(e.target.value))}
                >
                  <option value={1}>1 week</option>
                  <option value={2}>2 weeks</option>
                  <option value={3}>3 weeks</option>
                  <option value={4}>4 weeks</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Review Period (R wks)</label>
                <select
                  className="form-select"
                  value={reviewPeriod}
                  onChange={(e) => setReviewPeriod(Number(e.target.value))}
                >
                  <option value={1}>1 week</option>
                  <option value={2}>2 weeks</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Safety Stock (Units)</label>
                <input
                  type="number"
                  step="any"
                  className="form-input"
                  value={safetyStock}
                  onChange={(e) => setSafetyStock(e.target.value)}
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={isLoading || !isAuthorized}
              style={{ width: "100%", marginTop: "1rem", padding: "0.75rem" }}
            >
              {isLoading ? "Computing..." : "Simulate Replenishment Order"}
            </button>
          </form>
        </div>

        {/* Results Card */}
        <div>
          {result ? (
            <div className="glass-panel" style={{ padding: "1.75rem", border: "1px solid rgba(99, 102, 241, 0.3)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
                <h3 style={{ fontSize: "1.1rem" }}>Simulation Result</h3>
                <span className="badge badge-warning">User Assumptions</span>
              </div>

              {/* Recommended Order Quantity */}
              <div
                style={{
                  background: "rgba(99, 102, 241, 0.12)",
                  border: "1px solid rgba(99, 102, 241, 0.3)",
                  borderRadius: "var(--radius-lg)",
                  padding: "1.5rem",
                  textAlign: "center",
                  marginBottom: "1.5rem",
                }}
              >
                <div style={{ fontSize: "0.8rem", textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "0.05em" }}>
                  Suggested Replenishment Order
                </div>
                <div style={{ fontFamily: "var(--font-display)", fontSize: "2.75rem", fontWeight: 800, color: "#fff" }}>
                  {result.replenishment_order_units.toFixed(1)}{" "}
                  <span style={{ fontSize: "1.1rem", fontWeight: 500, color: "var(--primary-500)" }}>units</span>
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: "0.25rem" }}>
                  Formula: max(0, Gross Requirement &minus; Inventory Position)
                </div>
              </div>

              {/* Step-by-Step Breakdown */}
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", fontSize: "0.85rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "0.4rem 0", borderBottom: "1px solid var(--border-subtle)" }}>
                  <span style={{ color: "var(--text-muted)" }}>Protection Period (L + R):</span>
                  <span style={{ fontWeight: 600 }}>{result.protection_period_weeks} weeks</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "0.4rem 0", borderBottom: "1px solid var(--border-subtle)" }}>
                  <span style={{ color: "var(--text-muted)" }}>Forecast Demand:</span>
                  <span style={{ fontWeight: 600 }}>{result.forecast_demand_over_protection_period.toFixed(2)} units</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "0.4rem 0", borderBottom: "1px solid var(--border-subtle)" }}>
                  <span style={{ color: "var(--text-muted)" }}>Safety Stock Buffer:</span>
                  <span style={{ fontWeight: 600 }}>{result.safety_stock_units.toFixed(2)} units</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "0.4rem 0", borderBottom: "1px solid var(--border-subtle)" }}>
                  <span style={{ color: "var(--text-muted)" }}>Gross Requirement:</span>
                  <span style={{ fontWeight: 700, color: "var(--text-main)" }}>{result.gross_requirement_units.toFixed(2)} units</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "0.4rem 0", borderBottom: "1px solid var(--border-subtle)" }}>
                  <span style={{ color: "var(--text-muted)" }}>Inventory Position (On-Hand + In-Transit):</span>
                  <span style={{ fontWeight: 600 }}>{(result.stock_on_hand_units + result.incoming_stock_units).toFixed(2)} units</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "0.4rem 0" }}>
                  <span style={{ color: "var(--text-muted)" }}>Net Requirement:</span>
                  <span style={{ fontWeight: 700, color: "var(--status-info)" }}>{result.net_requirement_units.toFixed(2)} units</span>
                </div>
              </div>
            </div>
          ) : (
            <div
              className="glass-panel"
              style={{
                height: "100%",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                padding: "3rem",
                textAlign: "center",
                color: "var(--text-dim)",
              }}
            >
              <Layers size={40} style={{ marginBottom: "1rem", opacity: 0.4 }} />
              <div style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-muted)", marginBottom: "0.4rem" }}>
                Simulation Pending
              </div>
              <p style={{ fontSize: "0.825rem", maxWidth: "280px" }}>
                Fill in stock positions and supplier lead times on the left to simulate replenishment order quantities.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
