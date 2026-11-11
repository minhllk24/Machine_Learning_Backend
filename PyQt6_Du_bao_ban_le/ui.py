"""Các màn hình tiếng Việt theo bản Figma nhóm đã duyệt."""
from __future__ import annotations

import inspect
import os
from pathlib import Path
import sys
from typing import Any, Sequence

try:
    from dotenv import dotenv_values
except ImportError:
    dotenv_values = None  # type: ignore[assignment]

from PyQt6.QtCore import QModelIndex, Qt, pyqtSignal
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QCompleter,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from PyQt6_Du_bao_ban_le.models import (
        AuthUser,
        Forecast,
        OverviewStats,
        Product,
        SkuSummary,
        StockReview,
        to_float,
        to_int,
    )
    from PyQt6_Du_bao_ban_le.repository import (
        DEFAULT_FORECAST_WEEKS,
        FORECAST_ORIGIN,
        MODEL_IDS,
        MODEL_LABELS,
        RetailRepository,
    )
    from PyQt6_Du_bao_ban_le.widgets import (
        AMBER,
        BLUE,
        DANGER,
        INK,
        SUB,
        TEAL,
        Card,
        DemandChart,
        InventoryChart,
        decimal,
        format_short_date,
        label,
        metrics,
        number,
        row,
        set_rows,
        table,
    )
    from PyQt6_Du_bao_ban_le.workers import RequestCoordinator
except ImportError:
    from models import (
        AuthUser,
        Forecast,
        OverviewStats,
        Product,
        SkuSummary,
        StockReview,
        to_float,
        to_int,
    )
    from repository import (
        DEFAULT_FORECAST_WEEKS,
        FORECAST_ORIGIN,
        MODEL_IDS,
        MODEL_LABELS,
        RetailRepository,
    )
    from widgets import (
        AMBER,
        BLUE,
        DANGER,
        INK,
        SUB,
        TEAL,
        Card,
        DemandChart,
        InventoryChart,
        decimal,
        format_short_date,
        label,
        metrics,
        number,
        row,
        set_rows,
        table,
    )
    from workers import RequestCoordinator


TITLES = ("Tổng quan dữ liệu", "Lịch sử nhu cầu", "Dự báo nhu cầu", "Kiểm tra tồn kho")
ALLOWED_SAVE_ROLES = frozenset({"admin", "planner"})
READ_ONLY_SAVE_TOOLTIP = "Tài khoản chỉ có quyền xem (cần vai trò planner hoặc admin để lưu)"

STYLE = """
QWidget { font-family: "Segoe UI", "Roboto", sans-serif; font-size: 14px; color: #142238; }
QWidget#app { background: #F5F7FA; }
QFrame#card { background: white; border: 1px solid #DFE6EF; border-radius: 12px; }
QFrame#sidebar { background: #18273E; }
QFrame#topbar { background: white; border-bottom: 1px solid #DFE6EF; }
QPushButton { background: #2256CD; color: white; border: none; border-radius: 7px;
  padding: 10px 18px; font-weight: 600; min-height: 20px; }
QPushButton:hover { background: #1944AA; }
QPushButton:pressed { background: #123686; }
QPushButton:disabled { background: #CCD6E9; color: #667A97; }
QPushButton:focus { border: 2px solid #85A9FB; }
QPushButton#secondary { background: white; color: #142238; border: 1px solid #D8E0EA;
  padding: 8px 14px; font-weight: 600; min-height: 18px; }
QPushButton#secondary:hover { background: #F5F7FA; border: 1px solid #B6C4D8; }
QPushButton#secondary:pressed { background: #EAF1FF; }
QPushButton#secondary:disabled { background: #F5F7FA; color: #8A9BB0; border: 1px solid #E2E8F0; }
QPushButton#nav { background: transparent; color: #BAC9DC; text-align: left;
  padding: 12px 15px; border-radius: 7px; font-weight: 500; }
QPushButton#nav:checked { background: #29415F; color: white; font-weight: 700; }
QPushButton#nav:hover { background: #243A56; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: white; color: #142238;
  border: 1px solid #D8E0EA; border-radius: 7px; padding: 9px 12px; min-height: 21px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid #2256CD; }
QComboBox::drop-down { border: none; width: 25px; }
QComboBox::down-arrow { image: url("__CHEVRON__"); width: 14px; height: 14px; }
QComboBox QAbstractItemView { background: white; color: #142238;
  selection-background-color: #EAF1FF; selection-color: #2256CD; padding: 5px; }
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 0px; height: 0px; }
QTableWidget { background: white; border: none; color: #34465D; font-size: 13px; }
QTableWidget::item { padding: 6px 10px; border-bottom: 1px solid #E7EDF4; }
QHeaderView::section { background: #F5F7FA; border: none; color: #52657C;
  font-size: 12px; font-weight: 600; padding: 8px 10px; }
QScrollArea { background: #F5F7FA; border: none; }
QScrollBar:vertical { background: #F5F7FA; width: 9px; }
QScrollBar::handle:vertical { background: #C4D0E0; border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""
STYLE = STYLE.replace("__CHEVRON__", (Path(__file__).parent / "assets" / "chevron.svg").as_posix())


def field(caption: str, widget: QWidget) -> QVBoxLayout:
    layout = QVBoxLayout()
    layout.setSpacing(7)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(label(caption, 13, bold=True))
    layout.addWidget(widget)
    return layout


def _pill_style(bg: str, fg: str, border: str) -> str:
    return (
        f"background: {bg}; color: {fg}; border: 1px solid {border};"
        "border-radius: 12px; padding: 4px 11px; font-size: 12px; font-weight: 700;"
    )


def _banner_style(bg: str, fg: str, border: str) -> str:
    return (
        f"background: {bg}; color: {fg}; border: 1px solid {border};"
        "border-radius: 8px; padding: 8px 12px; font-size: 13px; font-weight: 600;"
    )


def _safe_error_text(
    message: Any, fallback: str = "Đã xảy ra lỗi kết nối hoặc xử lý dữ liệu."
) -> str:
    raw = str(message or "").strip()
    if not raw:
        return fallback
    first_line = raw.splitlines()[0].strip()
    lowered = first_line.lower()
    if (
        "connection refused" in lowered
        or "can't connect to mysql" in lowered
        or "lost connection" in lowered
    ):
        return "Không thể kết nối máy chủ MySQL — vui lòng kiểm tra lại kết nối hoặc dùng Offline fallback."
    if "access denied" in lowered:
        return "Không có quyền truy cập cơ sở dữ liệu MySQL."
    if "timed out" in lowered or "timeout" in lowered:
        return "Yêu cầu xử lý quá thời gian chờ."
    if len(first_line) > 160:
        return first_line[:157] + "..."
    return first_line


def _apply_db_badge(badge: QWidget, is_mysql: bool) -> None:
    if is_mysql:
        badge.setText("● MySQL live")
        badge.setStyleSheet(_pill_style("#E6F4F2", TEAL, "#A7DDD7"))
    else:
        badge.setText("● Offline fallback")
        badge.setStyleSheet(_pill_style("#FDF3EB", AMBER, "#E8C4A8"))


def _populate_week_combo(box: QComboBox, weeks: Sequence[str]) -> None:
    current = box.currentData(Qt.ItemDataRole.UserRole)
    box.blockSignals(True)
    box.clear()
    week_list = list(weeks) or list(DEFAULT_FORECAST_WEEKS)
    for idx, week_str in enumerate(week_list, start=1):
        box.addItem(f"{week_str} (Tuần h={idx})", week_str)
    if current:
        found = box.findData(current, Qt.ItemDataRole.UserRole)
        if found >= 0:
            box.setCurrentIndex(found)
    box.blockSignals(False)


class SkuSelector(QComboBox):
    """Searchable editable QComboBox preserving binary-exact SKU casing (`15056BL` vs `15056bl`)."""

    sku_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._sku_index: dict[str, int] = {}
        self._display_to_sku: dict[str, str] = {}
        self._last_emitted_sku = ""

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMinimumContentsLength(22)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        if self.lineEdit() is not None:
            self.lineEdit().setPlaceholderText("Tìm mã SKU hoặc tên sản phẩm...")
            self.lineEdit().setClearButtonEnabled(True)
            self.lineEdit().editingFinished.connect(self._on_editing_finished)

        completer = QCompleter(self.model(), self)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setMaxVisibleItems(12)
        self.setCompleter(completer)

        completer.activated[QModelIndex].connect(self._on_completer_index)
        self.activated.connect(self._on_activated)
        self.currentIndexChanged.connect(self._on_index_changed)

    def set_skus(self, skus: Sequence[SkuSummary], preferred_sku: str = "85123A") -> None:
        previous = self.current_sku()
        self.blockSignals(True)
        self.clear()
        self._sku_index.clear()
        self._display_to_sku.clear()

        for idx, item in enumerate(skus):
            suffix = "" if item.has_forecast else " [Chỉ lịch sử]"
            display = f"{item.sku_id} — {item.name}{suffix}"
            self.addItem(display, item.sku_id)
            self._sku_index[item.sku_id] = idx
            self._display_to_sku[display] = item.sku_id

        target = ""
        if previous and previous in self._sku_index:
            target = previous
        elif preferred_sku and preferred_sku in self._sku_index:
            target = preferred_sku
        elif skus:
            target = skus[0].sku_id

        if target:
            target_idx = self._sku_index[target]
            self.setCurrentIndex(target_idx)
            self.setEditText(self.itemText(target_idx))
            self._last_emitted_sku = target
        else:
            self._last_emitted_sku = ""
        self.blockSignals(False)

    def set_sku(self, sku_id: str, emit: bool = False) -> bool:
        idx = self._sku_index.get(sku_id)
        if idx is None:
            return False
        self.blockSignals(True)
        self.setCurrentIndex(idx)
        self.setEditText(self.itemText(idx))
        self._last_emitted_sku = sku_id
        self.blockSignals(False)
        if emit:
            self.sku_changed.emit(sku_id)
        return True

    def find_sku_index(self, sku_id: str) -> int:
        return self._sku_index.get(sku_id, -1)

    def current_sku(self) -> str:
        idx = self.currentIndex()
        typed = self.currentText().strip()
        if 0 <= idx < self.count():
            item_sku = self.itemData(idx, Qt.ItemDataRole.UserRole)
            if typed == self.itemText(idx):
                return str(item_sku or "")
        if typed in self._display_to_sku:
            return self._display_to_sku[typed]
        if typed in self._sku_index:
            return typed
        for sep in (" — ", " - "):
            if sep in typed:
                prefix = typed.split(sep, 1)[0].strip()
                if prefix in self._sku_index:
                    return prefix
        if 0 <= idx < self.count() and not typed:
            return str(self.itemData(idx, Qt.ItemDataRole.UserRole) or "")
        lowered = typed.lower()
        matches = [sku for sku in self._sku_index if sku.lower() == lowered]
        if len(matches) == 1:
            return matches[0]
        if 0 <= idx < self.count():
            return str(self.itemData(idx, Qt.ItemDataRole.UserRole) or "")
        return ""

    def _commit_sku(self, sku: str) -> None:
        if not sku or sku not in self._sku_index:
            return
        idx = self._sku_index[sku]
        self.blockSignals(True)
        self.setCurrentIndex(idx)
        self.setEditText(self.itemText(idx))
        self.blockSignals(False)
        if sku != self._last_emitted_sku:
            self._last_emitted_sku = sku
            self.sku_changed.emit(sku)

    def _on_completer_index(self, model_index: QModelIndex) -> None:
        sku = model_index.data(Qt.ItemDataRole.UserRole)
        if sku:
            self._commit_sku(str(sku))

    def _on_activated(self, index: int) -> None:
        if 0 <= index < self.count():
            sku = self.itemData(index, Qt.ItemDataRole.UserRole)
            if sku:
                self._commit_sku(str(sku))

    def _on_index_changed(self, index: int) -> None:
        if 0 <= index < self.count():
            sku = str(self.itemData(index, Qt.ItemDataRole.UserRole) or "")
            if sku and sku != self._last_emitted_sku:
                self._last_emitted_sku = sku
                self.sku_changed.emit(sku)

    def _on_editing_finished(self) -> None:
        sku = self.current_sku()
        if sku:
            self._commit_sku(sku)


def product_box(source: Any = None) -> SkuSelector:
    """Create a searchable SkuSelector populated optionally from repository or fixture."""
    selector = SkuSelector()
    if source is None:
        return selector
    if hasattr(source, "list_skus"):
        selector.set_skus(source.list_skus(limit=3000))
    elif hasattr(source, "products"):
        converted = [
            SkuSummary(
                sku_id=p.sku,
                name=p.name,
                total_demand=int(sum(p.history)) if getattr(p, "history", None) else 0,
                has_forecast=getattr(p, "has_forecast", True),
                cohort=getattr(p, "cohort", None),
            )
            for p in source.products
        ]
        selector.set_skus(converted)
    return selector


def page(title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout, Any]:
    widget = QWidget()
    widget.setObjectName("app")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(32, 24, 32, 26)
    layout.setSpacing(16)
    header = QVBoxLayout()
    header.setSpacing(5)
    header.addWidget(label(title, 32, bold=True))
    subtitle_lbl = label(subtitle, 14, SUB)
    header.addWidget(subtitle_lbl)
    layout.addLayout(header)
    return widget, layout, subtitle_lbl


def wrap_page(parent: QWidget, content: QWidget) -> None:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(content)
    layout = QVBoxLayout(parent)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(scroll)


class LoginPage(QWidget):
    logged_in = pyqtSignal(object)

    def __init__(self, repo: RetailRepository, parent: QWidget | None = None):
        super().__init__(parent)
        self.repo = repo
        self._auth_coordinator = RequestCoordinator(self)
        self._preview_coordinator = RequestCoordinator(self)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        left = QFrame()
        left.setStyleSheet("QFrame { background: #14243B; }")
        side = QVBoxLayout(left)
        side.setContentsMargins(48, 48, 48, 48)
        side.setSpacing(12)
        side.addWidget(label("↗   Kế hoạch bán lẻ", 22, "#FFFFFF", True))
        side.addStretch()
        side.addWidget(label("Dự báo nhu cầu\ntheo mã hàng", 42, "#FFFFFF", True))
        side.addWidget(
            label(
                "Xem lượng bán dự kiến theo tuần\nđể chuẩn bị tồn kho cho từng sản phẩm.",
                17,
                "#C1D1E5",
            )
        )
        side.addSpacing(24)

        preview = QFrame()
        preview.setStyleSheet(
            "QFrame { background: #1C3450; border: 1px solid #355171; border-radius: 14px; }"
        )
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(22, 20, 22, 18)
        preview_layout.addWidget(label("Nhu cầu theo tuần", 20, "#FFFFFF", True))
        self.preview_sub = label("Đang tải chuỗi mẫu...", 13, "#C1D1E5")
        preview_layout.addWidget(self.preview_sub)
        self.preview_chart = DemandChart((), dark=True)
        self.preview_chart.setMinimumHeight(190)
        preview_layout.addWidget(self.preview_chart)
        preview_layout.addWidget(label("━━  Thực tế        ┄┄  Dự báo", 12, "#C1D1E5"))
        side.addWidget(preview)
        side.addStretch()

        right = QWidget()
        right.setObjectName("app")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(52, 40, 52, 40)
        right_layout.addStretch()

        card = Card()
        card.setMinimumWidth(460)
        card.setMaximumWidth(526)
        card.body.setContentsMargins(40, 36, 40, 36)
        card.body.setSpacing(14)

        top_row = row(12)
        icon = QSvgWidget(str(Path(__file__).parent / "assets" / "lock.svg"))
        icon.setFixedSize(46, 46)
        top_row.addWidget(icon)
        top_row.addStretch()
        self.db_badge = label("", 12, TEAL, True)
        self.db_badge.setWordWrap(False)
        top_row.addWidget(self.db_badge, 0, Qt.AlignmentFlag.AlignTop)
        card.body.addLayout(top_row)

        card.body.addSpacing(4)
        card.body.addWidget(label("Đăng nhập", 36, bold=True))
        card.body.addWidget(label("Nhập tên đăng nhập hoặc email để vào hệ thống dự báo.", 15, SUB))
        card.body.addSpacing(12)

        self.identifier = QLineEdit()
        self.identifier.setPlaceholderText("Ví dụ: planner hoặc planner@retail.local")
        self.identifier.setClearButtonEnabled(True)
        self.identifier.setAccessibleName("Tên đăng nhập hoặc Email")

        self.password = QLineEdit()
        self.password.setPlaceholderText("Nhập mật khẩu tài khoản")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setAccessibleName("Mật khẩu")

        card.body.addLayout(field("Tên đăng nhập hoặc Email", self.identifier))
        card.body.addSpacing(4)
        card.body.addLayout(field("Mật khẩu", self.password))

        self.error = label("", 13, DANGER, True)
        self.error.hide()
        card.body.addWidget(self.error)

        self.submit = QPushButton("Đăng nhập")
        self.submit.setMinimumHeight(48)
        self.submit.clicked.connect(self.authenticate)
        self.password.returnPressed.connect(self.authenticate)
        self.identifier.returnPressed.connect(self.password.setFocus)
        card.body.addSpacing(8)
        card.body.addWidget(self.submit)

        right_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        right_layout.addStretch()
        root.addWidget(left, 46)
        root.addWidget(right, 54)

        self.refresh_connection_status()
        self._load_preview()
        self._apply_startup_autofill()

    def _apply_startup_autofill(self) -> None:
        """Tự điền thông tin đăng nhập cục bộ từ biến môi trường hoặc .env (nếu có)."""
        env_vals: dict[str, str | None] = {}
        env_path = PROJECT_ROOT / ".env"
        if dotenv_values is not None and env_path.is_file():
            try:
                env_vals = dotenv_values(env_path)
            except Exception:
                env_vals = {}

        default_user = (os.getenv("PYQT_AUTOFILL_USER") or env_vals.get("PYQT_AUTOFILL_USER") or "").strip()
        default_secret = os.getenv("PYQT_AUTOFILL_PASSWORD") or env_vals.get("PYQT_AUTOFILL_PASSWORD") or ""
        if default_user:
            self.identifier.setText(default_user)
        if default_secret:
            self.password.setText(default_secret)
        if default_user and default_secret:
            self.submit.setFocus()

    def refresh_connection_status(self) -> None:
        _apply_db_badge(self.db_badge, self.repo.is_mysql_available)

    def _load_preview(self) -> None:
        def task():
            skus = self.repo.list_skus(limit=5)
            preferred = next((s.sku_id for s in skus if s.sku_id == "85123A"), skus[0].sku_id if skus else "")
            if not preferred:
                return None, None
            product = self.repo.get_product(preferred, periods=None)
            fc = self.repo.get_forecast(preferred, MODEL_IDS[0])
            return product, fc

        self._preview_coordinator.submit(
            task,
            on_finished=self._on_preview_loaded,
            on_error=lambda _msg: self.preview_sub.setText("Sẵn sàng kết nối dữ liệu"),
        )

    def _on_preview_loaded(self, payload: Any) -> None:
        product, fc = payload
        self.refresh_connection_status()
        if product is None or not product.history:
            self.preview_sub.setText("Chưa có dữ liệu mẫu")
            return
        pairs = [(w, h) for w, h in zip(product.week_dates, product.history) if w <= FORECAST_ORIGIN]
        if not pairs:
            pairs = list(zip(product.week_dates, product.history))
        pairs = pairs[-8:]
        hist = [h for _, h in pairs]
        ticks = [format_short_date(w) for w, _ in pairs]
        pred_val = fc.quantity if fc is not None else None
        self.preview_sub.setText(f"SKU {product.sku}  •  {product.name[:34]}")
        self.preview_chart.set_data(hist, ticks=ticks, prediction=pred_val)

    def authenticate(self) -> None:
        if not self.submit.isEnabled():
            return
        ident = self.identifier.text().strip()
        secret = self.password.text()
        if not ident or not secret:
            self.error.setText("Vui lòng nhập tên đăng nhập/email và mật khẩu.")
            self.error.show()
            (self.identifier if not ident else self.password).setFocus()
            return

        self.error.hide()
        self.submit.setEnabled(False)
        self.submit.setText("Đang xác thực...")

        def task() -> tuple[AuthUser | None, bool]:
            user = self.repo.authenticate(ident, secret)
            return user, self.repo.is_mysql_available

        self._auth_coordinator.submit(
            task,
            on_finished=self._on_auth_finished,
            on_error=self._on_auth_error,
        )

    def _on_auth_finished(self, payload: tuple[AuthUser | None, bool]) -> None:
        user, mysql_up = payload
        self.submit.setEnabled(True)
        self.submit.setText("Đăng nhập")
        _apply_db_badge(self.db_badge, mysql_up)

        if user is None:
            self.error.setText("Tên đăng nhập/email hoặc mật khẩu chưa đúng.")
            self.error.show()
            self.password.setFocus()
            self.password.selectAll()
            return

        self.error.hide()
        self.password.clear()
        self.logged_in.emit(user)

    def _on_auth_error(self, message: str) -> None:
        self.submit.setEnabled(True)
        self.submit.setText("Đăng nhập")
        self.refresh_connection_status()
        self.error.setText(f"Không thể xác thực tài khoản: {_safe_error_text(message)}")
        self.error.show()

    def reset_for_logout(self) -> None:
        self._auth_coordinator.invalidate()
        self.password.clear()
        self.error.hide()
        self.submit.setEnabled(True)
        self.submit.setText("Đăng nhập")
        self.refresh_connection_status()
        self.identifier.setFocus()

    def cleanup(self) -> None:
        self._auth_coordinator.invalidate()
        self._preview_coordinator.invalidate()


class Overview(QWidget):
    def __init__(self, repo: RetailRepository, parent: QWidget | None = None):
        super().__init__(parent)
        self.repo = repo
        self._coordinator = RequestCoordinator(self)
        self._needs_refresh = True

        content, layout, self.subtitle_lbl = page(
            TITLES[0], "Online Retail II  •  Đang tải thống kê ETL từ hệ thống..."
        )

        toolbar = row(12)
        self.mode_badge = label("", 12, TEAL, True)
        self.mode_badge.setWordWrap(False)
        self.refresh_btn = QPushButton("Làm mới dữ liệu")
        self.refresh_btn.setObjectName("secondary")
        self.refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(self.mode_badge)
        toolbar.addStretch()
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        metric_row, self.values = metrics(
            ("Dòng giao dịch gốc", "Dòng sau làm sạch", "SKU mô hình / Danh mục", "Chuỗi tuần quan sát")
        )
        for item in self.values:
            item.set_value("—", "Đang tải...")
        layout.addLayout(metric_row)

        charts = row()
        self.sales_card = Card("Xu hướng tổng nhu cầu theo tuần", "Đang tải chuỗi tuần lịch sử...")
        self.sales_chart = DemandChart((), bars=False)
        self.sales_chart.setMinimumHeight(230)
        self.sales_card.body.addWidget(self.sales_chart, 1)
        charts.addWidget(self.sales_card, 2)

        cleaning = Card("Kết quả làm sạch ETL", "Tỷ lệ giữ lại sau làm sạch")
        self.kept_value = label("—", 20, TEAL, True)
        self.kept_bar = QProgressBar()
        self.excluded_value = label("—", 20, SUB, True)
        self.excluded_bar = QProgressBar()
        for caption, val_lbl, bar, color in (
            ("Giữ lại (transactions)", self.kept_value, self.kept_bar, TEAL),
            ("Loại bỏ (chỉ giữ sạch)", self.excluded_value, self.excluded_bar, SUB),
        ):
            cleaning.body.addSpacing(12)
            cleaning.body.addWidget(label(caption, 14, SUB))
            cleaning.body.addWidget(val_lbl)
            bar.setRange(0, 1)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar.setStyleSheet(
                f"QProgressBar {{border: none; background: #E7EDF4; border-radius: 4px;}} "
                f"QProgressBar::chunk {{background: {color}; border-radius: 4px;}}"
            )
            cleaning.body.addWidget(bar)
        cleaning.body.addStretch()
        self.total_raw_lbl = label("Tổng số dòng: —", 13, SUB)
        cleaning.body.addWidget(self.total_raw_lbl)
        charts.addWidget(cleaning, 1)
        layout.addLayout(charts, 1)

        recent = Card("Top 10 SKU theo tổng lượng bán", "Dữ liệu tổng hợp từ danh mục SKU")
        self.top_table = table(("SKU", "Sản phẩm", "Tuần gần nhất", "Tổng lượng bán"), (), stretch_column=1)
        recent.body.addWidget(self.top_table)
        layout.addWidget(recent)
        wrap_page(self, content)
        _apply_db_badge(self.mode_badge, self.repo.is_mysql_available)

    def refresh(self) -> None:
        self._needs_refresh = False
        self._coordinator.invalidate()
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Đang tải...")
        self._coordinator.submit(
            self.repo.get_overview,
            10,
            on_finished=self._apply_overview,
            on_error=self._on_error,
        )

    def _apply_overview(self, stats: OverviewStats) -> None:
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Làm mới dữ liệu")
        is_mysql = stats.data_source == "mysql"
        _apply_db_badge(self.mode_badge, is_mysql)
        source_text = "MySQL live" if is_mysql else "Offline fallback"
        self.subtitle_lbl.setText(
            f"Online Retail II  •  {stats.min_week_date or '—'} → {stats.max_week_date or '—'}  •  Nguồn: {source_text}"
        )

        kept_pct = (stats.clean_rows / stats.raw_rows * 100.0) if stats.raw_rows else 0.0
        self.values[0].set_value(number(stats.raw_rows), "Bảng gốc online_retail")
        self.values[1].set_value(
            number(stats.clean_rows),
            f"{decimal(kept_pct, 1)}% giữ lại  •  {number(stats.excluded_rows)} loại bỏ",
            TEAL,
        )
        self.values[2].set_value(
            f"{number(stats.model_skus)} / {number(stats.catalog_skus)}",
            "SKU có dự báo / Tổng danh mục",
            BLUE,
        )
        self.values[3].set_value(
            number(stats.total_weeks),
            f"{stats.min_week_date or '—'} → {stats.max_week_date or '—'}",
        )

        ticks = [format_short_date(w) for w in stats.weekly_labels]
        if self.sales_card.subtitle is not None:
            self.sales_card.subtitle.setText(
                f"Toàn bộ {number(stats.total_weeks)} tuần ({stats.min_week_date} → {stats.max_week_date})"
            )
        self.sales_chart.set_data(stats.weekly_totals, ticks=ticks)

        raw_max = max(stats.raw_rows, 1)
        self.kept_value.setText(number(stats.clean_rows))
        self.kept_bar.setRange(0, raw_max)
        self.kept_bar.setValue(min(stats.clean_rows, raw_max))
        self.excluded_value.setText(number(stats.excluded_rows))
        self.excluded_bar.setRange(0, raw_max)
        self.excluded_bar.setValue(min(stats.excluded_rows, raw_max))
        self.total_raw_lbl.setText(f"Tổng số dòng   {number(stats.raw_rows)}")

        formatted_rows = [
            (r[0], r[1] or r[0], r[2] or "—", number(to_int(r[3])))
            for r in stats.top_rows
        ]
        set_rows(self.top_table, formatted_rows)

    def _on_error(self, message: str) -> None:
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Làm mới dữ liệu")
        _apply_db_badge(self.mode_badge, self.repo.is_mysql_available)
        safe_msg = _safe_error_text(message)
        self.subtitle_lbl.setText(f"Không thể tải tổng quan: {safe_msg}")
        for item in self.values:
            if item.note.text() == "Đang tải...":
                item.set_value("—", "Chưa tải được dữ liệu")

    def cleanup(self) -> None:
        self._coordinator.invalidate()


class HistoryPage(QWidget):
    sku_selected = pyqtSignal(str)

    def __init__(self, repo: RetailRepository, parent: QWidget | None = None):
        super().__init__(parent)
        self.repo = repo
        self._coordinator = RequestCoordinator(self)
        self._needs_refresh = True

        content, layout, _ = page(TITLES[1], "Tra cứu lượng bán thực tế theo sản phẩm và tuần.")
        filters = Card()
        controls = row()
        self.sku = SkuSelector()
        self.period = QComboBox()
        for text, count in (
            ("4 tuần gần nhất", 4),
            ("8 tuần gần nhất", 8),
            ("12 tuần gần nhất", 12),
            ("26 tuần gần nhất", 26),
            ("52 tuần gần nhất", 52),
            ("Tất cả", None),
        ):
            self.period.addItem(text, count)
        self.period.setCurrentIndex(2)
        controls.addLayout(field("Sản phẩm (SKU)", self.sku), 3)
        controls.addLayout(field("Khoảng thời gian", self.period), 2)
        filters.body.addLayout(controls)
        layout.addWidget(filters)

        metric_row, self.values = metrics(
            ("Tuần gần nhất", "Trung bình mỗi tuần", "Cao nhất / Thấp nhất", "Cohort & Chuỗi tuần")
        )
        layout.addLayout(metric_row)

        self.chart_card = Card("Lượng bán theo tuần", "Chọn SKU để xem chuỗi nhu cầu")
        self.chart = DemandChart(())
        self.chart.setMinimumHeight(210)
        self.chart_card.body.addWidget(self.chart, 1)
        legend = label("━━  Lượng bán thực tế", 12, SUB)
        legend.setWordWrap(False)
        self.chart_card.body.addWidget(legend, 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.chart_card, 1)

        details = Card("Chi tiết theo tuần (tối đa 10 tuần gần nhất)")
        details.body.setContentsMargins(22, 12, 22, 12)
        details.body.setSpacing(6)
        self.details = table(("Tuần bắt đầu", "Mã SKU", "Tên sản phẩm", "Lượng bán"), (), stretch_column=2)
        details.body.addWidget(self.details)
        layout.addWidget(details)

        self.sku.sku_changed.connect(self._on_sku_changed)
        self.period.currentIndexChanged.connect(self.refresh)
        wrap_page(self, content)

    def _on_sku_changed(self, sku_id: str) -> None:
        self.sku_selected.emit(sku_id)
        self.refresh()

    def set_skus(self, skus: Sequence[SkuSummary]) -> None:
        self.sku.set_skus(skus)
        self._needs_refresh = True

    def sync_sku(self, sku_id: str) -> None:
        if self.sku.set_sku(sku_id, emit=False):
            self._needs_refresh = True

    def refresh(self) -> None:
        sku_id = self.sku.current_sku()
        if not sku_id:
            return
        self._needs_refresh = False
        periods = self.period.currentData(Qt.ItemDataRole.UserRole)
        self._coordinator.invalidate()
        if self.chart_card.subtitle is not None:
            self.chart_card.subtitle.setText(f"Đang tải lịch sử SKU {sku_id}...")
        self._coordinator.submit(
            self.repo.get_product,
            sku_id,
            periods,
            on_finished=self._apply_product,
            on_error=self._on_error,
        )

    def _apply_product(self, product: Product | None) -> None:
        if product is None:
            for item in self.values:
                item.set_value("—", "Không tìm thấy SKU")
            self.chart.set_data(())
            set_rows(self.details, ())
            return

        history = list(product.history)
        dates = list(product.week_dates)
        if len(dates) < len(history):
            dates.extend("" for _ in range(len(history) - len(dates)))

        cohort_text = product.cohort or "Chỉ lịch sử"
        fc_note = "Có dữ liệu dự báo" if product.has_forecast else "SKU chỉ có lịch sử"
        if self.chart_card.subtitle is not None:
            self.chart_card.subtitle.setText(f"SKU {product.sku}  —  {product.name}")

        if not history:
            self.values[0].set_value("0 đv", "Chưa phát sinh tuần bán")
            self.values[1].set_value("0,0 đv", "0 tuần quan sát")
            self.values[2].set_value("0 / 0 đv", "Chưa có đỉnh / đáy")
            self.values[3].set_value(cohort_text, f"0 tuần  •  {fc_note}")
            self.chart.set_data(())
            set_rows(self.details, ())
            return

        latest_val = history[-1]
        latest_date = dates[-1] or "—"
        avg_val = sum(history) / len(history)
        peak_val = max(history)
        min_val = min(history)
        peak_date = dates[history.index(peak_val)] or "—"
        min_date = dates[history.index(min_val)] or "—"

        self.values[0].set_value(f"{number(latest_val)} đv", f"Tuần {latest_date}")
        self.values[1].set_value(f"{decimal(avg_val, 1)} đv", f"Trên {len(history)} tuần đã chọn")
        self.values[2].set_value(
            f"{number(peak_val)} / {number(min_val)}",
            f"Đỉnh {peak_date}  |  Đáy {min_date}",
            BLUE,
        )
        self.values[3].set_value(cohort_text, f"{len(history)} tuần  •  {fc_note}", TEAL if product.has_forecast else AMBER)

        ticks = [format_short_date(d) if d else f"T{i + 1}" for i, d in enumerate(dates)]
        self.chart.set_data(history, ticks=ticks)

        recent_pairs = list(zip(dates[-10:], history[-10:]))
        recent_pairs.reverse()
        table_rows = [
            (w or "—", product.sku, product.name, f"{number(val)} đv")
            for w, val in recent_pairs
        ]
        set_rows(self.details, table_rows)

    def _on_error(self, message: str) -> None:
        if self.chart_card.subtitle is not None:
            self.chart_card.subtitle.setText(
                f"Không thể tải lịch sử nhu cầu: {_safe_error_text(message)}"
            )

    def cleanup(self) -> None:
        self._coordinator.invalidate()


class ForecastPage(QWidget):
    use_in_inventory = pyqtSignal(str, str, str, float)
    sku_selected = pyqtSignal(str)

    def __init__(self, repo: RetailRepository, parent: QWidget | None = None):
        super().__init__(parent)
        self.repo = repo
        self._coordinator = RequestCoordinator(self)
        self._needs_refresh = True
        self.result: Forecast | None = None

        content, layout, _ = page(
            TITLES[2],
            f"So sánh 5 mô hình dự báo trên 8 tuần hậu mốc origin {FORECAST_ORIGIN} (không rò rỉ dữ liệu tương lai).",
        )
        filters = Card()
        controls = row(12)
        self.sku = SkuSelector()
        self.target_week = QComboBox()
        _populate_week_combo(self.target_week, DEFAULT_FORECAST_WEEKS)

        self.model = QComboBox()
        for model_id in MODEL_IDS:
            self.model.addItem(MODEL_LABELS.get(model_id, model_id), model_id)
        self.model.setMinimumContentsLength(18)
        self.model.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)

        self.history_window = QComboBox()
        for text, count in (
            ("8 tuần trước origin", 8),
            ("12 tuần trước origin", 12),
            ("26 tuần trước origin", 26),
            ("Tất cả trước origin", None),
        ):
            self.history_window.addItem(text, count)
        self.history_window.setCurrentIndex(1)

        self.run_button = QPushButton("Chạy dự báo")
        controls.addLayout(field("Sản phẩm (SKU)", self.sku), 3)
        controls.addLayout(field("Tuần mục tiêu", self.target_week), 2)
        controls.addLayout(field("Mô hình dự báo", self.model), 2)
        controls.addLayout(field("Lịch sử nền", self.history_window), 2)
        controls.addWidget(self.run_button, 0, Qt.AlignmentFlag.AlignBottom)
        filters.body.addLayout(controls)

        self.status_banner = label("", 13, SUB, True)
        self.status_banner.hide()
        filters.body.addWidget(self.status_banner)
        layout.addWidget(filters)

        metric_row, self.values = metrics(
            ("Nhu cầu dự báo", f"Baseline ≤ {FORECAST_ORIGIN}", "Sai số Holdout MAE", "Thực tế & Khoảng 90%")
        )
        layout.addLayout(metric_row)

        self.chart_card = Card("Lịch sử tiền origin & Đường chân trời dự báo 8 tuần", "Chọn SKU và mô hình để chạy dự báo")
        self.chart = DemandChart(())
        self.chart.setMinimumHeight(235)
        self.chart_card.body.addWidget(self.chart, 1)
        self.legend_lbl = label(
            f"━━  Thực tế (≤ {FORECAST_ORIGIN})     ┄┄  Dự báo 8 tuần     ▒  Khoảng tin cậy 90%",
            12,
            SUB,
        )
        self.legend_lbl.setWordWrap(False)
        self.chart_card.body.addWidget(self.legend_lbl, 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.chart_card, 1)

        next_card = Card()
        next_row = row()
        info = QVBoxLayout()
        info.addWidget(label("Chuyển sang kiểm tra mức tồn kho", 16, bold=True))
        self.next_description = label("Chạy dự báo trước khi chuyển sang kiểm tra tồn kho.", 13, SUB)
        info.addWidget(self.next_description)
        self.to_stock = QPushButton("Dùng cho Kiểm tra tồn kho  →")
        self.to_stock.setEnabled(False)
        self.to_stock.clicked.connect(self._emit_use_in_inventory)
        next_row.addLayout(info, 1)
        next_row.addWidget(self.to_stock)
        next_card.body.addLayout(next_row)
        layout.addWidget(next_card)

        self.run_button.clicked.connect(self.run)
        self.sku.sku_changed.connect(self._on_sku_changed)
        self.target_week.currentIndexChanged.connect(self.run)
        self.model.currentIndexChanged.connect(self.run)
        self.history_window.currentIndexChanged.connect(self.run)
        wrap_page(self, content)

    def _on_sku_changed(self, sku_id: str) -> None:
        self.sku_selected.emit(sku_id)
        self.run()

    def set_skus(self, skus: Sequence[SkuSummary]) -> None:
        self.sku.set_skus(skus)
        self._needs_refresh = True

    def set_weeks(self, weeks: Sequence[str]) -> None:
        _populate_week_combo(self.target_week, weeks)

    def sync_sku(self, sku_id: str) -> None:
        if self.sku.set_sku(sku_id, emit=False):
            self._needs_refresh = True

    def refresh(self) -> None:
        self.run()

    def run(self) -> None:
        sku_id = self.sku.current_sku()
        if not sku_id:
            return
        self._needs_refresh = False
        model_id = str(self.model.currentData(Qt.ItemDataRole.UserRole) or MODEL_IDS[0])
        target_week = str(self.target_week.currentData(Qt.ItemDataRole.UserRole) or DEFAULT_FORECAST_WEEKS[0])
        hist_window = self.history_window.currentData(Qt.ItemDataRole.UserRole)

        self._coordinator.invalidate()
        self.result = None
        self.to_stock.setEnabled(False)
        if self.chart_card.subtitle is not None:
            self.chart_card.subtitle.setText(f"Đang tải dự báo {sku_id} ({MODEL_LABELS.get(model_id, model_id)})...")

        def task() -> tuple[Product | None, Forecast | None, Any]:
            product = self.repo.get_product(sku_id, periods=None)
            forecast = self.repo.get_forecast(sku_id, model_id, target_week=target_week)
            return product, forecast, hist_window

        self._coordinator.submit(
            task,
            on_finished=self._apply_forecast,
            on_error=self._on_error,
        )

    def _apply_forecast(self, payload: tuple[Product | None, Forecast | None, Any]) -> None:
        product, result, hist_window = payload
        pre_pairs: list[tuple[str, float | int]] = []
        if product is not None:
            pre_pairs = [
                (w, h)
                for w, h in zip(product.week_dates, product.history)
                if w and w <= FORECAST_ORIGIN
            ]
            if hist_window is not None and len(pre_pairs) > int(hist_window):
                pre_pairs = pre_pairs[-int(hist_window):]

        pre_history = [h for _, h in pre_pairs]
        pre_ticks = [format_short_date(w) for w, _ in pre_pairs]

        if result is None:
            self.result = None
            sku_id = product.sku if product is not None else self.sku.current_sku()
            sku_name = product.name if product is not None else sku_id
            self.status_banner.setText("SKU chưa có dự báo — chỉ có lịch sử")
            self.status_banner.setStyleSheet(_banner_style("#FDF3EB", AMBER, "#E8C4A8"))
            self.status_banner.show()

            self.values[0].set_value("—", "Không có bản ghi dự báo", SUB)
            if pre_pairs:
                self.values[1].set_value(f"{number(pre_pairs[-1][1])} đv", f"Tuần {pre_pairs[-1][0]}")
            else:
                self.values[1].set_value("—", f"Chưa có dữ liệu ≤ {FORECAST_ORIGIN}")
            self.values[2].set_value("N/A", "Không thuộc tập dự báo")
            self.values[3].set_value("N/A", "Khoảng 90%: Không áp dụng")

            self.chart.set_data(pre_history, ticks=pre_ticks)
            if self.chart_card.subtitle is not None:
                self.chart_card.subtitle.setText(f"SKU {sku_id}  —  {sku_name}  |  Chỉ có lịch sử tiền origin")
            self.legend_lbl.setText(f"━━  Thực tế (≤ {FORECAST_ORIGIN})")
            self.next_description.setText("SKU này chỉ có dữ liệu lịch sử, chưa có dự báo để kiểm tra tồn kho.")
            self.to_stock.setEnabled(False)
            return

        self.result = result
        model_label = MODEL_LABELS.get(result.model, result.model)
        strategy_text = f"  |  Chiến lược: {result.strategy}" if result.strategy else ""
        self.status_banner.setText(f"{result.note}{strategy_text}")
        self.status_banner.setStyleSheet(_banner_style("#EAF1FF", BLUE, "#BDD2FF"))
        self.status_banner.show()

        self.values[0].set_value(
            f"{number(result.quantity)} đv",
            f"Tuần {result.target_week} (h={result.horizon_step})",
            BLUE,
        )

        if result.prev_week_demand is not None:
            prev_val = to_float(result.prev_week_demand)
            qty_val = to_float(result.quantity)
            if prev_val > 0:
                delta_pct = (qty_val - prev_val) / prev_val * 100.0
                sign = "+" if delta_pct >= 0 else ""
                delta_note = f"Tuần {result.prev_week_label} ({sign}{decimal(delta_pct, 1)}%)"
            else:
                delta_note = f"Tuần {result.prev_week_label}"
            self.values[1].set_value(f"{number(result.prev_week_demand)} đv", delta_note, TEAL)
        else:
            self.values[1].set_value("—", f"Chưa có dữ liệu ≤ {FORECAST_ORIGIN}")

        mae_text = f"{decimal(result.mae, 2)} đv" if result.mae is not None else "N/A"
        self.values[2].set_value(mae_text, f"{model_label}  |  Holdout")

        actual_text = f"{number(result.actual_demand)} đv" if result.actual_demand is not None else "N/A"
        if result.lower_bound_90 is not None and result.upper_bound_90 is not None:
            band_text = f"Khoảng 90%: [{number(result.lower_bound_90)} ; {number(result.upper_bound_90)}]"
        else:
            band_text = "Khoảng 90%: Chỉ có ở CatBoost (MAE)"
        self.values[3].set_value(actual_text, band_text)

        has_band = any(lo is not None and hi is not None for lo, hi in zip(result.horizon_lowers, result.horizon_uppers))
        fc_ticks = [
            format_short_date(w) if len(w) == 10 else w
            for w in result.horizon_ticks
        ]
        self.chart.set_data(
            pre_history,
            ticks=pre_ticks,
            forecast_series=result.horizon_series or (result.quantity,),
            forecast_ticks=fc_ticks,
            lower_bounds=result.horizon_lowers if has_band else None,
            upper_bounds=result.horizon_uppers if has_band else None,
            selected_forecast_index=max(0, result.horizon_step - 1),
        )
        sku_name = product.name if product is not None else result.sku
        if self.chart_card.subtitle is not None:
            self.chart_card.subtitle.setText(
                f"SKU {result.sku} — {sku_name}  |  {model_label}  |  Mục tiêu {result.target_week}"
            )
        self.legend_lbl.setText(
            f"━━  Thực tế (≤ {FORECAST_ORIGIN})     ┄┄  Dự báo 8 tuần"
            + ("     ▒  Khoảng tin cậy 90%" if has_band else "")
        )
        self.next_description.setText(
            f"Dùng dự báo {number(result.quantity)} đv ({model_label}, tuần {result.target_week}) để đối chiếu tồn kho."
        )
        self.to_stock.setEnabled(True)

    def _emit_use_in_inventory(self) -> None:
        if self.result is None:
            return
        self.use_in_inventory.emit(
            self.result.sku,
            self.result.target_week,
            self.result.model,
            float(to_float(self.result.quantity)),
        )

    def _on_error(self, message: str) -> None:
        safe_msg = _safe_error_text(message)
        self.result = None
        self.to_stock.setEnabled(False)
        if self.chart_card.subtitle is not None:
            self.chart_card.subtitle.setText("Không thể tải dữ liệu dự báo")
        self.status_banner.setText(f"Không thể tải dự báo: {safe_msg}")
        self.status_banner.setStyleSheet(_banner_style("#FDF0ED", DANGER, "#F2C0B8"))
        self.status_banner.show()

    def cleanup(self) -> None:
        self._coordinator.invalidate()


class InventoryPage(QWidget):
    sku_selected = pyqtSignal(str)

    def __init__(
        self,
        repo: RetailRepository,
        user: AuthUser | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.repo = repo
        self.current_user = user
        self.model_name = MODEL_IDS[0]
        self._load_coordinator = RequestCoordinator(self)
        self._save_coordinator = RequestCoordinator(self)
        self._needs_refresh = True
        self._current_snapshot: dict[str, Any] = {}
        self._pending_forecast_override: tuple[str, str, str, float] | None = None
        self.review = StockReview(0.0, 0, 0.0)

        content, layout, _ = page(
            TITLES[3],
            "Đối chiếu tồn hiện tại với nhu cầu dự báo, ngưỡng dự phòng (Decimal) và lưu quyết định xuống MySQL.",
        )

        filters = Card()
        controls = row(12)
        self.sku = SkuSelector()
        self.target_week = QComboBox()
        _populate_week_combo(self.target_week, DEFAULT_FORECAST_WEEKS)

        self.forecast_qty = QDoubleSpinBox()
        self.forecast_qty.setDecimals(2)
        self.forecast_qty.setRange(0.0, 1_000_000.0)
        self.forecast_qty.setSingleStep(1.0)

        self.stock = QSpinBox()
        self.stock.setRange(0, 1_000_000)

        self.buffer = QDoubleSpinBox()
        self.buffer.setDecimals(2)
        self.buffer.setSingleStep(0.5)
        self.buffer.setRange(0.0, 1_000_000.0)

        self.check_button = QPushButton("Kiểm tra")
        self.check_button.setObjectName("secondary")

        controls.addLayout(field("Sản phẩm (SKU)", self.sku), 3)
        controls.addLayout(field("Tuần mục tiêu", self.target_week), 2)
        controls.addLayout(field("Dự báo (đv)", self.forecast_qty), 2)
        controls.addLayout(field("Tồn hiện tại (đv)", self.stock), 2)
        controls.addLayout(field("Dự phòng (đv)", self.buffer), 2)
        controls.addWidget(self.check_button, 0, Qt.AlignmentFlag.AlignBottom)
        filters.body.addLayout(controls)

        save_row = row(12)
        self.note_input = QLineEdit()
        self.note_input.setMaxLength(255)
        self.note_input.setPlaceholderText("Ghi chú điều chỉnh tồn kho (tuỳ chọn, tối đa 255 ký tự)...")
        self.save_button = QPushButton("Lưu xuống MySQL")
        save_row.addWidget(self.note_input, 1)
        save_row.addWidget(self.save_button, 0)
        filters.body.addLayout(save_row)

        self.save_status = label("", 13, SUB, True)
        self.save_status.hide()
        filters.body.addWidget(self.save_status)
        layout.addWidget(filters)

        metric_row, self.values = metrics(
            ("Mức cần chuẩn bị", "Thiếu hụt & Đề xuất đặt", "Độ bao phủ tồn kho", "Thực tế & Khoảng 90%")
        )
        layout.addLayout(metric_row)

        charts = row()
        self.chart_card = Card("Tồn hiện tại và mức cần chuẩn bị", "Chọn SKU và tuần để kiểm tra")
        self.chart = InventoryChart()
        self.chart_card.body.addWidget(self.chart, 1)
        legend = row(18)
        legend.addWidget(label("■  Tồn hiện tại", 12, TEAL))
        legend.addWidget(label("■  Nhu cầu dự báo", 12, BLUE))
        legend.addWidget(label("■  Dự phòng", 12, "#7892BB"))
        legend.addStretch()
        self.chart_card.body.addLayout(legend)
        charts.addWidget(self.chart_card, 2)

        result_card = Card("Trạng thái tồn kho (3 mức)")
        self.flag_pill = label("ADEQUATE", 12, TEAL, True)
        self.flag_pill.setWordWrap(False)
        self.shortage_hero = label("0", 46, TEAL, True)
        self.unit_lbl = label("", 15, INK, True)
        self.coverage_lbl = label("", 13, SUB)
        result_card.body.addWidget(self.flag_pill, 0, Qt.AlignmentFlag.AlignLeft)
        result_card.body.addSpacing(6)
        result_card.body.addWidget(self.shortage_hero)
        result_card.body.addWidget(self.unit_lbl)
        result_card.body.addWidget(self.coverage_lbl)
        result_card.body.addStretch()
        charts.addWidget(result_card, 1)
        layout.addLayout(charts, 1)

        audit_card = Card("Lịch sử điều chỉnh tồn kho (Audit Log)", "20 bản ghi gần nhất cho SKU đang chọn")
        self.audit_table = table(
            ("Thời gian", "Tuần", "Mô hình", "Tồn cũ → mới", "Dự phòng cũ → mới", "Cờ trạng thái", "Đặt thêm", "Người sửa", "Ghi chú"),
            (),
            stretch_column=8,
        )
        audit_card.body.addWidget(self.audit_table)
        layout.addWidget(audit_card)

        self.sku.sku_changed.connect(self._on_sku_changed)
        self.target_week.currentIndexChanged.connect(self.load_snapshot)
        self.check_button.clicked.connect(self.check)
        self.forecast_qty.valueChanged.connect(self.check)
        self.stock.valueChanged.connect(self.check)
        self.buffer.valueChanged.connect(self.check)
        self.save_button.clicked.connect(self.save_decision)
        wrap_page(self, content)
        self._refresh_save_availability()

    def set_user(self, user: AuthUser | None) -> None:
        self.current_user = user
        self._refresh_save_availability()

    def _current_role(self) -> str:
        return self.current_user.role.strip().lower() if self.current_user is not None else ""

    def set_skus(self, skus: Sequence[SkuSummary]) -> None:
        self.sku.set_skus(skus)
        self._needs_refresh = True

    def set_weeks(self, weeks: Sequence[str]) -> None:
        _populate_week_combo(self.target_week, weeks)

    def sync_sku(self, sku_id: str) -> None:
        if self.sku.set_sku(sku_id, emit=False):
            self._needs_refresh = True

    def _on_sku_changed(self, sku_id: str) -> None:
        self.sku_selected.emit(sku_id)
        self.load_snapshot()

    def apply_forecast(self, sku_id: str, target_week: str, model_id: str, quantity: float) -> None:
        self.model_name = model_id or MODEL_IDS[0]
        self._pending_forecast_override = (sku_id, target_week, self.model_name, max(0.0, to_float(quantity)))
        self.sku.set_sku(sku_id, emit=False)
        idx = self.target_week.findData(target_week, Qt.ItemDataRole.UserRole)
        if idx >= 0:
            self.target_week.blockSignals(True)
            self.target_week.setCurrentIndex(idx)
            self.target_week.blockSignals(False)
        self.load_snapshot()

    def use_forecast(self, result: Forecast | None) -> None:
        if result is None:
            return
        self.apply_forecast(result.sku, result.target_week, result.model, to_float(result.quantity))

    def refresh(self) -> None:
        self.load_snapshot()

    def load_snapshot(self) -> None:
        sku_id = self.sku.current_sku()
        if not sku_id:
            return
        self._needs_refresh = False
        week_str = str(self.target_week.currentData(Qt.ItemDataRole.UserRole) or DEFAULT_FORECAST_WEEKS[0])
        override = self._pending_forecast_override
        model_id = self.model_name
        if override and (override[0] != sku_id or override[1] != week_str):
            override = None
            self._pending_forecast_override = None

        self._load_coordinator.invalidate()
        if self.chart_card.subtitle is not None:
            self.chart_card.subtitle.setText(f"Đang tải tồn kho SKU {sku_id} tuần {week_str}...")

        def task() -> tuple[dict[str, Any], list[dict[str, Any]], Forecast | None]:
            snapshot = self.repo.get_inventory_snapshot(sku_id, target_week=week_str)
            audits = self.repo.get_audit_history(sku_id, limit=20)
            fc = None if override is not None else self.repo.get_forecast(sku_id, model_id, target_week=week_str)
            return snapshot, audits, fc

        self._load_coordinator.submit(
            task,
            on_finished=lambda payload: self._apply_snapshot(payload, override),
            on_error=self._on_load_error,
        )

    def _apply_snapshot(
        self,
        payload: tuple[dict[str, Any], list[dict[str, Any]], Forecast | None],
        override: tuple[str, str, str, float] | None,
    ) -> None:
        snapshot, audits, fc = payload
        self._current_snapshot = snapshot
        self._pending_forecast_override = None

        found = bool(snapshot.get("found"))
        if override is not None:
            fc_val = override[3]
            self.model_name = override[2]
        elif fc is not None:
            fc_val = to_float(fc.quantity)
        elif found:
            fc_val = to_float(snapshot.get("predicted_demand_catboost"))
        else:
            fc_val = 0.0

        stock_val = to_int(snapshot.get("simulated_current_stock")) if found else 0
        buf_val = to_float(snapshot.get("safety_buffer")) if found else 0.0

        for widget in (self.forecast_qty, self.stock, self.buffer):
            widget.blockSignals(True)
        self.forecast_qty.setValue(max(0.0, fc_val))
        self.stock.setValue(max(0, stock_val))
        self.buffer.setValue(max(0.0, buf_val))
        for widget in (self.forecast_qty, self.stock, self.buffer):
            widget.blockSignals(False)

        self._populate_audit_table(audits)
        self._refresh_save_availability()
        if not found:
            self._show_status(
                "SKU chưa có bản ghi trong bảng quyết định tồn kho — chỉ mô phỏng cục bộ.",
                "#FDF3EB",
                AMBER,
                "#E8C4A8",
            )
        elif not self.repo.is_mysql_available:
            self._show_status(
                "Đang ở chế độ Offline fallback — có thể mô phỏng cục bộ, không thể lưu xuống MySQL.",
                "#FDF3EB",
                AMBER,
                "#E8C4A8",
            )
        elif self._current_role() not in ALLOWED_SAVE_ROLES:
            self._show_status(
                READ_ONLY_SAVE_TOOLTIP,
                "#FDF3EB",
                AMBER,
                "#E8C4A8",
            )
        else:
            self.save_status.hide()
        self.check()

    def check(self) -> None:
        sku_id = self.sku.current_sku()
        week_str = str(self.target_week.currentData(Qt.ItemDataRole.UserRole) or DEFAULT_FORECAST_WEEKS[0])
        review = StockReview(
            forecast=self.forecast_qty.value(),
            current=self.stock.value(),
            buffer=self.buffer.value(),
        )
        self.review = review

        self.values[0].set_value(
            f"{number(review.requirement)} đv",
            f"{number(review.forecast)} dự báo + {number(review.buffer)} dự phòng",
            BLUE,
        )
        self.values[1].set_value(
            f"{number(review.shortage)} đv",
            f"Đề xuất đặt thêm: {number(review.suggested_order_qty)} đv",
            AMBER if review.shortage > 0 else TEAL,
        )
        cov_text = f"{decimal(review.coverage, 1)}%" if review.coverage is not None else "—"
        self.values[2].set_value(cov_text, f"Tồn hiện tại: {number(review.current)} đv")

        actual = self._current_snapshot.get("actual_demand")
        actual_text = f"{number(actual)} đv" if actual is not None else "N/A"
        if self._current_snapshot.get("found"):
            lo = self._current_snapshot.get("lower_bound_90")
            hi = self._current_snapshot.get("upper_bound_90")
            bounds_note = f"Khoảng 90%: [{number(lo)} ; {number(hi)}]"
        else:
            bounds_note = "Khoảng 90%: Chưa có"
        self.values[3].set_value(actual_text, bounds_note)

        self.chart.set_data(review)
        model_label = MODEL_LABELS.get(self.model_name, self.model_name)
        if self.chart_card.subtitle is not None:
            self.chart_card.subtitle.setText(f"SKU {sku_id}  •  Tuần {week_str}  |  {model_label}")

        flag = review.attention_flag
        self.flag_pill.setText(flag)
        if flag == "SHORTAGE RISK":
            self.flag_pill.setStyleSheet(_pill_style("#FDF0ED", DANGER, "#F2C0B8"))
            hero_color = DANGER
            self.shortage_hero.setText(number(review.shortage))
            self.unit_lbl.setText(f"đv thiếu  •  Đề xuất đặt: {number(review.suggested_order_qty)} đv")
        elif flag == "EXCESS STOCK":
            self.flag_pill.setStyleSheet(_pill_style("#EAF1FF", BLUE, "#BDD2FF"))
            hero_color = BLUE
            excess = max(0.0, round(review.current - review.requirement, 2))
            self.shortage_hero.setText(number(excess))
            self.unit_lbl.setText("đv vượt mức cần chuẩn bị (>2,5×)")
        else:
            self.flag_pill.setStyleSheet(_pill_style("#E6F4F2", TEAL, "#A7DDD7"))
            hero_color = TEAL
            self.shortage_hero.setText(number(review.shortage))
            self.unit_lbl.setText(
                f"đv thiếu  •  Đề xuất đặt: {number(review.suggested_order_qty)} đv"
                if review.shortage > 0
                else "đv thiếu (đạt ngưỡng an toàn)"
            )

        self.shortage_hero.setStyleSheet(
            f"font-size: 46px; font-weight: 700; color: {hero_color}; background: transparent; border: none;"
        )
        self.coverage_lbl.setText(
            f"Tồn hiện tại đáp ứng {decimal(review.coverage, 1)}% mức cần chuẩn bị ({number(review.requirement)} đv)."
            if review.coverage is not None
            else "Mức cần chuẩn bị bằng 0 đv."
        )

    def _populate_audit_table(self, audits: Sequence[dict[str, Any]]) -> None:
        rows = []
        for item in audits[:20]:
            rows.append(
                (
                    item.get("updated_at") or "—",
                    item.get("forecast_week_start") or "—",
                    MODEL_LABELS.get(str(item.get("model_id")), str(item.get("model_id") or "—")),
                    f"{number(item.get('old_stock'))} → {number(item.get('new_stock'))}",
                    f"{number(item.get('old_buffer'))} → {number(item.get('new_buffer'))}",
                    item.get("attention_flag") or "—",
                    number(item.get("suggested_order_qty")),
                    item.get("updated_by") or "—",
                    item.get("note") or "—",
                )
            )
        set_rows(self.audit_table, rows)

    def _refresh_save_availability(self) -> None:
        role = self._current_role()
        has_role = role in ALLOWED_SAVE_ROLES
        has_snapshot = bool(self._current_snapshot.get("found"))
        can_save = self.repo.is_mysql_available and has_snapshot and has_role
        self.save_button.setEnabled(can_save)
        if not has_role:
            self.save_button.setToolTip(READ_ONLY_SAVE_TOOLTIP)
        elif not self.repo.is_mysql_available:
            self.save_button.setToolTip(
                "Đang ở chế độ Offline fallback — không thể lưu xuống MySQL"
            )
        elif not has_snapshot:
            self.save_button.setToolTip(
                "SKU hoặc tuần mục tiêu chưa có bản ghi trong bảng quyết định tồn kho"
            )
        else:
            self.save_button.setToolTip("Lưu quyết định tồn kho xuống MySQL và ghi Audit Log")

    def _show_status(self, text: str, bg: str, fg: str, border: str) -> None:
        self.save_status.setText(text)
        self.save_status.setStyleSheet(_banner_style(bg, fg, border))
        self.save_status.show()

    def save_decision(self) -> None:
        role = self._current_role()
        if role not in ALLOWED_SAVE_ROLES:
            self._refresh_save_availability()
            self._show_status(READ_ONLY_SAVE_TOOLTIP, "#FDF3EB", AMBER, "#E8C4A8")
            return

        sku_id = self.sku.current_sku()
        week_str = str(self.target_week.currentData(Qt.ItemDataRole.UserRole) or DEFAULT_FORECAST_WEEKS[0])
        if not sku_id or not self.repo.is_mysql_available or not self._current_snapshot.get("found"):
            self._refresh_save_availability()
            return

        new_stock = self.stock.value()
        new_buffer = round(self.buffer.value(), 2)
        forecast_qty = round(self.forecast_qty.value(), 4)
        note = self.note_input.text().strip()
        actor = self.current_user.username if self.current_user is not None else "planner"

        self._save_coordinator.invalidate()
        self.save_button.setEnabled(False)
        self.save_button.setText("Đang lưu...")

        def task() -> tuple[dict[str, Any], list[dict[str, Any]]]:
            save_kwargs: dict[str, Any] = {
                "sku_id": sku_id,
                "forecast_week_start": week_str,
                "new_stock": new_stock,
                "new_buffer": new_buffer,
                "forecast_qty": forecast_qty,
                "model_id": self.model_name,
                "updated_by": actor,
                "note": note,
            }
            sig = inspect.signature(self.repo.save_inventory_decision)
            if "user_role" in sig.parameters or any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            ):
                save_kwargs["user_role"] = role
            res = self.repo.save_inventory_decision(**save_kwargs)
            audits = self.repo.get_audit_history(sku_id, limit=20) if res.get("ok") else []
            return res, audits

        self._save_coordinator.submit(
            task,
            on_finished=self._on_save_finished,
            on_error=self._on_save_error,
        )

    def _on_save_finished(self, payload: tuple[dict[str, Any], list[dict[str, Any]]]) -> None:
        res, audits = payload
        self.save_button.setText("Lưu xuống MySQL")
        self._refresh_save_availability()
        if res.get("ok"):
            self._current_snapshot["simulated_current_stock"] = res.get("new_stock", self.stock.value())
            self._current_snapshot["safety_buffer"] = res.get("new_buffer", self.buffer.value())
            self.note_input.clear()
            self._populate_audit_table(audits)
            self._show_status(
                f"Đã lưu thành công (Audit #{res.get('audit_id')})  •  Cờ: {res.get('attention_flag')}  •  Đề xuất đặt: {number(res.get('suggested_order_qty'))} đv.",
                "#E6F4F2",
                TEAL,
                "#A7DDD7",
            )
        else:
            self._show_status(
                f"Không thể lưu xuống MySQL: {res.get('error', 'Lỗi không xác định')}",
                "#FDF0ED",
                DANGER,
                "#F2C0B8",
            )

    def _on_save_error(self, message: str) -> None:
        self.save_button.setText("Lưu xuống MySQL")
        self._refresh_save_availability()
        self._show_status(
            f"Không thể lưu quyết định tồn kho: {_safe_error_text(message)}",
            "#FDF0ED",
            DANGER,
            "#F2C0B8",
        )

    def _on_load_error(self, message: str) -> None:
        safe_msg = _safe_error_text(message)
        if self.chart_card.subtitle is not None:
            self.chart_card.subtitle.setText(f"Không thể tải tồn kho: {safe_msg}")
        self._refresh_save_availability()
        self._show_status(f"Không thể tải dữ liệu tồn kho: {safe_msg}", "#FDF0ED", DANGER, "#F2C0B8")

    def cleanup(self) -> None:
        self._load_coordinator.invalidate()
        self._save_coordinator.invalidate()


class Dashboard(QWidget):
    logged_out = pyqtSignal()

    def __init__(self, repo: RetailRepository, user: AuthUser | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = user
        self._catalog_coordinator = RequestCoordinator(self)
        self._conn_coordinator = RequestCoordinator(self)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(224)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(12, 26, 12, 24)
        side.setSpacing(8)
        side.addWidget(label("↗  Kế hoạch bán lẻ", 19, "#FFFFFF", True))
        side.addWidget(label("     Dự báo theo SKU", 12, "#BAC9DC"))
        side.addSpacing(30)

        self.navigation = QButtonGroup(self)
        self.navigation.setExclusive(True)
        for index, title in enumerate(TITLES):
            button = QPushButton(title)
            button.setObjectName("nav")
            button.setCheckable(True)
            self.navigation.addButton(button, index)
            side.addWidget(button)

        side.addStretch()
        side.addWidget(label("MÔ HÌNH HỌC MÁY", 11, "#BAC9DC", True))
        side.addWidget(label("DỰ BÁO NHU CẦU", 11, "#BAC9DC", True))
        root.addWidget(sidebar)

        right = QVBoxLayout()
        right.setSpacing(0)
        top = QFrame()
        top.setObjectName("topbar")
        top.setFixedHeight(61)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(28, 0, 28, 0)
        top_layout.setSpacing(10)

        self.breadcrumb = label("", 14, SUB)
        self.breadcrumb.setWordWrap(False)
        top_layout.addWidget(self.breadcrumb, 1)

        self.db_badge = label("", 12, TEAL, True)
        self.db_badge.setWordWrap(False)
        top_layout.addWidget(self.db_badge)

        self.reconnect_btn = QPushButton("Kiểm tra DB")
        self.reconnect_btn.setObjectName("secondary")
        self.reconnect_btn.clicked.connect(self.check_db_connection)
        top_layout.addWidget(self.reconnect_btn)

        self.user_badge = label("", 13, INK, True)
        self.user_badge.setWordWrap(False)
        top_layout.addWidget(self.user_badge)

        self.logout_btn = QPushButton("Đăng xuất")
        self.logout_btn.setObjectName("secondary")
        self.logout_btn.clicked.connect(self._handle_logout)
        top_layout.addWidget(self.logout_btn)
        right.addWidget(top)

        self.pages = QStackedWidget()
        self.overview = Overview(repo)
        self.history = HistoryPage(repo)
        self.forecast = ForecastPage(repo)
        self.inventory = InventoryPage(repo, user=user)
        for widget in (self.overview, self.history, self.forecast, self.inventory):
            self.pages.addWidget(widget)
        right.addWidget(self.pages, 1)
        root.addLayout(right, 1)

        self.navigation.idClicked.connect(self.navigate)
        self.history.sku_selected.connect(lambda sku: self._sync_sku_across_tabs(sku, self.history))
        self.forecast.sku_selected.connect(lambda sku: self._sync_sku_across_tabs(sku, self.forecast))
        self.inventory.sku_selected.connect(lambda sku: self._sync_sku_across_tabs(sku, self.inventory))
        self.forecast.use_in_inventory.connect(self._open_inventory_with_forecast)

        self.set_user(user)
        self.update_connection_badge(self.repo.is_mysql_available)
        self.navigate(0)
        self._load_shared_catalog()

    def set_user(self, user: AuthUser | None) -> None:
        self.current_user = user
        self.inventory.set_user(user)
        if user is None:
            self.user_badge.setText("Khách")
        else:
            self.user_badge.setText(f"{user.full_name} ({user.role})")

    def update_connection_badge(self, is_mysql: bool) -> None:
        _apply_db_badge(self.db_badge, is_mysql)
        _apply_db_badge(self.overview.mode_badge, is_mysql)
        self.inventory._refresh_save_availability()

    def check_db_connection(self) -> None:
        self._conn_coordinator.invalidate()
        self.reconnect_btn.setEnabled(False)
        self.reconnect_btn.setText("Đang kiểm tra...")
        self._conn_coordinator.submit(
            self.repo.check_connection,
            on_finished=self._on_db_checked,
            on_error=lambda _msg: self._on_db_checked((False, "Không thể kiểm tra kết nối MySQL.")),
        )

    def _on_db_checked(self, payload: tuple[bool, str]) -> None:
        is_mysql, _ = payload
        self.reconnect_btn.setEnabled(True)
        self.reconnect_btn.setText("Kiểm tra DB")
        self.update_connection_badge(is_mysql)
        current_widget = self.pages.currentWidget()
        if hasattr(current_widget, "refresh"):
            current_widget.refresh()

    def _load_shared_catalog(self) -> None:
        self._catalog_coordinator.invalidate()

        def task() -> tuple[list[SkuSummary], tuple[str, ...]]:
            skus = self.repo.list_skus(limit=3000)
            weeks = self.repo.list_forecast_weeks()
            return skus, weeks

        self._catalog_coordinator.submit(
            task,
            on_finished=self._apply_shared_catalog,
            on_error=self._on_catalog_error,
        )

    def _on_catalog_error(self, message: str) -> None:
        safe_msg = _safe_error_text(message)
        if self.history.chart_card.subtitle is not None:
            self.history.chart_card.subtitle.setText(f"Không thể tải danh mục SKU: {safe_msg}")
        if self.forecast.chart_card.subtitle is not None:
            self.forecast.chart_card.subtitle.setText(f"Không thể tải danh mục SKU: {safe_msg}")
        if self.inventory.chart_card.subtitle is not None:
            self.inventory.chart_card.subtitle.setText(f"Không thể tải danh mục SKU: {safe_msg}")

    def _apply_shared_catalog(self, payload: tuple[list[SkuSummary], tuple[str, ...]]) -> None:
        skus, weeks = payload
        for page_widget in (self.history, self.forecast, self.inventory):
            page_widget.set_skus(skus)
        self.forecast.set_weeks(weeks)
        self.inventory.set_weeks(weeks)
        self.update_connection_badge(self.repo.is_mysql_available)

        current = self.pages.currentWidget()
        if current in (self.history, self.forecast, self.inventory):
            current.refresh()

    def _sync_sku_across_tabs(self, sku_id: str, source: QWidget) -> None:
        for page_widget in (self.history, self.forecast, self.inventory):
            if page_widget is not source:
                page_widget.sync_sku(sku_id)

    def _open_inventory_with_forecast(
        self, sku_id: str, target_week: str, model_id: str, quantity: float
    ) -> None:
        self._sync_sku_across_tabs(sku_id, self.inventory)
        self.inventory.apply_forecast(sku_id, target_week, model_id, quantity)
        self.navigate(3, force_refresh=False)

    def focus_sku(
        self,
        sku_id: str,
        tab_index: int | None = None,
        model_id: str | None = None,
        target_week: str | None = None,
    ) -> None:
        for page_widget in (self.history, self.forecast, self.inventory):
            page_widget.sync_sku(sku_id)
        if model_id:
            idx = self.forecast.model.findData(model_id, Qt.ItemDataRole.UserRole)
            if idx >= 0:
                self.forecast.model.blockSignals(True)
                self.forecast.model.setCurrentIndex(idx)
                self.forecast.model.blockSignals(False)
            self.inventory.model_name = model_id
        if target_week:
            for combo in (self.forecast.target_week, self.inventory.target_week):
                idx = combo.findData(target_week, Qt.ItemDataRole.UserRole)
                if idx >= 0:
                    combo.blockSignals(True)
                    combo.setCurrentIndex(idx)
                    combo.blockSignals(False)
        if tab_index is not None:
            self.navigate(tab_index, force_refresh=True)

    def navigate(self, index: int, force_refresh: bool = False) -> None:
        safe_idx = max(0, min(int(index), len(TITLES) - 1))
        self.pages.setCurrentIndex(safe_idx)
        self.navigation.button(safe_idx).setChecked(True)
        self.breadcrumb.setText(f"Hoạch định tồn kho  /  {TITLES[safe_idx]}")
        current = self.pages.widget(safe_idx)
        if force_refresh or getattr(current, "_needs_refresh", False):
            if hasattr(current, "refresh"):
                current.refresh()

    def _handle_logout(self) -> None:
        self.cleanup()
        self.logged_out.emit()

    def cleanup(self) -> None:
        self._catalog_coordinator.invalidate()
        self._conn_coordinator.invalidate()
        self.overview.cleanup()
        self.history.cleanup()
        self.forecast.cleanup()
        self.inventory.cleanup()
