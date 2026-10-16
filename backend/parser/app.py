"""parser sidecar —— 扫描件 PDF 解析微服务。

存在的理由：主后端跑在 Python 3.13，而 MinerU 的 Windows 支持上限是 3.12，
PaddleOCR 要求 ≤3.12 —— 两者都无法在主进程内安装。把解析拆成独立服务后，
主后端的依赖面保持干净，解析栈单独升级。

契约：
    POST /parse   multipart/form-data，字段名 file（扫描件 PDF）
                  → 200 {"markdown": "<结构化文本>"}
                  → 4xx/5xx 表示失败，调用方据���回退本地子进程
    GET  /health  → 200 {"ok": true, "mineru": bool}

本服务只做一件事：收 PDF、跑 MinerU、回 Markdown。
失败一律走异常中间件转成 5xx JSON，绝不返回 HTML。
"""
import io
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO'),
    format='%(asctime)s %(levelname)s [parser] %(message)s',
)
log = logging.getLogger('parser')

app = FastAPI(title='parser sidecar', docs_url=None, redoc_url=None)

# MinerU 单次推理占用整块显存，串行化避免并发请求互相 OOM
_sem = threading.Semaphore(1)
_SEM_WAIT = int(os.environ.get('PARSER_SEM_WAIT', '600'))
_TIMEOUT = int(os.environ.get('MINERU_TIMEOUT', '600'))
_BACKEND = os.environ.get('MINERU_BACKEND', 'pipeline')
_PY = os.environ.get('MINERU_PYTHON', sys.executable)
_MAX_UPLOAD = int(os.environ.get('PARSER_MAX_UPLOAD_MB', '64')) * 1024 * 1024


def _mineru_available() -> bool:
    try:
        import mineru  # noqa: F401
        return True
    except ImportError:
        return False


@app.get('/health')
def health():
    return {'ok': True, 'mineru': _mineru_available(), 'backend': _BACKEND}


@app.post('/parse')
async def parse(file: UploadFile = File(...)):
    buf = await file.read()

    if len(buf) > _MAX_UPLOAD:
        return JSONResponse(
            status_code=413,
            content={'error': f'文件过大 {len(buf)} 字节，上限 {_MAX_UPLOAD}'},
        )
    if not buf:
        return JSONResponse(status_code=400, content={'error': '空文件'})

    if not _sem.acquire(timeout=_SEM_WAIT):
        return JSONResponse(status_code=503, content={'error': '解析队列已满'})

    tmpdir = None
    try:
        t0 = time.time()
        tmpdir = tempfile.mkdtemp(prefix='parser_')
        in_pdf = os.path.join(tmpdir, 'input.pdf')
        outdir = os.path.join(tmpdir, 'out')
        with open(in_pdf, 'wb') as f:
            f.write(buf)

        proc = subprocess.run(
            [_PY, '-m', 'mineru.cli.client', '-p', in_pdf, '-o', outdir, '-b', _BACKEND],
            capture_output=True,
            timeout=_TIMEOUT,
            env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8',
                 'MINERU_MODEL_SOURCE': os.environ.get('MINERU_MODEL_SOURCE', 'modelscope')},
        )

        import glob
        md_files = sorted(glob.glob(os.path.join(outdir, '**', '*.md'), recursive=True))
        for p in md_files:
            with open(p, encoding='utf-8') as f:
                content = f.read().strip()
            if content:
                log.info('success chars=%d dur=%.1fs', len(content), time.time() - t0)
                return {'markdown': content, 'chars': len(content)}

        stderr = proc.stderr.decode('utf-8', 'ignore')[:500]
        log.warning('未产出 markdown rc=%s stderr=%s', proc.returncode, stderr)
        return JSONResponse(
            status_code=502,
            content={'error': 'MinerU 未产出 markdown',
                     'rc': proc.returncode, 'stderr': stderr},
        )

    except subprocess.TimeoutExpired:
        log.warning('MinerU 超时 %ds', _TIMEOUT)
        return JSONResponse(status_code=504, content={'error': f'解析超时 {_TIMEOUT}s'})
    except Exception as e:  # noqa: BLE001
        log.exception('解析异常')
        return JSONResponse(
            status_code=500, content={'error': f'{type(e).__name__}: {e}'})
    finally:
        _sem.release()
        if tmpdir:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)