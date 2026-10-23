import React, { useEffect, useState } from "react";
import {
  LayoutDashboard,
  TrendingUp,
  Package,
  Layers,
  Award,
  History,
  Cpu,
  Users,
  LogOut,
  Activity,
  ShieldCheck,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { api } from "../../api/client";

interface NavbarProps {
  currentPath: string;
  onNavigate: (path: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentPath, onNavigate }) => {
  const { user, logout, hasRole } = useAuth();
  const [healthStatus, setHealthStatus] = useState<string>("HEALTHY");

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const live = await api.checkHealthLive();
        if (live && live.status && live.status.toLowerCase() === "live") {
          setHealthStatus("HEALTHY");
        } else {
          setHealthStatus("DEGRADED");
        }
      } catch {
        setHealthStatus("DEGRADED");
      }
    };
    checkStatus();
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { label: "Dashboard", path: "/", icon: LayoutDashboard },
    { label: "Demand Forecasting", path: "/forecast", icon: TrendingUp },
    { label: "SKU Explorer", path: "/skus", icon: Package },
    { label: "Replenishment Plan", path: "/planning", icon: Layers },
    { label: "Model Leaderboard", path: "/evaluation", icon: Award },
    { label: "Run History & Exports", path: "/history", icon: History },
    { label: "Model Registry", path: "/registry", icon: Cpu },
  ];

  if (hasRole("admin")) {
    navItems.push({ label: "User Accounts", path: "/admin/users", icon: Users });
  }

  return (
    <aside
      style={{
        width: "270px",
        background: "rgba(10, 14, 23, 0.95)",
        backdropFilter: "blur(20px)",
        borderRight: "1px solid var(--border-subtle)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "1.75rem 1.25rem",
        position: "sticky",
        top: 0,
        height: "100vh",
        zIndex: 50,
      }}
    >
      <div>
        {/* Brand Header */}
        <div style={{ marginBottom: "2rem", paddingLeft: "0.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.35rem" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "10px",
                background: "var(--primary-gradient)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 4px 12px rgba(99, 102, 241, 0.4)",
              }}
            >
              <TrendingUp size={20} color="#fff" />
            </div>
            <div>
              <div style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: "1.1rem", lineHeight: 1.1 }}>
                RETAIL ML
              </div>
              <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
                Demand & Inventory
              </div>
            </div>
          </div>
        </div>

        {/* Navigation Links */}
        <nav style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentPath === item.path;
            return (
              <button
                key={item.path}
                onClick={() => onNavigate(item.path)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.85rem",
                  padding: "0.75rem 1rem",
                  borderRadius: "var(--radius-md)",
                  border: "none",
                  background: isActive ? "rgba(99, 102, 241, 0.15)" : "transparent",
                  color: isActive ? "#ffffff" : "var(--text-muted)",
                  fontWeight: isActive ? 600 : 500,
                  fontSize: "0.85rem",
                  textAlign: "left",
                  width: "100%",
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                  borderLeft: isActive ? "3px solid var(--primary-500)" : "3px solid transparent",
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.color = "var(--text-main)";
                    e.currentTarget.style.background = "rgba(255, 255, 255, 0.04)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.color = "var(--text-muted)";
                    e.currentTarget.style.background = "transparent";
                  }
                }}
              >
                <Icon size={18} style={{ color: isActive ? "var(--primary-500)" : "inherit" }} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer / System Status & Account */}
      <div>
        {/* System Health Pill */}
        <div
          style={{
            background: "rgba(15, 23, 42, 0.6)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "0.65rem 0.85rem",
            marginBottom: "1rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: "0.75rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Activity size={14} color={healthStatus === "HEALTHY" ? "var(--status-success)" : "var(--status-warning)"} />
            <span style={{ color: "var(--text-muted)" }}>Backend API:</span>
          </div>
          <span
            style={{
              fontWeight: 700,
              fontSize: "0.7rem",
              color: healthStatus === "HEALTHY" ? "var(--status-success)" : "var(--status-warning)",
            }}
          >
            {healthStatus}
          </span>
        </div>

        {/* User Profile Card */}
        {user ? (
          <div
            style={{
              background: "rgba(30, 41, 59, 0.5)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "0.85rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.65rem" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "50%",
                  background: "var(--primary-gradient)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 700,
                  fontSize: "0.85rem",
                }}
              >
                {user.username.charAt(0).toUpperCase()}
              </div>
              <div>
                <div style={{ fontSize: "0.825rem", fontWeight: 600, color: "var(--text-main)" }}>
                  {user.username}
                </div>
                <div
                  style={{
                    fontSize: "0.675rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    color: "var(--primary-500)",
                    fontWeight: 700,
                  }}
                >
                  {user.role}
                </div>
              </div>
            </div>
            <button
              onClick={logout}
              title="Logout"
              style={{
                background: "transparent",
                border: "none",
                color: "var(--text-muted)",
                padding: "0.4rem",
                borderRadius: "var(--radius-sm)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "var(--status-danger)")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
            >
              <LogOut size={16} />
            </button>
          </div>
        ) : null}
      </div>
    </aside>
  );
};
