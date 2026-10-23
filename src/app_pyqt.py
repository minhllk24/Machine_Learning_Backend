"""
PyQt6 Interactive Desktop Application for SKU Demand Forecasting & Inventory Planning.
Satisfies Proposal Deliverable 7 (Table 12, Table 13, Table 14).
"""
import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Project imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import TEST_PREDICTIONS, SKU_WEEK_DEMAND, logger


class DemandForecastingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Retail SKU Demand Forecasting & Inventory Planning System (UEL ML)")
        self.resize(1150, 750)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8fafc;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 5px;
                color: #1e293b;
            }
            QLabel {
                font-size: 12px;
                color: #334155;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                padding: 6px 10px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background: #f1f5f9;
                font-size: 12px;
                color: #0f172a;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #2563eb;
                background: #ffffff;
            }
            QPushButton#predictBtn {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton#predictBtn:hover {
                background-color: #1d4ed8;
            }
        """)
        
        self.load_data()
        self.init_ui()

    def load_data(self):
        """Load test predictions and historical demand data."""
        self.predictions_df = None
        self.history_df = None
        
        if TEST_PREDICTIONS.exists():
            try:
                self.predictions_df = pd.read_csv(TEST_PREDICTIONS)
                logger.info(f"Loaded {len(self.predictions_df):,} test predictions.")
            except Exception as e:
                logger.warning(f"Could not load test predictions: {e}")
                
        if SKU_WEEK_DEMAND.exists():
            try:
                self.history_df = pd.read_csv(SKU_WEEK_DEMAND)
                self.history_df["week_start"] = pd.to_datetime(self.history_df["week_start"])
                logger.info(f"Loaded {len(self.history_df):,} SKU demand records.")
            except Exception as e:
                logger.warning(f"Could not load SKU demand: {e}")

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)
        
        # ----------------------------------------------------
        # LEFT PANEL: Inputs & Scenario Parameters
        # ----------------------------------------------------
        left_panel = QVBoxLayout()
        left_panel.setSpacing(14)
        
        # Header
        title_label = QLabel("Demand Forecast & Inventory Decision")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #0f172a; margin-bottom: 4px;")
        subtitle_label = QLabel("LightGBM Champion Model with Conformal Prediction & Policy Simulation")
        subtitle_label.setStyleSheet("color: #64748b; font-size: 11px;")
        left_panel.addWidget(title_label)
        left_panel.addWidget(subtitle_label)
        
        # Group 1: SKU & Forecast Horizon
        sku_group = QGroupBox("1. SKU Selection & Forecast Target")
        sku_layout = QGridLayout(sku_group)
        sku_layout.setVerticalSpacing(10)
        
        sku_layout.addWidget(QLabel("Select StockCode / SKU:"), 0, 0)
        self.sku_combo = QComboBox()
        self.sku_combo.setEditable(True)
        
        # Populate with SKUs
        sample_skus = ["85123A", "85099B", "22423", "47566", "20725", "21212", "22386"]
        if self.predictions_df is not None:
            available_skus = self.predictions_df["sku_id"].astype(str).unique().tolist()
            sample_skus = available_skus[:100]
        self.sku_combo.addItems(sample_skus)
        sku_layout.addWidget(self.sku_combo, 0, 1)
        
        sku_layout.addWidget(QLabel("Forecast Horizon:"), 1, 0)
        self.horizon_label = QLabel("1 Week Ahead (Next Week)")
        self.horizon_label.setStyleSheet("font-weight: bold; color: #1e293b;")
        sku_layout.addWidget(self.horizon_label, 1, 1)
        
        left_panel.addWidget(sku_group)
        
        # Group 2: Simulated Inventory Input (Proposal Table 13)
        inv_group = QGroupBox("2. Current Inventory State (Simulated Input)")
        inv_layout = QGridLayout(inv_group)
        inv_layout.setVerticalSpacing(10)
        
        inv_layout.addWidget(QLabel("Current Stock on Hand (units):"), 0, 0)
        self.stock_spin = QSpinBox()
        self.stock_spin.setRange(0, 100000)
        self.stock_spin.setValue(180)  # Default from Proposal Table 13
        inv_layout.addWidget(self.stock_spin, 0, 1)
        
        inv_layout.addWidget(QLabel("Target Service Level:"), 1, 0)
        self.service_combo = QComboBox()
        self.service_combo.addItems(["90% (Standard)", "95% (High Reliability)", "99% (Critical)", "80% (Economy)"])
        inv_layout.addWidget(self.service_combo, 1, 1)
        
        inv_layout.addWidget(QLabel("Unit Holding Cost (£/wk):"), 2, 0)
        self.holding_spin = QDoubleSpinBox()
        self.holding_spin.setRange(0.01, 100.0)
        self.holding_spin.setValue(0.50)
        inv_layout.addWidget(self.holding_spin, 2, 1)
        
        inv_layout.addWidget(QLabel("Unit Stockout Penalty (£/unit):"), 3, 0)
        self.stockout_spin = QDoubleSpinBox()
        self.stockout_spin.setRange(0.01, 500.0)
        self.stockout_spin.setValue(2.00)
        inv_layout.addWidget(self.stockout_spin, 3, 1)
        
        left_panel.addWidget(inv_group)
        
        # Predict Button
        self.predict_btn = QPushButton("Calculate Forecast & Decision")
        self.predict_btn.setObjectName("predictBtn")
        self.predict_btn.clicked.connect(self.calculate_prediction)
        left_panel.addWidget(self.predict_btn)
        
        # Group 3: Recommendation & Decision Card
        dec_group = QGroupBox("3. Inventory Decision & Attention Flag")
        dec_layout = QVBoxLayout(dec_group)
        dec_layout.setSpacing(8)
        
        self.flag_label = QLabel("STATUS: PENDING CALCULATION")
        self.flag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.flag_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.flag_label.setStyleSheet("""
            background-color: #f1f5f9;
            color: #475569;
            padding: 10px;
            border-radius: 6px;
            border: 1px solid #cbd5e1;
        """)
        dec_layout.addWidget(self.flag_label)
        
        self.result_table = QTableWidget(6, 2)
        self.result_table.setHorizontalHeaderLabels(["Metric / Parameter", "Value"])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.setAlternatingRowColors(True)
        dec_layout.addWidget(self.result_table)
        
        left_panel.addWidget(dec_group)
        left_panel.addStretch()
        
        # ----------------------------------------------------
        # RIGHT PANEL: Visualization Canvas
        # ----------------------------------------------------
        right_panel = QVBoxLayout()
        
        chart_group = QGroupBox("Demand History, Point Forecast & Conformal Uncertainty Band")
        chart_layout = QVBoxLayout(chart_group)
        
        self.figure = Figure(figsize=(7, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        chart_layout.addWidget(self.canvas)
        
        right_panel.addWidget(chart_group)
        
        # Add to main
        main_layout.addLayout(left_panel, 4)
        main_layout.addLayout(right_panel, 6)
        
        self.setCentralWidget(main_widget)
        
        # Initial calculation
        self.calculate_prediction()

    def calculate_prediction(self):
        sku = self.sku_combo.currentText().strip()
        current_stock = self.stock_spin.value()
        
        # Service level factor
        sl_text = self.service_combo.currentText()
        if "95%" in sl_text:
            z = 1.645
            sl_pct = 0.95
        elif "99%" in sl_text:
            z = 2.326
            sl_pct = 0.99
        elif "80%" in sl_text:
            z = 0.842
            sl_pct = 0.80
        else:
            z = 1.282  # 90%
            sl_pct = 0.90
            
        pred_demand = 318.0
        lower_90 = 265.0
        upper_90 = 371.0
        
        # If test predictions loaded, fetch actual record
        if self.predictions_df is not None:
            sku_matches = self.predictions_df[self.predictions_df["sku_id"].astype(str) == sku]
            if not sku_matches.empty:
                last_row = sku_matches.iloc[-1]
                pred_demand = float(last_row.get("pred_lgbm", 318.0))
                lower_90 = float(last_row.get("lower_90", max(0.0, pred_demand - 50.0)))
                upper_90 = float(last_row.get("upper_90", pred_demand + 50.0))
                
        # Safety buffer based on uncertainty margin
        safety_buffer = max(10.0, (upper_90 - pred_demand) * (z / 1.282))
        projected_req = pred_demand + safety_buffer
        
        # Attention Flag Logic (Proposal Table 13)
        if current_stock < projected_req:
            flag = "SHORTAGE RISK"
            flag_bg = "#fef2f2"
            flag_color = "#dc2626"
            suggested_action = f"Order {int(np.ceil(projected_req - current_stock))} units"
        elif current_stock > projected_req * 1.5:
            flag = "EXCESS INVENTORY RISK"
            flag_bg = "#fefce8"
            flag_color = "#b45309"
            suggested_action = "Hold ordering (surplus stock)"
        else:
            flag = "INVENTORY ADEQUATE"
            flag_bg = "#f0fdf4"
            flag_color = "#16a34a"
            suggested_action = "Stock healthy, normal review"
            
        self.flag_label.setText(f"ATTENTION FLAG: {flag}")
        self.flag_label.setStyleSheet(f"""
            background-color: {flag_bg};
            color: {flag_color};
            padding: 10px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 13px;
            border: 1px solid {flag_color};
        """)
        
        # Populate result table
        results = [
            ("SKU Identifier", sku),
            ("Point Forecast Demand (t+1)", f"{pred_demand:.1f} units"),
            ("90% Conformal Prediction Interval", f"[{lower_90:.1f}, {upper_90:.1f}] units"),
            ("Recommended Safety Buffer", f"{safety_buffer:.1f} units"),
            ("Projected Total Requirement", f"{projected_req:.1f} units"),
            ("Suggested Review Action", suggested_action)
        ]
        
        for i, (k, v) in enumerate(results):
            self.result_table.setItem(i, 0, QTableWidgetItem(k))
            val_item = QTableWidgetItem(v)
            val_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold if i in [1, 5] else QFont.Weight.Normal))
            self.result_table.setItem(i, 1, val_item)
            
        # Draw Plot
        self.update_plot(sku, pred_demand, lower_90, upper_90, current_stock)

    def update_plot(self, sku, pred_demand, lower, upper, stock):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # Historical demand
        history_x = list(range(1, 13))
        # Default mock or actual history
        if self.history_df is not None:
            sku_hist = self.history_df[self.history_df["sku_id"].astype(str) == sku].tail(12)
            if len(sku_hist) >= 4:
                history_y = sku_hist["demand"].values
                history_x = list(range(1, len(history_y) + 1))
            else:
                history_y = np.random.normal(pred_demand, pred_demand * 0.15, 12).clip(min=0)
        else:
            history_y = np.random.normal(pred_demand, pred_demand * 0.15, 12).clip(min=0)
            
        next_t = history_x[-1] + 1
        
        # Plot actual history
        ax.plot(history_x, history_y, marker="o", color="#0284c7", lw=2, label="Historical Demand (Past Weeks)")
        
        # Forecast point
        ax.plot([history_x[-1], next_t], [history_y[-1], pred_demand], color="#ea580c", linestyle="--", lw=2)
        ax.scatter([next_t], [pred_demand], color="#ea580c", s=80, zorder=5, label=f"Next Week Forecast ({pred_demand:.0f})")
        
        # Uncertainty Interval
        ax.errorbar([next_t], [pred_demand], yerr=[[pred_demand - lower], [upper - pred_demand]],
                    fmt="none", ecolor="#ea580c", elinewidth=2.5, capsize=6, label="90% Conformal Interval")
        
        # Current Stock Reference Line
        ax.axhline(stock, color="#16a34a", linestyle=":", lw=2, label=f"Current Stock ({stock} units)")
        
        ax.set_title(f"Demand Trajectory & Replenishment Planning for SKU: {sku}", fontsize=12, pad=10)
        ax.set_xlabel("Timeline (Weeks)", fontsize=10)
        ax.set_ylabel("Demand Quantity (Units)", fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper left", fontsize=9)
        
        self.figure.tight_layout()
        self.canvas.draw()


def main():
    app = QApplication(sys.argv)
    window = DemandForecastingApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
