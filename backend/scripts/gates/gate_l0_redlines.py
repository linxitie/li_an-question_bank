#!/usr/bin/env python3
"""L0 静态红线门禁 — 6 条 SHA256/字面量断言，秒级，无语料。

用法:
  python scripts/gate_l0_redlines.py           # 校验
  python scripts/gate_l0_redlines.py --update-baseline  # 更新基线（需人工确认）
"""
import ast
import hashlib
import json
import os
import re
import sys

BASELINE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'gates', 'L0_redlines.json')
REPO_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def sha256_file(path: str) -> str:
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def extract_function_body(filepath: str, func_name: str) -> str | None:
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return ast.get_source_segment(source, node)
    return None


def check_all() -> list[tuple[str, bool, str]]:
    results = []
    baseline_path = os.path.normpath(BASELINE_PATH)
    if not os.path.exists(baseline_path):
        return [('基线文件', False, f'{baseline_path} 不存在')]

    with open(baseline_path, 'r', encoding='utf-8') as f:
        baseline = json.load(f)

    # 1. extract_question_blocks 函数体 SHA256
    tp_path = os.path.join(REPO_ROOT, 'backend', 'app', 'services', 'text_parser.py')
    body = extract_function_body(tp_path, 'extract_question_blocks')
    if body is None:
        results.append(('extract_question_blocks 函数体', False, '函数未找到'))
    else:
        actual = sha256_text(body)
        ok = actual == baseline['extract_question_blocks_sha256']
        results.append(('extract_question_blocks 函数体', ok, f'{"PASS" if ok else "FAIL"} (len={len(body)})'))

    # 2. dispatch 块 SHA256（按内容定位，不依赖行号）
    qi_path = os.path.join(REPO_ROOT, 'backend', 'app', 'api', 'v1', 'catalog', 'question_import.py')
    with open(qi_path, 'r', encoding='utf-8') as f:
        qi_lines = f.readlines()
    # 定位 dispatch 块：查找包含 "separate_match_endpoint" 的 def 行，其上方的 if/elif 分支块
    dispatch_block = None
    for i, line in enumerate(qi_lines):
        if 'def separate_match_endpoint' in line:
            # dispatch 块在 def 之前，向上找到第一个 if/elif 行
            for j in range(i - 1, max(0, i - 30), -1):
                stripped = qi_lines[j].strip()
                if stripped.startswith('if ') or stripped.startswith('elif '):
                    # 从这个 if 行开始，取到 def 行之前
                    dispatch_block = ''.join(qi_lines[j:i])
                    break
            break
    if dispatch_block is None:
        # 回退：用基线长度定位
        dispatch_block = ''.join(qi_lines[4004:4011])
    actual = sha256_text(dispatch_block)
    ok = actual == baseline['dispatch_block_sha256']
    results.append(('dispatch 块', ok, f'{"PASS" if ok else "FAIL"} (len={len(dispatch_block)})'))

    # 3. question_import.json SHA256
    json_path = os.path.join(REPO_ROOT, '.vtj', 'files', 'question_import.json')
    actual = sha256_file(json_path)
    ok = actual == baseline['question_import_json_sha256']
    results.append(('question_import.json', ok, 'PASS' if ok else 'FAIL'))

    # 4. question_import.vue 前 493 行 SHA256
    vue_path = os.path.join(REPO_ROOT, '.vtj', 'vue', 'question_import.vue')
    with open(vue_path, 'r', encoding='utf-8') as f:
        vue_lines = f.readlines()
    template_section = ''.join(vue_lines[:493])
    actual = sha256_text(template_section)
    ok = actual == baseline['question_import_vue_template_sha256']
    results.append(('question_import.vue template 段', ok, 'PASS' if ok else 'FAIL'))

    # 5. useProvider version
    with open(vue_path, 'r', encoding='utf-8') as f:
        vue_content = f.read()
    ok = f"version: '{baseline['useprovider_version']}'" in vue_content
    results.append(('useProvider version', ok, 'PASS' if ok else 'FAIL'))

    # 6. extract_question_blocks 未被 import 到新模块
    services_dir = os.path.join(REPO_ROOT, 'backend', 'app', 'services')
    leaked = False
    for root, dirs, files in os.walk(services_dir):
        for fn in files:
            if fn.endswith('.py') and fn != 'text_parser.py':
                fp = os.path.join(root, fn)
                with open(fp, 'r', encoding='utf-8') as f:
                    content = f.read()
                if 'extract_question_blocks' in content and 'import' in content:
                    # 检查是否是 import 语句引用
                    for line in content.split('\n'):
                        if 'extract_question_blocks' in line and ('import' in line or 'from' in line):
                            leaked = True
                            break
    results.append(('extract_question_blocks 未外泄', not leaked, 'PASS' if not leaked else 'FAIL'))

    # 7. 凭据泄露扫描
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from check_secrets import check_secrets
        ok, hits, scanned = check_secrets()
        if ok:
            results.append(('凭据泄露扫描', True, f'PASS (已扫 {scanned} 个文件)'))
        else:
            detail = '; '.join(f'{r}:{l} [{rule}]' for r, l, rule, _ in hits[:3])
            if len(hits) > 3:
                detail += f' 等 {len(hits)} 处'
            results.append(('凭据泄露扫描', False, f'FAIL — {detail}'))
    except Exception as exc:
        results.append(('凭据泄露扫描', False, f'扫描器异常: {exc}'))

    return results


def main():
    if '--update-baseline' in sys.argv:
        print('⚠️  更新基线需要人工确认。请确认当前代码状态是正确的，然后按 Enter 继续...')
        input()
        # 重新计算并写入
        tp_path = os.path.join(REPO_ROOT, 'backend', 'app', 'services', 'text_parser.py')
        body = extract_function_body(tp_path, 'extract_question_blocks')
        if body is None:
            print('ERROR: extract_question_blocks 函数未找到')
            sys.exit(1)
        qi_path = os.path.join(REPO_ROOT, 'backend', 'app', 'api', 'v1', 'catalog', 'question_import.py')
        with open(qi_path, 'r', encoding='utf-8') as f:
            qi_lines = f.readlines()
        dispatch_block = None
        for i, line in enumerate(qi_lines):
            if 'def separate_match_endpoint' in line:
                for j in range(i - 1, max(0, i - 30), -1):
                    stripped = qi_lines[j].strip()
                    if stripped.startswith('if ') or stripped.startswith('elif '):
                        dispatch_block = ''.join(qi_lines[j:i])
                        break
                break
        if dispatch_block is None:
            dispatch_block = ''.join(qi_lines[4004:4011])
        json_path = os.path.join(REPO_ROOT, '.vtj', 'files', 'question_import.json')
        vue_path = os.path.join(REPO_ROOT, '.vtj', 'vue', 'question_import.vue')
        with open(vue_path, 'r', encoding='utf-8') as f:
            vue_lines = f.readlines()
        template_section = ''.join(vue_lines[:493])
        baseline = {
            'extract_question_blocks_sha256': sha256_text(body),
            'dispatch_block_sha256': sha256_text(dispatch_block),
            'question_import_json_sha256': sha256_file(json_path),
            'question_import_vue_template_sha256': sha256_text(template_section),
            'useprovider_version': '1790329880372',
            'dispatch_block_length': len(dispatch_block),
            'extract_question_blocks_length': len(body),
        }
        with open(os.path.normpath(BASELINE_PATH), 'w', encoding='utf-8') as f:
            json.dump(baseline, f, ensure_ascii=False, indent=2)
        print('基线已更新。')
        return

    results = check_all()
    all_pass = True
    for name, ok, detail in results:
        status = '✅ PASS' if ok else '❌ FAIL'
        print(f'  {status}  {name}: {detail}')
        if not ok:
            all_pass = False

    if all_pass:
        print(f'\nL0 红线门禁: 全部通过 ({len(results)}/{len(results)})')
        sys.exit(0)
    else:
        failed = sum(1 for _, ok, _ in results if not ok)
        print(f'\nL0 红线门禁: {failed}/{len(results)} 项失败')
        sys.exit(1)


if __name__ == '__main__':
    main()
