import React from "react";

interface BadgeProps {
  status?: string;
  variant?: "success" | "warning" | "danger" | "info" | "neutral";
  children?: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({ status, variant, children }) => {
  let resolvedVariant = variant || "neutral";

  if (status) {
    const s = status.toUpperCase();
    if (s === "SERVING_READY" || s === "SUCCEEDED" || s === "A" || s === "X" || s === "SMOOTH") {
      resolvedVariant = "success";
    } else if (s === "RUNNING" || s === "B" || s === "Y" || s === "ERRATIC" || s === "PARTIAL") {
      resolvedVariant = "warning";
    } else if (s === "FAILED" || s === "NOT_READY" || s === "BLOCKED" || s === "C" || s === "Z" || s === "LUMPY") {
      resolvedVariant = "danger";
    } else if (s === "INTERMITTENT" || s === "CAUSAL_MATURE" || s === "LATE_MATURING") {
      resolvedVariant = "info";
    }
  }

  return (
    <span className={`badge badge-${resolvedVariant}`}>
      {children || status}
    </span>
  );
};
