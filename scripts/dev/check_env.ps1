<#
.SYNOPSIS
  砺安题库一键环境自检：分支 / 提交 / 两个服务的 pid 与启动时刻 / 前后端版本号 / 关键页面入口。

.DESCRIPTION
  为什么需要它：2026-11-14 出现「联考小智变成功能开发中」，实际是工作区被切到 feat/teacher-administrator
  旧分支，而界面上没有任何信号。此脚本把「我现在跑的是哪份代码」一次性摊开，避免再次凭印象误判。

.EXAMPLE
  pwsh -File scripts/dev/check_env.ps1
#>
$ErrorActionPreference = 'SilentlyContinue'
$repo = Resolve-Path (Join-Path $PSScriptRoot '../..')

function Write-Section($text) {
  Write-Host ""
  Write-Host "== $text ==" -ForegroundColor Cyan
}

Write-Section 'Git'
Push-Location $repo
$branch = (git branch --show-current) 2>$null
$head = (git log --oneline -1) 2>$null
$behind = (git rev-list --count "HEAD..origin/main") 2>$null
Write-Host ("分支      : {0}" -f $branch)
Write-Host ("HEAD      : {0}" -f $head)
Write-Host ("落后 main : {0} 个提交" -f $behind)
$dirty = (git status --porcelain) 2>$null
if ($dirty) { Write-Host ("工作区    : 有 {0} 处未提交改动" -f ($dirty | Measure-Object).Count) -ForegroundColor Yellow }
else { Write-Host "工作区    : 干净" -ForegroundColor Green }
Pop-Location

Write-Section '关键页面（入口缺失 = 旧分支）'
$pages = @(
  @{ Path = '.vtj/vue/question_bank.vue'; Pattern = "router.push('/ai-assistant')"; Name = '题库页 → 联考小智' },
  @{ Path = '.vtj/vue/question_bank.vue'; Pattern = "router.push('/study-plan')"; Name = '题库页 → 学习计划' },
  @{ Path = '.vtj/vue/ai_chat.vue'; Pattern = '联考小智'; Name = '联考小智页面' },
  @{ Path = '.vtj/vue/study_plan.vue'; Pattern = '3D学习日历'; Name = '学习计划页面' }
)
foreach ($p in $pages) {
  $full = Join-Path $repo $p.Path
  if (-not (Test-Path $full)) { Write-Host ("  ✗ {0}：文件不存在 {1}" -f $p.Name, $p.Path) -ForegroundColor Red; continue }
  $hit = Select-String -Path $full -Pattern $p.Pattern -SimpleMatch -Quiet
  if ($hit) { Write-Host ("  ✓ {0}" -f $p.Name) -ForegroundColor Green }
  else { Write-Host ("  ✗ {0}：{1} 中找不到入口" -f $p.Name, $p.Path) -ForegroundColor Red }
}

Write-Section '服务'
$ports = @(
  @{ Port = 8000; Name = '后端' },
  @{ Port = 9527; Name = '前端 vite' }
)
foreach ($p in $ports) {
  $conn = Get-NetTCPConnection -LocalPort $p.Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $conn) { Write-Host ("  ✗ {0} 端口 {1} 未监听" -f $p.Name, $p.Port) -ForegroundColor Red; continue }
  $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
  $started = if ($proc) { $proc.StartTime.ToString('yyyy-MM-dd HH:mm:ss') } else { '?' }
  Write-Host ("  ✓ {0} pid={1} 启动于 {2}" -f $p.Name, $conn.OwningProcess, $started)
}

Write-Section '版本号'
$health = try { Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 3 } catch { $null }
if ($health) { Write-Host ("  后端 revision : {0}" -f $health.revision) } else { Write-Host '  ✗ /health 不可用' -ForegroundColor Red }
$web = try { (Invoke-WebRequest -Uri 'http://127.0.0.1:9527/' -TimeoutSec 3 -UseBasicParsing).StatusCode } catch { 0 }
Write-Host ("  前端 HTTP     : {0}" -f $web)
Write-Host "  前端 SHA 请查看页面右下角构建戳（或控制台 [砺安题库] 前端构建 …）"

Write-Section '处置建议'
if ($behind -and [int]$behind -gt 0) { Write-Host '  当前分支落后 origin/main，若页面功能看起来"消失"，先确认分支是否正确。' -ForegroundColor Yellow }
Write-Host '  后端改代码不生效 → 确认启动命令带 --reload（见 docs/superpowers/specs/手机端全链路修复与增强方案_v6.0.md §1.6）'
