# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    推送 main 到 GitHub，自动绕过被墙的 DNS 解析（curloptResolve）。

.DESCRIPTION
    背景：本机 DNS 经常把 github.com 解析到 20.205.243.166，而该 IP 的 443 被黑洞，
    表现是 push/fetch 卡 21 秒后报 "Failed to connect to github.com port 443"。
    同一时刻 140.82.113.3 / 140.82.112.3 / 20.27.177.113 却是通的。

    本脚本流程：
      1) 先试一次普通 push（DNS 正常时最快）；
      2) 失败则逐个测试候选 IP 的 443 连通性；
      3) 用第一个可达 IP 执行 `git -c http.curloptResolve=... push`；
      4) 推送前自动 fetch，若远端领先则提示（默认不自动合并，避免隐式改动）。

.PARAMETER Merge
    远端领先时自动 merge origin/main（无冲突才继续推送）。
.PARAMETER ForceIp
    跳过普通 push，强制走 IP 覆盖（用于验证回退链路）。
.PARAMETER Message
    合并提交信息（默认自动生成）。
.PARAMETER Remote
    远端名，默认 origin。
.PARAMETER Branch
    分支名，默认 main。

.EXAMPLE
    .\scripts\push-main.ps1

.EXAMPLE
    .\scripts\push-main.ps1 -Merge
#>
param(
    [switch]$Merge,
    [switch]$ForceIp,
    [string]$Message = "",
    [string]$Remote = "origin",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$CandidateIps = @(
    "140.82.113.3",
    "140.82.112.3",
    "140.82.114.3",
    "20.27.177.113",
    "20.205.243.166"
)

function Write-Step([string]$text) {
    Write-Host ""
    Write-Host "== $text ==" -ForegroundColor Cyan
}

function Write-Ok([string]$text) { Write-Host "   ✓ $text" -ForegroundColor Green }
function Write-Warn2([string]$text) { Write-Host "   ! $text" -ForegroundColor Yellow }
function Write-Err2([string]$text) { Write-Host "   × $text" -ForegroundColor Red }

function Test-IpPort([string]$ip, [int]$port = 443, [int]$timeoutMs = 3000) {
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $task = $client.ConnectAsync($ip, $port)
        if (-not $task.Wait($timeoutMs)) { $client.Dispose(); return $false }
        $ok = $client.Connected
        $client.Dispose()
        return $ok
    } catch {
        return $false
    }
}

function Invoke-Git([string[]]$arguments, [string]$resolveIp = "") {
    $base = @("git")
    if ($resolveIp) {
        $base += @("-c", "http.curloptResolve=github.com:443:$resolveIp")
    }
    $all = $base + $arguments

    # 关键：git 会把进度/提示写到 stderr；在 $ErrorActionPreference='Stop' 下
    # 这些会被当成终止错误（"To https://github.com/..."），导致脚本误判失败。
    # 这里临时改成 Continue，只以退出码判断成败。
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $output = & $all[0] $all[1..($all.Length - 1)] 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    return @{ Code = $code; Output = ($output | Out-String) }
}

# ---------- 0. 预检 ----------
Write-Step "预检"

$branchNow = (& git rev-parse --abbrev-ref HEAD 2>$null | Out-String).Trim()
if ($branchNow -ne $Branch) {
    Write-Err2 "当前分支是 '$branchNow'，脚本只推送 '$Branch'。请先切换或改参数：-Branch $branchNow"
    exit 1
}
Write-Ok "分支 $Branch"

$dirty = (& git status --porcelain 2>$null | Out-String).Trim()
if ($dirty) {
    Write-Err2 "工作区有未提交改动，先提交再推送："
    Write-Host $dirty
    exit 1
}
Write-Ok "工作区干净"

# ---------- 1. 普通 push ----------
if ($ForceIp) {
    Write-Warn2 "已指定 -ForceIp，跳过普通 push，直接走 IP 覆盖"
} else {
    Write-Step "尝试普通 push（DNS 正常时最快）"
    $plain = Invoke-Git @("push", $Remote, $Branch)
    if ($plain.Code -eq 0) {
        Write-Ok "推送成功（未使用 IP 覆盖）"
        Write-Host $plain.Output
        exit 0
    }
    Write-Warn2 "普通 push 失败（多为 DNS 解析到被墙 IP，属已知问题）"
}

# ---------- 2. 探测可用 IP ----------
Write-Step "探测 GitHub 可用 IP（443 连通性）"
$usefulIp = $null
foreach ($ip in $CandidateIps) {
    $ok = Test-IpPort $ip
    if ($ok) {
        Write-Ok "$ip 可达"
        if (-not $usefulIp) { $usefulIp = $ip }
    } else {
        Write-Warn2 "$ip 不可达"
    }
}

if (-not $usefulIp) {
    Write-Err2 "所有候选 IP 都不通。可能是本机网络中断（而非 DNS 问题）。"
    Write-Host "   可选排查："
    Write-Host "     1) 浏览器打开 https://gitee.com 确认整体网络"
    Write-Host "     2) 若开了代理，设置：git config --global http.proxy http://127.0.0.1:端口"
    exit 1
}
Write-Ok "使用 IP：$usefulIp"

# ---------- 3. fetch 并检查是否落后 ----------
Write-Step "同步远端状态"
$fetch = Invoke-Git @("fetch", $Remote) $usefulIp
if ($fetch.Code -ne 0) {
    Write-Err2 "fetch 失败："
    Write-Host $fetch.Output
    exit 1
}
Write-Ok "fetch 成功"

$counts = (& git rev-list --left-right --count "$Remote/$Branch...HEAD" | Out-String).Trim() -split "\s+"
$behind = [int]$counts[0]
$ahead = [int]$counts[1]
Write-Host "   落后远端 $behind 个提交，领先 $ahead 个提交"

if ($behind -gt 0) {
    if ($Merge) {
        Write-Step "合并 $Remote/$Branch（-$behind 个提交）"
        $msg = if ($Message) { $Message } else { "merge: 同步 $Remote/$Branch（$behind 个提交）" }
        $mergeResult = Invoke-Git @("merge", "--no-ff", "$Remote/$Branch", "-m", $msg)
        if ($mergeResult.Code -ne 0) {
            Write-Err2 "合并失败（可能有冲突），请手动解决："
            Write-Host $mergeResult.Output
            exit 1
        }
        Write-Ok "合并完成"
    } else {
        Write-Warn2 "远端领先 $behind 个提交，直接推会被拒。"
        Write-Host "   处理方式：重新执行并加 -Merge   （例：.\scripts\push-main.ps1 -Merge）"
        exit 2
    }
}

if ($ahead -eq 0 -and $behind -eq 0) {
    Write-Ok "本地与远端已一致，无需推送"
    exit 0
}

# ---------- 4. 用可用 IP 推送 ----------
Write-Step "推送（IP 覆盖）"
$push = Invoke-Git @("push", $Remote, $Branch) $usefulIp
if ($push.Code -eq 0) {
    Write-Ok "推送成功"
    Write-Host $push.Output
    exit 0
}

Write-Err2 "推送失败："
Write-Host $push.Output
Write-Host "   若刚合并过，可能是远端又更新了，重跑本脚本即可。"
exit 1
