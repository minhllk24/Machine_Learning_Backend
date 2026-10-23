import React, { useState } from "react";
import { TrendingUp, Shield, Key, AlertCircle } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export const LoginPage: React.FC = () => {
  const { login, isLoading } = useAuth();
  const [username, setUsername] = useState<string>("admin");
  const [password, setPassword] = useState<string>("Admin123!");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await login(username, password);
    } catch (err: any) {
      setError(err.message || "Authentication failed. Please verify credentials.");
    }
  };

  const setDemoUser = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
    setError(null);
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem",
      }}
    >
      <div
        className="glass-panel"
        style={{
          width: "100%",
          maxWidth: "460px",
          padding: "2.5rem",
          boxShadow: "var(--shadow-lg), var(--shadow-glow)",
        }}
      >
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "14px",
              background: "var(--primary-gradient)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 1rem auto",
              boxShadow: "0 6px 18px rgba(99, 102, 241, 0.45)",
            }}
          >
            <TrendingUp size={26} color="#fff" />
          </div>
          <h2 style={{ fontSize: "1.5rem", marginBottom: "0.4rem" }}>Forecasting Portal</h2>
          <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
            Retail SKU-Week Demand & Inventory Planning
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.65rem",
              background: "var(--status-danger-bg)",
              border: "1px solid rgba(244, 63, 94, 0.3)",
              borderRadius: "var(--radius-md)",
              padding: "0.75rem 1rem",
              marginBottom: "1.25rem",
              fontSize: "0.825rem",
              color: "var(--status-danger)",
            }}
          >
            <AlertCircle size={18} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Username</label>
            <input
              type="text"
              className="form-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              disabled={isLoading}
              placeholder="e.g. admin, analyst, planner, viewer"
            />
          </div>

          <div className="form-group" style={{ marginBottom: "1.75rem" }}>
            <label className="form-label">Password</label>
            <input
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isLoading}
              placeholder="Enter password"
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: "100%", padding: "0.8rem", fontSize: "0.95rem" }}
            disabled={isLoading}
          >
            {isLoading ? "Authenticating..." : "Sign In with RBAC Session"}
          </button>
        </form>

        {/* Quick Demo Accounts Selection */}
        <div style={{ marginTop: "2rem", borderTop: "1px solid var(--border-subtle)", paddingTop: "1.5rem" }}>
          <div
            style={{
              fontSize: "0.75rem",
              color: "var(--text-dim)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: "0.75rem",
              display: "flex",
              alignItems: "center",
              gap: "0.35rem",
            }}
          >
            <Key size={12} />
            Demo RBAC Accounts (Click to test role permissions):
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ fontSize: "0.75rem", padding: "0.45rem" }}
              onClick={() => setDemoUser("admin", "Admin123!")}
            >
              Admin (Full Control)
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ fontSize: "0.75rem", padding: "0.45rem" }}
              onClick={() => setDemoUser("analyst", "Analyst123!")}
            >
              Analyst (Forecasts)
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ fontSize: "0.75rem", padding: "0.45rem" }}
              onClick={() => setDemoUser("planner", "Planner123!")}
            >
              Planner (Replenishment)
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ fontSize: "0.75rem", padding: "0.45rem" }}
              onClick={() => setDemoUser("viewer", "Viewer123!")}
            >
              Viewer (Read-Only)
            </button>
          </div>
        </div>

        {/* Security Notice */}
        <div
          style={{
            marginTop: "1.5rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.4rem",
            fontSize: "0.725rem",
            color: "var(--text-dim)",
          }}
        >
          <Shield size={13} style={{ color: "var(--status-success)" }} />
          <span>PBKDF2-HMAC-SHA256 &bull; JWT HS256 Session Token</span>
        </div>
      </div>
    </div>
  );
};
