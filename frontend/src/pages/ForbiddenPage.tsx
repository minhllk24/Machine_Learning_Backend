import React from "react";
import { ShieldX } from "lucide-react";

export const ForbiddenPage: React.FC<{ onNavigate: (p: string) => void }> = ({ onNavigate }) => {
  return (
    <div
      style={{
        minHeight: "70vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: "2rem",
      }}
    >
      <div
        style={{
          width: "64px",
          height: "64px",
          borderRadius: "50%",
          background: "var(--status-danger-bg)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: "1.5rem",
          border: "1px solid rgba(244, 63, 94, 0.3)",
        }}
      >
        <ShieldX size={32} color="var(--status-danger)" />
      </div>
      <h1 style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>403 &ndash; Access Forbidden</h1>
      <p style={{ color: "var(--text-muted)", maxWidth: "420px", marginBottom: "1.5rem", fontSize: "0.95rem" }}>
        Your account role does not possess administrative privileges required to access this resource.
      </p>
      <button className="btn btn-secondary" onClick={() => onNavigate("/")}>
        Return to Dashboard
      </button>
    </div>
  );
};
