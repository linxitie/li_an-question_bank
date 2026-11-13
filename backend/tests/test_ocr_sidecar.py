# -*- coding: utf-8 -*-
"""OCR P1：sidecar 协议 + 扫描件路由 + 大小写不敏感（2026-11-12）。

**不依赖真实 OCR 环境**：用当前解释器当"假 worker"，只验证协议解析、超时/失败映射、
以及 `read_text_of` 的分流（文字版 PDF 绝不能走 OCR）。
真实识别效果见 `docs/plans/扫描件OCR能力_方案_v1.md` §9（真机 8.6s/页、13/13 题号）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.services import ocr_sidecar
from app.services.answer_ingest import extractor, service

#: 假 worker 的四种"性格"：正常 / 一页失败 / 全失败 / 卡死。
#: 注意：mode 写死在文件里（sidecar 传的最后一个参数是 --max-pages 的值，不能拿来当模式）。
FAKE_WORKER = r'''
import json, sys, time

MODE = "__MODE__"


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


emit({"t": "meta", "pages": 3, "will_do": 3, "dpi": 200, "engine": "rapidocr"})
if MODE == "hang":
    time.sleep(30)
elif MODE == "allfail":
    emit({"t": "page_error", "page": 1, "message": "页面解码失败"})
    emit({"t": "done", "pages_done": 0, "pages_failed": 1, "secs": 0.1, "truncated": False})
elif MODE == "partial":
    emit({"t": "page", "page": 1, "chars": 4, "secs": 0.1, "text": "1、A"})
    emit({"t": "page_error", "page": 2, "message": "图像损坏"})
    emit({"t": "done", "pages_done": 1, "pages_failed": 1, "secs": 0.2, "truncated": False})
else:
    emit({"t": "page", "page": 1, "chars": 8, "secs": 0.1, "text": "第一页"})
    emit({"t": "page", "page": 2, "chars": 8, "secs": 0.1, "text": "第二页"})
    emit({"t": "done", "pages_done": 2, "pages_failed": 0, "secs": 0.2, "truncated": True})
'''


@pytest.fixture()
def fake_worker(tmp_path, monkeypatch):
    """把 sidecar 指向"当前解释器 + 假 worker"（**强制 oneshot 模式**测 P1 老路径）。"""
    def make(mode: str = "ok") -> str:
        path = tmp_path / f"worker_{mode}.py"
        path.write_text(FAKE_WORKER.replace("__MODE__", mode), encoding="utf-8")
        monkeypatch.setenv(ocr_sidecar.OCR_PYTHON_ENV, sys.executable)
        monkeypatch.setenv(ocr_sidecar.OCR_MODE_ENV, "oneshot")
        monkeypatch.setattr(ocr_sidecar, "WORKER_PATH", path)
        return mode
    return make


#: S-C：常驻模式假 worker —— 支持 --serve，用 pid 证明"进程被复用"
FAKE_DAEMON = r'''
import json, os, sys, time

MODE = "__MODE__"


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if "--serve" not in sys.argv:
    emit({"t": "error", "message": "常驻测试要求 --serve"})
    sys.exit(9)

emit({"t": "ready", "pid": os.getpid()})
served = 0
for raw in sys.stdin:
    line = raw.strip()
    if not line:
        continue
    cmd = json.loads(line)
    if cmd.get("cmd") == "quit":
        break
    if cmd.get("cmd") != "ocr":
        continue
    served += 1
    emit({"t": "meta", "pages": 2})
    if MODE == "hang":
        time.sleep(30)
    emit({"t": "page", "page": 1, "chars": 8, "secs": 0.1,
          "text": "pid=%d page1" % os.getpid()})
    emit({"t": "page", "page": 2, "chars": 8, "secs": 0.1,
          "text": "pid=%d page2" % os.getpid()})
    emit({"t": "done", "pages_done": 2, "pages_failed": 0, "secs": 0.2, "truncated": False})
    if MODE == "die_after_first" and served == 1:
        sys.exit(0)
'''


@pytest.fixture()
def fake_daemon(tmp_path, monkeypatch):
    """常驻模式：指向假 daemon worker，并在用前后清掉单例。"""
    def make(mode: str = "ok") -> str:
        path = tmp_path / f"daemon_{mode}.py"
        path.write_text(FAKE_DAEMON.replace("__MODE__", mode), encoding="utf-8")
        monkeypatch.setenv(ocr_sidecar.OCR_PYTHON_ENV, sys.executable)
        monkeypatch.setenv(ocr_sidecar.OCR_MODE_ENV, "daemon")
        monkeypatch.setattr(ocr_sidecar, "WORKER_PATH", path)
        ocr_sidecar.shutdown()
        return mode
    yield make
    ocr_sidecar.shutdown()


def _pdf(tmp_path: Path, pages: int, text: str = "") -> str:
    """造一个 PDF：`text` 空 = 扫描件（无文字层）。"""
    import pymupdf
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), f"{text}{i + 1}", fontsize=12, fontname="china-s")
    path = tmp_path / f"sample_{pages}_{len(text)}.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


# --------------------------------------------------------------- 环境自检
def test_available_reports_missing_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv(ocr_sidecar.OCR_PYTHON_ENV, str(tmp_path / "nope" / "python.exe"))
    ok, reason = ocr_sidecar.available()
    assert ok is False
    assert "OCR 运行时没装" in reason
    with pytest.raises(ocr_sidecar.OcrError) as err:
        ocr_sidecar.read_pdf_text(str(tmp_path / "x.pdf"))
    assert "找不到" in str(err.value)


# --------------------------------------------------------------- 协议解析
def test_reads_pages_and_reports_progress(tmp_path, fake_worker):
    fake_worker("ok")
    seen = []
    text, meta = ocr_sidecar.read_pdf_text(
        _pdf(tmp_path, 2), progress=lambda done, total: seen.append((done, total)))
    assert text.split("\n") == ["第一页", "第二页"]
    assert meta["pages_done"] == 2 and meta["pages_failed"] == 0
    assert meta["truncated"] is True and meta["engine"] == "rapidocr"
    assert seen == [(1, 3), (2, 3)]


def test_page_error_does_not_drop_good_pages(tmp_path, fake_worker):
    fake_worker("partial")
    text, meta = ocr_sidecar.read_pdf_text(_pdf(tmp_path, 3))
    assert text == "1、A"
    assert meta["pages_failed"] == 1
    assert meta["errors"][0]["page"] == 2
    assert "图像损坏" in meta["errors"][0]["message"]


def test_all_pages_failed_raises_with_page_number(tmp_path, fake_worker):
    fake_worker("allfail")
    with pytest.raises(ocr_sidecar.OcrError) as err:
        ocr_sidecar.read_pdf_text(_pdf(tmp_path, 1))
    msg = str(err.value)
    assert "没有识别出任何文字" in msg and "第 1 页" in msg


def test_page_timeout_kills_worker(tmp_path, fake_worker):
    fake_worker("hang")
    with pytest.raises(ocr_sidecar.OcrError) as err:
        ocr_sidecar.read_pdf_text(_pdf(tmp_path, 1), page_timeout=1.0)
    msg = str(err.value)
    assert "超时" in msg and "第 1 页" in msg


# --------------------------------------------------------------- 分流
def test_text_layer_pdf_never_calls_ocr(tmp_path, monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("文字版 PDF 不该走 OCR")
    monkeypatch.setattr(ocr_sidecar, "read_pdf_text", boom)
    meta: dict = {}
    text = service.read_text_of(_pdf(tmp_path, 2, "正确答案是：A"), "pdf", meta=meta)
    assert "正确答案是：A" in text
    assert meta == {}


def test_scanned_pdf_routes_to_ocr_and_records_meta(tmp_path, monkeypatch):
    def fake(path, **kw):
        return "1、正确答案是：D", {"pages_done": 24, "pages": 24, "seconds": 206.0,
                                    "dpi": 200, "pages_failed": 0}
    monkeypatch.setattr(ocr_sidecar, "read_pdf_text", fake)
    meta: dict = {}
    text = service.read_text_of(_pdf(tmp_path, 1), "pdf", meta=meta)
    assert text == "1、正确答案是：D"
    assert meta["ocr"]["pages_done"] == 24


# --------------------------------------------------------------- OCR 小写字母
def test_ocr_lowercase_letters_are_understood():
    # `正确答案是：D` 走 L2（L1 只吃"答案：D"这种紧贴冒号的写法）；关键是字母要认出来
    items = extractor.parse_text("1、正确答案是：d\n解析\n本题考查公安时政。")
    assert items[0]["answer"] == "D" and items[0]["tier"] in ("L1", "L2")

    # L3：`c项错误` 必须把 C 排除，否则会把 C 当"建议"
    items = extractor.parse_text(
        "2、解析\nA项正确\nc项错误，理由：主体不对\nB项正确")
    assert items[0]["suggestion"] == "AB"
    assert "C" not in items[0]["suggestion"]


# --------------------------------------------------------------- S-C 常驻模式
def test_daemon_reuses_same_process_for_two_files(tmp_path, fake_daemon):
    """连续两份 PDF 必须复用同一个 worker 进程（模型只加载一次）。"""
    fake_daemon("ok")
    t1, m1 = ocr_sidecar.read_pdf_text(_pdf(tmp_path, 2))
    t2, m2 = ocr_sidecar.read_pdf_text(_pdf(tmp_path, 3))
    pid1 = t1.split()[0]
    pid2 = t2.split()[0]
    assert pid1 == pid2, (pid1, pid2)          # 同一个 pid ⇒ 没重启进程
    assert m1["pages_done"] == 2 and m2["pages_done"] == 2


def test_daemon_crash_is_reported_then_restart_works(tmp_path, fake_daemon):
    """worker 半路退出：本次报错，下一次自动重启（不能永久坏掉）。"""
    fake_daemon("die_after_first")
    text, _ = ocr_sidecar.read_pdf_text(_pdf(tmp_path, 2))
    assert "page1" in text
    with pytest.raises(ocr_sidecar.OcrError) as err:
        ocr_sidecar.read_pdf_text(_pdf(tmp_path, 2))
    assert "退出" in str(err.value) or "失败" in str(err.value)
    text2, _ = ocr_sidecar.read_pdf_text(_pdf(tmp_path, 2))
    assert "page1" in text2


def test_daemon_timeout_kills_process(tmp_path, fake_daemon):
    fake_daemon("hang")
    with pytest.raises(ocr_sidecar.OcrError) as err:
        ocr_sidecar.read_pdf_text(_pdf(tmp_path, 1), page_timeout=1.0)
    assert "超时" in str(err.value)
