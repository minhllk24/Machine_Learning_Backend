"""Các thành phần Qt dùng chung cho các màn hình."""
from __future__ import annotations

from decimal import Decimal
import math
from typing import Any, Sequence

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

INK = "#142238"
SUB = "#52657C"
BLUE = "#2256CD"
TEAL = "#05786D"
AMBER = "#8B4817"
DANGER = "#AD352A"
BORDER = "#DFE6EF"


def _to_finite_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
        num = float(value)
        return num if math.isfinite(num) else None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if math.isfinite(num) else None


def _format_vi_grouped(formatted_en: str) -> str:
    """Convert English `1,234.56` grouped text into Vietnamese `1.234,56`."""
    return formatted_en.replace(",", "_").replace(".", ",").replace("_", ".")


def number(value: Any) -> str:
    """Format int/float/Decimal safely in Vietnamese notation; None/NaN -> '—'."""
    if value is None or isinstance(value, bool):
        return "—"
    if isinstance(value, int):
        return f"{value:,}".replace(",", ".")
    if isinstance(value, Decimal):
        if not value.is_finite():
            return "—"
        if value == value.to_integral_value():
            return f"{int(value):,}".replace(",", ".")
    num = _to_finite_float(value)
    if num is None:
        return "—"
    if abs(num - round(num)) < 1e-9:
        return f"{int(round(num)):,}".replace(",", ".")
    precision = 4 if 0 < abs(num) < 0.01 else 2
    text = f"{num:,.{precision}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return _format_vi_grouped(text)


def decimal(value: Any, digits: int = 1) -> str:
    """Format floating/Decimal numbers safely with fixed decimals; None/NaN -> '—'."""
    num = _to_finite_float(value)
    if num is None:
        return "—"
    prec = max(0, int(digits))
    if abs(num) < 0.5 * (10 ** -prec):
        num = 0.0
    return _format_vi_grouped(f"{num:,.{prec}f}")


def format_short_date(iso_date: str) -> str:
    """Format ISO YYYY-MM-DD as DD/MM/YY for compact non-overlapping chart ticks."""
    text = (iso_date or "").strip()[:10]
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return f"{text[8:10]}/{text[5:7]}/{text[2:4]}"
    return text


def _nice_scale(top_value: float, intervals: int = 4) -> tuple[float, float, int]:
    """Compute a readable axis (step, maximum, step_count) for positive or zero data."""
    if not math.isfinite(top_value) or top_value <= 0.0:
        return 1.0, float(intervals), intervals
    raw_step = max(top_value / max(intervals, 1), 1e-6)
    magnitude = 10.0 ** math.floor(math.log10(raw_step))
    step = next(
        (unit * magnitude for unit in (1.0, 2.0, 5.0, 10.0) if unit * magnitude >= raw_step - 1e-12),
        10.0 * magnitude,
    )
    step_count = max(intervals, math.ceil(top_value / step - 1e-12))
    return step, step * step_count, step_count


def label(text: str, size: int = 14, color: str = INK, bold: bool = False) -> QLabel:
    widget = QLabel(text)
    widget.setWordWrap(True)
    widget.setStyleSheet(
        f"background: transparent; color: {color}; font-size: {size}px;"
        f"font-weight: {700 if bold else 400}; border: none;"
    )
    return widget


def row(spacing: int = 16) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    return layout


class Card(QFrame):
    def __init__(self, title: str | None = None, subtitle: str | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(22, 18, 22, 18)
        self.body.setSpacing(8)
        if title:
            self.body.addWidget(label(title, 19, bold=True))
        self.subtitle: QLabel | None = None
        if subtitle:
            self.subtitle = label(subtitle, 13, SUB)
            self.body.addWidget(self.subtitle)


class Metric(Card):
    def __init__(self, title: str):
        super().__init__()
        self.setMinimumHeight(106)
        self.body.setContentsMargins(17, 14, 17, 14)
        self.body.setSpacing(4)
        self.body.addWidget(label(title, 13, SUB))
        self.value = label("", 28, bold=True)
        self.note = label("", 12, SUB)
        self.body.addWidget(self.value)
        self.body.addWidget(self.note)

    def set_value(self, value: str, note: str, color: str = INK) -> None:
        self.value.setText(value)
        self.value.setStyleSheet(
            f"font-size: 28px; font-weight: 700; color: {color};"
            "background: transparent; border: none;"
        )
        self.note.setText(note)


def metrics(titles: Sequence[str]) -> tuple[QHBoxLayout, list[Metric]]:
    layout = row()
    items = [Metric(title) for title in titles]
    for item in items:
        layout.addWidget(item, 1)
    return layout, items


def table(headers: Sequence[str], rows: Sequence[Sequence[Any]], stretch_column: int = 1) -> QTableWidget:
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(list(headers))
    widget.verticalHeader().hide()
    widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    widget.setShowGrid(False)
    widget.setAlternatingRowColors(False)
    widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    widget.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    header = widget.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    if 0 <= stretch_column < len(headers):
        header.setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)
    header.setMinimumSectionSize(84)
    set_rows(widget, rows)
    return widget


def set_rows(widget: QTableWidget, rows: Sequence[Sequence[Any]], max_visible_rows: int = 10) -> None:
    bounded_rows = list(rows[:50])
    widget.setRowCount(len(bounded_rows))
    row_height = 36
    for row_index, values in enumerate(bounded_rows):
        for column, value in enumerate(values):
            widget.setItem(row_index, column, QTableWidgetItem(str(value)))
        widget.setRowHeight(row_index, row_height)

    header_h = max(36, widget.horizontalHeader().sizeHint().height(), widget.horizontalHeader().height())
    visible = min(max(len(bounded_rows), 1), max_visible_rows)
    target_h = header_h + visible * row_height + 4
    min_h = header_h + min(max(len(bounded_rows), 1), 4) * row_height + 4
    widget.setMinimumHeight(min_h)
    widget.setMaximumHeight(target_h)


class DemandChart(QWidget):
    """Đồ thị co giãn theo kích thước thật của widget, vẽ trực tiếp bằng QPainter."""

    def __init__(
        self,
        history: Sequence[Any] = (),
        ticks: Sequence[str] | None = None,
        prediction: Any = None,
        dark: bool = False,
        bars: bool = False,
        forecast_series: Sequence[Any] | None = None,
        forecast_ticks: Sequence[str] | None = None,
        lower_bounds: Sequence[Any] | None = None,
        upper_bounds: Sequence[Any] | None = None,
        selected_forecast_index: int | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.dark = dark
        self.bars = bars
        self.history: tuple[float, ...] = ()
        self.ticks: list[str] = []
        self.prediction: float | None = None
        self.forecast_series: tuple[float, ...] = ()
        self.forecast_ticks: list[str] = []
        self.lower_bounds: tuple[float | None, ...] = ()
        self.upper_bounds: tuple[float | None, ...] = ()
        self.selected_forecast_index: int | None = None
        self.setMinimumHeight(175)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.set_data(
            history,
            ticks=ticks,
            prediction=prediction,
            forecast_series=forecast_series,
            forecast_ticks=forecast_ticks,
            lower_bounds=lower_bounds,
            upper_bounds=upper_bounds,
            selected_forecast_index=selected_forecast_index,
        )

    @staticmethod
    def _clean_series(values: Sequence[Any] | None) -> tuple[float, ...]:
        if not values:
            return ()
        cleaned: list[float] = []
        for item in values:
            num = _to_finite_float(item)
            cleaned.append(num if num is not None else 0.0)
        return tuple(cleaned)

    @staticmethod
    def _clean_bounds(values: Sequence[Any] | None, length: int) -> tuple[float | None, ...]:
        if not values or length <= 0:
            return ()
        padded = list(values[:length]) + [None] * max(0, length - len(values))
        return tuple(_to_finite_float(v) for v in padded)

    def set_data(
        self,
        history: Sequence[Any],
        ticks: Sequence[str] | None = None,
        prediction: Any = None,
        forecast_series: Sequence[Any] | None = None,
        forecast_ticks: Sequence[str] | None = None,
        lower_bounds: Sequence[Any] | None = None,
        upper_bounds: Sequence[Any] | None = None,
        selected_forecast_index: int | None = None,
    ) -> None:
        self.history = self._clean_series(history)
        raw_ticks = list(ticks) if ticks else [f"T{i + 1}" for i in range(len(self.history))]
        if len(raw_ticks) < len(self.history):
            raw_ticks.extend(f"T{i + 1}" for i in range(len(raw_ticks), len(self.history)))
        self.ticks = raw_ticks[: len(self.history)]

        self.prediction = _to_finite_float(prediction)
        self.forecast_series = self._clean_series(forecast_series)
        if self.forecast_series:
            fc_len = len(self.forecast_series)
            raw_fc_ticks = list(forecast_ticks) if forecast_ticks else [f"H{i + 1}" for i in range(fc_len)]
            if len(raw_fc_ticks) < fc_len:
                raw_fc_ticks.extend(f"H{i + 1}" for i in range(len(raw_fc_ticks), fc_len))
            self.forecast_ticks = raw_fc_ticks[:fc_len]
            self.lower_bounds = self._clean_bounds(lower_bounds, fc_len)
            self.upper_bounds = self._clean_bounds(upper_bounds, fc_len)
            if selected_forecast_index is None:
                self.selected_forecast_index = 0
            else:
                self.selected_forecast_index = max(0, min(int(selected_forecast_index), fc_len - 1))
        else:
            self.forecast_ticks = ["Dự báo"] if self.prediction is not None else []
            self.lower_bounds = self._clean_bounds(lower_bounds, 1) if self.prediction is not None else ()
            self.upper_bounds = self._clean_bounds(upper_bounds, 1) if self.prediction is not None else ()
            self.selected_forecast_index = 0 if self.prediction is not None else None
        self.update()

    def _compute_visible_ticks(
        self, all_ticks: list[str], x_fn, plot_width: float, fm: QFontMetrics, highlight_idx: int | None
    ) -> list[int]:
        count = len(all_ticks)
        if count == 0:
            return []
        sample_max_w = max((fm.horizontalAdvance(t) for t in all_ticks if t), default=36) + 14
        max_labels = max(2, int(plot_width // max(sample_max_w, 38)))
        if count <= 10 and count <= max_labels:
            return list(range(count))

        stride = max(1, math.ceil((count - 1) / max(1, max_labels - 1)))
        indices = list(range(0, count, stride))
        if indices[-1] != count - 1:
            if abs(x_fn(count - 1) - x_fn(indices[-1])) >= sample_max_w * 0.85:
                indices.append(count - 1)
            else:
                indices[-1] = count - 1
        if highlight_idx is not None and 0 <= highlight_idx < count and highlight_idx not in indices:
            indices = [
                idx for idx in indices if abs(x_fn(idx) - x_fn(highlight_idx)) >= sample_max_w * 0.8
            ]
            indices.append(highlight_idx)
            indices.sort()
        return indices

    def _draw_callout_pill(
        self, painter: QPainter, anchor_x: float, anchor_y: float, text: str, plot: QRectF, accent: QColor
    ) -> None:
        pill_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(pill_font)
        fm = QFontMetrics(pill_font)
        pill_w = max(44.0, fm.horizontalAdvance(text) + 16.0)
        pill_h = 22.0
        px = min(max(plot.left(), anchor_x - pill_w / 2.0), max(plot.left(), self.width() - pill_w - 8.0))
        py = anchor_y - pill_h - 10.0
        if py < 4.0:
            py = min(plot.bottom() - pill_h - 4.0, anchor_y + 10.0)
        rect = QRectF(px, py, pill_w, pill_h)
        painter.setPen(QPen(accent, 1.2))
        painter.setBrush(QColor("#14243B" if self.dark else "#FFFFFF"))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(accent)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        foreground = QColor("#C1D1E5" if self.dark else SUB)
        grid = QColor("#355171" if self.dark else "#E7EDF4")
        actual_color = QColor("#A5C4FF" if self.dark else BLUE)
        forecast_color = QColor("#82E1CA" if self.dark else TEAL)
        band_fill = QColor(130, 225, 202, 42) if self.dark else QColor(5, 120, 109, 36)
        band_edge = QColor(130, 225, 202, 120) if self.dark else QColor(5, 120, 109, 100)

        axis_font = QFont("Segoe UI", 9)
        painter.setFont(axis_font)
        fm = QFontMetrics(axis_font)
        painter.setPen(foreground)
        painter.drawText(QRectF(4, 2, 180, 20), "Số lượng (đv)")

        fc_points: tuple[float, ...] = ()
        if self.forecast_series:
            fc_points = self.forecast_series
        elif self.prediction is not None:
            fc_points = (self.prediction,)

        all_values = list(self.history) + list(fc_points)
        if not all_values:
            painter.setPen(foreground)
            painter.drawText(
                QRectF(16, 28, max(80, self.width() - 32), max(60, self.height() - 48)),
                Qt.AlignmentFlag.AlignCenter,
                "Chưa có dữ liệu chuỗi thời gian cho lựa chọn hiện tại.",
            )
            painter.end()
            return

        scale_candidates = list(all_values)
        for v in self.upper_bounds:
            if v is not None:
                scale_candidates.append(v)
        top_value = max(scale_candidates, default=0.0)
        step, maximum, step_count = _nice_scale(top_value, intervals=4)

        y_labels = [number(i * step) for i in range(step_count + 1)]
        max_y_width = max((fm.horizontalAdvance(lbl) for lbl in y_labels), default=32)
        left_margin = max(56, max_y_width + 16)
        right_margin = 22
        plot = QRectF(
            left_margin,
            32,
            max(80.0, self.width() - left_margin - right_margin),
            max(70.0, self.height() - 74),
        )

        n_hist = len(self.history)
        n_fc = len(fc_points)
        count = n_hist + n_fc

        def x(index: int) -> float:
            if self.bars:
                return plot.left() + plot.width() * (index + 0.5) / max(count, 1)
            if count <= 1:
                return plot.left() + plot.width() / 2.0
            usable = max(0.0, plot.width() - 24.0)
            return plot.left() + 12.0 + usable * index / (count - 1)

        def y(value: float) -> float:
            safe_val = max(0.0, min(value, maximum))
            return plot.bottom() - (safe_val / maximum) * plot.height()

        if n_fc > 0 and count > 0:
            if n_hist > 0:
                divider = (x(n_hist - 1) + x(n_hist)) / 2.0
            else:
                divider = plot.left()
            painter.fillRect(
                QRectF(divider, plot.top(), plot.right() - divider, plot.height()),
                QColor("#254254" if self.dark else "#EAF1FF"),
            )

        for idx, lbl in enumerate(y_labels):
            ordinate = y(idx * step)
            painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(plot.left(), ordinate), QPointF(plot.right(), ordinate))
            painter.setPen(foreground)
            painter.drawText(
                QRectF(4, ordinate - 10, left_margin - 12, 20),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                lbl,
            )

        if self.bars and n_hist > 0:
            bar_w = min(36.0, plot.width() / max(count, 1) * 0.48)
            for index, value in enumerate(self.history):
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(BLUE if index == n_hist - 1 else "#7892BB"))
                top_y = y(value)
                painter.drawRoundedRect(
                    QRectF(x(index) - bar_w / 2.0, top_y, bar_w, max(0.0, plot.bottom() - top_y)),
                    4,
                    4,
                )
        elif n_hist > 0:
            path = QPainterPath(QPointF(x(0), y(self.history[0])))
            for index, value in enumerate(self.history[1:], 1):
                path.lineTo(x(index), y(value))
            if not self.dark:
                area = QPainterPath(path)
                area.lineTo(x(n_hist - 1), plot.bottom())
                area.lineTo(x(0), plot.bottom())
                area.closeSubpath()
                painter.fillPath(area, QColor("#EDF3FF"))
            painter.setPen(QPen(actual_color, 2.3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            if n_hist <= 36:
                dot_r = 2.5 if n_hist <= 18 else 1.8
                for index, value in enumerate(self.history):
                    painter.setBrush(QColor("#1C3450" if self.dark else "#FFFFFF"))
                    painter.drawEllipse(QPointF(x(index), y(value)), dot_r, dot_r)
            else:
                painter.setBrush(QColor("#1C3450" if self.dark else "#FFFFFF"))
                painter.drawEllipse(QPointF(x(n_hist - 1), y(self.history[-1])), 2.8, 2.8)

        if n_fc > 0:
            valid_band_indices = [
                i
                for i in range(n_fc)
                if i < len(self.lower_bounds)
                and i < len(self.upper_bounds)
                and self.lower_bounds[i] is not None
                and self.upper_bounds[i] is not None
            ]
            if len(valid_band_indices) >= 2:
                upper_pts = [QPointF(x(n_hist + i), y(self.upper_bounds[i])) for i in valid_band_indices]
                lower_pts = [QPointF(x(n_hist + i), y(self.lower_bounds[i])) for i in reversed(valid_band_indices)]
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(band_fill)
                painter.drawPolygon(QPolygonF(upper_pts + lower_pts))
                painter.setPen(QPen(band_edge, 1.0, Qt.PenStyle.DotLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                for seq in (upper_pts, list(reversed(lower_pts))):
                    bpath = QPainterPath(seq[0])
                    for pt in seq[1:]:
                        bpath.lineTo(pt)
                    painter.drawPath(bpath)
            elif len(valid_band_indices) == 1:
                i = valid_band_indices[0]
                cx = x(n_hist + i)
                y_hi = y(self.upper_bounds[i])
                y_lo = y(self.lower_bounds[i])
                painter.setPen(QPen(band_edge, 2.0))
                painter.drawLine(QPointF(cx, y_hi), QPointF(cx, y_lo))
                painter.drawLine(QPointF(cx - 6, y_hi), QPointF(cx + 6, y_hi))
                painter.drawLine(QPointF(cx - 6, y_lo), QPointF(cx + 6, y_lo))

            fc_path = QPainterPath(
                QPointF(x(n_hist - 1), y(self.history[-1]))
                if n_hist > 0
                else QPointF(x(n_hist), y(fc_points[0]))
            )
            start_idx = 0 if n_hist > 0 else 1
            for offset in range(start_idx, n_fc):
                fc_path.lineTo(x(n_hist + offset), y(fc_points[offset]))
            painter.setPen(QPen(forecast_color, 2.4, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(fc_path)

            sel_offset = self.selected_forecast_index if self.selected_forecast_index is not None else 0
            sel_offset = max(0, min(sel_offset, n_fc - 1))
            for offset, val in enumerate(fc_points):
                pt = QPointF(x(n_hist + offset), y(val))
                is_sel = offset == sel_offset
                painter.setPen(QPen(forecast_color, 2.5 if is_sel else 1.8))
                painter.setBrush(QColor("#1C3450" if self.dark else "#FFFFFF"))
                painter.drawEllipse(pt, 4.5 if is_sel else 2.8, 4.5 if is_sel else 2.8)

            sel_val = fc_points[sel_offset]
            self._draw_callout_pill(
                painter,
                x(n_hist + sel_offset),
                y(sel_val),
                number(sel_val),
                plot,
                forecast_color,
            )

        painter.setFont(axis_font)
        all_ticks = list(self.ticks) + list(self.forecast_ticks)
        highlight_idx = (n_hist + self.selected_forecast_index) if (n_fc > 0 and self.selected_forecast_index is not None) else None
        visible_indices = self._compute_visible_ticks(all_ticks, x, plot.width(), fm, highlight_idx)
        for index in visible_indices:
            tick = all_ticks[index]
            is_fc_tick = n_fc > 0 and index >= n_hist
            painter.setPen(forecast_color if is_fc_tick else foreground)
            tick_w = max(54.0, fm.horizontalAdvance(tick) + 8.0)
            tx = min(max(4.0, x(index) - tick_w / 2.0), max(4.0, self.width() - tick_w - 4.0))
            painter.drawText(
                QRectF(tx, plot.bottom() + 9, tick_w, 20),
                Qt.AlignmentFlag.AlignCenter,
                tick,
            )
        painter.end()


class InventoryChart(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.current = 0.0
        self.forecast = 0.0
        self.buffer = 0.0
        self.setMinimumHeight(190)

    def set_data(self, review: Any) -> None:
        if isinstance(review, tuple) and len(review) == 3:
            cur, fc, buf = review
        else:
            cur = getattr(review, "current", 0.0)
            fc = getattr(review, "forecast", 0.0)
            buf = getattr(review, "buffer", 0.0)
        self.current = max(0.0, _to_finite_float(cur) or 0.0)
        self.forecast = max(0.0, _to_finite_float(fc) or 0.0)
        self.buffer = max(0.0, _to_finite_float(buf) or 0.0)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        axis_font = QFont("Segoe UI", 9)
        p.setFont(axis_font)
        fm = QFontMetrics(axis_font)

        captions = ("Tồn hiện tại", "Mức cần chuẩn bị")
        left = max(136, max(fm.horizontalAdvance(c) for c in captions) + 18)

        total_req = self.forecast + self.buffer
        val_labels = (number(self.current), number(total_req))
        max_val_w = max(fm.horizontalAdvance(v) for v in val_labels)
        right_margin = max(62, max_val_w + 22)
        right = max(left + 120, self.width() - right_margin)
        width = max(40.0, float(right - left))

        largest = max(self.current, total_req, 0.0)
        step, maximum, step_count = _nice_scale(largest, intervals=4)

        top = 24
        bottom = max(138, self.height() - 40)
        for index in range(step_count + 1):
            x_pos = left + (index / step_count) * width
            p.setPen(QPen(QColor("#E7EDF4"), 1))
            p.drawLine(QPointF(x_pos, top), QPointF(x_pos, bottom))
            lbl = number(index * step)
            lbl_w = max(52.0, fm.horizontalAdvance(lbl) + 8.0)
            p.setPen(QColor(SUB))
            p.drawText(
                QRectF(x_pos - lbl_w / 2.0, bottom + 9, lbl_w, 20),
                Qt.AlignmentFlag.AlignCenter,
                lbl,
            )

        rows_data = (
            ("Tồn hiện tại", self.current, TEAL, False),
            ("Mức cần chuẩn bị", total_req, BLUE, True),
        )
        for index, (caption, value, color, split_buffer) in enumerate(rows_data):
            y_pos = top + 18 + index * 66
            p.setPen(QColor(INK))
            p.drawText(QRectF(0, y_pos + 7, left - 10, 24), caption)

            bar_w = (value / maximum) * width if maximum > 0 else 0.0
            bar_rect = QRectF(left, y_pos, bar_w, 34)
            if bar_w > 0.5:
                clip_path = QPainterPath()
                clip_path.addRoundedRect(bar_rect, 4, 4)
                p.save()
                p.setClipPath(clip_path)
                p.setPen(Qt.PenStyle.NoPen)
                if split_buffer:
                    fc_w = (self.forecast / maximum) * width if maximum > 0 else 0.0
                    p.setBrush(QColor(BLUE))
                    p.drawRect(QRectF(left, y_pos, fc_w, 34))
                    if self.buffer > 0:
                        p.setBrush(QColor("#7892BB"))
                        p.drawRect(QRectF(left + fc_w, y_pos, max(0.0, bar_w - fc_w), 34))
                else:
                    p.setBrush(QColor(color))
                    p.drawRect(bar_rect)
                p.restore()

            p.setPen(QColor(INK))
            p.drawText(
                QRectF(left + bar_w + 8, y_pos + 6, right_margin - 12, 24),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                number(value),
            )
        p.end()
