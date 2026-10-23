import React from "react";
import { AlertCircle, CheckCircle, Info, AlertTriangle } from "lucide-react";

interface AlertProps {
  type?: "info" | "success" | "warning" | "error";
  title?: string;
  children: React.ReactNode;
}

export const Alert: React.FC<AlertProps> = ({ type = "info", title, children }) => {
  const getIcon = () => {
    switch (type) {
      case "success":
        return <CheckCircle size={18} className="text-emerald-400" style={{ color: "var(--status-success)" }} />;
      case "warning":
        return <AlertTriangle size={18} className="text-amber-400" style={{ color: "var(--status-warning)" }} />;
      case "error":
        return <AlertCircle size={18} className="text-rose-400" style={{ color: "var(--status-danger)" }} />;
      default:
        return <Info size={18} className="text-cyan-400" style={{ color: "var(--status-info)" }} />;
    }
  };

  const getBorderColor = () => {
    switch (type) {
      case "success": return "rgba(16, 185, 129, 0.3)";
      case "warning": return "rgba(245, 158, 11, 0.3)";
      case "error": return "rgba(244, 63, 94, 0.3)";
      default: return "rgba(6, 182, 212, 0.3)";
    }
  };

  const getBgColor = () => {
    switch (type) {
      case "success": return "rgba(16, 185, 129, 0.08)";
      case "warning": return "rgba(245, 158, 11, 0.08)";
      case "error": return "rgba(244, 63, 94, 0.08)";
      default: return "rgba(6, 182, 212, 0.08)";
    }
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "0.75rem",
        padding: "0.85rem 1.15rem",
        borderRadius: "var(--radius-md)",
        border: `1px solid ${getBorderColor()}`,
        background: getBgColor(),
        marginBottom: "1.25rem",
        fontSize: "0.85rem",
        lineHeight: "1.45",
      }}
    >
      <div style={{ marginTop: "2px", flexShrink: 0 }}>{getIcon()}</div>
      <div>
        {title && <div style={{ fontWeight: 700, marginBottom: "0.2rem" }}>{title}</div>}
        <div style={{ color: "var(--text-main)" }}>{children}</div>
      </div>
    </div>
  );
};
