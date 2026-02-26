from __future__ import annotations

import os
from pathlib import Path

try:
    import fcntl  # type: ignore

    _HAS_FCNTL = True
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None
    _HAS_FCNTL = False
    import msvcrt


class PollerFileLock:
    def __init__(self, path: str | Path = "/data/poller.lock") -> None:
        self.path = Path(path)
        self._handle = None
        self.lock_acquired = False

    def acquire(self, non_blocking: bool = True) -> bool:
        if self.lock_acquired:
            return True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(self.path, "a+", encoding="utf-8")
        try:
            if _HAS_FCNTL:
                flags = fcntl.LOCK_EX
                if non_blocking:
                    flags |= fcntl.LOCK_NB
                fcntl.flock(self._handle.fileno(), flags)
            else:  # pragma: no cover - Windows fallback
                mode = msvcrt.LK_NBLCK if non_blocking else msvcrt.LK_LOCK
                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), mode, 1)
            self.lock_acquired = True
            return True
        except OSError:
            self._close()
            return False

    def release(self) -> None:
        if not self._handle:
            self.lock_acquired = False
            return
        try:
            if _HAS_FCNTL:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            else:  # pragma: no cover - Windows fallback
                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self._close()

    def _close(self) -> None:
        if self._handle:
            try:
                self._handle.close()
            finally:
                self._handle = None
        self.lock_acquired = False
