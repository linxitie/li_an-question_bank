"""F2b：Dispatcher 单写者文件锁。

SQLite 是单机事实源，Outbox 是持久队列；同一台机器上可能有多个 uvicorn
worker，每个进程都会启动 Dispatcher。没有锁时它们会同时 fetch_pending，
同一条事件被处理多次。文件锁只解决「同机多进程」，不引入 Redis Stream
的第二套持久化语义。

Windows 用 msvcrt.locking，POSIX 用 fcntl.flock；锁随进程退出自动释放。
锁文件保留不删，避免 Windows 上删文件与持有句柄竞争。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class DispatcherLock:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._fh = None
        self._locked = False

    @property
    def locked(self) -> bool:
        return self._locked

    def acquire(self) -> bool:
        if self._locked:
            return True
        fh = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fh = open(self.path, "a+b")
            if fh.seek(0, os.SEEK_END) == 0:
                fh.write(b"0")
                fh.flush()
            fh.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if fh is not None:
                try:
                    fh.close()
                except OSError as close_exc:
                    logger.debug("dispatcher 锁句柄关闭失败: %s", close_exc)
            logger.debug("dispatcher 锁被占用: %s", exc)
            return False
        self._fh = fh
        self._locked = True
        return True

    def release(self) -> None:
        if not self._locked or self._fh is None:
            return
        try:
            self._fh.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except OSError as exc:
            logger.debug("dispatcher 锁释放失败: %s", exc)
        finally:
            try:
                self._fh.close()
            except OSError as close_exc:
                logger.debug("dispatcher 锁句柄关闭失败: %s", close_exc)
            self._fh = None
            self._locked = False
