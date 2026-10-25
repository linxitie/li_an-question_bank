# -*- coding: utf-8 -*-
"""
ocr_worker.py — PaddleOCR 独立子进程执行器（P1.1 进程隔离）

背景：本机 Python 3.13 超出 PaddleOCR 官方支持（≤3.12），Paddle 原生层
加载模型后可能硬崩整个进程。将 OCR 移入本子进程执行：
  - 子进程崩溃 → 主后端进程无恙，返回明确错误
  - 超时 → 父进程强杀子进程
  - 单页失败跳过，不阻断整批

用法（由 question_import._extract_text_from_scanned_pdf 调用，勿手动运行）:
  python -m app.services.ocr_worker <images_dir> <out_json>

输入 : images_dir 内按文件名排序的 png/jpg 图片（每页一张）
输出 : out_json = {"ok": bool, "text": str, "pages_ok": n, "pages_fail": n, "error": str}
"""
import sys
import os
import json
import glob
import traceback

# ★ Paddle 3.x 已知缺陷规避（必须在 import paddle 前设置）：
# (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support
#   → 关闭 PIR 新执行器与 OneDNN，回退传统执行路径
os.environ.setdefault('FLAGS_enable_pir_api', '0')
os.environ.setdefault('FLAGS_enable_pir_in_executor', '0')
os.environ.setdefault('FLAGS_use_mkldnn', '0')


def main(images_dir: str, out_json: str):
    result = {"ok": False, "text": "", "pages_ok": 0, "pages_fail": 0, "error": ""}
    try:
        images = sorted(
            glob.glob(os.path.join(images_dir, '*.png'))
            + glob.glob(os.path.join(images_dir, '*.jpg'))
            + glob.glob(os.path.join(images_dir, '*.jpeg'))
        )
        if not images:
            result["error"] = "no images"
            _write(out_json, result)
            return

        # 延迟导入：仅子进程加载 Paddle（主进程永不导入）
        # 兼容 PaddleOCR 2.x/3.x：新版移除了 show_log/cls 参数，用最小参数集
        from paddleocr import PaddleOCR
        try:
            import paddle
            # paddle 3.x 推理默认启用 OneDNN 且在本机损坏
            # (NotFound) OneDnnContext does not have the input Filter → 运行时关闭
            paddle.set_flags({'FLAGS_use_mkldnn': 0})
            # CPU-only 环境（实测 is_compiled_with_cuda=False）：按核数放开线程，
            # 默认 1 线程时 24 页答案卷要跑数分钟，是导入链最大的时间黑洞。
            try:
                paddle.set_num_threads(max(2, min(8, (os.cpu_count() or 2) - 1)))
            except Exception:
                pass
        except Exception:
            pass
        try:
            # 试卷扫描件都是正向排版：关掉方向分类可显著提速（每页少一次模型推理）
            ocr = PaddleOCR(lang='ch', enable_mkldnn=False,
                            use_angle_cls=False, show_log=False)
        except Exception as e:
            print(f"[ocr_worker] 参数化初始化失败，回退最小参数集: {e}", file=sys.stderr)
            try:
                ocr = PaddleOCR(lang='ch', enable_mkldnn=False)
            except Exception:
                ocr = PaddleOCR(lang='ch')

        parts = []
        for img_path in images:
            try:
                res = None
                # PaddleOCR 3.x：predict()（返回 dict 含 rec_texts）；失败回退旧 ocr()
                try:
                    res = ocr.predict(img_path)
                except Exception:
                    try:
                        res = ocr.ocr(img_path)
                    except (TypeError, ValueError):
                        res = ocr.ocr(img_path, cls=True)
                page_text = _res_to_text(res)
                if page_text:
                    parts.append(page_text)
                    result["pages_ok"] += 1
                else:
                    result["pages_fail"] += 1
            except Exception as pe:  # 单页失败跳过
                result["pages_fail"] += 1
                print(f"[ocr_worker] page fail {img_path}: {pe}", file=sys.stderr)

        result["text"] = "\n".join(parts).strip()
        result["ok"] = bool(result["text"])
        if not result["ok"]:
            result["error"] = "ocr produced no text"
    except Exception as e:  # noqa: BLE001 — 初始化/整体失败也要写出结果
        result["error"] = f"{type(e).__name__}: {e}"
        traceback.print_exc()
    _write(out_json, result)


def _res_to_text(res) -> str:
    """兼容 PaddleOCR 2.x/3.x 返回结构，提取文本行。

    3.x predict(): [ {'rec_texts': [...], 'rec_scores': [...]}, ... ]
    2.x ocr():     [ [ [box, (text, conf)], ... ], ... ]
    """
    lines = []
    if not res:
        return ""
    items = res if isinstance(res, list) else [res]
    for page in items:
        if not page:
            continue
        if isinstance(page, dict):
            # 3.x predict 结构
            texts = page.get('rec_texts') or []
            lines.extend(str(t) for t in texts)
            continue
        if not isinstance(page, (list, tuple)):
            continue
        for item in page:
            try:
                # 2.x 结构: [box, (text, conf)]
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    payload = item[1]
                    if isinstance(payload, (list, tuple)) and payload:
                        lines.append(str(payload[0]))
                    else:
                        lines.append(str(payload))
            except Exception:
                continue
    return "\n".join(lines)


def _write(path: str, obj: dict):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("usage: python -m app.services.ocr_worker <images_dir> <out_json>", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
