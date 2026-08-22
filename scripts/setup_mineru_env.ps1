#Requires -Version 5.1
<#
.SYNOPSIS
    MinerU 独立环境一键安装脚本（幂等，可重复执行）。
.DESCRIPTION
    为砺安题库扫描件OCR功能部署 MinerU（opendatalab/MinerU v3.x）独立 Python 3.12 环境。
    设计规格: docs/superpowers/specs/2026-08-22-mineru-scanned-pdf-ocr-design.md §5.5

    五步骤:
      ① 定位 Python 3.12 并创建独立 venv（主后端 3.13 无法安装 MinerU，必须隔离）
      ② 安装 mineru[all]（uv 加速）
      ③ 覆盖安装 CUDA 12.4 版 PyTorch（关键！否则仅有 CPU 模式）
      ④ ModelScope 下载解析模型（约 3-5GB，一次性）
      ⑤ 自检 torch.cuda.is_available()

    幂等性: 各步骤检测到已完成即跳过；传 -Force 强制重装②③。
.PARAMETER EnvPath
    venv 目标目录，默认 D:\mineru-env（须与 backend/.env 的 MINERU_PYTHON 一致）。
.PARAMETER Force
    强制重装 mineru 与 CUDA torch（模型不重复下载）。
.EXAMPLE
    .\scripts\setup_mineru_env.ps1                    # 常规安装
    .\scripts\setup_mineru_env.ps1 -Force             # 重装依赖
#>
param(
    [string]$EnvPath = "D:\mineru-env",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Write-Step([int]$n, [string]$msg) {
    Write-Host ""
    Write-Host ("=" * 62) -ForegroundColor DarkGray
    Write-Host "[Step $n] $msg" -ForegroundColor Cyan
}
function Write-Ok([string]$msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Skip([string]$msg) { Write-Host "  [SKIP] $msg（已完成，跳过）" -ForegroundColor Yellow }
function Die([string]$msg) {
    Write-Host "  [FAIL] $msg" -ForegroundColor Red
    exit 1
}

Write-Host "MinerU 独立环境安装 -> $EnvPath" -ForegroundColor White

# ---------------------------------------------------------------- ① venv
Write-Step 1 "定位 Python 3.12 并创建独立 venv"

$pyExe = Join-Path $EnvPath "Scripts\python.exe"
if (Test-Path $pyExe) {
    Write-Skip "venv 已存在: $pyExe"
} else {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $launcher) { Die "未找到 py 启动器。请先安装 Python 3.12（勾选 py launcher）。" }

    & py -3.12 --version 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { Die "未找到 Python 3.12（py -3.12 失败）。MinerU 在 Windows 不支持 3.13，请安装 3.12.x。" }

    Write-Host "  创建 venv ..."
    & py -3.12 -m venv $EnvPath
    if ($LASTEXITCODE -ne 0) { Die "venv 创建失败: $EnvPath" }
    Write-Ok "venv 已创建"
}

& $pyExe --version | ForEach-Object { Write-Ok "解释器: $_" }

# uv 加速（②③共用）
& $pyExe -m pip install --quiet --disable-pip-version-check uv
if ($LASTEXITCODE -ne 0) { Die "uv 安装失败" }

# ------------------------------------------------- ② mineru[all]
Write-Step 2 "安装 mineru[all]$([char](0xD7))（$(if($Force){'强制重装'}else{'已装则跳过'})）"

& $pyExe -c "import mineru" 2>$null | Out-Null
$mineruInstalled = ($LASTEXITCODE -eq 0)
if ($mineruInstalled -and -not $Force) {
    Write-Skip "mineru 已安装"
} else {
    & $pyExe -m uv pip install -U "mineru[all]"
    if ($LASTEXITCODE -ne 0) { Die "mineru[all] 安装失败（检查网络/镜像源）" }
    Write-Ok "mineru[all] 就绪"
}

# ------------------------------------------- ③ CUDA torch（关键）
Write-Step 3 "覆盖安装 CUDA 12.4 版 PyTorch（否则 GPU 不生效，速度差3-15倍）"

$cudaOk = (& $pyExe -c "import torch; print(torch.cuda.is_available())" 2>$null) -eq "True"
if ($cudaOk -and -not $Force) {
    Write-Skip "CUDA 版 torch 已就绪"
} else {
    Write-Host "  下载约 2.5GB，请耐心等待 ..."
    & $pyExe -m pip install --force-reinstall torch torchvision torchaudio `
        --index-url https://download.pytorch.org/whl/cu124
    if ($LASTEXITCODE -ne 0) { Die "CUDA torch 安装失败" }
    Write-Ok "CUDA torch 已安装"
}

# --------------------------------------------------- ④ 模型下载
Write-Step 4 "ModelScope 下载解析模型（约 3-5GB，一次性；已存在则秒过）"

$cfgJson = Join-Path $env:USERPROFILE ".cache\mineru.json"
$altCfg = Join-Path $env:USERPROFILE "mineru.json"
if ((Test-Path $cfgJson) -or (Test-Path $altCfg)) {
    Write-Skip "检测到模型配置文件，如需重下请删除后重跑"
} else {
    Write-Host "  预计 10-30 分钟（取决于带宽），期间请勿中断 ..."
    & $pyExe -m mineru.cli.client --help *>$null
    # 优先 CLI 子命令；不同小版本入口名可能为 models 下载器脚本
    & $pyExe -m mineru.model.download -s modelscope -m all 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [i] 尝试备用入口 mineru-models-download ..." -ForegroundColor DarkCyan
        $dl = Join-Path $EnvPath "Scripts\mineru-models-download.exe"
        if (Test-Path $dl) {
            & $dl -s modelscope -m all
        } elseif (Get-Command mineru-models-download -ErrorAction SilentlyContinue) {
            & mineru-models-download -s modelscope -m all
        } else {
            Die "未找到模型下载器。请手动执行: $pyExe -m pip show mineru 后按官方文档下载模型。"
        }
    }
    if ($LASTEXITCODE -ne 0) { Die "模型下载失败（检查网络或改用 -s huggingface 手动重试）" }
    Write-Ok "模型就绪"
}

# ------------------------------------------------------- ⑤ 自检
Write-Step 5 "自检"

& $pyExe -c "import torch; print('torch:', torch.__version__, '| cuda:', torch.cuda.is_available())"
& $pyExe -m mineru.cli.client --version
if ($LASTEXITCODE -ne 0) { Die "mineru --version 失败" }

Write-Host ""
Write-Host "=" * 62 -ForegroundColor DarkGray
Write-Host "[DONE] 环境就绪: $pyExe" -ForegroundColor Green
Write-Host "后续动作:" -ForegroundColor White
Write-Host "  1. backend/.env 设置: MINERU_ENABLED=true / MINERU_PYTHON=$pyExe"
Write-Host "  2. 运行自检: python backend/scripts/test_mineru.py"
Write-Host "  3. 重启后端服务生效"
