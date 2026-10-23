/**
 * Canonical TypeScript interfaces for Retail Demand Forecasting API & Frontend.
 * Synchronized with OpenAPI schema and backend Pydantic models.
 */

export type UserRole = "admin" | "analyst" | "planner" | "viewer";

export interface UserProfile {
  user_id: string;
  username: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  created_at_utc: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in_seconds: number;
  user: UserProfile;
}

export interface CatalogSummary {
  total_skus: number;
  primary_cohort_skus: number;
  secondary_cohort_skus: number;
}

export interface TimelineSummary {
  dataset_start_week: string;
  training_cutoff: string;
  development_weeks_count: number;
  holdout_start_week: string;
  holdout_end_week: string;
  holdout_weeks_count: number;
  excluded_boundary_week: string;
}

export interface CandidateModelStatus {
  model_id: string;
  role: string;
  serving_status: string;
  supported_horizons: number[];
  holdout_h4_wape_pct?: number | null;
  holdout_h4_mae?: number | null;
  holdout_h4_bias_pct?: number | null;
}

export interface BackendServicesHealth {
  persistence_sqlite: string;
  model_registry: string;
  allowlist_verified: boolean;
  export_service: string;
}

export interface RecentRunsSummary {
  total_runs_recorded: number;
  latest_run_id?: string | null;
  latest_run_status?: string | null;
  latest_run_created_at?: string | null;
}

export interface EvaluationGovernance {
  final_test_evaluation_completed: boolean;
  model_selection_protocol_preserved: boolean;
  serving_inference_validated: boolean;
  current_market_applicability_assessed: boolean;
  governance_note: string;
}

export interface DashboardSummary {
  system_status: string;
  dataset_version: string;
  feature_schema_version: string;
  catalog: CatalogSummary;
  timeline: TimelineSummary;
  backend_services: BackendServicesHealth;
  candidate_models: CandidateModelStatus[];
  recent_forecast_runs: RecentRunsSummary;
  governance: EvaluationGovernance;
}

export type ServingStatus = "SERVING_READY" | "NOT_READY";

export interface ModelDetail {
  model_id: string;
  model_name: string;
  model_version: string;
  algorithm_family?: string;
  framework?: string;
  objective?: string;
  cohort?: string;
  serving_status: ServingStatus;
  serving_ready?: boolean;
  artifact_role?: string;
  model_role?: string;
  target_variable?: string;
  training_cutoff?: string;
  supported_horizons: number[];
  artifact_path?: string;
  artifact_checksum?: string;
  artifact_sha256?: string;
  readiness_reasons?: string[];
  fold_id?: number | null;
  best_iteration?: number | null;
  entry_type?: string;
  has_weights?: boolean;
}


export interface SKUDetail {
  sku_id: string;
  cohort_tier: string;
  abc_demand_class?: string | null;
  abc_value_class?: string | null;
  xyz_variability_class?: string | null;
  sbc_regime?: string | null;
  total_demand_units: number;
  avg_weekly_demand: number;
  zero_weeks_count: number;
  active_weeks_count?: number;
  intermittency_ratio?: number;
  last_observed_price?: number | null;
}

export interface SKUListResponse {
  total: number;
  page: number;
  page_size: number;
  items: SKUDetail[];
}

export interface SKUHistoryPoint {
  week_start: string;
  demand: number;
  avg_unit_price?: number;
  transaction_count?: number;
  unique_customer_count?: number;
  zero_demand_flag?: number;
}

export interface SKUHistoryResponse {
  sku_id: string;
  cohort_tier: string;
  total_weeks: number;
  history: SKUHistoryPoint[];
}

export interface SKUForecastRecord {
  sku_id: string;
  target_week: string;
  horizon_step: number;
  prediction: number;
  prediction_status: string;
}

export interface ForecastRequest {
  model_id: string;
  sku_ids: string[];
  forecast_origin: string;
  horizon_weeks: number; // Authorized range: 1..4 for CatBoost__MAE champion
}

export interface ForecastResponse {
  forecast_run_id: string;
  model_id: string;
  model_version: string;
  forecast_origin: string;
  horizon_weeks: number;
  data_snapshot_id?: string;
  predictions: SKUForecastRecord[];
  warnings: string[];
}

export type ForecastRunStatus = "RUNNING" | "SUCCEEDED" | "FAILED";

export interface ForecastRunSummary {
  forecast_run_id: string;
  created_at_utc: string;
  status: ForecastRunStatus;
  model_id: string;
  model_version: string;
  forecast_origin: string;
  horizon_weeks: number;
  requested_sku_count: number;
  prediction_count: number;
  user_id?: string | null;
}

export interface ForecastRunDetail extends ForecastRunSummary {
  source_dataset_id?: string;
  data_snapshot_id?: string;
  training_cutoff?: string;
  forecast_strategy?: string;
  request_metadata?: Record<string, any>;
  failure_code?: string;
  failure_message?: string;
}

export interface ForecastRunListResponse {
  total: number;
  page: number;
  page_size: number;
  items: ForecastRunSummary[];
}

export interface ForecastRecordResponse {
  sku_id: string;
  target_week: string;
  horizon_step: number;
  prediction: number;
  prediction_raw?: number;
  prediction_status: string;
  clipped_at_zero: boolean;
}

export interface ForecastRecordListResponse {
  forecast_run_id: string;
  total: number;
  page: number;
  page_size: number;
  items: ForecastRecordResponse[];
}

export type ExportFormat = "CSV" | "XLSX";

export interface ExportArtifactResponse {
  export_id: string;
  forecast_run_id: string;
  format: ExportFormat;
  row_count: number;
  file_size_bytes: number;
  sha256: string;
  created_at_utc: string;
  status: string;
  download_url: string;
  user_id?: string | null;
}

export interface ReplenishmentSimulationRequest {
  sku_id: string;
  forecast_run_id?: string;
  manual_forecast_demand?: number;
  stock_on_hand: number;
  incoming_stock: number;
  lead_time_weeks: number;
  review_period_weeks: number;
  safety_stock_units: number;
}

export interface ReplenishmentSimulationResponse {
  sku_id: string;
  lead_time_weeks: number;
  review_period_weeks: number;
  protection_period_weeks: number;
  forecast_demand_over_protection_period: number;
  safety_stock_units: number;
  gross_requirement_units: number;
  stock_on_hand_units: number;
  incoming_stock_units: number;
  net_requirement_units: number;
  replenishment_order_units: number;
  simulation_status: string;
  disclaimer: string;
}

export interface BenchmarkMetric {
  model_family: string;
  model_id: string;
  role: string;
  protocol: string;
  horizon: string;
  wape: number;
  mae: number;
  rmse: number;
  signed_bias: number;
  status: string;
}

export interface LeaderboardResponse {
  holdout_metrics: BenchmarkMetric[];
  oof_metrics: BenchmarkMetric[];
  frozen_notice: string;
}

