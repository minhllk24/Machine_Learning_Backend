"""Thread-safe QThreadPool workers with stale-request token filtering."""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, Qt, pyqtSignal

logger = logging.getLogger(__name__)
_SAFE_WORKER_ERROR = "Lỗi xử lý tác vụ nền. Vui lòng thử lại."


class WorkerSignals(QObject):
    """Qt signals emitted by FunctionWorker back to the GUI thread."""

    finished = pyqtSignal(object, int)
    error = pyqtSignal(str, int)


class FunctionWorker(QRunnable):
    """Run a blocking callable off the GUI thread and tag output with a token."""

    def __init__(
        self,
        fn: Callable[..., Any],
        *args: Any,
        token: int = 0,
        cancel_check: Callable[[], bool] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.token = int(token)
        self.cancel_check = cancel_check
        self.signals = WorkerSignals()

    def _is_cancelled(self) -> bool:
        return self.cancel_check is not None and self.cancel_check()

    def run(self) -> None:
        if self._is_cancelled():
            return
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            logger.exception("Background worker error")
            if not self._is_cancelled():
                self._emit_safe(self.signals.error, _SAFE_WORKER_ERROR, self.token)
            return
        if not self._is_cancelled():
            self._emit_safe(self.signals.finished, result, self.token)

    @staticmethod
    def _emit_safe(signal: Any, payload: Any, token: int) -> None:
        try:
            signal.emit(payload, token)
        except RuntimeError:
            # Qt receiver/application is already shutting down.
            pass


class RequestCoordinator(QObject):
    """Coordinate async QThreadPool jobs and ignore stale request tokens."""

    def __init__(
        self,
        parent: QObject | None = None,
        pool: QThreadPool | None = None,
    ) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._token = 0
        self._pool = pool or QThreadPool.globalInstance()
        self._callbacks: dict[
            int, tuple[Callable[[Any], None] | None, Callable[[str], None] | None]
        ] = {}

    def next_token(self) -> int:
        with self._lock:
            self._token += 1
            self._callbacks.clear()
            return self._token

    def current_token(self) -> int:
        with self._lock:
            return self._token

    def is_current(self, token: int) -> bool:
        with self._lock:
            return token == self._token

    def invalidate(self) -> int:
        return self.next_token()

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        on_finished: Callable[[Any], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> int:
        with self._lock:
            self._token += 1
            token = self._token
            self._callbacks.clear()
            self._callbacks[token] = (on_finished, on_error)

        worker = FunctionWorker(
            fn,
            *args,
            token=token,
            cancel_check=lambda t=token: not self.is_current(t),
            **kwargs,
        )
        worker.signals.finished.connect(
            self._on_worker_finished, Qt.ConnectionType.QueuedConnection
        )
        worker.signals.error.connect(
            self._on_worker_error, Qt.ConnectionType.QueuedConnection
        )
        self._pool.start(worker)
        return token

    def _on_worker_finished(self, result: Any, emitted_token: int) -> None:
        with self._lock:
            if emitted_token != self._token:
                self._callbacks.pop(emitted_token, None)
                return
            on_finished, _ = self._callbacks.pop(emitted_token, (None, None))
        if on_finished is not None:
            on_finished(result)

    def _on_worker_error(self, message: str, emitted_token: int) -> None:
        with self._lock:
            if emitted_token != self._token:
                self._callbacks.pop(emitted_token, None)
                return
            _, on_error = self._callbacks.pop(emitted_token, (None, None))
        if on_error is not None:
            on_error(message)


__all__ = ["FunctionWorker", "RequestCoordinator", "WorkerSignals"]
