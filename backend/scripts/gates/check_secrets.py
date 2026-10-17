#!/usr/bin/env python3
"""凭据泄露扫描 — 供 L0 红线门禁调用，也可独立执行。

扫描 Git 已跟踪的文本文件，命中疑似密钥即失败。
只报告 文件:行号 与掩码前缀，绝不打印密钥本身。

用法:
  python scripts/check_secrets.py
  python scripts/check_secrets.py --scan-working-tree   # 连未跟踪文件一起扫
"""
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

BINARY_EXT = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.webp', '.pdf', '.zip',
    '.rar', '.7z', '.gz', '.tar', '.mp3', '.mp4', '.wav', '.woff', '.woff2',
    '.ttf', '.eot', '.db', '.sqlite', '.pyc', '.so', '.dll', '.exe',
}

# (规则名, 正则, 说明) —— 密钥本体在输出中被掩码
RULES = [
    ('OpenAI/DeepSeek 风格密钥', re.compile(r'\bsk-[A-Za-z0-9]{16,}\b')),
    ('GitHub token', re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b')),
    ('GitHub fine-grained token', re.compile(r'\bgithub_pat_[A-Za-z0-9_]{40,}\b')),
    ('AWS access key id', re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
    ('Slack token', re.compile(r'\bxox[baprs]-[A-Za-z0-9-]{10,}\b')),
    ('Google API key', re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b')),
]

# 赋值型规则。需兼容两种写法：
#   KEY=value / KEY: value            （env / yaml）
#   KEY: 类型 = Field("value")        （pydantic 声明式，须跨过类型注解与 Field( 包装）
_ASSIGN_TAIL = r'\s*(?::\s*[\w\[\], .|]+)?\s*=\s*(?:Field\(\s*)?["\']?([^\s"\',)]+)'
ASSIGN_RULES = [
    ('JWT 签名密钥', re.compile(r'^\s*(?:JWT_SECRET_KEY|SECRET_KEY)' + _ASSIGN_TAIL)),
    ('数据库口令', re.compile(r'^\s*DB_PASSWORD' + _ASSIGN_TAIL)),
    ('API 密钥字段', re.compile(r'^\s*[A-Z_]*(?:API_KEY|APIKEY|SECRET|TOKEN|PASSWORD)' + _ASSIGN_TAIL)),
    ('json apiKey', re.compile(r'"(?:apiKey|api_key|secret|password|token)"\s*:\s*"([^"]+)"')),
]

# 允许出现的非密钥值：占位符、空、示例值、环境变量引用
ALLOW_EXACT = {
    '', 'null', 'none', 'true', 'false', 'changeme', 'example', 'placeholder',
    'dummy', 'xxx', 'process.env', 'os.environ', 'os.getenv',
}
ALLOW_PREFIX = (
    '<', '${', '$', 'your-', 'your_', 'yoursecret', '*', 'xxx',
    'example', 'placeholder', 'test-key', 'test_key',
)


def is_allowed(value: str) -> bool:
    v = value.strip().strip('"\'')
    if v.lower() in ALLOW_EXACT:
        return True
    low = v.lower()
    return any(low.startswith(p) for p in ALLOW_PREFIX)

# 整体豁免文件
EXEMPT_FILES = {
    'scripts/gates/check_secrets.py',       # 本脚本含规则本身
    'backend/.env.example',           # 模板，明确标注为占位符
    'docs/superpowers/specs/2026-10-15-student-containerization-modularization-design.md',
    'docs/superpowers/plans/2026-10-15-student-containerization-implementation-plan.md',
    'solve_problems_files/学生端容器化模块化设计方案_v2.0.md',
    'solve_problems_files/学生端容器化模块化设计方案_v2.0_实施计划.md',
    'AGENTS.md',
}


def mask(value: str) -> str:
    v = value.strip().strip('"\'')
    if len(v) <= 8:
        return '*' * len(v)
    return v[:4] + '*' * (len(v) - 8) + v[-4:]


def _ignored_paths():
    """向 git 查询被忽略的文件。.env 这类文件本就存放真实凭据，
    它们被 gitignore 保护；纳入扫描会使 --scan-working-tree 永久失败。"""
    try:
        out = subprocess.run(
            ['git', 'status', '--porcelain', '--ignored=matching', '-z'],
            cwd=REPO_ROOT, capture_output=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()
    # 二进制读取：git status 输出含中文路径，text=True 会按 GBK 解码而崩溃
    paths = set()
    for entry in out.split(b'\0'):
        if not entry.strip():
            continue
        # -z 格式每条为 "XY<空格>路径"，需跳过 3 字符状态前缀。
        # 只收 '!!'（已忽略）；'??'（未跟踪）必须纳入扫描，
        # 否则未提交的草稿文件会漏检——这正是本检查要防的场景。
        text = entry.decode('utf-8', 'replace')
        if text.startswith('!!') and len(text) > 3:
            paths.add(text[3:])
    return paths


def tracked_files(scan_working_tree: bool = False):
    if not scan_working_tree:
        try:
            out = subprocess.run(['git', 'ls-files'], cwd=REPO_ROOT,
                                 capture_output=True, text=True, check=True).stdout
            return [os.path.join(REPO_ROOT, p) for p in out.splitlines() if p.strip()]
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []

    ignored = {os.path.normpath(os.path.join(REPO_ROOT, p)) for p in _ignored_paths()}
    files = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in {'.git', 'node_modules', '.worktrees', '__pycache__',
                                    'dist', '.pytest_cache', '.playwright-mcp', '.idea'}]
        for fn in filenames:
            full = os.path.normpath(os.path.join(dirpath, fn))
            if full not in ignored:
                files.append(full)
    return files


def scan_file(path: str) -> list[tuple[str, int, str]]:
    if os.path.splitext(path)[1].lower() in BINARY_EXT:
        return []
    rel = os.path.relpath(path, REPO_ROOT).replace('\\', '/')
    if rel in EXEMPT_FILES:
        return []
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            lines = fh.readlines()
    except (UnicodeDecodeError, OSError):
        return []

    hits = []
    for lineno, line in enumerate(lines, 1):
        for rule_name, pattern in RULES:
            m = pattern.search(line)
            if m:
                hits.append((rel, lineno, rule_name, mask(m.group(0))))
        for rule_name, pattern in ASSIGN_RULES:
            m = pattern.match(line)
            if m and not is_allowed(m.group(1)):
                hits.append((rel, lineno, rule_name, mask(m.group(1))))
    return hits


def check_secrets(scan_working_tree: bool = False):
    """返回 (是否通过, 命中列表)。命中元素为 (文件, 行号, 规则, 掩码值)。"""
    all_hits = []
    files = tracked_files(scan_working_tree)
    for path in files:
        all_hits.extend(scan_file(path))
    return (not all_hits), all_hits, len(files)


def main():
    scan_wt = '--scan-working-tree' in sys.argv
    ok, hits, scanned = check_secrets(scan_wt)
    mode = '工作区全量' if scan_wt else 'Git 已跟踪'
    print(f'  已扫描 {mode}文件 {scanned} 个')
    if ok:
        print('  ✅ PASS  无疑似凭据')
        sys.exit(0)
    print(f'  ❌ FAIL  命中 {len(hits)} 处疑似凭据：')
    for rel, lineno, rule, masked in hits:
        print(f'      {rel}:{lineno}  [{rule}]  {masked}')
    print('\n  处置：将真实值移入 .env（已 gitignore），仓库内只保留占位符。')
    print('  真实密钥必须轮换——清理文件不能撤销已泄露的密钥。')
    sys.exit(1)


if __name__ == '__main__':
    main()
