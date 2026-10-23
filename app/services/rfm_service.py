import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

from app.database import query_dataframe
from app.models.schemas import ClusterSummary, KMeansClusterResponse, CustomerPredictResponse

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models_saved")
os.makedirs(MODEL_DIR, exist_ok=True)
MODEL_PATH = os.path.join(MODEL_DIR, "kmeans_rfm_model.joblib")

class RFMService:
    _cached_model: Optional[KMeans] = None
    _cached_scaler: Optional[StandardScaler] = None
    _cached_labels_map: Dict[int, str] = {}
    _cached_rfm_df: Optional[pd.DataFrame] = None

    @classmethod
    def get_rfm_data(cls, year_cohort: Optional[str] = None) -> pd.DataFrame:
        """Truy vấn dữ liệu giao dịch từ MySQL và tính toán ma trận RFM cho từng khách hàng"""
        cohort_filter = ""
        params = ()
        if year_cohort:
            cohort_filter = "AND year_cohort = %s"
            params = (year_cohort,)

        sql = f"""
        SELECT 
            customer_id,
            MAX(invoice_date) as last_purchase_date,
            COUNT(DISTINCT invoice_no) as frequency,
            SUM(quantity * unit_price) as monetary
        FROM online_retail
        WHERE customer_id IS NOT NULL 
          AND quantity > 0 
          AND unit_price > 0
          {cohort_filter}
        GROUP BY customer_id
        HAVING monetary > 0;
        """
        df = query_dataframe(sql, params if params else None)
        if df.empty:
            return df

        # Ngày tham chiếu = ngày giao dịch muộn nhất + 1 ngày
        ref_date = df['last_purchase_date'].max() + pd.Timedelta(days=1)
        df['recency'] = (ref_date - df['last_purchase_date']).dt.days

        # Giữ lại các cột RFM cần thiết
        rfm = df[['customer_id', 'recency', 'frequency', 'monetary']].copy()
        rfm['recency'] = rfm['recency'].astype(int)
        rfm['frequency'] = rfm['frequency'].astype(int)
        rfm['monetary'] = rfm['monetary'].astype(float).round(2)
        return rfm

    @classmethod
    def run_kmeans_clustering(cls, n_clusters: int = 4, year_cohort: Optional[str] = None, limit_sample: int = 3000) -> KMeansClusterResponse:
        """Huấn luyện mô hình K-Means và phân đoạn khách hàng theo chỉ số RFM"""
        rfm_df = cls.get_rfm_data(year_cohort)
        if rfm_df.empty:
            return KMeansClusterResponse(n_clusters=n_clusters, total_customers=0, clusters=[], sample_points=[])

        # Áp dụng Log transformation để giảm độ lệch (skewness) của Frequency & Monetary
        rfm_features = rfm_df[['recency', 'frequency', 'monetary']].copy()
        rfm_log = np.log1p(rfm_features)

        # Chuẩn hóa StandardScaler
        scaler = StandardScaler()
        rfm_scaled = scaler.fit_transform(rfm_log)

        # Huấn luyện K-Means
        kmeans = KMeans(n_clusters=n_clusters, init='k-means++', random_state=42, n_init=10)
        clusters = kmeans.fit_predict(rfm_scaled)
        rfm_df['cluster'] = clusters

        # Giảm chiều PCA 2D để vẽ đồ thị trong PyQt6
        pca = PCA(n_components=2, random_state=42)
        coords_2d = pca.fit_transform(rfm_scaled)
        rfm_df['pca_x'] = np.round(coords_2d[:, 0], 3)
        rfm_df['pca_y'] = np.round(coords_2d[:, 1], 3)

        # Tính toán đặc trưng trung bình của từng cụm
        summary_df = rfm_df.groupby('cluster').agg({
            'customer_id': 'count',
            'recency': 'mean',
            'frequency': 'mean',
            'monetary': 'mean'
        }).reset_index()

        total_cust = len(rfm_df)
        cluster_summaries = []
        labels_map = {}

        # Gán tên phân khúc kinh doanh dựa trên đặc trưng RFM
        # Sắp xếp các cụm theo Monetary & Frequency giảm dần
        sorted_by_value = summary_df.sort_values(by=['monetary', 'frequency'], ascending=[False, False])
        rank_names = [
            "VIP / Khách hàng Hàng đầu (Champions)",
            "Khách hàng Trung thành (Loyal Customers)",
            "Khách hàng Tiềm năng (Potential Loyalists)",
            "Khách hàng Nguy cơ Rời bỏ (At Risk / Churn)",
            "Khách hàng Cần Kích hoạt (Hibernating / Lost)",
            "Khách hàng Mới Mua sắm (Recent Customers)"
        ]

        for rank, (_, row) in enumerate(sorted_by_value.iterrows()):
            c_id = int(row['cluster'])
            name = rank_names[rank] if rank < len(rank_names) else f"Phân khúc {c_id + 1}"
            labels_map[c_id] = name

        for _, row in summary_df.iterrows():
            c_id = int(row['cluster'])
            c_count = int(row['customer_id'])
            cluster_summaries.append(ClusterSummary(
                cluster_id=c_id,
                cluster_name=labels_map.get(c_id, f"Cluster {c_id}"),
                customer_count=c_count,
                percentage=round((c_count / total_cust) * 100, 2),
                avg_recency=round(float(row['recency']), 1),
                avg_frequency=round(float(row['frequency']), 1),
                avg_monetary=round(float(row['monetary']), 2)
            ))

        # Lưu model & scaler vào bộ nhớ cache & file
        cls._cached_model = kmeans
        cls._cached_scaler = scaler
        cls._cached_labels_map = labels_map
        cls._cached_rfm_df = rfm_df

        try:
            joblib.dump({
                'model': kmeans,
                'scaler': scaler,
                'labels_map': labels_map,
                'n_clusters': n_clusters
            }, MODEL_PATH)
        except Exception as e:
            print(f"[!] Không thể lưu model ra disk: {e}")

        # Chọn mẫu đại diện để trả về cho Client PyQt6 hiển thị biểu đồ
        sample_df = rfm_df.sample(min(limit_sample, len(rfm_df)), random_state=42)
        sample_points = sample_df[['customer_id', 'recency', 'frequency', 'monetary', 'cluster', 'pca_x', 'pca_y']].to_dict(orient='records')
        for p in sample_points:
            p['cluster_name'] = labels_map.get(p['cluster'], f"Cluster {p['cluster']}")

        return KMeansClusterResponse(
            n_clusters=n_clusters,
            total_customers=total_cust,
            clusters=sorted(cluster_summaries, key=lambda x: x.cluster_id),
            sample_points=sample_points
        )

    @classmethod
    def predict_customer_segment(cls, recency: float, frequency: float, monetary: float) -> CustomerPredictResponse:
        """Dự đoán phân khúc khách hàng mới dựa trên 3 chỉ số RFM"""
        # Tải mô hình nếu chưa có trong cache
        if cls._cached_model is None or cls._cached_scaler is None:
            if os.path.exists(MODEL_PATH):
                data = joblib.load(MODEL_PATH)
                cls._cached_model = data['model']
                cls._cached_scaler = data['scaler']
                cls._cached_labels_map = data['labels_map']
            else:
                # Nếu chưa chạy huấn luyện, tự động huấn luyện mặc định 4 cụm
                cls.run_kmeans_clustering(n_clusters=4)

        # Chuẩn bị vector đặc trưng
        raw_feat = np.array([[max(0.0, recency), max(0.0, frequency), max(0.0, monetary)]])
        log_feat = np.log1p(raw_feat)
        scaled_feat = cls._cached_scaler.transform(log_feat)

        predicted_cluster = int(cls._cached_model.predict(scaled_feat)[0])
        cluster_name = cls._cached_labels_map.get(predicted_cluster, f"Cụm {predicted_cluster}")

        # Đưa ra mô tả và chiến lược đề xuất kinh doanh
        if "VIP" in cluster_name or "Champions" in cluster_name:
            desc = "Khách hàng mua hàng rất thường xuyên, chi tiêu giá trị cao và giao dịch gần đây."
            action = "Chăm sóc đặc biệt (VIP Lounge), gửi quà tri ân, mời tham gia chương trình khách hàng thân thiết cao cấp."
        elif "Trung thành" in cluster_name:
            desc = "Khách hàng mua đều đặn với tổng chi tiêu khá tốt, gắn bó với thương hiệu."
            action = "Giới thiệu các sản phẩm mới, tặng voucher giảm giá cho các đơn hàng tiếp theo."
        elif "Tiềm năng" in cluster_name or "Mới" in cluster_name:
            desc = "Khách hàng mới phát sinh giao dịch gần đây hoặc có tiềm năng tăng trưởng chi tiêu."
            action = "Gửi email gợi ý các sản phẩm bán chạy (cross-sell/up-sell), hỗ trợ trải nghiệm sau mua."
        else:
            desc = "Khách hàng đã lâu không quay lại mua sắm, tần suất thấp hoặc chi tiêu nhỏ giọt."
            action = "Gửi chiến dịch Re-engagement: mã giảm giá đặc biệt 'Chúng tôi nhớ bạn', thông báo khuyến mãi lớn."

        return CustomerPredictResponse(
            predicted_cluster=predicted_cluster,
            cluster_name=cluster_name,
            description=desc,
            recommended_action=action
        )
