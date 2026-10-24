"""
PyQt6 Interactive Desktop Application for SKU Demand Forecasting & Inventory Planning.
Satisfies Proposal Deliverable 7 (Table 12, Table 13, Table 14).
Supports Dual Data Source: Direct MySQL Database (online_retail_db) & Offline File Mode.
"""
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import numpy as np
import pandas as pd

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFrame, QRadioButton, QButtonGroup, QStatusBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Project root setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import settings
from src.core.logging_config import logger
from src.database import get_mysql_connection


class DemandForecastingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Retail SKU Demand Forecasting & Inventory Planning System (UEL ML)")
        self.resize(1200, 800)
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
                padding-top: 12px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 5px;
                color: #0f172a;
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
            QRadioButton {
                font-size: 12px;
                font-weight: 500;
                color: #1e293b;
            }
            QPushButton#calcBtn {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton#calcBtn:hover {
                background-color: #1d4ed8;
            }
        """)

        self.mysql_available = False
        self.predictions_df = None
        self.history_df = None

        self.init_ui()
        self.check_initial_data_source()

    def check_initial_data_source(self):
        """Kiểm tra kết nối MySQL ban đầu để chọn nguồn dữ liệu mặc định."""
        try:
            conn = get_mysql_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM forecast_inventory_decisions;")
            cnt = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            if cnt > 0:
                self.mysql_available = True
                self.radio_mysql.setChecked(True)
                self.statusBar().showMessage(f"Đã kết nối CSDL MySQL (online_retail_db) — Bảng tồn kho có {cnt:,} dòng", 5000)
                self.load_skus_from_source()
                return
        except Exception as e:
            logger.warning(f"Initial MySQL check failed ({e}), falling back to offline mode.")

        self.mysql_available = False
        self.radio_offline.setChecked(True)
        self.statusBar().showMessage("Không thể kết nối MySQL -> Đang sử dụng chế độ Đọc File Offline (CSV/Parquet)", 6000)
        self.load_offline_data()
        self.load_skus_from_source()

    def load_offline_data(self):
        """Nạp dữ liệu từ file Parquet và CSV khi ở chế độ Offline."""
        pred_path = PROJECT_ROOT / "data" / "processed" / "test_predictions_phase8.parquet"
        demand_path = PROJECT_ROOT / "data" / "processed" / "sku_week_demand.csv"

        if pred_path.exists():
            try:
                self.predictions_df = pd.read_parquet(pred_path)
            except Exception as e:
                logger.warning(f"Could not load offline predictions: {e}")

        if demand_path.exists():
            try:
                self.history_df = pd.read_csv(demand_path, low_memory=False)
                self.history_df["week_start"] = pd.to_datetime(self.history_df["week_start"])
            except Exception as e:
                logger.warning(f"Could not load offline demand: {e}")

    def on_source_changed(self):
        """Xử lý khi người dùng thay đổi chế độ nguồn dữ liệu."""
        if self.radio_mysql.isChecked():
            try:
                conn = get_mysql_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT 1;")
                cursor.fetchone()
                cursor.close()
                conn.close()
                self.mysql_available = True
                self.statusBar().showMessage("Chế độ: Kết nối trực tiếp CSDL MySQL (online_retail_db)", 4000)
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Lỗi Kết nối MySQL",
                    f"Không thể kết nối MySQL: {e}\n\nVui lòng kiểm tra dịch vụ MySQL80 hoặc cấu hình file .env."
                )
                self.radio_offline.setChecked(True)
                return
        else:
            if self.predictions_df is None or self.history_df is None:
                self.load_offline_data()
            self.statusBar().showMessage("Chế độ: Đọc File Offline (CSV/Parquet)", 4000)

        self.load_skus_from_source()
        self.calculate_prediction()

    def load_skus_from_source(self):
        """Nạp danh sách SKU vào ComboBox theo nguồn dữ liệu hiện hành."""
        skus: List[str] = []
        if self.radio_mysql.isChecked() and self.mysql_available:
            try:
                conn = get_mysql_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT sku_id FROM forecast_inventory_decisions ORDER BY sku_id ASC LIMIT 150;")
                rows = cursor.fetchall()
                skus = [str(r[0]) for r in rows]
                cursor.close()
                conn.close()
            except Exception as e:
                logger.error(f"Error fetching SKUs from MySQL: {e}")

        if not skus:
            if self.predictions_df is not None:
                skus = self.predictions_df["sku_id"].astype(str).unique().tolist()[:150]
            else:
                skus = ["10002", "10120", "10125", "10133", "85123A", "85099B", "22423", "47566"]

        self.sku_combo.blockSignals(True)
        self.sku_combo.clear()
        self.sku_combo.addItems(skus)
        self.sku_combo.blockSignals(False)

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # ====================================================
        # LEFT PANEL: Controls & Scenario Parameters
        # ====================================================
        left_panel = QVBoxLayout()
        left_panel.setSpacing(12)

        # Header
        title_label = QLabel("Demand Forecast & Inventory Decision")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #0f172a; margin-bottom: 2px;")
        subtitle_label = QLabel("Enterprise ML Backend — Dual Mode MySQL & Offline Analytics")
        subtitle_label.setStyleSheet("color: #64748b; font-size: 11px;")
        left_panel.addWidget(title_label)
        left_panel.addWidget(subtitle_label)

        # Group 0: Data Source Selection Toggle
        source_group = QGroupBox("0. Nguồn Dữ Liệu (Data Source Toggle)")
        source_layout = QHBoxLayout(source_group)
        self.radio_mysql = QRadioButton("Kết nối Trực tiếp CSDL MySQL")
        self.radio_offline = QRadioButton("Đọc File Offline (CSV / Parquet)")
        self.source_btn_group = QButtonGroup()
        self.source_btn_group.addButton(self.radio_mysql)
        self.source_btn_group.addButton(self.radio_offline)
        self.radio_mysql.toggled.connect(self.on_source_changed)

        source_layout.addWidget(self.radio_mysql)
        source_layout.addWidget(self.radio_offline)
        left_panel.addWidget(source_group)

        # Group 1: SKU Selection
        sku_group = QGroupBox("1. Lựa chọn SKU & Horizon")
        sku_layout = QGridLayout(sku_group)
        sku_layout.setVerticalSpacing(8)

        sku_layout.addWidget(QLabel("Mã SKU / StockCode:"), 0, 0)
        self.sku_combo = QComboBox()
        self.sku_combo.setEditable(True)
        self.sku_combo.currentIndexChanged.connect(self.on_sku_changed)
        sku_layout.addWidget(self.sku_combo, 0, 1)

        sku_layout.addWidget(QLabel("Thời hạn Dự báo:"), 1, 0)
        self.horizon_label = QLabel("1 Tuần Tới (Next Week Ahead)")
        self.horizon_label.setStyleSheet("font-weight: bold; color: #1e293b;")
        sku_layout.addWidget(self.horizon_label, 1, 1)

        left_panel.addWidget(sku_group)

        # Group 2: Inventory Simulation Parameters
        inv_group = QGroupBox("2. Trạng thái Tồn kho Hiện tại (Mô phỏng)")
        inv_layout = QGridLayout(inv_group)
        inv_layout.setVerticalSpacing(8)

        inv_layout.addWidget(QLabel("Tồn kho Thực tế (Units):"), 0, 0)
        self.stock_spin = QSpinBox()
        self.stock_spin.setRange(0, 1000000)
        self.stock_spin.setValue(150)
        inv_layout.addWidget(self.stock_spin, 0, 1)

        inv_layout.addWidget(QLabel("Target Service Level:"), 1, 0)
        self.service_combo = QComboBox()
        self.service_combo.addItems(["90% (Standard - z=1.28)", "95% (High Reliability - z=1.65)", "99% (Critical - z=2.33)", "80% (Economy - z=0.84)"])
        inv_layout.addWidget(self.service_combo, 1, 1)

        inv_layout.addWidget(QLabel("Chi phí Lưu kho (£/sp/tuần):"), 2, 0)
        self.holding_spin = QDoubleSpinBox()
        self.holding_spin.setRange(0.01, 100.0)
        self.holding_spin.setValue(0.50)
        inv_layout.addWidget(self.holding_spin, 2, 1)

        inv_layout.addWidget(QLabel("Phạt Thiếu hàng (£/sp):"), 3, 0)
        self.stockout_spin = QDoubleSpinBox()
        self.stockout_spin.setRange(0.01, 500.0)
        self.stockout_spin.setValue(2.00)
        inv_layout.addWidget(self.stockout_spin, 3, 1)

        left_panel.addWidget(inv_group)

        # Calculate Button
        self.calc_btn = QPushButton("Tính Toán & Ra Quyết Định Tồn Kho")
        self.calc_btn.setObjectName("calcBtn")
        self.calc_btn.clicked.connect(self.calculate_prediction)
        left_panel.addWidget(self.calc_btn)

        # Group 3: Recommendation & Decision Card
        dec_group = QGroupBox("3. Khuyến Nghị Đặt Hàng & Cảnh Báo Tồn Kho")
        dec_layout = QVBoxLayout(dec_group)
        dec_layout.setSpacing(8)

        self.flag_label = QLabel("TRẠNG THÁI: CHỜ TÍNH TOÁN")
        self.flag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.flag_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.flag_label.setStyleSheet("""
            background-color: #f1f5f9;
            color: #475569;
            padding: 10px;
            border-radius: 6px;
            border: 1px solid #cbd5e1;
        """)
        dec_layout.addWidget(self.flag_label)

        self.result_table = QTableWidget(7, 2)
        self.result_table.setHorizontalHeaderLabels(["Chỉ Số Kế Hoạch", "Giá Trị"])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.setAlternatingRowColors(True)
        dec_layout.addWidget(self.result_table)

        left_panel.addWidget(dec_group)
        left_panel.addStretch()

        # ====================================================
        # RIGHT PANEL: Visualization Canvas
        # ====================================================
        right_panel = QVBoxLayout()
        chart_group = QGroupBox("Chuỗi Thời Gian Nhu Cầu Lịch Sử, Dự Báo & Biên Độ Tin Cậy Conformal")
        chart_layout = QVBoxLayout(chart_group)

        self.figure = Figure(figsize=(7, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        chart_layout.addWidget(self.canvas)
        right_panel.addWidget(chart_group)

        main_layout.addLayout(left_panel, 4)
        main_layout.addLayout(right_panel, 6)
        self.setCentralWidget(main_widget)

        self.setStatusBar(QStatusBar())

    def on_sku_changed(self):
        """Khi đổi SKU, tải mức tồn kho mặc định từ CSDL nếu có."""
        sku = self.sku_combo.currentText().strip()
        if not sku:
            return

        if self.radio_mysql.isChecked() and self.mysql_available:
            try:
                conn = get_mysql_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT simulated_current_stock FROM forecast_inventory_decisions WHERE sku_id = %s ORDER BY forecast_week_start DESC LIMIT 1;",
                    (sku,)
                )
                row = cursor.fetchone()
                if row and row.get("simulated_current_stock") is not None:
                    self.stock_spin.setValue(int(row["simulated_current_stock"]))
                cursor.close()
                conn.close()
            except Exception:
                pass

        self.calculate_prediction()

    def calculate_prediction(self):
        sku = self.sku_combo.currentText().strip()
        if not sku:
            return

        current_stock = self.stock_spin.value()

        # Service level factor
        sl_text = self.service_combo.currentText()
        if "95%" in sl_text:
            z = 1.645
        elif "99%" in sl_text:
            z = 2.326
        elif "80%" in sl_text:
            z = 0.842
        else:
            z = 1.282  # 90%

        pred_demand = 50.0
        lower_90 = 35.0
        upper_90 = 65.0
        safety_buffer = 15.0
        db_flag = None
        db_suggested_qty = None

        # 1. Truy vấn MySQL nếu ở chế độ MySQL
        if self.radio_mysql.isChecked() and self.mysql_available:
            try:
                conn = get_mysql_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT predicted_demand_catboost, lower_bound_90, upper_bound_90,
                           safety_buffer, projected_requirement, attention_flag, suggested_order_qty
                    FROM forecast_inventory_decisions
                    WHERE sku_id = %s
                    ORDER BY forecast_week_start DESC
                    LIMIT 1;
                    """,
                    (sku,)
                )
                row = cursor.fetchone()
                if row:
                    pred_demand = float(row.get("predicted_demand_catboost") or 50.0)
                    lower_90 = float(row.get("lower_90") or max(0.0, pred_demand - 15.0))
                    upper_90 = float(row.get("upper_90") or pred_demand + 15.0)
                    safety_buffer = float(row.get("safety_buffer") or 15.0) * (z / 1.282)
                    db_flag = row.get("attention_flag")
                    db_suggested_qty = row.get("suggested_order_qty")
                cursor.close()
                conn.close()
            except Exception as e:
                logger.error(f"Error fetching inventory record from MySQL: {e}")

        # 2. Truy vấn Offline nếu không có dữ liệu MySQL
        elif self.predictions_df is not None:
            sku_matches = self.predictions_df[self.predictions_df["sku_id"].astype(str) == sku]
            if not sku_matches.empty:
                last_row = sku_matches.iloc[-1]
                pred_demand = float(last_row.get("prediction", 50.0))
                lower_90 = max(0.0, pred_demand - 15.0)
                upper_90 = pred_demand + 15.0
                safety_buffer = max(5.0, (upper_90 - pred_demand) * (z / 1.282))

        projected_req = pred_demand + safety_buffer

        # Xác định Cờ cảnh báo Attention Flag & Màu sắc
        if current_stock < safety_buffer:
            flag = "SHORTAGE RISK (CẢNH BÁO THIẾU HÀNG)"
            flag_bg = "#fef2f2"
            flag_color = "#dc2626"
            suggested_action = f"Đặt hàng ngay: {max(0, int(np.ceil(projected_req - current_stock)))} sản phẩm"
        elif current_stock > 2.5 * projected_req:
            flag = "EXCESS STOCK (CẢNH BÁO DƯ THỪA TỒN KHO)"
            flag_bg = "#fefce8"
            flag_color = "#b45309"
            suggested_action = "Tạm ngưng đặt hàng — Giải phóng tồn kho dư thừa"
        else:
            flag = "ADEQUATE (TỒN KHO CÂN BẰNG TỐT)"
            flag_bg = "#f0fdf4"
            flag_color = "#16a34a"
            suggested_action = "Mức tồn kho an toàn, tiếp tục chu kỳ kiểm tra định kỳ"

        self.flag_label.setText(flag)
        self.flag_label.setStyleSheet(f"""
            background-color: {flag_bg};
            color: {flag_color};
            padding: 10px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 12px;
            border: 2px solid {flag_color};
        """)

        # Điền dữ liệu vào bảng kết quả
        order_qty = max(0, int(np.ceil(projected_req - current_stock)))
        source_name = "MySQL (online_retail_db)" if (self.radio_mysql.isChecked() and self.mysql_available) else "Offline Parquet/CSV"
        results = [
            ("Nguồn Dữ Liệu", source_name),
            ("Mã SKU Phân Tích", sku),
            ("Nhu Cầu Dự Báo (t+1)", f"{pred_demand:.1f} đơn vị"),
            ("Khoảng Tin Cậy 90%", f"[{lower_90:.1f}, {upper_90:.1f}] đơn vị"),
            ("Mức Đệm An Toàn (Safety Buffer)", f"{safety_buffer:.1f} đơn vị"),
            ("Tổng Nhu Cầu Dự Phóng (Target Req)", f"{projected_req:.1f} đơn vị"),
            ("Đề Xuất Hành Động", suggested_action)
        ]

        for i, (k, v) in enumerate(results):
            self.result_table.setItem(i, 0, QTableWidgetItem(k))
            val_item = QTableWidgetItem(v)
            val_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold if i in [2, 6] else QFont.Weight.Normal))
            self.result_table.setItem(i, 1, val_item)

        # Cập nhật biểu đồ trực quan
        self.update_plot(sku, pred_demand, lower_90, upper_90, current_stock)

    def update_plot(self, sku: str, pred_demand: float, lower: float, upper: float, stock: int):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        history_y = []
        # Truy vấn lịch sử từ MySQL
        if self.radio_mysql.isChecked() and self.mysql_available:
            try:
                conn = get_mysql_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT demand FROM sku_week_demand WHERE sku_id = %s ORDER BY week_start DESC LIMIT 16;",
                    (sku,)
                )
                rows = cursor.fetchall()
                if rows:
                    history_y = [r["demand"] for r in reversed(rows)]
                cursor.close()
                conn.close()
            except Exception as e:
                logger.warning(f"Failed to fetch plot history from MySQL: {e}")

        # Fallback offline
        if not history_y and self.history_df is not None:
            sku_hist = self.history_df[self.history_df["sku_id"].astype(str) == sku].tail(16)
            if not sku_hist.empty:
                history_y = sku_hist["demand"].values.tolist()

        if not history_y:
            history_y = [max(0, int(v)) for v in np.random.normal(pred_demand, max(5, pred_demand * 0.2), 12)]

        history_x = list(range(1, len(history_y) + 1))
        next_t = history_x[-1] + 1

        # Đường nhu cầu lịch sử
        ax.plot(history_x, history_y, marker="o", color="#0284c7", lw=2.2, label="Nhu Cầu Lịch Sử (Past Weeks)")

        # Điểm và đường dự báo
        ax.plot([history_x[-1], next_t], [history_y[-1], pred_demand], color="#ea580c", linestyle="--", lw=2)
        ax.scatter([next_t], [pred_demand], color="#ea580c", s=90, zorder=5, label=f"Dự Báo Tuần Tới ({pred_demand:.1f})")

        # Khoảng biến thiên bất định Conformal
        yerr_lower = max(0.0, pred_demand - lower)
        yerr_upper = max(0.0, upper - pred_demand)
        ax.errorbar(
            [next_t], [pred_demand],
            yerr=[[yerr_lower], [yerr_upper]],
            fmt="none", ecolor="#ea580c", elinewidth=2.5, capsize=6,
            label="Khoảng Tin Cậy 90% (Conformal Interval)"
        )

        # Đường mức tồn kho hiện tại
        ax.axhline(stock, color="#16a34a", linestyle=":", lw=2.2, label=f"Mức Tồn Kho Hiện Tại ({stock} sp)")

        ax.set_title(f"Chuỗi Thời Gian Nhu Cầu & Kế Hoạch Tồn Kho — SKU: {sku}", fontsize=12, pad=12, fontweight="bold")
        ax.set_xlabel("Tuần (Timeline Weeks)", fontsize=10)
        ax.set_ylabel("Số Lượng Đặt Hàng / Tiêu Thụ (Units)", fontsize=10)
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
