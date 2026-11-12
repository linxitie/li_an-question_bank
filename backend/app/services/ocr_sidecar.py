# -*- coding: utf-8 -*-
"""扫描件 OCR sidecar（P1，2026-11-12 用户批准）。

**为什么是子进程**：主后端跑 Python 3.14、不装 onnxruntime/opencv；OCR 运行时是独立的
`C:\\ocr-env`（Python 3.11 + rapidocr-onnxruntime，287MB，模型随包自带、不联网）。
主进程只起子进程、读 JSONL —— 主环境**零新增依赖**，OCR 环境坏了也不影响文字版链路。

方案与 P0 实测见 `docs/plans/扫描件OCR能力_方案_v1.md` §3 / §9；
worker 协议见 `backend/scripts/ocr/rapidocr_worker.py` 的模块文档。

边界（刻意不做的事）：
  · 不写库、不建表、不新增端点（守 R11）；
  · 不缓存识别结果（P4 再做 sha256 缓存）；
  · 只吃 PDF 文件的绝对路径；页数上限默认 60 页，超了截断并在 meta 里标 `truncated`。
"""
from __future__ import annotations

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

#: 默认参数（与方案 §7 风险表一致：60s/页、60 页、封顶 30 分钟、200dpi）
DEFAULT_DPI = 200
DEFAULT_MAX_PAGES = 60
DEFAULT_PAGE_TIMEOUT = 60.0
DEFAULT_TOTAL_TIMEOUT = 1800.0

Progress = Optional[Callable[[int, int], None]]


class OcrError(RuntimeError):
    """OCR 不可用或识别失败（调用方转成可读的业务错误）。"""


def python_exe() -> str:
    """OCR 解释器路径（环境变量优先）。"""
    return (os.environ.get(OCR_PYTHON_ENV) or DEFAULT_OCR_PYTHON).strip()


def available() -> Tuple[bool, str]:
    """快速自检：只看文件在不在（不跑 import，便于健康检查/报错前置）。

    返回 `(是否可用, 原因)`；不可用时原因直接可以给用户看。
    """
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


def read_pdf_text(
        abs_path: str,
        *,
        max_pages: int = DEFAULT_MAX_PAGES,
        dpi: int = DEFAULT_DPI,
        page_timeout: float = DEFAULT_PAGE_TIMEOUT,
        total_timeout: float = DEFAULT_TOTAL_TIMEOUT,
        progress: Progress = None) -> Tuple[str, Dict]:
    """扫描版 PDF → 文本（按页拼接）+ 识别元信息。

    失败一律抛 `OcrError`，消息里带**页号与原因**（这是 P1 的 DoD：
    不要再出现"组件未就绪"这种一句话）。
    """
    ok, reason = available()
    if not ok:
        raise OcrError(reason)
    if not os.path.isfile(abs_path):
        raise OcrError(f"待识别的文件不见了：{abs_path}")

    cmd = [python_exe(), "-u", str(WORKER_PATH), abs_path,
           "--dpi", str(int(dpi)), "--max-pages", str(int(max_pages))]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            env=env, creationflags=flags)
    except OSError as exc:
        raise OcrError(f"OCR 进程起不来：{exc}") from exc

    q: queue.Queue = queue.Queue()
    errs: List[str] = []
    threading.Thread(target=_pump, args=(proc.stdout, q, "out"), daemon=True).start()
    threading.Thread(target=_pump, args=(proc.stderr, q, "err"), daemon=True).start()

    texts: List[str] = []
    fails: List[Dict] = []
    total = 0
    page_secs = 0.0
    truncated = False
    finished = False
    got_meta = False
    deadline = time.monotonic() + total_timeout
    last_page = 0

    try:
        while not finished:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise OcrError(
                    f"OCR 超时：总时长超过 {int(total_timeout)}s"
                    f"（已识别 {len(texts)}/{total or '?'} 页）")
            # 首个事件要等解释器 + 模型加载（≈3–8s），给 120s 兜底；
            # 之后每页按 page_timeout 卡，超时说明卡在"下一页"
            wait = min(page_timeout, remaining) if got_meta else min(120.0, remaining)
            try:
                tag, line = q.get(timeout=max(0.1, wait))
            except queue.Empty:
                done_pages = len(texts) + len(fails)
                raise OcrError(
                    f"OCR 超时：第 {done_pages + 1} 页超过 {int(page_timeout)}s 没有结果"
                    f"（已识别 {len(texts)} 页）")
            if line is None:
                if tag == "err":
                    continue
                break
            if tag == "err":
                errs.append(line)
                continue
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
                last_page = int(evt.get("page") or 0)
                texts.append(evt.get("text") or "")
                page_secs += float(evt.get("secs") or 0)
                if progress:
                    try:
                        progress(len(texts), total)
                    except Exception:              # noqa: BLE001
                        pass
            elif kind == "page_error":
                fails.append({"page": int(evt.get("page") or 0),
                              "message": (evt.get("message") or "")[:300]})
            elif kind == "done":
                truncated = bool(evt.get("truncated"))
                finished = True
        try:
            proc.wait(timeout=10)
        except Exception:                          # noqa: BLE001
            _kill(proc)
    finally:
        if proc.poll() is None:
            _kill(proc)

    if not texts:
        detail = ""
        if fails:
            detail = f"首条：第 {fails[0]['page']} 页 {fails[0]['message']}"
        elif errs:
            detail = "；".join(errs[-3:])[:600]
        raise OcrError(f"OCR 没有识别出任何文字（失败 {len(fails)} 页）" + (f"，{detail}" if detail else ""))

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
    return "\n".join(texts), meta
