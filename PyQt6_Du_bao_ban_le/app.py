"""Entrypoint cho ứng dụng desktop PyQt6 Dự báo nhu cầu bán lẻ & Tồn kho."""
from __future__ import annotations

from pathlib import Path
import sys

from PyQt6.QtCore import QThreadPool
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from PyQt6_Du_bao_ban_le.models import AuthUser
    from PyQt6_Du_bao_ban_le.repository import RetailRepository
    from PyQt6_Du_bao_ban_le.ui import STYLE, Dashboard, LoginPage
except ImportError:
    from models import AuthUser
    from repository import RetailRepository
    from ui import STYLE, Dashboard, LoginPage


class MainWindow(QMainWindow):
    def __init__(self, repo: RetailRepository | None = None):
        super().__init__()
        self.setWindowTitle("Kế hoạch bán lẻ")
        self.resize(1280, 860)
        self.setMinimumSize(1100, 760)
        self.setObjectName("app")

        self.repo = repo or RetailRepository(check_on_init=True)
        self.stack = QStackedWidget()
        self.login = LoginPage(self.repo)
        self.dashboard: Dashboard | None = None

        self.stack.addWidget(self.login)
        self.setCentralWidget(self.stack)
        self.login.logged_in.connect(self._on_logged_in)

    def _on_logged_in(self, user: AuthUser) -> None:
        if self.dashboard is not None:
            self.dashboard.cleanup()
            self.stack.removeWidget(self.dashboard)
            self.dashboard.deleteLater()
            self.dashboard = None

        self.dashboard = Dashboard(self.repo, user=user)
        self.dashboard.logged_out.connect(self._on_logged_out)
        self.stack.addWidget(self.dashboard)
        self.stack.setCurrentWidget(self.dashboard)

    def _on_logged_out(self) -> None:
        if self.dashboard is not None:
            self.dashboard.cleanup()
            self.stack.removeWidget(self.dashboard)
            self.dashboard.deleteLater()
            self.dashboard = None

        self.login.reset_for_logout()
        self.stack.setCurrentWidget(self.login)

    def closeEvent(self, event) -> None:
        self.login.cleanup()
        if self.dashboard is not None:
            self.dashboard.cleanup()
        QThreadPool.globalInstance().waitForDone(2000)
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
