"""MinerU 环境自检脚本 —— 运维一键验收工具。

用法:
    cd backend && python scripts/test_mineru.py

五连检查（任一失败即 exit 1）:
    [1/5] 配置读取        MINERU_* 四键可见
    [2/5] 解释器存在      MINERU_PYTHON 指向的 venv python 可执行
    [3/5] MinerU 可用     health_check(force=True) 探测 --version
    [4/5] 样例端到端解析  fitz 生成含中文题目的PDF → extract_text_sync 全链路
    [5/5] 性能基线        打印解析耗时（供运维记录基线）

当前未部署环境时本脚本预期 exit 1 —— 这属正确行为（提示先跑 setup_mineru_env.ps1）。
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


def _fail(step_no, msg):
    print(f"  [FAIL] [{step_no}/5] {msg}")
    sys.exit(1)


def _ok(step_no, msg):
    print(f"  [OK]   [{step_no}/5] {msg}")


def main():
    from app.core.config import settings
    from app.services import mineru_service as ms

    # ---------------------------------------------------------- [1/5] 配置
    cfg = {
        'MINERU_ENABLED': getattr(settings, 'MINERU_ENABLED', None),
        'MINERU_PYTHON': getattr(settings, 'MINERU_PYTHON', ''),
        'MINERU_TIMEOUT': getattr(settings, 'MINERU_TIMEOUT', None),
        'MINERU_BACKEND': getattr(settings, 'MINERU_BACKEND', ''),
    }
    print(f"[1/5] 配置读取: enabled={cfg['MINERU_ENABLED']} "
          f"python={cfg['MINERU_PYTHON']} timeout={cfg['MINERU_TIMEOUT']}s "
          f"backend={cfg['MINERU_BACKEND']}")
    if not cfg['MINERU_ENABLED']:
        _fail(1, "MINERU_ENABLED=false。请编辑 backend/.env 开启后再检。")
    if not cfg['MINERU_PYTHON']:
        _fail(1, "MINERU_PYTHON 为空")
    _ok(1, "配置完整")

    # ------------------------------------------------------ [2/5] 解释器
    py = str(cfg['MINERU_PYTHON'])
    if not os.path.isfile(py):
        _fail(2, f"解释器不存在: {py}。请先运行 scripts/setup_mineru_env.ps1")
    _ok(2, f"解释器存在: {py}")

    # --------------------------------------------- [3/5] health_check
    hc = ms.health_check(force=True)
    if not hc.get('available'):
        _fail(3, f"MinerU 不可用: {hc.get('message')}")
    _ok(3, f"MinerU 版本: {hc.get('version')}")

    # --------------------------------------- [4/5] 端到端样例解析
    try:
        import fitz  # PyMuPDF，主后端既有依赖
    except ImportError:
        _fail(4, "主后端缺少 PyMuPDF(fitz)，无法生成样例PDF；请 pip install PyMuPDF")

    sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '_mineru_sample.pdf')
    try:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "1. 公安联考测试题目内容", fontname='china-s',
                         fontsize=12)
        page.insert_text((72, 100), "A. 选项一  B. 选项二", fontname='china-s',
                         fontsize=11)
        page.insert_text((72, 128), "答案：A", fontname='china-s', fontsize=11)
        doc.save(sample_path)
        doc.close()

        t0 = time.time()
        with open(sample_path, 'rb') as f:
            buf = f.read()
        text = ms.extract_text_sync(buf)
        dur = time.time() - t0
    finally:
        if os.path.exists(sample_path):
            os.remove(sample_path)

    if not text or len(text.strip()) < 4:
        _fail(4, f"端到端解析失败或输出过短({len(text or '')}字符)，详见 [mineru] 日志")
    _ok(4, f"端到端解析成功: {len(text)} 字符（含题目文本: "
           f"{'公安联考' in text or '测试' in text or '答案' in text}）")

    # ---------------------------------------------------- [5/5] 基线
    pages_hint = '单页'
    print(f"[5/5] 性能基线: {pages_hint}样例耗时 {dur:.1f}s "
          f"(timeout={cfg['MINERU_TIMEOUT']}s)")
    if dur > float(cfg['MINERU_TIMEOUT'] or 300):
        _fail(5, "样例耗时超过配置超时——请核查GPU是否生效（见[3/5]版本与CUDA日志）")
    _ok(5, "性能达标")

    print("\n[DONE] MinerU 环境自检全部通过 ✓ 可开启导入功能使用。")


if __name__ == '__main__':
    main()
