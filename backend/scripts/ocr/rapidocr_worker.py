# -*- coding: utf-8 -*-
"""扫描件 OCR worker（P1 sidecar 的执行端，跑在 `C:\\ocr-env`，不在主环境）。

为什么是独立脚本：主后端是 Python 3.14、不装 onnxruntime/opencv；OCR 环境是 3.11
（`C:\\ocr-env`）。主进程只负责起子进程 + 读 JSONL，主环境零新增依赖。
方案与 P0 实测见 `docs/plans/扫描件OCR能力_方案_v1.md` §3 / §9。

stdout 协议（一行一个 JSON，**只有这些**；诊断一律走 stderr）：

    {"t":"meta","pages":24,"will_do":24,"dpi":200,"engine":"rapidocr"}
    {"t":"page","page":1,"chars":1245,"secs":9.2,"text":"1、正确答案是：D\\n..."}
    {"t":"page_error","page":7,"message":"..."}
    {"t":"done","pages_done":23,"pages_failed":1,"secs":206.3,"truncated":false}

为什么要 `-u`（无缓冲）：主进程按行读做逐页超时，缓冲会把进度一次性吐出来。
"""
from __future__ import annotations

import argparse
import json
import sys
import time

#: 每 12px 归为一行（与 P0 PoC 同口径；200dpi 下正文行高约 25–35px）
LINE_BUCKET = 12


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def render_png(page, dpi: int) -> bytes:
    """页面 → PNG 字节（不落盘：P0 时落盘是为了出证据图，线上没必要）。"""
    return page.get_pixmap(dpi=dpi).tobytes("png")


def ocr_page(engine, cv2, np, png: bytes):
    """PNG 字节 → 按"先上后下、同行从左到右"排好的文本行列表。"""
    arr = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    result = engine(arr)
    boxes = result[0] if isinstance(result, tuple) else result
    items = []
    for box, text, score in (boxes or []):
        if not (text or "").strip():
            continue
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append({"y": sum(ys) / len(ys), "x": min(xs),
                      "text": text.strip(), "score": float(score)})
    items.sort(key=lambda it: (round(it["y"] / LINE_BUCKET), it["x"]))
    return [it["text"] for it in items]


def main() -> int:
    ap = argparse.ArgumentParser(description="RapidOCR 扫描件识别（JSONL 输出）")
    ap.add_argument("pdf", help="待识别的 PDF 绝对路径")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--max-pages", type=int, default=60)
    args = ap.parse_args()

    try:
        import cv2
        import numpy as np
        import pymupdf
        from rapidocr_onnxruntime import RapidOCR
    except Exception as exc:                        # noqa: BLE001
        sys.stderr.write(f"OCR 环境不完整：{exc}\n")
        return 3

    try:
        doc = pymupdf.open(args.pdf)
    except Exception as exc:                        # noqa: BLE001
        sys.stderr.write(f"PDF 打不开：{exc}\n")
        return 2

    total = int(doc.page_count)
    will_do = min(total, max(1, args.max_pages))
    emit({"t": "meta", "pages": total, "will_do": will_do,
          "dpi": args.dpi, "engine": "rapidocr"})

    engine = RapidOCR()
    done = failed = 0
    t_all = time.time()
    for i in range(will_do):
        t0 = time.time()
        try:
            png = render_png(doc[i], args.dpi)
            lines = ocr_page(engine, cv2, np, png)
        except Exception as exc:                    # noqa: BLE001
            failed += 1
            emit({"t": "page_error", "page": i + 1, "message": str(exc)[:300]})
            continue
        done += 1
        text = "\n".join(lines)
        emit({"t": "page", "page": i + 1, "chars": len(text),
              "secs": round(time.time() - t0, 2), "text": text})

    emit({"t": "done", "pages_done": done, "pages_failed": failed,
          "secs": round(time.time() - t_all, 1),
          "truncated": will_do < total})
    return 0 if done else 4


if __name__ == "__main__":
    sys.exit(main())
