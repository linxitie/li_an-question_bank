<#
.SYNOPSIS
    Liaan question-bank collaboration Git doctor: diagnose, fetch, push, bundle.

.DESCRIPTION
    Background: a teammate set the remote to
        https://mirror.ghproxy.com/https://github.com/...
    That mirror is dead, so git reported "Could not connect to server".
    Separately, direct github.com:443 is intermittently blocked on this
    network, which is why a single fixed remote can never be "stable".

    This script fixes both layers:
      * config layer  : remove dead-mirror url.insteadOf rewrites, restore origin
      * link layer    : fetch/push through a fallback chain instead of one endpoint
      * transfer layer: recommend shallow + filtered clone for this 900MB repo

    It never modifies tracked files and never force-pushes.

    ASCII-only on purpose: Windows PowerShell 5.1 decodes BOM-less UTF-8 as
    ANSI/GBK, which previously broke non-ASCII literals.

.PARAMETER Fix
    Remove url.*.insteadOf rewrites pointing at dead mirrors; reset origin to
    the canonical URL.

.PARAMETER Fetch
    Fetch through the fallback chain: canonical HTTPS -> gh-proxy -> ghfast -> SSH/443.

.PARAMETER Push
    Push the current branch through the fallback chain: canonical HTTPS -> SSH/443.

.PARAMETER SetupFallback
    Add a read-only `mirror` remote (gh-proxy) and pin origin's push URL to
    canonical, so `git fetch mirror` works even when github.com is blocked.

.PARAMETER Bundle
    Write an offline bundle containing all refs.

.PARAMETER FromBundle
    Fetch all remote-tracking refs from an offline bundle.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/dev/git-collab-doctor.ps1
    powershell -ExecutionPolicy Bypass -File scripts/dev/git-collab-doctor.ps1 -Fix -Fetch
    powershell -ExecutionPolicy Bypass -File scripts/dev/git-collab-doctor.ps1 -Push
    powershell -ExecutionPolicy Bypass -File scripts/dev/git-collab-doctor.ps1 -Bundle D:\share\liankao.bundle
#>
[CmdletBinding()]
param(
    [switch]$Fix,
    [switch]$Fetch,
    [switch]$Push,
    [switch]$SetupFallback,
    [string]$Bundle,
    [string]$FromBundle
)

$ErrorActionPreference = 'Continue'
$CanonicalUrl = 'https://github.com/linxitie/li_an-question_bank.git'
$SshUrl = 'git@ssh.github.com:linxitie/li_an-question_bank.git'
$MirrorUrls = @(
    'https://gh-proxy.com/https://github.com/linxitie/li_an-question_bank.git',
    'https://ghfast.top/https://github.com/linxitie/li_an-question_bank.git'
)
$DeadMirrorPattern = 'ghproxy|kgithub|fastgit|ghps|gitclone|moeyy|gh-proxy|ghfast'
$env:GIT_TERMINAL_PROMPT = '0'

function Write-Section([string]$Title) {
    Write-Host ''
    Write-Host ('=== ' + $Title + ' ===') -ForegroundColor Cyan
}

function Test-Endpoint([string]$TargetHost, [int]$Port = 443, [int]$TimeoutMs = 4000) {
    # Own timeout: Test-NetConnection can hang for tens of seconds on bad links.
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $task = $client.BeginConnect($TargetHost, $Port, $null, $null)
        $ok = $task.AsyncWaitHandle.WaitOne($TimeoutMs)
        if (-not $ok) { return @{ Ok = $false; Reason = 'timeout' } }
        $client.EndConnect($task)
        return @{ Ok = $true; Reason = 'open' }
    } catch {
        return @{ Ok = $false; Reason = $_.Exception.Message }
    } finally {
        $client.Close()
    }
}

function Test-HasSshKey {
    $keys = @(Get-ChildItem (Join-Path $HOME '.ssh') -Filter '*.pub' -ErrorAction SilentlyContinue)
    return ($keys.Count -gt 0)
}

function Invoke-Attempt([string]$Label, [scriptblock]$Action) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $out = & $Action 2>&1
    $code = $LASTEXITCODE
    $sw.Stop()
    $ok = ($code -eq 0)
    $colour = 'Red'
    if ($ok) { $colour = 'Green' }
    Write-Host ('  [{0}] {1} ({2:N1}s)' -f $(if ($ok) { 'ok' } else { 'fail' }), $Label, $sw.Elapsed.TotalSeconds) -ForegroundColor $colour
    if (-not $ok) {
        $out | Select-Object -Last 2 | ForEach-Object { Write-Host ('        ' + $_) -ForegroundColor DarkGray }
    }
    return @{ Ok = $ok; Out = $out }
}

# ---------- 1. repo state ----------
Write-Section '1. Repository and remote'
$root = (git rev-parse --show-toplevel 2>$null)
if (-not $root) {
    Write-Host 'Not inside a Git repository. cd to the repo root first.' -ForegroundColor Red
    exit 2
}
$branch = (git rev-parse --abbrev-ref HEAD 2>$null)
Write-Host ('repo   : ' + $root)
Write-Host ('branch : ' + $branch)
Write-Host ('HEAD   : ' + (git rev-parse --short HEAD 2>$null))

$originUrl = (git config --get remote.origin.url 2>$null)
$pushUrl = (git config --get remote.origin.pushurl 2>$null)
Write-Host ('origin : ' + $originUrl)
if ($pushUrl) { Write-Host ('pushurl: ' + $pushUrl) }
if ($originUrl -match $DeadMirrorPattern) {
    Write-Host '  [!] origin points at a mirror prefix; a dead mirror means "cannot connect".' -ForegroundColor Yellow
}
if ($originUrl -eq '') { Write-Host '  [!] no origin remote configured.' -ForegroundColor Yellow }

# ---------- 2. insteadOf rewrites ----------
Write-Section '2. url.<base>.insteadOf rewrites'
$rewrites = @()
$raw = git config --null --get-regexp 'url\..*\.insteadof' 2>$null
if ($LASTEXITCODE -eq 0 -and $raw) {
    $rewrites = @($raw -split "`0" | Where-Object { $_ -ne '' })
}
if ($rewrites.Count -eq 0) {
    Write-Host 'none (good)'
} else {
    foreach ($line in $rewrites) {
        if ($line -match $DeadMirrorPattern) {
            Write-Host ('  [x] dead mirror  ' + $line) -ForegroundColor Yellow
        } else {
            Write-Host ('  [ ] ' + $line) -ForegroundColor Gray
        }
    }
}

# ---------- 3. proxy ----------
Write-Section '3. Proxy and HTTP buffers'
foreach ($v in @('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy')) {
    $val = [Environment]::GetEnvironmentVariable($v)
    if ($val) { Write-Host ('env ' + $v + ' = ' + $val) }
}
foreach ($k in @('http.proxy', 'https.proxy', 'http.postBuffer', 'http.lowSpeedLimit', 'http.lowSpeedTime')) {
    $v = (git config --get $k 2>$null)
    if ($v) { Write-Host ('git ' + $k + ' = ' + $v) }
}

# ---------- 4. connectivity ----------
Write-Section '4. Endpoint connectivity (443, 3 samples each)'
$endpoints = @(
    @{ Name = 'github.com';          TargetHost = 'github.com' },
    @{ Name = 'ssh.github.com';      TargetHost = 'ssh.github.com' },
    @{ Name = 'gh-proxy.com';        TargetHost = 'gh-proxy.com' },
    @{ Name = 'ghfast.top';          TargetHost = 'ghfast.top' },
    @{ Name = 'mirror.ghproxy.com';  TargetHost = 'mirror.ghproxy.com' }
)
$alive = @()
foreach ($e in $endpoints) {
    $opens = 0
    $lastReason = ''
    foreach ($i in 1..3) {
        $r = Test-Endpoint -TargetHost $e.TargetHost -TimeoutMs 3000
        if ($r.Ok) { $opens++ } else { $lastReason = $r.Reason }
    }
    $line = '{0,-22} {1}/3 open' -f $e.Name, $opens
    if ($opens -gt 0) {
        $alive += $e.Name
        Write-Host $line -ForegroundColor Green
    } else {
        Write-Host ($line + '  ' + $lastReason) -ForegroundColor DarkGray
    }
}

# ---------- 5. remote readability ----------
Write-Section '5. Remote readability (git ls-remote, 30s cap)'
if ($originUrl -ne '') {
    $job = Start-Job -ScriptBlock {
        param($u)
        git ls-remote --heads $u 2>&1
    } -ArgumentList $originUrl
    if (Wait-Job $job -Timeout 30) {
        $out = Receive-Job $job
        $lines = @($out | Where-Object { $_ -match 'refs/heads/' })
        if ($lines.Count -gt 0) {
            Write-Host ('OK: remote has ' + $lines.Count + ' branches') -ForegroundColor Green
        } else {
            Write-Host 'FAILED to read remote:' -ForegroundColor Red
            $out | Select-Object -Last 3 | ForEach-Object { Write-Host ('  ' + $_) }
        }
    } else {
        Write-Host 'TIMEOUT (30s): link is slow or blocked. Run with -Fetch for the fallback chain.' -ForegroundColor Red
    }
    Remove-Job $job -Force -ErrorAction SilentlyContinue
}

# ---------- 6. repository size ----------
Write-Section '6. Repository size (what every clone/fetch must transfer)'
$gitDir = Join-Path $root '.git'
if (Test-Path $gitDir) {
    $size = (Get-ChildItem $gitDir -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    Write-Host ('.git is about {0:N0} MB' -f ($size / 1MB))
    if ($size -gt 200MB) {
        Write-Host '  [!] Heavy repo: weak links time out or get reset. Prefer a filtered clone:' -ForegroundColor Yellow
        Write-Host ('      git clone --filter=blob:none --sparse --depth 1 ' + $CanonicalUrl)
    }
}

# ---------- 7. fix ----------
if ($Fix) {
    Write-Section '7. Applying fixes'
    $fixedAny = $false
    foreach ($line in $rewrites) {
        if ($line -notmatch $DeadMirrorPattern) { continue }
        $key = ($line -split '\s+', 2)[0]
        $base = ($key -replace '^url\.', '' -replace '\.insteadof$', '')
        git config --global --unset-all ($base + '.insteadOf') 2>$null
        git config --local --unset-all ($base + '.insteadOf') 2>$null
        git config --global --remove-section ('url.' + $base) 2>$null
        Write-Host ('removed rewrite: ' + $line) -ForegroundColor Green
        $fixedAny = $true
    }
    if (-not $fixedAny) { Write-Host 'no dead-mirror rewrite to remove.' }
    if ($originUrl -match $DeadMirrorPattern) {
        git remote set-url origin $CanonicalUrl
        Write-Host ('origin reset to ' + $CanonicalUrl) -ForegroundColor Green
    }
}

# ---------- 8. fallback remote ----------
if ($SetupFallback) {
    Write-Section '8. Setting up read-only mirror fallback'
    git remote remove mirror 2>$null
    git remote add mirror $MirrorUrls[0]
    git config remote.mirror.tagopt --no-tags
    git remote set-url --push origin $CanonicalUrl
    Write-Host ('mirror -> ' + $MirrorUrls[0]) -ForegroundColor Green
    Write-Host 'origin push URL pinned to canonical (mirrors reject pushes).'
    Write-Host 'Use: git fetch mirror "+refs/heads/*:refs/remotes/origin/*" --prune'
}

# ---------- 9. fetch with fallback ----------
if ($Fetch) {
    Write-Section '9. Fetch through fallback chain'
    $done = $false
    $done = (Invoke-Attempt 'origin (canonical HTTPS)' { git fetch origin --prune }).Ok
    if (-not $done) {
        foreach ($m in $MirrorUrls) {
            if ($done) { break }
            $done = (Invoke-Attempt ('mirror ' + $m.Split('/')[2]) {
                    git fetch $m '+refs/heads/*:refs/remotes/origin/*' --prune
                }).Ok
        }
    }
    if (-not $done -and (Test-HasSshKey)) {
        $done = (Invoke-Attempt 'SSH over 443' { git fetch $SshUrl '+refs/heads/*:refs/remotes/origin/*' --prune }).Ok
    }
    if ($done) {
        Write-Host ('fetch OK; main vs origin/main: ' + ((git rev-list --left-right --count main...origin/main) -join ' / ')) -ForegroundColor Green
    } else {
        Write-Host 'all channels failed. Options:' -ForegroundColor Red
        Write-Host '  1) rerun in a few minutes (blocking is intermittent)'
        Write-Host '  2) ask the lead for an offline bundle: -FromBundle <file>'
        if (-not (Test-HasSshKey)) { Write-Host '  3) generate an SSH key and add it to GitHub: ssh-keygen -t ed25519' }
    }
}

# ---------- 10. push with fallback ----------
if ($Push) {
    Write-Section '10. Push through fallback chain'
    if ($branch -eq 'main') {
        Write-Host '  [!] pushing main directly is reserved for the lead after gates pass.' -ForegroundColor Yellow
    }
    $done = (Invoke-Attempt ('origin (canonical HTTPS), branch ' + $branch) { git push origin $branch }).Ok
    if (-not $done) {
        if (Test-HasSshKey) {
            $done = (Invoke-Attempt 'SSH over 443' { git push $SshUrl $branch }).Ok
        } else {
            Write-Host '  SSH fallback unavailable: no public key in ~/.ssh.' -ForegroundColor Yellow
            Write-Host '  Create one and register it at GitHub > Settings > SSH keys:' -ForegroundColor Yellow
            Write-Host '    ssh-keygen -t ed25519 -C "<your-name>"' -ForegroundColor Yellow
        }
    }
    if ($done) {
        Write-Host 'push OK.' -ForegroundColor Green
    } else {
        Write-Host 'push failed on every channel (mirrors are read-only by design).' -ForegroundColor Red
        Write-Host 'Export a patch and hand it over instead:' -ForegroundColor Yellow
        Write-Host ('  git format-patch origin/main --stdout > ' + $env:TEMP + '\' + $branch + '.patch')
    }
}

# ---------- 11. bundle ----------
if ($Bundle) {
    Write-Section '11. Creating offline bundle'
    $dir = Split-Path -Parent $Bundle
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    git bundle create $Bundle --all 2>&1 | Select-Object -Last 2
    if ($LASTEXITCODE -eq 0) {
        $mb = (Get-Item $Bundle).Length / 1MB
        Write-Host ('bundle written: ' + $Bundle + (' ({0:N0} MB)' -f $mb)) -ForegroundColor Green
        Write-Host 'Teammate usage: git bundle verify <file> ; git fetch <file> "refs/remotes/origin/*:refs/remotes/origin/*"'
    } else {
        Write-Host 'bundle creation FAILED.' -ForegroundColor Red
    }
}

if ($FromBundle) {
    Write-Section '11. Fetching from offline bundle'
    if (-not (Test-Path $FromBundle)) {
        Write-Host ('not found: ' + $FromBundle) -ForegroundColor Red
        exit 2
    }
    git bundle verify $FromBundle 2>&1 | Select-Object -Last 2
    git fetch $FromBundle 'refs/remotes/origin/*:refs/remotes/origin/*' 2>&1 | Select-Object -Last 3
    if ($LASTEXITCODE -eq 0) {
        Write-Host 'Remote-tracking refs updated; continue with git checkout / pull --rebase.' -ForegroundColor Green
    }
}

# ---------- 12. advice ----------
Write-Section '12. Advice'
if ($alive -contains 'github.com') {
    Write-Host '* github.com:443 reachable now. Keep origin canonical; fetch may still drop mid-transfer.'
} else {
    Write-Host '* github.com:443 is blocked right now.' -ForegroundColor Yellow
    Write-Host '  - fetch via mirror: -Fetch  (gh-proxy / ghfast), or -SetupFallback once'
    if ($alive -contains 'ssh.github.com') {
        Write-Host '  - write path: SSH over 443 works at TCP level; needs a key registered on GitHub'
        Write-Host ('    git remote set-url --push origin ' + $SshUrl)
    }
}
Write-Host '* Mirrors only proxy downloads; they can never accept a push.'
Write-Host '* Daily: -Fetch at start; one task one branch; -Push the branch; lead merges main.'
Write-Host '* Never commit: backend/data/*.db, backend/uploads/, large corpus files.'
