import React, { useEffect, useState } from "react";
import {
  Package,
  Search,
  Filter,
  BarChart2,
  X,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
} from "lucide-react";
import { api } from "../api/client";
import { SKUDetail, SKUHistoryResponse } from "../types/api";
import { Badge } from "../components/ui/Badge";
import { SvgChart, DataPoint } from "../components/ui/SvgChart";
import { Alert } from "../components/ui/Alert";

export const SkuExplorerPage: React.FC = () => {
  const [skus, setSkus] = useState<SKUDetail[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const pageSize = 20;

  const [search, setSearch] = useState<string>("");
  const [cohortFilter, setCohortFilter] = useState<string>("");
  const [abcFilter, setAbcFilter] = useState<string>("");
  const [sbcFilter, setSbcFilter] = useState<string>("");

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedSku, setSelectedSku] = useState<SKUDetail | null>(null);
  const [skuHistory, setSkuHistory] = useState<SKUHistoryResponse | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadSkus = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await api.listSkus({
        page,
        page_size: pageSize,
        search: search.trim() || undefined,
        cohort: cohortFilter || undefined,
        abc_demand: abcFilter || undefined,
        sbc_class: sbcFilter || undefined,
      });
      setSkus(resp.items);
      setTotal(resp.total);
    } catch (err: any) {
      setError(err.message || "Failed to load SKU catalog from API.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadSkus();
  }, [page, cohortFilter, abcFilter, sbcFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadSkus();
  };

  const handleSelectSku = async (sku: SKUDetail) => {
    setSelectedSku(sku);
    setIsLoadingHistory(true);
    try {
      const hist = await api.getSkuHistory(sku.sku_id);
      setSkuHistory(hist);
    } catch (err) {
      console.error("Failed to load history for SKU:", sku.sku_id);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  // Convert SKU history into SvgChart DataPoints
  const chartPoints: DataPoint[] =
    skuHistory && skuHistory.history
      ? skuHistory.history.map((h) => ({
          label: h.week_start,
          actual: h.demand,
        }))
      : [];

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="page-wrapper">
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "1.85rem", marginBottom: "0.35rem" }}>SKU Catalog Explorer</h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
          Explore 2,785 qualified merchandise items, ABC/XYZ/SBC patterns, and historical demand series.
        </p>
      </div>

      {error && <Alert type="error">{error}</Alert>}

      {/* Search and Filters Bar */}
      <div className="glass-panel" style={{ padding: "1.25rem 1.5rem", marginBottom: "1.75rem" }}>
        <form
          onSubmit={handleSearchSubmit}
          style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr auto", gap: "1rem", alignItems: "flex-end" }}
        >
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Search SKU or Description</label>
            <div style={{ position: "relative" }}>
              <input
                type="text"
                className="form-input"
                placeholder="Enter stock code (e.g. 10002, 20713, 85123A)..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <Search
                size={16}
                color="var(--text-dim)"
                style={{ position: "absolute", right: "12px", top: "50%", transform: "translateY(-50%)" }}
              />
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Cohort</label>
            <select
              className="form-select"
              value={cohortFilter}
              onChange={(e) => {
                setCohortFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All Cohorts (2,785)</option>
              <option value="CAUSAL_MATURE">Causal Mature (1,717)</option>
              <option value="LATE_MATURING">Late Maturing (1,068)</option>
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">ABC (Volume)</label>
            <select
              className="form-select"
              value={abcFilter}
              onChange={(e) => {
                setAbcFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All ABC Classes</option>
              <option value="A">Class A (Top 80% Vol)</option>
              <option value="B">Class B (Next 15% Vol)</option>
              <option value="C">Class C (Tail 5% Vol)</option>
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">SBC Intermittency</label>
            <select
              className="form-select"
              value={sbcFilter}
              onChange={(e) => {
                setSbcFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All SBC Classes</option>
              <option value="Smooth">Smooth</option>
              <option value="Erratic">Erratic</option>
              <option value="Intermittent">Intermittent</option>
              <option value="Lumpy">Lumpy</option>
            </select>
          </div>

          <button type="submit" className="btn btn-primary" style={{ height: "40px" }}>
            Search
          </button>
        </form>
      </div>

      {/* Catalog Table */}
      <div className="table-container" style={{ marginBottom: "1.5rem" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>SKU Code</th>
              <th>Merchandise Description</th>
              <th>Cohort</th>
              <th>ABC (Vol)</th>
              <th>ABC (Val)</th>
              <th>SBC Class</th>
              <th>Mean Weekly Demand</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                  Loading SKUs...
                </td>
              </tr>
            ) : skus.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: "3rem", color: "var(--text-dim)" }}>
                  No SKUs matched your search filter criteria.
                </td>
              </tr>
            ) : (
              skus.map((sku) => (
                <tr key={sku.sku_id}>
                  <td style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--primary-500)" }}>
                    {sku.sku_id}
                  </td>
                  <td style={{ maxWidth: "320px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    Merchandise Item #{sku.sku_id}
                  </td>
                  <td>
                    <Badge status={sku.cohort_tier} />
                  </td>
                  <td>
                    <span className="badge badge-neutral">Class {sku.abc_demand_class || "N/A"}</span>
                  </td>
                  <td>
                    <span className="badge badge-neutral">Class {sku.abc_value_class || "N/A"}</span>
                  </td>
                  <td>
                    <Badge status={sku.sbc_regime || "SMOOTH"} />
                  </td>
                  <td style={{ fontWeight: 600 }}>{sku.avg_weekly_demand.toFixed(1)} units/wk</td>
                  <td>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: "0.35rem 0.65rem", fontSize: "0.75rem" }}
                      onClick={() => handleSelectSku(sku)}
                    >
                      <BarChart2 size={13} />
                      Inspect Series
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: "0.825rem", color: "var(--text-muted)" }}>
          Showing {skus.length > 0 ? (page - 1) * pageSize + 1 : 0} &ndash;{" "}
          {Math.min(page * pageSize, total)} of {total.toLocaleString()} SKUs
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

      {/* SKU History Drilldown Modal */}
      {selectedSku && (
        <div className="modal-overlay" onClick={() => setSelectedSku(null)}>
          <div className="modal-content" style={{ maxWidth: "860px" }} onClick={(e) => e.stopPropagation()}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                marginBottom: "1.5rem",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.35rem" }}>
                  <h2 style={{ fontSize: "1.4rem", fontFamily: "var(--font-mono)" }}>SKU {selectedSku.sku_id}</h2>
                  <Badge status={selectedSku.cohort_tier} />
                  <Badge status={selectedSku.sbc_regime || "SMOOTH"} />
                </div>
                <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                  Merchandise Item #{selectedSku.sku_id} &bull; Cleaned UCI Online Retail II
                </p>
              </div>
              <button
                className="btn btn-ghost"
                onClick={() => setSelectedSku(null)}
                style={{ padding: "0.4rem", borderRadius: "var(--radius-sm)" }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Quick Metrics */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
              <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "1rem", borderRadius: "var(--radius-md)" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Total Demand</div>
                <div style={{ fontSize: "1.25rem", fontWeight: 700 }}>
                  {selectedSku.total_demand_units.toLocaleString()} units
                </div>
              </div>
              <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "1rem", borderRadius: "var(--radius-md)" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Mean Weekly</div>
                <div style={{ fontSize: "1.25rem", fontWeight: 700 }}>
                  {selectedSku.avg_weekly_demand.toFixed(2)} units
                </div>
              </div>
              <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "1rem", borderRadius: "var(--radius-md)" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Zero Demand Weeks</div>
                <div style={{ fontSize: "1.25rem", fontWeight: 700 }}>
                  {selectedSku.zero_weeks_count} weeks
                </div>
              </div>
              <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "1rem", borderRadius: "var(--radius-md)" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Active Weeks</div>
                <div style={{ fontSize: "1.25rem", fontWeight: 700 }}>
                  {selectedSku.active_weeks_count ?? (104 - selectedSku.zero_weeks_count)} weeks
                </div>
              </div>
            </div>

            {/* Full 104-week Historical Series Chart */}
            {isLoadingHistory ? (
              <div style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                Loading weekly sales history series...
              </div>
            ) : (
              <SvgChart
                data={chartPoints}
                title="104-Week Historical Weekly Sales Demand (Dec 2009 &ndash; Nov 2011)"
                subtitle="Complete observation series under canonical ISO Monday floor week aggregation."
                height={260}
                actualLabel="Weekly Demand Units"
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
};
