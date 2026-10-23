import React, { useState } from "react";

export interface DataPoint {
  label: string; // e.g. "2011-10-10"
  actual?: number | null;
  forecast?: number | null;
}

interface SvgChartProps {
  data: DataPoint[];
  title?: string;
  subtitle?: string;
  height?: number;
  actualLabel?: string;
  forecastLabel?: string;
}

export const SvgChart: React.FC<SvgChartProps> = ({
  data,
  title,
  subtitle,
  height = 300,
  actualLabel = "Actual Demand",
  forecastLabel = "Forecast Prediction",
}) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (!data || data.length === 0) {
    return (
      <div
        className="glass-panel"
        style={{
          height: `${height}px`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--text-muted)",
          fontSize: "0.875rem",
        }}
      >
        No series data available to render chart.
      </div>
    );
  }

  const width = 800;
  const paddingLeft = 50;
  const paddingRight = 30;
  const paddingTop = 25;
  const paddingBottom = 40;

  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;

  // Compute max value
  const allValues: number[] = [];
  data.forEach((d) => {
    if (d.actual !== undefined && d.actual !== null) allValues.push(d.actual);
    if (d.forecast !== undefined && d.forecast !== null) allValues.push(d.forecast);
  });
  const maxVal = Math.max(10, Math.ceil(Math.max(...allValues, 1) * 1.15));

  // Coordinate mappers
  const getX = (index: number) => {
    if (data.length <= 1) return paddingLeft + chartWidth / 2;
    return paddingLeft + (index / (data.length - 1)) * chartWidth;
  };

  const getY = (val: number) => {
    return paddingTop + chartHeight - (val / maxVal) * chartHeight;
  };

  // Build actual path
  const actualPoints = data
    .map((d, i) => (d.actual !== undefined && d.actual !== null ? { x: getX(i), y: getY(d.actual) } : null))
    .filter(Boolean) as { x: number; y: number }[];

  const actualPath =
    actualPoints.length > 0
      ? actualPoints.reduce((acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x.toFixed(1)},${p.y.toFixed(1)}`, "")
      : "";

  // Build forecast path
  const forecastPoints = data
    .map((d, i) => (d.forecast !== undefined && d.forecast !== null ? { x: getX(i), y: getY(d.forecast) } : null))
    .filter(Boolean) as { x: number; y: number }[];

  const forecastPath =
    forecastPoints.length > 0
      ? forecastPoints.reduce((acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x.toFixed(1)},${p.y.toFixed(1)}`, "")
      : "";

  // Y-axis gridlines (4 steps)
  const yTicks = [0, maxVal * 0.25, maxVal * 0.5, maxVal * 0.75, maxVal];

  // X-axis sampled labels (max 8)
  const step = Math.max(1, Math.floor(data.length / 7));
  const xLabels = data.filter((_, idx) => idx % step === 0 || idx === data.length - 1);

  const hoveredPoint = hoverIndex !== null && hoverIndex >= 0 && hoverIndex < data.length ? data[hoverIndex] : null;

  return (
    <div className="glass-panel" style={{ padding: "1.5rem" }}>
      {(title || subtitle) && (
        <div style={{ marginBottom: "1rem", display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          <div>
            {title && <h3 style={{ fontSize: "1.1rem", marginBottom: "0.2rem" }}>{title}</h3>}
            {subtitle && <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{subtitle}</p>}
          </div>
          {/* Legend */}
          <div style={{ display: "flex", gap: "1rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
            {actualPoints.length > 0 && (
              <span style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#06b6d4" }} />
                {actualLabel}
              </span>
            )}
            {forecastPoints.length > 0 && (
              <span style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#8b5cf6" }} />
                {forecastLabel}
              </span>
            )}
          </div>
        </div>
      )}

      <div style={{ position: "relative", width: "100%" }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: "100%", height: "auto", display: "block" }}
          onMouseLeave={() => setHoverIndex(null)}
        >
          <defs>
            <linearGradient id="actualGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="forecastGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Gridlines */}
          {yTicks.map((tick, idx) => {
            const y = getY(tick);
            return (
              <g key={idx}>
                <line
                  x1={paddingLeft}
                  y1={y}
                  x2={width - paddingRight}
                  y2={y}
                  stroke="rgba(255, 255, 255, 0.06)"
                  strokeDasharray="4 4"
                />
                <text
                  x={paddingLeft - 8}
                  y={y + 4}
                  fill="var(--text-dim)"
                  fontSize="10"
                  textAnchor="end"
                  fontFamily="var(--font-mono)"
                >
                  {Math.round(tick)}
                </text>
              </g>
            );
          })}

          {/* Actual Line */}
          {actualPoints.length > 0 && (
            <>
              <path d={actualPath} fill="none" stroke="#06b6d4" strokeWidth="2.5" strokeLinecap="round" />
              {actualPoints.map((p, i) => (
                <circle
                  key={i}
                  cx={p.x}
                  cy={p.y}
                  r={hoverIndex === i ? 5 : 2.5}
                  fill="#06b6d4"
                  stroke="#0a0e17"
                  strokeWidth="1.5"
                />
              ))}
            </>
          )}

          {/* Forecast Line */}
          {forecastPoints.length > 0 && (
            <>
              <path
                d={forecastPath}
                fill="none"
                stroke="#8b5cf6"
                strokeWidth="2.5"
                strokeDasharray="6 4"
                strokeLinecap="round"
              />
              {forecastPoints.map((p, i) => (
                <circle
                  key={i}
                  cx={p.x}
                  cy={p.y}
                  r={hoverIndex === i ? 6 : 3.5}
                  fill="#8b5cf6"
                  stroke="#ffffff"
                  strokeWidth="1.5"
                />
              ))}
            </>
          )}

          {/* Interactive Hover Guides & Slices */}
          {data.map((_, idx) => {
            const x = getX(idx);
            const sliceWidth = chartWidth / data.length;
            return (
              <rect
                key={idx}
                x={x - sliceWidth / 2}
                y={paddingTop}
                width={sliceWidth}
                height={chartHeight}
                fill="transparent"
                onMouseEnter={() => setHoverIndex(idx)}
                style={{ cursor: "crosshair" }}
              />
            );
          })}

          {/* Hover Crosshair */}
          {hoverIndex !== null && (
            <line
              x1={getX(hoverIndex)}
              y1={paddingTop}
              x2={getX(hoverIndex)}
              y2={paddingTop + chartHeight}
              stroke="rgba(255, 255, 255, 0.25)"
              strokeDasharray="2 2"
            />
          )}

          {/* X-axis Labels */}
          {xLabels.map((item, idx) => {
            const indexInData = data.indexOf(item);
            const x = getX(indexInData);
            return (
              <text
                key={idx}
                x={x}
                y={height - 10}
                fill="var(--text-dim)"
                fontSize="10"
                textAnchor="middle"
                fontFamily="var(--font-mono)"
              >
                {item.label.substring(5)} {/* MM-DD */}
              </text>
            );
          })}
        </svg>

        {/* Floating Tooltip */}
        {hoveredPoint && hoverIndex !== null && (
          <div
            style={{
              position: "absolute",
              top: "10px",
              left: `${Math.min(75, Math.max(15, (getX(hoverIndex) / width) * 100))}%`,
              transform: "translateX(-50%)",
              background: "rgba(15, 23, 42, 0.95)",
              border: "1px solid var(--border-card)",
              borderRadius: "var(--radius-sm)",
              padding: "0.5rem 0.75rem",
              fontSize: "0.75rem",
              boxShadow: "var(--shadow-lg)",
              pointerEvents: "none",
              zIndex: 10,
              minWidth: "140px",
            }}
          >
            <div style={{ color: "var(--text-muted)", marginBottom: "0.25rem", fontFamily: "var(--font-mono)" }}>
              Week: {hoveredPoint.label}
            </div>
            {hoveredPoint.actual !== undefined && hoveredPoint.actual !== null && (
              <div style={{ color: "#06b6d4", fontWeight: 600 }}>
                Actual: {hoveredPoint.actual.toFixed(2)} units
              </div>
            )}
            {hoveredPoint.forecast !== undefined && hoveredPoint.forecast !== null && (
              <div style={{ color: "#8b5cf6", fontWeight: 600 }}>
                Forecast: {hoveredPoint.forecast.toFixed(2)} units
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
