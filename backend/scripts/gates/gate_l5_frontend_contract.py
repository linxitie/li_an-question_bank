#!/usr/bin/env python3
"""L5 前端数据契约门禁 — 必需标识符 + RC-2 反向守卫"""
import os, sys, re

VUE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.vtj', 'vue', 'question_import.vue')

def main():
    with open(VUE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # 正向：必需标识符
    required = ['handleFetchError', '_uploadAndPoll', '_pollImportStatus', 'blocked', 'block_reasons']
    missing = [r for r in required if r not in content]

    # 反向守卫（RC-2）：按钮计数不得直接读 batchPreviewData.length
    # 只检查 script 段（行号 > 493），排除 template 和注释
    violations = []
    for i, line in enumerate(content.split('\n'), 1):
        if i <= 493:
            continue  # template 段，不可改
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('*'):
            continue  # 注释行
        if 'batchPreviewData.length' in line and 'pendingQuestions' not in line:
            violations.append(f'  行 {i}: {stripped[:80]}')

    if missing:
        print(f'L5 FAIL: 缺少必需标识符 {missing}')
    if violations:
        print(f'L5 FAIL: RC-2 反向守卫触发（{len(violations)} 处违规）:')
        for v in violations:
            print(v)

    if missing or violations:
        sys.exit(1)
    else:
        print(f'L5 前端数据契约: PASS（{len(required)} 个必需标识符存在，0 处 RC-2 违规）')
        sys.exit(0)

if __name__ == '__main__':
    main()
