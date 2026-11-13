# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    一键重启开发环境（后端 8001 + 前端 9527），并自检 + 自动探测手机端地址。

.DESCRIPTION
    背景：手工重启最容易踩四个坑——
      1) 前端漏设 DEV_BACKEND_ORIGIN，/api 会代理到 8000 → 全站 404「请求的资源不存在」；
      2) 端口被旧进程占用时，新进程会静默退出（ERROR: [Errno 10048]），看起来"重启了但没生效"；
      3) **PYTHONNOUSERSITE 必须清掉**：DSH/沙箱会给子进程设 `PYTHONNOUSERSITE=1`，而本项目
         后端依赖装在**用户级** site-packages（`%APPDATA%\Python\Python314\site-packages`），
         不清掉就会 `No module named uvicorn`（换成系统 Python 也一样）；
      4) **不要按端口号瞎杀**：在 DSH 里 `9527` 的监听者可能显示成 `DSH Desktop.exe`（宿主替
         子进程做端口转发），按端口杀会误杀宿主。本脚本会跳过 `DSH*` 进程，前端改按命令行
         (`npm run dev` + 本项目路径) 找自己的进程。
    固定五步：停旧进程 → 等端口释放 → 分离启动（日志落 _run/）→ 自检（health / openapi / 代理）→ 打印地址。

    手机端地址探测会**排除虚拟网卡**（VMware / VirtualBox / Hyper-V / Loopback / APIPA），
    优先取默认路由所在网卡的 IPv4，避免给出 192.168.189.1 这类连不上的地址。

.PARAMETER SkipFrontend
    只重启后端。
.PARAMETER SkipBackend
    只重启前端。
.PARAMETER BePort
    后端端口，默认 8001（本机 Docker 占了 8000）。
.PARAMETER FePort
    前端端口，默认 9527。

.EXAMPLE
    .\scripts\dev-restart.ps1
    .\scripts\dev-restart.ps1 -SkipFrontend
#>
param(
    [switch]$SkipFrontend,
    [switch]$SkipBackend,
    [int]$BePort = 8001,
    [int]$FePort = 9527
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$backend = Join-Path $repo 'backend'
$runDir = Join-Path (Split-Path -Parent $repo) '_run'
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$BE_PORT = $BePort
$FE_PORT = $FePort

function Write-Step([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

function Stop-Port([int]$port, [string]$kind) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { Write-Host "    $port 未被占用" }
    else {
        $pids = $conns.OwningProcess | Select-Object -Unique
        foreach ($procId in $pids) {
            $ci = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
            $cmd = if ($ci) { [string]$ci.CommandLine } else { '' }
            $name = if ($ci) { $ci.Name } else { 'unknown' }
            # 判断依据是**命令行**，不是进程名：
            # · 后端 uvicorn 的命令行里没有项目路径（靠工作目录），只能认 `uvicorn` + `app.main:app`；
            # · 前端 vite 被 DSH 包成 "DSH Desktop.exe ...\node_modules\.bin\vite.js"，命令行里**有**项目路径；
            # · 真正的宿主转发器两个特征都不满足 → 跳过，绝不误杀。
            $ours = if ($kind -eq 'backend') {
                $cmd -like '*uvicorn*' -and $cmd -like '*app.main:app*'
            } else {
                $cmd -like "*$repo*" -and $cmd -like '*vite*'
            }
            if (-not $ours) {
                Write-Host "    $port 的监听者 $name (PID $procId) 不是本项目进程，跳过不杀"
                continue
            }
            try {
                Write-Host "    停止 $name (PID $procId) 占用 $port"
                & "$env:SystemRoot\System32\taskkill.exe" /T /F /PID $procId 2>&1 | Out-Null
            } catch {
                Write-Host "    跳过 PID $procId（已退出或无权限）" -ForegroundColor DarkYellow
            }
        }
    }
    if ($kind -eq 'frontend') { Stop-FrontendByCmd }
}

#: 前端真正的进程：命令行里带本项目路径的 `npm run dev` / vite 链（含被宿主包了一层的情况）
function Stop-FrontendByCmd {
    $hits = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and $_.CommandLine -like "*$repo*" -and
        ($_.CommandLine -like '*npm run dev*' -or
         $_.CommandLine -like '*ENV_TYPE=local vite*' -or
         $_.CommandLine -like '*vite\bin\vite.js*' -or
         $_.CommandLine -like '*node_modules\.bin*vite*')
    }
    foreach ($h in $hits) {
        Write-Host "    停止前端进程 $($h.Name) (PID $($h.ProcessId))"
        & "$env:SystemRoot\System32\taskkill.exe" /T /F /PID $h.ProcessId 2>&1 | Out-Null
    }
}

function Wait-PortFree([int]$port, [int]$timeoutSec = 20, [switch]$Soft) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)) {
            Write-Host "    $port 已释放"; return $true
        }
        Start-Sleep -Milliseconds 400
    }
    if ($Soft) {
        Write-Host "    $port 在 ${timeoutSec}s 内未释放 —— 继续尝试启动（宿主可能仍持有转发）" -ForegroundColor DarkYellow
        return $true
    }
    Write-Host "    $port 在 ${timeoutSec}s 内未释放" -ForegroundColor Red
    return $false
}

function Wait-Http([string]$url, [int]$timeoutSec = 60) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
        } catch { }
        Start-Sleep -Milliseconds 700
    }
    return $false
}

function Get-LanIPv4 {
    # 物理网卡候选：排除虚拟/隧道/回环/APIPA，且状态为 Up
    $bad = 'VMware|VirtualBox|Hyper-V|Loopback|vEthernet|Teredo|isatap|Bluetooth|Tailscale|WSL|Docker'
    $cands = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike '127.*' -and
            $_.IPAddress -notlike '169.254.*' -and
            $_.IPAddress -ne '0.0.0.0' -and
            $_.InterfaceAlias -notmatch $bad
        }
    # 只保留私网段
    $priv = $cands | Where-Object {
        $_.IPAddress -like '10.*' -or
        $_.IPAddress -like '192.168.*' -or
        ($_.IPAddress -match '^172\.(1[6-9]|2\d|3[01])\.')
    }
    if (-not $priv) { return $null }
    # 优先默认路由所在网卡
    try {
        $route = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
            Sort-Object RouteMetric | Select-Object -First 1
        if ($route) {
            $hit = $priv | Where-Object { $_.InterfaceIndex -eq $route.InterfaceIndex }
            if ($hit) { return ($hit | Select-Object -First 1).IPAddress }
        }
    } catch { }
    return ($priv | Select-Object -First 1).IPAddress
}

Write-Step "1/5 停止旧进程"
if (-not $SkipBackend) { Stop-Port $BE_PORT 'backend' | Out-Null }
if (-not $SkipFrontend) { Stop-Port $FE_PORT 'frontend' | Out-Null }
if (-not $SkipBackend) { if (-not (Wait-PortFree $BE_PORT)) { throw "后端端口 $BE_PORT 未释放，中止" } }
if (-not $SkipFrontend) { Wait-PortFree $FE_PORT -Soft | Out-Null }

Write-Step "2/5 启动后端（$BE_PORT）"
if (-not $SkipBackend) {
    $beOut = Join-Path $runDir 'backend.out.log'
    $beErr = Join-Path $runDir 'backend.err.log'
    # 关键：清掉 PYTHONNOUSERSITE（沙箱会设成 1），否则用户级 site-packages 里的 uvicorn/fastapi 不可见
    $env:PYTHONNOUSERSITE = ''
    if (-not $env:PYTHONIOENCODING) { $env:PYTHONIOENCODING = 'utf-8' }
    # 优先用系统 Python 的绝对路径：`python` 在部分 shell 里会被沙箱垫片劫持到没有依赖的解释器
    $pyExe = 'python'
    foreach ($cand in @('C:\Python314\python.exe', "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe")) {
        if (Test-Path $cand) { $pyExe = $cand; break }
    }
    Start-Process -FilePath $pyExe `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$BE_PORT" `
        -WorkingDirectory $backend `
        -RedirectStandardOutput $beOut -RedirectStandardError $beErr `
        -WindowStyle Hidden | Out-Null
    if (-not (Wait-Http "http://127.0.0.1:$BE_PORT/health" 60)) {
        Write-Host "    后端未起来，err 日志尾部：" -ForegroundColor Red
        Get-Content $beErr -Tail 15 -ErrorAction SilentlyContinue
        throw "后端启动失败"
    }
    Write-Host "    后端 OK：http://127.0.0.1:$BE_PORT/health"
}

Write-Step "3/5 启动前端（$FE_PORT，带 DEV_BACKEND_ORIGIN）"
if (-not $SkipFrontend) {
    $env:DEV_BACKEND_ORIGIN = "http://127.0.0.1:$BE_PORT"   # 与 $BE_PORT 绑定；端口若改回非 8000 而漏这句，Vite 仍代理到 8000 → 全站 404
    $feOut = Join-Path $runDir 'vite.out.log'
    $feErr = Join-Path $runDir 'vite.err.log'
    Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', 'dev' `
        -WorkingDirectory $repo `
        -RedirectStandardOutput $feOut -RedirectStandardError $feErr `
        -WindowStyle Hidden | Out-Null
    if (-not (Wait-Http "http://localhost:$FE_PORT/" 90)) {
        Write-Host "    前端未起来，err 日志尾部：" -ForegroundColor Red
        Get-Content $feErr -Tail 15 -ErrorAction SilentlyContinue
        throw "前端启动失败"
    }
    Write-Host "    前端 OK：http://localhost:$FE_PORT/"
}

Write-Step "4/5 自检（health / openapi / api 代理）"
$checks = @()
try {
    $h = Invoke-WebRequest "http://127.0.0.1:$BE_PORT/health" -UseBasicParsing -TimeoutSec 10
    $checks += [pscustomobject]@{ 项 = '后端 /health'; 结果 = "HTTP $($h.StatusCode)" }
} catch { $checks += [pscustomobject]@{ 项 = '后端 /health'; 结果 = "失败: $($_.Exception.Message)" } }

try {
    $o = Invoke-WebRequest "http://127.0.0.1:$BE_PORT/openapi.json" -UseBasicParsing -TimeoutSec 15
    $n = ($o.Content | ConvertFrom-Json).paths.PSObject.Properties.Name.Count
    $checks += [pscustomobject]@{ 项 = 'OpenAPI 端点数'; 结果 = $n }
} catch { $checks += [pscustomobject]@{ 项 = 'OpenAPI 端点数'; 结果 = '失败' } }

if (-not $SkipFrontend) {
    try {
        $p = Invoke-WebRequest "http://localhost:$FE_PORT/api/materials?subject=xingce&type=card&page_size=1" `
            -UseBasicParsing -TimeoutSec 15
        $total = ($p.Content | ConvertFrom-Json).total
        $checks += [pscustomobject]@{ 项 = '前端 /api 代理'; 结果 = "HTTP $($p.StatusCode) total=$total" }
    } catch { $checks += [pscustomobject]@{ 项 = '前端 /api 代理'; 结果 = "失败: $($_.Exception.Message)" } }
}
$checks | Format-Table -AutoSize | Out-String | Write-Host

Write-Step "5/5 访问地址"
Write-Host ("    电脑端：http://localhost:$FE_PORT/#/")
$lan = Get-LanIPv4
if ($lan) {
    Write-Host ("    手机/平板：http://{0}:$FE_PORT/#/   （同一 Wi-Fi）" -f $lan) -ForegroundColor Green
} else {
    Write-Host "    未探测到可用的局域网 IPv4（检查网络适配器或用 ipconfig 手动确认）" -ForegroundColor DarkYellow
}

$failed = $checks | Where-Object { $_.结果 -like '*失败*' }
if ($failed) { Write-Host "`n自检存在失败项，请查看 $runDir 下日志" -ForegroundColor Red; exit 1 }
Write-Host "`n全部就绪。" -ForegroundColor Green
