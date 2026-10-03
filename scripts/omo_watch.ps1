<#
.SYNOPSIS
    启动后台任务运行状态展示器。

.DESCRIPTION
    检查前置条件后启动 omo_status.py 的 HTTP 服务，并在控制台打印访问地址。
    仅监听 127.0.0.1，不对外暴露。

.EXAMPLE
    .\scripts\omo_watch.ps1
    .\scripts\omo_watch.ps1 -Port 9601
#>
param(
    [int]$Port = 9600,
    [string]$Db = ''
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$collector = Join-Path $scriptDir 'omo_status.py'
$dashboard = Join-Path $scriptDir 'omo_dashboard.html'

# --- 前置检查 -------------------------------------------------------------
if (-not (Test-Path -LiteralPath $collector)) {
    Write-Host "[FAIL] 找不到采集器: $collector" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path -LiteralPath $dashboard)) {
    Write-Host "[WARN] 找不到面板文件: $dashboard（页面会返回 500）" -ForegroundColor Yellow
}

$python = $null
foreach ($cand in @('python', 'python3', 'py')) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if ($cmd) { $python = $cmd.Source; break }
}
if (-not $python) {
    Write-Host "[FAIL] 未找到 Python，请先安装 Python 3 并加入 PATH" -ForegroundColor Red
    exit 1
}

# --- 端口占用检查 ---------------------------------------------------------
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    Write-Host "[FAIL] 端口 $Port 已被占用（PID $($busy[0].OwningProcess)）" -ForegroundColor Red
    Write-Host "       换端口重试： .\scripts\omo_watch.ps1 -Port 9601" -ForegroundColor Yellow
    exit 1
}

# --- 数据库可达性（只读检查，不修改） -------------------------------------
$env:PYTHONIOENCODING = 'utf-8'
$probe = & $python $collector 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] 采集器自检返回非 0，但服务仍会启动，面板会显示错误" -ForegroundColor Yellow
}
if ($probe -match '"error":\s*null') {
    Write-Host "[OK] opencode.db 只读访问正常" -ForegroundColor Green
} else {
    Write-Host "[WARN] opencode.db 访问可能异常，面板会显示具体错误" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  面板地址 : http://127.0.0.1:$Port" -ForegroundColor Cyan
Write-Host "  接口地址 : http://127.0.0.1:$Port/api/status" -ForegroundColor DarkGray
Write-Host "  停止服务 : Ctrl+C" -ForegroundColor DarkGray
Write-Host ""

if ($Db) {
    & $python $collector --serve --port $Port --db $Db
} else {
    & $python $collector --serve --port $Port
}