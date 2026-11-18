#!/usr/bin/env python3
"""下载商品图抠像模型（BiRefNet），跨平台（2026-11-18）。

默认下载 birefnet-general（973MB），保存到 rembg 的模型目录：
    %USERPROFILE%/.rembg/models/birefnet-general/birefnet-general.onnx   (Windows)
    ~/.rembg/models/birefnet-general/birefnet-general.onnx               (Linux/macOS)
若设置了 REMBG_HOME / XDG_DATA_HOME / U2NET_HOME，则按 rembg 自己的规则落位。

用法：
    python scripts/shop/fetch_cutout_model.py                 # general（推荐）
    python scripts/shop/fetch_cutout_model.py --variant lite  # 224MB，快但质量差
    python scripts/shop/fetch_cutout_model.py --check         # 只校验本机是否已就绪
    python scripts/shop/fetch_cutout_model.py --force         # 已存在也重新下载
    python scripts/shop/fetch_cutout_model.py --out /models   # 指定目录（容器挂载卷）
    python scripts/shop/fetch_cutout_model.py --url <镜像URL>  # 内网镜像/加速源

断点续传：下载写到 <file>.part，中断后重新执行会带 Range 续传；MD5 校验不过会自动重下。
模型权重不进 Git（>100MB），每台机器/部署环境各下载一次即可。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MODELS = {
    "general": {
        "session": "birefnet-general",
        "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/BiRefNet-general-epoch_244.onnx",
        "md5": "7a35a0141cbbc80de11d9c9a28f52697",
        "size": 972666916,
    },
    "lite": {
        "session": "birefnet-general-lite",
        "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx",
        "md5": "4fab47adc4ff364be1713e97b7e66334",
        "size": 224005088,
    },
}


def target_dir(session: str) -> Path:
    """优先问 rembg 自己要目录（会正确处理 REMBG_HOME/U2NET_HOME/XDG_DATA_HOME）。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
        from rembg.sessions import sessions_class

        cls = next(c for c in sessions_class if c.name() == session)
        return Path(cls.model_dir())
    except Exception:  # noqa: BLE001 - rembg 未安装时退回默认目录
        home = os.getenv("REMBG_HOME") or os.getenv("XDG_DATA_HOME")
        root = os.getenv("U2NET_HOME") or (os.path.join(home, "rembg") if home else str(Path.home() / ".rembg"))
        return Path(root) / "models" / session


def md5_of(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _curl_download(url: str, part: Path) -> None:
    """urllib 被墙/超时时的兜底：交给系统 curl（Windows 10+/Linux/macOS 自带）。

    curl 的 -C - 自带断点续传；失败会返回非零，由调用方提示。
    """
    import shutil
    import subprocess

    curl = shutil.which("curl")
    if not curl:
        raise RuntimeError("urllib 下载失败，且系统没有 curl 可兜底")
    cmd = [curl, "-L", "--fail", "-C", "-", "--retry", "5", "--retry-all-errors", "-o", str(part), url]
    print("urllib 连接失败，改用 curl 续传：" + " ".join(cmd))
    subprocess.run(cmd, check=True)


def download(url: str, dest: Path, expected_size: int) -> None:
    part = dest.with_suffix(dest.suffix + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    start = part.stat().st_size if part.exists() else 0
    if start >= expected_size:
        part.unlink()
        start = 0
    headers = {"User-Agent": "lian-cutout-fetch/1.0"}
    if start:
        headers["Range"] = f"bytes={start}-"
    req = urllib.request.Request(url, headers=headers)
    print(f"下载 {url}\n  -> {dest}（已有 {start} / {expected_size} 字节）")
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as exc:
        if exc.code == 416 and start:
            print("服务器不支持续传（416），从头下载")
            part.unlink(missing_ok=True)
            start = 0
            resp = urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": headers["User-Agent"]}),
                timeout=60,
            )
        elif exc.code in (403, 404):
            raise SystemExit(f"下载地址无效（HTTP {exc.code}）：{url}") from exc
        else:
            print(f"urllib HTTP {exc.code}，尝试 curl 兜底")
            _curl_download(url, part)
            return
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"urllib 连接失败（{exc}），尝试 curl 兜底")
        _curl_download(url, part)
        return
    # 服务器忽略 Range 返回 200 时，必须清空 .part 再写，否则会拼接出坏文件
    if start and getattr(resp, "status", 200) == 200:
        print("服务器未接受续传（200），从头下载")
        start = 0
    mode = "ab" if start else "wb"
    with resp, part.open(mode) as fh:
        total = expected_size
        done = start
        last = time.time()
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
            done += len(chunk)
            if time.time() - last > 2:
                pct = done * 100 / total if total else 0
                print(f"  {pct:5.1f}%  {done / 1048576:.1f} MB", flush=True)
                last = time.time()
    part.replace(dest)


def main() -> int:
    parser = argparse.ArgumentParser(description="下载 BiRefNet 商品图抠像模型")
    parser.add_argument("--variant", choices=sorted(MODELS), default="general")
    parser.add_argument("--force", action="store_true", help="已存在也重新下载")
    parser.add_argument("--out", default=None, help="指定模型目录（默认用 rembg 的模型目录）")
    parser.add_argument("--url", default=None, help="自定义下载地址（内网镜像/加速源）")
    parser.add_argument("--check", action="store_true", help="只校验是否已就绪，不下载")
    args = parser.parse_args()

    m = MODELS[args.variant]
    session = m["session"]
    dest = (Path(args.out) / (session + ".onnx")) if args.out else (target_dir(session) / (session + ".onnx"))

    if args.check:
        ok = dest.exists() and dest.stat().st_size == m["size"] and md5_of(dest) == m["md5"]
        print(("OK   " if ok else "MISS ") + str(dest))
        if not ok:
            print("修复：python scripts/shop/fetch_cutout_model.py" + (" --out " + args.out if args.out else ""))
        return 0 if ok else 2

    if dest.exists() and not args.force:
        if dest.stat().st_size == m["size"] and md5_of(dest) == m["md5"]:
            print(f"已存在且校验通过：{dest}")
            return 0
        print("已有文件校验不通过，重新下载")

    download(args.url or m["url"], dest, m["size"])
    if dest.stat().st_size != m["size"]:
        raise SystemExit(f"大小不对：{dest.stat().st_size} != {m['size']}")
    got = md5_of(dest)
    if got != m["md5"]:
        dest.unlink(missing_ok=True)
        raise SystemExit(f"MD5 校验失败：{got} != {m['md5']}")
    print(f"完成：{dest}")
    print("验证：python -c \"from app.services import product_image as m; print(m.cutout_engine())\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
