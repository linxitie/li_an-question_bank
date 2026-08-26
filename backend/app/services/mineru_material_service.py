"""MinerU 子进程集成（备考资料专用）：扫描件 PDF -> Markdown -> 消毒 HTML。

命名说明：项目已有 services/mineru_service.py（题目导入的三级回退链组件，
配置门控 MINERU_ENABLED，勿动）。本模块为备考资料内容工厂专用，路径与
超时按 T0 部署基线硬编码 + 环境变量可覆盖。

进程隔离原则：
- MinerU(含 torch) 装在独立 venv `C:\\mineru_env`（uv 托管 Python 3.11），
  主服务绝不 import 它，仅经 subprocess 调用 CLI；
- venv 必须位于纯 ASCII 路径：项目原路径含中文会导致 fast_langdetect 的
  FastText 模型加载失败，详见 solve_problems_files/mineru_deployment_log.md。

阻塞说明：run_mineru 为阻塞调用（T0 基线：CPU 单页约 70s），路由层必须经
BackgroundTasks 线程池使用，前端 3s 轮询 import_record.parse_status。
"""
import os
import re
import subprocess
import time
from pathlib import Path

from .material_sanitizer import sanitize_html

# 部署基线见 solve_problems_files/mineru_deployment_log.md；可用环境变量覆盖
MINERU_EXE = Path(os.environ.get("MINERU_EXE", r"C:\mineru_env\Scripts\mineru.exe"))
TIMEOUT_SECONDS = int(os.environ.get("MINERU_TIMEOUT_SECONDS", "600"))


class MineruError(Exception):
    """MinerU 解析失败（进程错误/无产出/组件未就绪）。"""


class MineruTimeout(MineruError):
    """解析超时。"""


def mineru_available() -> bool:
    return MINERU_EXE.exists()


def run_mineru(input_path: str, work_dir: Path,
               timeout: int = TIMEOUT_SECONDS) -> dict:
    """阻塞执行 OCR。返回 {html, images:[{src_path,name}], seconds}。

    失败抛 MineruError / MineruTimeout（调用方写入 import_record.error_message）。
    """
    if not mineru_available():
        raise MineruError("该 PDF 为扫描图片版且系统 OCR 组件未就绪，"
                          "请转存为文字版 Word 后重新上传")
    out_dir = Path(work_dir) / f"mineru_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "MINERU_MODEL_SOURCE": "modelscope"}
    t0 = time.time()
    try:
        r = subprocess.run(
            [str(MINERU_EXE), "-p", str(input_path),
             "-o", str(out_dir), "-b", "pipeline"],
            env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise MineruTimeout(f"OCR 解析超时(>{timeout}s)，可重试或拆分文件")
    if r.returncode != 0:
        tail = ((r.stderr or "") + (r.stdout or ""))[-400:]
        raise MineruError(f"OCR 进程失败 rc={r.returncode}: {tail}")

    mds = list(out_dir.rglob("*.md"))
    if not mds:
        raise MineruError("OCR 未产出内容")
    md_text = mds[0].read_text(encoding="utf-8", errors="ignore")
    html = _md_to_html(md_text)

    # 收集提取图片（confirm 阶段统一迁移到正式目录并改写引用）
    images = []
    for img_root in mds[0].parent.rglob("images"):
        if img_root.is_dir():
            for f in img_root.iterdir():
                if f.is_file():
                    images.append({"src_path": str(f), "name": f.name})
    return {"html": sanitize_html(html), "images": images,
            "seconds": round(time.time() - t0, 1)}


def _md_to_html(md: str) -> str:
    """Markdown -> HTML（覆盖备考素材常见结构：标题/粗体/段落/图片）。"""
    parts = []
    for block in re.split(r"\n\s*\n", md):
        b = block.strip()
        if not b:
            continue
        b = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)",
                   r'<img src="\2" alt="\1"/>', b)
        if b.startswith("### "):
            parts.append(f"<h4>{_inline(b[4:].strip())}</h4>")
        elif b.startswith("## "):
            parts.append(f"<h3>{_inline(b[3:].strip())}</h3>")
        elif b.startswith("# "):
            parts.append(f"<h2>{_inline(b[2:].strip())}</h2>")
        else:
            lines = [_inline(ln.strip()) for ln in b.splitlines()]
            parts.append("<p>" + "<br/>".join(lines) + "</p>")
    return "".join(parts)


def _inline(text: str) -> str:
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    return text
