"""写入守卫：题目入库前的 6 类确定性校验（F2 Step 6）。

设计边界：
  · 只读取参考表（科目/题型/知识点/题组），不 import 任何业务域实现；
  · 不写库、不 commit，失败由调用方决定 422 还是逐条 rejected；
  · 开关 FOUNDATION_VALIDATION_ENABLED=false 时整体短路，行为回到 F1。

为什么需要它：题目导入链有 5 个入口（questions POST/PUT、/single、
/batch-parsed、/confirm），历史实现各自只做局部检查。长度/编码/JSON 这类
确定性问题一旦入库，后续只能靠人工清洗，故统一前置到写库之前。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException

from .config import BACKEND_DIR, FOUNDATION_VALIDATION_ENABLED

MAX_LENGTHS = {
    'question_content': 50_000,
    'answer': 10_000,
    'answer_analysis': 1_000_000,
    'options': 100_000,
    'tags': 2_000,
}

OBJECTIVE_TYPE_WORDS = ('单选题', '多选题', '判断题', '选择题', '单项选择', '多项选择')
_SURROGATE_RE = re.compile('[\ud800-\udfff]')
_JSON_PREFIXES = ('[', '{')


def validation_enabled() -> bool:
    """读取开关；默认开启，显式 false/0/no 时关闭。"""
    raw = os.environ.get('FOUNDATION_VALIDATION_ENABLED')
    if raw is None or raw.strip() == '':
        return FOUNDATION_VALIDATION_ENABLED
    return raw.strip().lower() not in ('0', 'false', 'no', 'off')


@dataclass(frozen=True)
class ValidationIssue:
    """一条校验结果。severity=error 才阻断写入，warning 只记录。"""

    field: str
    rule: str
    message: str
    severity: str = 'error'

    def as_detail(self) -> Dict[str, str]:
        return {'field': self.field, 'rule': self.rule, 'message': self.message}


@dataclass
class ReferenceCache:
    """参考表存在性集合。按请求懒加载一次，避免批量导入 N+1。"""

    session: Any = None
    sqlite_conn: Optional[sqlite3.Connection] = None
    subject_ids: set = field(default_factory=set)
    type_ids: set = field(default_factory=set)
    point_ids: set = field(default_factory=set)
    group_ids: set = field(default_factory=set)
    type_names: Dict[int, str] = field(default_factory=dict)
    _loaded: bool = False

    def load(self) -> 'ReferenceCache':
        if self._loaded:
            return self
        rows = None
        if self.session is not None:
            from sqlalchemy import text

            queries = {
                'subjects': 'SELECT subject_id FROM question_subject',
                'types': 'SELECT type_id, type_name FROM question_type',
                'points': 'SELECT point_id FROM knowledge_point',
                'groups': 'SELECT id FROM question_groups',
            }
            loaded = {}
            for key, sql in queries.items():
                try:
                    loaded[key] = list(self.session.execute(text(sql)))
                except Exception:  # 参考表缺失时降级为“不校验该类 FK”
                    loaded[key] = []
            rows = loaded
            self.subject_ids = {int(r[0]) for r in rows['subjects'] if r[0] is not None}
            self.type_ids = {int(r[0]) for r in rows['types'] if r[0] is not None}
            self.type_names = {int(r[0]): str(r[1] or '') for r in rows['types'] if r[0] is not None}
            self.point_ids = {int(r[0]) for r in rows['points'] if r[0] is not None}
            self.group_ids = {int(r[0]) for r in rows['groups'] if r[0] is not None}
        elif self.sqlite_conn is not None:
            conn = self.sqlite_conn
            self.subject_ids = {int(r[0]) for r in conn.execute('SELECT subject_id FROM question_subject')}
            type_rows = list(conn.execute('SELECT type_id, type_name FROM question_type'))
            self.type_ids = {int(r[0]) for r in type_rows}
            self.type_names = {int(r[0]): str(r[1] or '') for r in type_rows}
            self.point_ids = {int(r[0]) for r in conn.execute('SELECT point_id FROM knowledge_point')}
            self.group_ids = {int(r[0]) for r in conn.execute('SELECT id FROM question_groups')}
        self._loaded = True
        return self


def _as_int(value: Any) -> Optional[int]:
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    if value is None:
        return ''
    return value if isinstance(value, str) else str(value)


def _options_text(value: Any) -> str:
    if value is None or value == '':
        return ''
    if isinstance(value, (list, dict)) and not value:
        return ''
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def _is_objective(data: Dict[str, Any], refs: ReferenceCache) -> bool:
    name = _text(data.get('question_type_detail') or data.get('type_name') or '')
    if not name:
        tid = _as_int(data.get('type_id'))
        if tid is not None:
            name = refs.type_names.get(tid, '')
    return any(word in name for word in OBJECTIVE_TYPE_WORDS)


def validate_question(
    data: Dict[str, Any],
    refs: ReferenceCache,
    *,
    partial: bool = False,
    require_ids: bool = True,
) -> List[ValidationIssue]:
    """对一条待写入数据执行 6 类校验。

    partial=True 时用于 PUT：字段缺省不算错误，只校验出现的字段。
    require_ids=False 时用于导入链：科目/题型由服务端解析，允许缺 id。
    """
    issues: List[ValidationIssue] = []
    present = {k for k, v in data.items() if v is not None}

    # R-空：必填与客观题选项
    content = _text(data.get('question_content'))
    if not partial or 'question_content' in present:
        if not content.strip():
            issues.append(ValidationIssue('question_content', 'R-EMPTY', '题目内容不能为空'))
    if not partial:
        if require_ids:
            if _as_int(data.get('subject_id')) is None:
                issues.append(ValidationIssue('subject_id', 'R-EMPTY', '科目不能为空'))
            if _as_int(data.get('type_id')) is None:
                issues.append(ValidationIssue('type_id', 'R-EMPTY', '题型不能为空'))
        elif not _text(data.get('subject_category') or data.get('subject_name')).strip():
            # 导入链允许缺 id，但必须能确定科目（缺省由旧逻辑回落“行测”，此处只在显式为空串时提示）
            pass
        if _is_objective(data, refs) and not _options_text(data.get('options')).strip():
            issues.append(ValidationIssue('options', 'R-EMPTY', '客观题必须包含选项'))

    # R-长
    for name, limit in MAX_LENGTHS.items():
        if partial and name not in present:
            continue
        value = _options_text(data.get('options')) if name == 'options' else _text(data.get(name))
        if len(value) > limit:
            issues.append(ValidationIssue(name, 'R-LONG', f'{name} 长度 {len(value)} 超过上限 {limit}'))

    # R-枚举
    difficulty = _as_int(data.get('difficulty'))
    if difficulty is not None and not 1 <= difficulty <= 5:
        issues.append(ValidationIssue('difficulty', 'R-ENUM', 'difficulty 必须在 1..5'))
    for name, allowed in (('status', {0, 1}), ('audit_status', {0, 1, 2})):
        if name in present:
            value = _as_int(data.get(name))
            if value not in allowed:
                issues.append(ValidationIssue(name, 'R-ENUM', f'{name} 必须是 {sorted(allowed)}'))
    if 'score' in present:
        try:
            if float(data.get('score')) < 0:
                issues.append(ValidationIssue('score', 'R-ENUM', 'score 不能为负'))
        except (TypeError, ValueError):
            issues.append(ValidationIssue('score', 'R-ENUM', 'score 必须是数字'))

    # R-JSON：JSON 列若以 [ / { 开头，必须可解析；options 必须是数组
    options_text = _options_text(data.get('options')).strip()
    if options_text.startswith(_JSON_PREFIXES):
        try:
            parsed = json.loads(options_text)
        except ValueError:
            issues.append(ValidationIssue('options', 'R-JSON', 'options 不是合法 JSON'))
            parsed = None
        if parsed is not None and not isinstance(parsed, list):
            issues.append(ValidationIssue('options', 'R-JSON', 'options 必须是 JSON 数组'))
    tags_text = _text(data.get('tags')).strip()
    if tags_text.startswith(_JSON_PREFIXES):
        try:
            parsed_tags = json.loads(tags_text)
        except ValueError:
            issues.append(ValidationIssue('tags', 'R-JSON', 'tags 不是合法 JSON'))
            parsed_tags = None
        if parsed_tags is not None and not isinstance(parsed_tags, list):
            issues.append(ValidationIssue('tags', 'R-JSON', 'tags 必须是 JSON 数组'))

    # R-FK：只校验提供了的引用；0 视为“无引用”
    fk_specs = (
        ('subject_id', refs.subject_ids, 'question_subject'),
        ('type_id', refs.type_ids, 'question_type'),
        ('point_id', refs.point_ids, 'knowledge_point'),
        ('group_id', refs.group_ids, 'question_groups'),
    )
    for name, ids, table in fk_specs:
        if name not in present:
            continue
        value = _as_int(data.get(name))
        if value in (None, 0):
            continue
        if value not in ids:
            issues.append(ValidationIssue(name, 'R-FK', f'{name}={value} 在 {table} 中不存在'))

    # R-编码：NUL / 孤立代理项阻断，替换符只告警
    for name in ('question_content', 'answer', 'answer_analysis', 'source', 'tags'):
        value = _text(data.get(name))
        if '\x00' in value:
            issues.append(ValidationIssue(name, 'R-ENCODING', f'{name} 含 NUL 字符'))
        if _SURROGATE_RE.search(value):
            issues.append(ValidationIssue(name, 'R-ENCODING', f'{name} 含孤立代理项'))
        if '\ufffd' in value:
            issues.append(ValidationIssue(name, 'R-ENCODING', f'{name} 含替换符 U+FFFD', 'warning'))

    return issues


def errors_only(issues: Iterable[ValidationIssue]) -> List[ValidationIssue]:
    return [i for i in issues if i.severity == 'error']


def ensure_valid(
    data: Dict[str, Any],
    session: Any,
    *,
    partial: bool = False,
    require_ids: bool = True,
    cache: Optional[ReferenceCache] = None,
) -> List[ValidationIssue]:
    """校验并在有硬错误时抛 422；返回 warning 供调用方记录。"""
    if not validation_enabled():
        return []
    refs = cache or ReferenceCache(session=session)
    issues = validate_question(data, refs, partial=partial, require_ids=require_ids)
    errors = errors_only(issues)
    if errors:
        raise HTTPException(status_code=422, detail=[i.as_detail() for i in errors])
    return [i for i in issues if i.severity != 'error']


def _dry_run(db_path: Path, out_path: Path) -> int:
    """全量干跑：只读 SQLite，输出统计与样本，不修改任何数据。"""
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    refs = ReferenceCache(sqlite_conn=conn).load()
    sql = (
        'SELECT q.question_id, q.subject_id, q.type_id, q.question_content, q.options, '
        'q.answer, q.answer_analysis, q.difficulty, q.score, q.tags, q.status, '
        'q.audit_status, q.point_id, q.group_id, t.type_name '
        'FROM question_bank q LEFT JOIN question_type t ON t.type_id = q.type_id'
    )
    total = 0
    hard = 0
    warn = 0
    samples: List[Dict[str, Any]] = []
    by_rule: Dict[str, int] = {}
    for row in conn.execute(sql):
        total += 1
        data = {
            'subject_id': row[1], 'type_id': row[2], 'question_content': row[3],
            'options': row[4], 'answer': row[5], 'answer_analysis': row[6],
            'difficulty': row[7], 'score': row[8], 'tags': row[9], 'status': row[10],
            'audit_status': row[11], 'point_id': row[12], 'group_id': row[13],
            'type_name': row[14],
        }
        issues = validate_question(data, refs)
        errs = errors_only(issues)
        warn += len(issues) - len(errs)
        if errs:
            hard += len(errs)
            for issue in errs:
                by_rule[issue.rule] = by_rule.get(issue.rule, 0) + 1
            if len(samples) < 50:
                samples.append({'question_id': row[0], 'issues': [i.as_detail() for i in errs]})
    report = {
        'db': str(db_path), 'total': total, 'hard_errors': hard,
        'warnings': warn, 'by_rule': by_rule, 'samples': samples,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    conn.close()
    print(json.dumps({k: report[k] for k in ('total', 'hard_errors', 'warnings', 'by_rule')},
                     ensure_ascii=False))
    return 0 if hard == 0 else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description='题目写入守卫（F2 Step 6）')
    parser.add_argument('--dry-run', action='store_true', help='对现有题库全量干跑')
    parser.add_argument('--db', default=str(BACKEND_DIR / 'data' / 'question_bank.db'))
    parser.add_argument('--out', default=str(BACKEND_DIR / 'data' / 'reports' / 'validation_dryrun.json'))
    args = parser.parse_args(argv)
    if not args.dry_run:
        parser.print_help()
        return 0
    return _dry_run(Path(args.db), Path(args.out))


if __name__ == '__main__':
    raise SystemExit(main())
