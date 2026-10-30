/**
 * Typed API Client for Retail SKU-Week Demand Forecasting & Inventory Planning.
 * Handles JWT bearer authentication, error formatting, and request sanitization.
 */
import {
  DashboardSummary,
  ExportArtifactResponse,
  ExportFormat,
  ForecastRecordListResponse,
  ForecastRequest,
  ForecastResponse,
  ForecastRunDetail,
  ForecastRunListResponse,
  LeaderboardResponse,
  LoginResponse,
  ModelDetail,
  ReplenishmentSimulationRequest,
  ReplenishmentSimulationResponse,
  SKUDetail,
  SKUHistoryResponse,
  SKUListResponse,
  UserProfile,
} from "../types/api";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string) || (import.meta.env.VITE_API_URL as string) || "";

class ApiError extends Error {
  status: number;
  errorCode: string;
  details?: any;

  constructor(status: number, message: string, errorCode = "API_ERROR", details?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorCode = errorCode;
    this.details = details;
  }
}

export class ApiClient {
  private token: string | null = null;

  constructor() {
    this.token = localStorage.getItem("forecast_jwt_token");
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem("forecast_jwt_token", token);
    } else {
      localStorage.removeItem("forecast_jwt_token");
    }
  }

  getToken(): string | null {
    return this.token;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    const headers = new Headers(options.headers || {});

    if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }

    if (this.token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${this.token}`);
    }

    try {
      const response = await fetch(url, { ...options, headers });

      if (response.status === 401) {
        // Clear invalid token on 401
        this.setToken(null);
      }

      const contentType = response.headers.get("content-type");
      let data: any = null;
      if (contentType && contentType.includes("application/json")) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        const errorMsg =
          (typeof data === "object" && (data.message || data.detail)) ||
          `Request failed with status ${response.status}`;
        const errorCode = (typeof data === "object" && data.error_code) || `HTTP_${response.status}`;
        throw new ApiError(response.status, errorMsg, errorCode, typeof data === "object" ? data.details : undefined);
      }

      return data as T;
    } catch (err: any) {
      if (err instanceof ApiError) {
        throw err;
      }
      throw new ApiError(500, err.message || "Network error. Please verify backend is running on port 8000.", "NETWORK_ERROR");
    }
  }

  // ===================================================================
  // 1. AUTHENTICATION & USERS
  // ===================================================================
  async login(username: string, password: string): Promise<LoginResponse> {
    const data = await this.request<LoginResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    this.setToken(data.access_token);
    return data;
  }

  async logout(): Promise<void> {
    try {
      await this.request<{ status: string }>("/api/v1/auth/logout", {
        method: "POST",
      });
    } finally {
      this.setToken(null);
    }
  }

  async getMe(): Promise<UserProfile> {
    return this.request<UserProfile>("/api/v1/auth/me");
  }

  async listUsers(): Promise<UserProfile[]> {
    return this.request<UserProfile[]>("/api/v1/auth/users");
  }

  async createUser(payload: { username: string; password: string; role: string; full_name?: string }): Promise<UserProfile> {
    return this.request<UserProfile>("/api/v1/auth/users", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  // ===================================================================
  // 2. DASHBOARD
  // ===================================================================
  async getDashboardSummary(): Promise<DashboardSummary> {
    return this.request<DashboardSummary>("/api/v1/dashboard/summary");
  }

  // ===================================================================
  // 3. MODEL REGISTRY
  // ===================================================================
  async listModels(): Promise<ModelDetail[]> {
    const res = await this.request<any>("/api/v1/models");
    return Array.isArray(res) ? res : (res?.items || []);
  }

  async getModel(modelId: string): Promise<ModelDetail> {
    return this.request<ModelDetail>(`/api/v1/models/${encodeURIComponent(modelId)}`);
  }

  async getLeaderboard(): Promise<LeaderboardResponse> {
    return this.request<LeaderboardResponse>("/api/v1/models/leaderboard");
  }

  // ===================================================================
  // 4. SKU EXPLORER
  // ===================================================================
  async listSkus(params: {
    page?: number;
    page_size?: number;
    search?: string;
    cohort?: string;
    abc_class?: string;
    abc_demand?: string;
    sbc_regime?: string;
    sbc_class?: string;
  } = {}): Promise<SKUListResponse> {
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    if (params.search) query.set("search", params.search);
    if (params.cohort) query.set("cohort", params.cohort);
    const abc = params.abc_class || params.abc_demand;
    if (abc) {
      query.set("abc_class", abc);
      query.set("abc_demand", abc);
    }
    const sbc = params.sbc_regime || params.sbc_class;
    if (sbc) {
      query.set("sbc_regime", sbc);
      query.set("sbc_class", sbc);
    }

    const qs = query.toString();
    return this.request<SKUListResponse>(`/api/v1/skus${qs ? `?${qs}` : ""}`);
  }

  async getSku(skuId: string): Promise<SKUDetail> {
    return this.request<SKUDetail>(`/api/v1/skus/${encodeURIComponent(skuId)}`);
  }

  async getSkuHistory(skuId: string): Promise<SKUHistoryResponse> {
    return this.request<SKUHistoryResponse>(`/api/v1/skus/${encodeURIComponent(skuId)}/history`);
  }

  // ===================================================================
  // 5. DEMAND FORECASTING
  // ===================================================================
  async createForecast(payload: ForecastRequest): Promise<ForecastResponse> {
    return this.request<ForecastResponse>("/api/v1/forecasts", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async listForecastRuns(params: {
    page?: number;
    page_size?: number;
    status?: string;
    model_id?: string;
  } = {}): Promise<ForecastRunListResponse> {
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    if (params.status) query.set("status", params.status);
    if (params.model_id) query.set("model_id", params.model_id);

    const qs = query.toString();
    return this.request<ForecastRunListResponse>(`/api/v1/forecasts/runs${qs ? `?${qs}` : ""}`);
  }

  async getForecastRun(runId: string): Promise<ForecastRunDetail> {
    return this.request<ForecastRunDetail>(`/api/v1/forecasts/runs/${encodeURIComponent(runId)}`);
  }

  async getForecastRunResults(runId: string, page = 1, pageSize = 100, skuId?: string): Promise<ForecastRecordListResponse> {
    const query = new URLSearchParams();
    query.set("page", String(page));
    query.set("page_size", String(pageSize));
    if (skuId) query.set("sku_id", skuId);

    return this.request<ForecastRecordListResponse>(
      `/api/v1/forecasts/runs/${encodeURIComponent(runId)}/results?${query.toString()}`
    );
  }

  // ===================================================================
  // 6. EXPORTS
  // ===================================================================
  async createExport(runId: string, format: ExportFormat = "CSV"): Promise<ExportArtifactResponse> {
    return this.request<ExportArtifactResponse>(`/api/v1/forecasts/runs/${encodeURIComponent(runId)}/exports`, {
      method: "POST",
      body: JSON.stringify({ format }),
    });
  }

  async getExport(runId: string, exportId: string): Promise<ExportArtifactResponse> {
    return this.request<ExportArtifactResponse>(
      `/api/v1/forecasts/runs/${encodeURIComponent(runId)}/exports/${encodeURIComponent(exportId)}`
    );
  }

  getDownloadUrl(runId: string, exportId: string): string {
    return `/api/v1/forecasts/runs/${encodeURIComponent(runId)}/exports/${encodeURIComponent(exportId)}/download`;
  }

  // ===================================================================
  // 7. INVENTORY REPLENISHMENT
  // ===================================================================
  async simulateReplenishment(payload: ReplenishmentSimulationRequest): Promise<ReplenishmentSimulationResponse> {
    return this.request<ReplenishmentSimulationResponse>("/api/v1/planning/replenish", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  // ===================================================================
  // 8. HEALTH CHECKS
  // ===================================================================
  async checkHealthLive(): Promise<{ status: string; uptime_seconds: number }> {
    return this.request("/health/live");
  }

  async checkHealthReady(): Promise<{ status: string; checks: Record<string, boolean> }> {
    return this.request("/health/ready");
  }
}

export const api = new ApiClient();
