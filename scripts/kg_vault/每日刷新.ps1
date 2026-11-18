# 知识图谱自生长：每日刷新（Windows 计划任务调用）
# 由 scripts/kg_vault/export_kg_vault.py 生成 Obsidian 笔记；只读数据库，不写库。
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo
$env:PYTHONIOENCODING = 'utf-8'
python scripts/kg_vault/export_kg_vault.py --user 202516001 2>&1 | Tee-Object -FilePath (Join-Path $env:TEMP 'kg_vault_last_run.log')
