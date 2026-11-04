#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PEP 649 前瞻检查：模块级函数签名里的注解/默认值，是否引用了「后面才绑定」的名字。

背景
----
Python 3.14 起注解默认惰性求值（PEP 649），因此

    from fastapi import APIRouter
    def upload(image: UploadFile = File(None)): ...
    ...
    from fastapi import UploadFile   # 迟到的导入

在 3.14 上能跑，在 3.11/3.13（CI、生产）上会在导入时 `NameError: name 'UploadFile'
is not defined`。2026-11-04 的 container-ci 就是这么红的。

本脚本用 AST 静态检查：对每个模块级函数，收集参数注解 / 返回注解 / 默认值里用到的
Name，若该名字在文件里的「最早绑定行号」晚于函数定义行，就报问题并退出码 1。

用法
----
    python backend/scripts/gates/check_eager_annotations.py            # 默认查 backend/app
    python backend/scripts/gates/check_eager_annotations.py --root backend/app

退出码：0 = 无问题；1 = 有问题。
"""
import argparse
import ast
import sys
from pathlib import Path

# typing 里的构造器名字：它们本身就在注解里用，不必判断绑定位置
TYPING_NAMES = {
    'Optional', 'List', 'Dict', 'Union', 'Tuple', 'Set', 'FrozenSet', 'Callable',
    'Type', 'Annotated', 'Sequence', 'Mapping', 'MutableMapping', 'Iterable',
    'Iterator', 'Any', 'Literal', 'ClassVar', 'Final', 'TypeVar', 'Generic',
}


def bound_positions(tree: ast.AST) -> dict[str, int]:
    """名字 -> 文件中最早绑定行号（import / 赋值 / class / def 均算绑定）"""
    pos: dict[str, int] = {}
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [(a.asname or a.name.split('.')[0]) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(a.asname or a.name) for a in node.names if a.name != '*']
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        elif isinstance(node, (ast.For, ast.comprehension)):
            pass
        for n in names:
            pos.setdefault(n, node.lineno)
    return pos


def names_in(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    return {sub.id for sub in ast.walk(node) if isinstance(sub, ast.Name)}


def check_file(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except SyntaxError as exc:  # 语法本身有问题先报出来
        return [f'{path}: 语法错误 {exc}']

    pos = bound_positions(tree)
    problems: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.col_offset != 0:      # 只看模块级函数：类方法/嵌套函数的注解在类体内求值，风险不同
            continue

        used: set[str] = set()
        for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            used |= names_in(arg.annotation)
        if node.args.vararg is not None:
            used |= names_in(node.args.vararg.annotation)
        if node.args.kwarg is not None:
            used |= names_in(node.args.kwarg.annotation)
        for default in node.args.defaults:
            used |= names_in(default)
        for default in node.args.kw_defaults:
            used |= names_in(default)
        used |= names_in(node.returns)

        for name in sorted(used):
            if name in TYPING_NAMES:
                continue
            first = pos.get(name)
            if first is not None and first > node.lineno:
                problems.append(
                    f'{path}:{node.lineno} {node.name}() 的签名用到 {name}，'
                    f'但它最早在 {first} 行才绑定（Python < 3.14 会 NameError）')
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='PEP 649 前瞻检查（惰性注解）')
    parser.add_argument(
        '--root', default=None,
        help='扫描根目录；不传时用本脚本所在仓库的 backend/app（从仓库根或 backend/ 调用都可用）')
    args = parser.parse_args(argv)

    if args.root:
        root = Path(args.root)
    else:
        # 本文件位于 <repo>/backend/scripts/gates/ → parents[2] = <repo>/backend
        root = Path(__file__).resolve().parents[2] / 'app'

    if not root.exists():
        print(f'❌ 目录不存在: {root}')
        return 1

    files = sorted(p for p in root.rglob('*.py') if '__pycache__' not in p.parts)
    total = 0
    for f in files:
        problems = check_file(f)
        for p in problems:
            print('  ' + p)
        total += len(problems)

    print(f'注解前瞻检查：扫描 {len(files)} 个文件，问题 {total} 个')
    if total:
        print('❌ 存在「注解引用后绑定名字」的写法，请把相关 import 提到文件顶部')
        return 1
    print('✅ 无「注解引用后绑定名字」问题（Python 3.11/3.13 可安全导入）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
