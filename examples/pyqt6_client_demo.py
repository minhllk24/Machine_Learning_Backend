"""
MẪU GIAO DIỆN CLIENT PYQT6 KẾT NỐI VỚI BACKEND MACHINE LEARNING
Dành cho đồ án môn Học Máy - Thầy Trần Duy Thanh

Cách chạy:
    python examples/pyqt6_client_demo.py
"""
import sys
import requests
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QTabWidget, QGroupBox, QGridLayout,
    QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

BACKEND_URL = "http://127.0.0.1:8000"

class MLClientWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Machine Learning Client - Online Retail (PyQt6)")
        self.resize(1000, 700)
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Tiêu đề Header
        header = QLabel("HỆ THỐNG PHÂN TÍCH & DỰ ĐOÁN HỌC MÁY (ONLINE RETAIL II)")
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("color: #1A365D; margin: 10px 0;")
        main_layout.addWidget(header)

        # Tab Widget
        tabs = QTabWidget()
        tabs.addTab(self.create_dashboard_tab(), "📊 Tổng quan (Dashboard & KPIs)")
        tabs.addTab(self.create_prediction_tab(), "🤖 Dự đoán Phân khúc Khách hàng (K-Means)")
        tabs.addTab(self.create_transactions_tab(), "📋 Lịch sử Giao dịch (MySQL)")
        main_layout.addWidget(tabs)

    # =========================================================================
    # TAB 1: DASHBOARD & KPIS
    # =========================================================================
    def create_dashboard_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Nút Refresh
        btn_refresh = QPushButton("🔄 Tải lại dữ liệu KPIs từ Backend")
        btn_refresh.setStyleSheet("background-color: #2B6CB0; color: white; padding: 8px; font-weight: bold; border-radius: 5px;")
        btn_refresh.clicked.connect(self.fetch_kpis)
        layout.addWidget(btn_refresh)

        # Nhóm hiển thị thẻ KPI
        kpi_group = QGroupBox("Các chỉ số kinh doanh chính (KPIs)")
        kpi_layout = QGridLayout(kpi_group)

        self.lbl_records = QLabel("---")
        self.lbl_orders = QLabel("---")
        self.lbl_customers = QLabel("---")
        self.lbl_revenue = QLabel("---")
        self.lbl_aov = QLabel("---")

        labels = [
            ("Tổng số dòng dữ liệu (Rows):", self.lbl_records, 0, 0),
            ("Tổng số hóa đơn (Invoices):", self.lbl_orders, 0, 1),
            ("Tổng số khách hàng (Customers):", self.lbl_customers, 1, 0),
            ("Tổng doanh thu (Total Revenue):", self.lbl_revenue, 1, 1),
            ("Giá trị đơn hàng TB (AOV):", self.lbl_aov, 2, 0)
        ]

        for title, val_lbl, r, c in labels:
            box = QGroupBox(title)
            b_layout = QVBoxLayout(box)
            val_lbl.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            val_lbl.setStyleSheet("color: #2C5282;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            b_layout.addWidget(val_lbl)
            kpi_layout.addWidget(box, r, c)

        layout.addWidget(kpi_group)
        layout.addStretch()

        # Tự động nạp dữ liệu lần đầu
        self.fetch_kpis()
        return tab

    def fetch_kpis(self):
        try:
            resp = requests.get(f"{BACKEND_URL}/api/analytics/kpis", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                self.lbl_records.setText(f"{data['total_records']:,}")
                self.lbl_orders.setText(f"{data['total_orders']:,}")
                self.lbl_customers.setText(f"{data['total_customers']:,}")
                self.lbl_revenue.setText(f"${data['total_revenue']:,.2f}")
                self.lbl_aov.setText(f"${data['avg_order_value']:,.2f}")
            else:
                QMessageBox.warning(self, "Lỗi", f"Không lấy được KPIs (Mã {resp.status_code})")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi kết nối", f"Không thể kết nối đến Backend: {e}\nHãy chắc chắn server backend đang chạy (python run.py)!")

    # =========================================================================
    # TAB 2: MACHINE LEARNING PREDICTION (K-MEANS)
    # =========================================================================
    def create_prediction_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        input_group = QGroupBox("Nhập thông số RFM của khách hàng cần dự đoán:")
        grid = QGridLayout(input_group)

        grid.addWidget(QLabel("1. Recency (Số ngày kể từ lần mua gần nhất):"), 0, 0)
        self.spin_recency = QDoubleSpinBox()
        self.spin_recency.setRange(1, 1000)
        self.spin_recency.setValue(15)
        grid.addWidget(self.spin_recency, 0, 1)

        grid.addWidget(QLabel("2. Frequency (Tổng số lần mua hàng):"), 1, 0)
        self.spin_freq = QSpinBox()
        self.spin_freq.setRange(1, 500)
        self.spin_freq.setValue(12)
        grid.addWidget(self.spin_freq, 1, 1)

        grid.addWidget(QLabel("3. Monetary (Tổng số tiền đã chi tiêu $):"), 2, 0)
        self.spin_monetary = QDoubleSpinBox()
        self.spin_monetary.setRange(1, 1000000)
        self.spin_monetary.setValue(4500)
        grid.addWidget(self.spin_monetary, 2, 1)

        btn_predict = QPushButton("🔮 Dự đoán Phân khúc Khách hàng (K-Means)")
        btn_predict.setStyleSheet("background-color: #38A169; color: white; padding: 10px; font-weight: bold; border-radius: 5px;")
        btn_predict.clicked.connect(self.process_prediction)
        grid.addWidget(btn_predict, 3, 0, 1, 2)

        layout.addWidget(input_group)

        # Kết quả dự đoán
        result_group = QGroupBox("Kết quả Phân loại & Đề xuất Chiến lược:")
        res_layout = QVBoxLayout(result_group)

        self.lbl_result_cluster = QLabel("Chưa có dự đoán")
        self.lbl_result_cluster.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        self.lbl_result_cluster.setStyleSheet("color: #2F855A;")
        res_layout.addWidget(self.lbl_result_cluster)

        self.lbl_result_desc = QLabel("")
        self.lbl_result_desc.setWordWrap(True)
        res_layout.addWidget(self.lbl_result_desc)

        self.lbl_result_action = QLabel("")
        self.lbl_result_action.setWordWrap(True)
        self.lbl_result_action.setStyleSheet("color: #C53030; font-weight: bold;")
        res_layout.addWidget(self.lbl_result_action)

        layout.addWidget(result_group)
        layout.addStretch()
        return tab

    def process_prediction(self):
        payload = {
            "recency_days": self.spin_recency.value(),
            "frequency_orders": self.spin_freq.value(),
            "monetary_amount": self.spin_monetary.value()
        }
        try:
            resp = requests.post(f"{BACKEND_URL}/api/ml/segmentation/predict", json=payload, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                self.lbl_result_cluster.setText(f"🎯 Phân khúc: {data['cluster_name']} (Cụm ID: {data['predicted_cluster']})")
                self.lbl_result_desc.setText(f"📝 Đặc điểm: {data['description']}")
                self.lbl_result_action.setText(f"💡 Đề xuất hành động: {data['recommended_action']}")
            else:
                QMessageBox.warning(self, "Lỗi", f"Dự đoán thất bại (Mã {resp.status_code})")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể gọi API: {e}")

    # =========================================================================
    # TAB 3: TRANSACTIONS TABLE
    # =========================================================================
    def create_transactions_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        btn_load = QPushButton("📥 Tải 50 giao dịch gần nhất từ CSDL MySQL")
        btn_load.clicked.connect(self.load_transactions)
        layout.addWidget(btn_load)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Hóa đơn", "Mã hàng", "Mô tả sản phẩm", "Số lượng", "Đơn giá ($)", "Mã KH", "Thời gian"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        return tab

    def load_transactions(self):
        try:
            resp = requests.get(f"{BACKEND_URL}/api/retail/transactions?limit=50", timeout=5)
            if resp.status_code == 200:
                rows = resp.json()
                self.table.setRowCount(len(rows))
                for i, r in enumerate(rows):
                    self.table.setItem(i, 0, QTableWidgetItem(str(r["invoice_no"])))
                    self.table.setItem(i, 1, QTableWidgetItem(str(r["stock_code"])))
                    self.table.setItem(i, 2, QTableWidgetItem(str(r["description"] or "")))
                    self.table.setItem(i, 3, QTableWidgetItem(str(r["quantity"])))
                    self.table.setItem(i, 4, QTableWidgetItem(f"${r['unit_price']:.2f}"))
                    self.table.setItem(i, 5, QTableWidgetItem(str(r["customer_id"]) if r["customer_id"] else "Khách vãng lai"))
                    self.table.setItem(i, 6, QTableWidgetItem(str(r["invoice_date"])))
            else:
                QMessageBox.warning(self, "Lỗi", "Không tải được danh sách giao dịch.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi gọi API: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MLClientWindow()
    window.show()
    sys.exit(app.exec())
