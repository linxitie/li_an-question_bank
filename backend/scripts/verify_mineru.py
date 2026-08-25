"""MinerU 部署自检。用法：
    python backend/scripts/verify_mineru.py <sample.pdf>          # 完整OCR链路验收
    python backend/scripts/verify_mineru.py <sample.pdf> --text   # 仅测文字层
"""
import os
import subprocess
import sys
import time
from pathlib import Path

# 注意：MinerU venv 必须位于纯 ASCII 路径（如 C:\mineru_env）。
# 项目原路径含中文会导致 fast_langdetect 的 FastText 模型加载失败
# （FastText C++ 层不支持非 ANSI 路径），详见 solve_problems_files/mineru_deployment_log.md
MINERU_EXE = Path(r"C:\mineru_env\Scripts\mineru.exe")


def check_text_layer(pdf: str) -> int:
    import pdfplumber
    chars = pages = 0
    with pdfplumber.open(pdf) as doc:
        for p in doc.pages:
            chars += len((p.extract_text() or "").strip())
            pages += 1
    avg = chars // max(pages, 1)
    print(f"[text-layer] pages={pages} total_chars={chars} avg/page={avg}")
    return avg


def run_mineru(pdf: str) -> float:
    if not MINERU_EXE.exists():
        sys.exit(f"[FAIL] mineru.exe not found: {MINERU_EXE}")
    out_dir = Path("./mineru_verify_out")
    out_dir.mkdir(exist_ok=True)
    env = {**os.environ, "MINERU_MODEL_SOURCE": "modelscope"}
    t0 = time.time()
    r = subprocess.run(
        [str(MINERU_EXE), "-p", pdf, "-o", str(out_dir), "-b", "pipeline"],
        env=env, capture_output=True, text=True, timeout=900)
    cost = time.time() - t0
    mds = list(out_dir.rglob("*.md"))
    if r.returncode != 0 or not mds:
        print((r.stdout or "")[-1500:])
        print((r.stderr or "")[-1500:])
        sys.exit(f"[FAIL] returncode={r.returncode} md_count={len(mds)}")
    content = mds[0].read_text(encoding="utf-8", errors="ignore")
    cjk = sum(1 for c in content[:5000] if "\u4e00" <= c <= "\u9fff")
    print(f"[OK] cost={cost:.1f}s md={mds[0]} cjk_in_head={cjk}")
    print(f"[BASELINE] pdf={pdf} seconds={cost:.1f} cjk_sample={cjk}")
    return cost


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pdf = sys.argv[1]
    if "--text" in sys.argv:
        check_text_layer(pdf)
    else:
        run_mineru(pdf)
