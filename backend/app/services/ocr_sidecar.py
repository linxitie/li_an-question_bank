# -*- coding: utf-8 -*-
"""扫描件 OCR sidecar（P1 交付；S-C 增加常驻模式）。

**为什么是子进程**：主后端跑 Python 3.14、不装 onnxruntime/opencv；OCR 运行时是独立的
`C:\\ocr-env`（Python 3.11 + rapidocr-onnxruntime，287MB，模型随包自带、不联网）。
主进程只起子进程、读 JSONL —— 主环境**零新增依赖**，OCR 环境坏了也不影响文字版链路。

两种运行模式（`OCR_MODE` 环境变量，默认 `daemon`）：

| 模式 | 行为 | 用途 |
|---|---|---|
| `daemon`（S-C 默认） | 起一个常驻 worker（`--serve`），模型只加载一次，之后每份 PDF 发一条命令复用 | 省掉每篇 **20–25s** 的模型加载（实测首条进度固定晚 25s 就是它） |
| `oneshot` | 每份 PDF 起一个新进程，跑完退出 | 兜底/排障；P1 的老路径，行为完全不变 |

协议见 `backend/scripts/ocr/rapidocr_worker.py` 的模块文档。
边界（刻意不做）：不写库、不建表、不新增端点（守 R11）；不缓存识别结果（P4）。
"""
from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

#: 覆盖 OCR 解释器的环境变量（换机/换目录不用改代码）
OCR_PYTHON_ENV = "OCR_PYTHON"
#: 默认 OCR 解释器（P0 装在这里；仓库外）
DEFAULT_OCR_PYTHON = r"C:\ocr-env\Scripts\python.exe"
#: worker 脚本（仓库内，随代码走）
WORKER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ocr" / "rapidocr_worker.py"

#: 运行模式：daemon（常驻，默认）/ oneshot（每次新进程）
OCR_MODE_ENV = "OCR_MODE"
DEFAULT_OCR_MODE = "daemon"
#: 常驻进程首次就绪（解释器 + 模型加载）最多等多久
DAEMON_READY_TIMEOUT = 150.0
#: 常驻进程空闲多久回收（避免长期挂着占内存；下次调用会重新拉起）
DAEMON_IDLE_SECONDS = 30 * 60

#: 默认参数（与方案 §7 风险表一致：60s/页、60 页、封顶 30 分钟、200dpi）
DEFAULT_DPI = 200
DEFAULT_MAX_PAGES = 60
DEFAULT_PAGE_TIMEOUT = 60.0
DEFAULT_TOTAL_TIMEOUT = 1800.0

#: 条带重跑（T4，2026-11-14）：被水印压住的整行在 200dpi 整页里会被漏掉，
#: 按 300dpi 把那一小条带**原样**重跑才逐字正确（二值化/400dpi 会掉字，实测见方案 §2）。
REGION_DPI = 300
#: 单条带（一次裁剪）默认超时
REGION_TIMEOUT = 30.0

Progress = Optional[Callable[[int, int], None]]


class OcrError(RuntimeError):
    """OCR 不可用或识别失败（调用方转成可读的业务错误）。"""


class OcrTimeout(OcrError):
    """条带重跑超时 —— 调用方可据此停止继续补行，而不是逐条等满。"""


def python_exe() -> str:
    """OCR 解释器路径（环境变量优先）。"""
    return (os.environ.get(OCR_PYTHON_ENV) or DEFAULT_OCR_PYTHON).strip()


def ocr_mode() -> str:
    mode = (os.environ.get(OCR_MODE_ENV) or DEFAULT_OCR_MODE).strip().lower()
    return mode if mode in ("daemon", "oneshot") else DEFAULT_OCR_MODE


def available() -> Tuple[bool, str]:
    """快速自检：只看文件在不在（不跑 import，便于健康检查/报错前置）。"""
    exe = python_exe()
    if not os.path.isfile(exe):
        return False, (f"OCR 运行时没装：找不到 {exe}"
                       f"（安装步骤见 docs/plans/扫描件OCR能力_方案_v1.md §9.1）")
    if not WORKER_PATH.is_file():
        return False, f"OCR worker 脚本缺失：{WORKER_PATH}"
    return True, ""


def _kill(proc: subprocess.Popen) -> None:
    try:
        proc.kill()
    except Exception:                              # noqa: BLE001
        pass
    try:
        proc.wait(timeout=5)
    except Exception:                              # noqa: BLE001
        pass


def _pump(pipe, sink: queue.Queue, tag: str) -> None:
    """把子进程输出逐行塞进队列（None 表示 EOF）。"""
    try:
        for line in pipe:
            sink.put((tag, line.rstrip("\n")))
    except Exception:                              # noqa: BLE001
        pass
    finally:
        sink.put((tag, None))


def _spawn(extra_args: List[str]) -> Tuple[subprocess.Popen, queue.Queue]:
    cmd = [python_exe(), "-u", str(WORKER_PATH)] + extra_args
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
            errors="replace", bufsize=1, env=env, creationflags=flags)
    except OSError as exc:
        raise OcrError(f"OCR 进程起不来：{exc}") from exc
    q: queue.Queue = queue.Queue()
    threading.Thread(target=_pump, args=(proc.stdout, q, "out"), daemon=True).start()
    threading.Thread(target=_pump, args=(proc.stderr, q, "err"), daemon=True).start()
    return proc, q


def _consume(q: queue.Queue, *, page_timeout: float, total_timeout: float,
             progress: Progress, errs: List[str],
             first_wait: float = 120.0) -> Dict:
    """读事件直到 `done`（或超时/EOF）。返回聚合结果；超时抛 OcrError。"""
    texts: List[str] = []
    fails: List[Dict] = []
    layouts: List[List[Dict]] = []          # T1：每页的带坐标框（只有 with_layout 才有）
    total = 0
    page_secs = 0.0
    truncated = False
    got_meta = False
    deadline = time.monotonic() + total_timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OcrError(f"OCR 超时：总时长超过 {int(total_timeout)}s"
                           f"（已识别 {len(texts)}/{total or '?'} 页）")
        wait = min(page_timeout, remaining) if got_meta else min(first_wait, remaining)
        try:
            tag, line = q.get(timeout=max(0.1, wait))
        except queue.Empty:
            done_pages = len(texts) + len(fails)
            raise OcrError(f"OCR 超时：第 {done_pages + 1} 页超过 {int(page_timeout)}s 没有结果"
                           f"（已识别 {len(texts)} 页）")
        if tag == "err":
            if line is not None:
                errs.append(line)
            continue
        if line is None:
            raise OcrError("OCR 进程意外退出"
                           + (f"：{'；'.join(errs[-3:])[:300]}" if errs else ""))
        try:
            evt = json.loads(line)
        except ValueError:
            errs.append(line)
            continue
        kind = evt.get("t")
        if kind == "meta":
            total = int(evt.get("pages") or 0)
            got_meta = True
        elif kind == "page":
            texts.append(evt.get("text") or "")
            page_lines = evt.get("lines")
            if isinstance(page_lines, list):
                layouts.append(page_lines)
            page_secs += float(evt.get("secs") or 0)
            if progress:
                try:
                    progress(len(texts), total)
                except Exception:                  # noqa: BLE001
                    pass
        elif kind == "page_error":
            fails.append({"page": int(evt.get("page") or 0),
                          "message": (evt.get("message") or "")[:300]})
        elif kind == "done":
            truncated = bool(evt.get("truncated"))
            break
        elif kind == "error":
            raise OcrError(f"OCR 失败：{(evt.get('message') or '')[:300]}")
        # ready / pong 等控制事件直接忽略
    return {"texts": texts, "fails": fails, "total": total,
            "page_secs": page_secs, "truncated": truncated, "layouts": layouts}


def _result(texts: List[str], fails: List[Dict], total: int, page_secs: float,
            truncated: bool, dpi: int,
            layouts: Optional[List[List[Dict]]] = None) -> Tuple[str, Dict]:
    if not texts:
        detail = ""
        if fails:
            detail = f"，首条：第 {fails[0]['page']} 页 {fails[0]['message']}"
        raise OcrError(f"OCR 没有识别出任何文字（失败 {len(fails)} 页）{detail}")
    meta = {
        "engine": "rapidocr",
        "dpi": int(dpi),
        "pages": total or len(texts) + len(fails),
        "pages_done": len(texts),
        "pages_failed": len(fails),
        "truncated": truncated,
        "seconds": round(page_secs, 1),
        "errors": fails[:5],
    }
    if layouts:
        # T1（2026-11-14）：只有请求了 with_layout 才带坐标，避免文章/答案链路白白多传数据
        meta["layout"] = layouts
    return "\n".join(texts), meta


def _await_crop(q: queue.Queue, *, proc: Optional[subprocess.Popen] = None,
                timeout: float = REGION_TIMEOUT) -> List[Dict]:
    """读一条 `crop` 事件（跳过 stderr 噪声与控制事件）。返回带 pt 坐标的框。"""
    deadline = time.monotonic() + max(1.0, float(timeout))
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OcrTimeout(f"OCR 条带重跑超时（>{int(timeout)}s）")
        try:
            tag, line = q.get(timeout=max(0.1, min(5.0, remaining)))
        except queue.Empty:
            if proc is not None and proc.poll() is not None:
                raise OcrError(f"OCR 进程已退出（exit {proc.returncode}），条带重跑没有结果")
            continue
        if line is None:
            raise OcrError("OCR 进程意外退出，条带重跑没有结果")
        if tag == "err":
            continue
        try:
            evt = json.loads(line)
        except ValueError:
            continue
        kind = evt.get("t")
        if kind == "crop":
            return [it for it in (evt.get("lines") or []) if isinstance(it, dict)]
        if kind == "error":
            raise OcrError(f"OCR 条带重跑失败：{(evt.get('message') or '')[:200]}")
        # ready / pong 等控制事件直接忽略


# --------------------------------------------------------------- 常驻 worker
class _Daemon:
    """常驻 OCR worker：模型只加载一次，之后复用进程。"""

    def __init__(self) -> None:
        self.proc: Optional[subprocess.Popen] = None
        self.q: Optional[queue.Queue] = None
        self.errs: List[str] = []
        self.pid: Optional[int] = None
        self.last_used = 0.0

    def _ensure(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            if self.last_used and (time.monotonic() - self.last_used) > DAEMON_IDLE_SECONDS:
                self.close()          # 空闲回收
            else:
                return
        self.close()
        proc, q = _spawn(["--serve"])
        self.proc, self.q, self.errs = proc, q, []
        deadline = time.monotonic() + DAEMON_READY_TIMEOUT
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.close()
                raise OcrError(f"OCR 常驻进程启动超时（模型加载 >{int(DAEMON_READY_TIMEOUT)}s）")
            try:
                tag, line = q.get(timeout=min(5.0, remaining))
            except queue.Empty:
                if proc.poll() is not None:
                    detail = "；".join(self.errs[-3:])[:300]
                    self.close()
                    raise OcrError(f"OCR 常驻进程启动失败（exit {proc.returncode}）"
                                   + (f"：{detail}" if detail else ""))
                continue
            if tag == "err":
                if line:
                    self.errs.append(line)
                continue
            if line is None:
                detail = "；".join(self.errs[-3:])[:300]
                self.close()
                raise OcrError("OCR 常驻进程启动时退出" + (f"：{detail}" if detail else ""))
            try:
                evt = json.loads(line)
            except ValueError:
                continue
            if evt.get("t") == "ready":
                self.pid = evt.get("pid")
                return

    def read(self, abs_path: str, *, dpi: int, max_pages: int,
             page_timeout: float, total_timeout: float,
             progress: Progress, with_layout: bool = False) -> Tuple[str, Dict]:
        self._ensure()
        self.last_used = time.monotonic()
        assert self.proc is not None and self.q is not None
        cmd = json.dumps({"cmd": "ocr", "path": abs_path,
                          "dpi": int(dpi), "max_pages": int(max_pages),
                          "with_layout": bool(with_layout)},
                         ensure_ascii=False)
        try:
            self.proc.stdin.write(cmd + "\n")      # type: ignore[union-attr]
            self.proc.stdin.flush()                # type: ignore[union-attr]
        except Exception as exc:                    # noqa: BLE001
            self.close()
            raise OcrError(f"OCR 常驻进程写命令失败：{exc}") from exc
        try:
            out = _consume(self.q, page_timeout=page_timeout,
                           total_timeout=total_timeout, progress=progress,
                           errs=self.errs)
        except OcrError:
            # 超时/崩溃后进程状态不可信，直接回收，下次调用自动重启
            self.close()
            raise
        return _result(out["texts"], out["fails"], out["total"],
                       out["page_secs"], out["truncated"], dpi,
                       layouts=out.get("layouts") or None)

    def crop(self, abs_path: str, *, page: int, rect: List[float], dpi: int,
             timeout: float) -> List[Dict]:
        """只识别一页的一个矩形（pt）→ 带 pt 坐标的框（T4 缺行回收）。"""
        self._ensure()
        self.last_used = time.monotonic()
        assert self.proc is not None and self.q is not None
        cmd = json.dumps({"cmd": "crop", "path": abs_path, "page": int(page),
                          "rect": [float(v) for v in rect], "dpi": int(dpi)},
                         ensure_ascii=False)
        try:
            self.proc.stdin.write(cmd + "\n")      # type: ignore[union-attr]
            self.proc.stdin.flush()                # type: ignore[union-attr]
        except Exception as exc:                    # noqa: BLE001
            self.close()
            raise OcrError(f"OCR 常驻进程写命令失败：{exc}") from exc
        try:
            return _await_crop(self.q, proc=self.proc, timeout=timeout)
        except OcrTimeout:
            self.close()                            # 超时后进程状态不可信，回收下次重建
            raise
        except OcrError:
            if self.proc.poll() is not None:        # 进程死了才回收；业务错误保留常驻进程
                self.close()
            raise

    def close(self) -> None:
        if self.proc is None:
            return
        try:
            if self.proc.poll() is None and self.proc.stdin:
                self.proc.stdin.write('{"cmd":"quit"}\n')
                self.proc.stdin.flush()
                self.proc.wait(timeout=3)
        except Exception:                          # noqa: BLE001
            pass
        if self.proc.poll() is None:
            _kill(self.proc)
        self.proc = None
        self.q = None
        self.pid = None


_DAEMON_LOCK = threading.Lock()
_DAEMON: Optional[_Daemon] = None


def _get_daemon() -> _Daemon:
    global _DAEMON
    if _DAEMON is None:
        _DAEMON = _Daemon()
        atexit.register(_DAEMON.close)
    return _DAEMON


def shutdown() -> None:
    """关闭常驻进程（测试与进程退出用）。"""
    global _DAEMON
    with _DAEMON_LOCK:
        if _DAEMON is not None:
            _DAEMON.close()
            _DAEMON = None


# --------------------------------------------------------------- 对外入口
def read_pdf_text(
        abs_path: str,
        *,
        max_pages: int = DEFAULT_MAX_PAGES,
        dpi: int = DEFAULT_DPI,
        page_timeout: float = DEFAULT_PAGE_TIMEOUT,
        total_timeout: float = DEFAULT_TOTAL_TIMEOUT,
        progress: Progress = None,
        with_layout: bool = False) -> Tuple[str, Dict]:
    """扫描版 PDF → 文本（按页拼接）+ 识别元信息。

    `with_layout=True`（T1，2026-11-14）：`meta["layout"]` 里带**每页的带坐标框**
    （text/x/y/w/h/score），供试卷拆题判水印与选项缩进；默认关，文章/答案链路零影响。

    失败一律抛 `OcrError`，消息里带**页号与原因**。模式由 `OCR_MODE` 决定：
    `daemon`（默认，复用常驻进程）/ `oneshot`（每份新进程）。
    """
    ok, reason = available()
    if not ok:
        raise OcrError(reason)
    if not os.path.isfile(abs_path):
        raise OcrError(f"待识别的文件不见了：{abs_path}")

    if ocr_mode() == "daemon":
        with _DAEMON_LOCK:
            return _get_daemon().read(
                abs_path, dpi=dpi, max_pages=max_pages,
                page_timeout=page_timeout, total_timeout=total_timeout,
                progress=progress, with_layout=with_layout)

    extra = [abs_path, "--dpi", str(int(dpi)), "--max-pages", str(int(max_pages))]
    if with_layout:
        extra.append("--with-layout")
    proc, q = _spawn(extra)
    errs: List[str] = []
    try:
        out = _consume(q, page_timeout=page_timeout, total_timeout=total_timeout,
                       progress=progress, errs=errs)
        try:
            proc.wait(timeout=10)
        except Exception:                          # noqa: BLE001
            _kill(proc)
    finally:
        if proc.poll() is None:
            _kill(proc)
    return _result(out["texts"], out["fails"], out["total"],
                   out["page_secs"], out["truncated"], dpi,
                   layouts=out.get("layouts") or None)


def read_region_text(
        abs_path: str,
        *,
        page: int,
        rect: List[float],
        dpi: int = REGION_DPI,
        timeout: float = REGION_TIMEOUT) -> List[Dict]:
    """只识别 PDF 某一页的一个矩形（单位 pt）→ 带 pt 坐标的框（T4，2026-11-14）。

    用途：扫描件「整行漏检」的回收 —— 只把那一小条带按 300dpi **原样**重跑一遍
    （200dpi 整页里被斜向水印压住的行，行检测会整行跳过）。
    返回项：`{text, x, y, w, h, score}`，其中 `y` 是框中心、坐标单位 **pt**；
    调用方按自己的版面 dpi 换回像素（`px = pt × dpi / 72`）即可插回原行序。
    失败抛 `OcrError`（超时为子类 `OcrTimeout`）；调用方只记失败数，不让整份导入失败。
    """
    ok, reason = available()
    if not ok:
        raise OcrError(reason)
    if not os.path.isfile(abs_path):
        raise OcrError(f"待识别的文件不见了：{abs_path}")
    if int(page) < 1 or len(list(rect or [])) != 4:
        raise OcrError("条带重跑参数不合法（需要 1 基页码 + 4 个 pt 坐标）")

    if ocr_mode() == "daemon":
        with _DAEMON_LOCK:
            return _get_daemon().crop(abs_path, page=int(page), rect=list(rect),
                                      dpi=int(dpi), timeout=float(timeout))

    extra = [abs_path, "--page", str(int(page)), "--dpi", str(int(dpi)),
             "--clip", ",".join(f"{float(v):.2f}" for v in rect)]
    proc, q = _spawn(extra)
    try:
        return _await_crop(q, proc=proc, timeout=timeout)
    finally:
        try:
            proc.wait(timeout=5)
        except Exception:                          # noqa: BLE001
            _kill(proc)
