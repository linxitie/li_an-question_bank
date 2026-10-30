# -*- coding: utf-8 -*-
"""存量复合题材料组修复脚本（一次性）。

背景
----
2024 申论（安徽 A/B/C）与 2025 行测的 PDF 预览里其实带着完整材料，
但当年的确认入库把材料丢了，question_bank.group_id 全是 0。
本脚本从 import_previews 的 raw_text/items 重新解析材料，按题干内容
匹配已入库题目，补建 QuestionGroup 并回填 group_id / question_level / sort_order。

安全约束
--------
1. 默认 dry-run，只打印计划，不改库、不落图片。
2. --apply 前用 sqlite3.backup() 全量备份（AGENTS.md R10）。
3. 成员必须全部匹配成功且全部 group_id=0，否则整组跳过（不制造半组）。
4. 材料建组复用导入链路的 _get_or_create_* 助手，保证去重与图片落盘规范。

用法
----
    cd backend
    python scripts/repair_composite_groups.py --import-id 1602 1606 1619 1622 1629
    python scripts/repair_composite_groups.py --all-shenlun
    python scripts/repair_composite_groups.py --all-shenlun --apply
"""
import argparse
import glob
import gzip
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from sqlalchemy import text  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.models.models import QuestionBank  # noqa: E402
from app.services.text_parser import extract_question_blocks_with_material_sets  # noqa: E402

SUBJECT_IDS = {'行测': 1, '申论': 2, '公专': 3}
PREVIEW_ROOT = os.path.join(BACKEND_DIR, 'data', 'import_previews')
_TAG_RE = re.compile(r'<[^>]+>')
_IMG_RE = re.compile(r'\[IMAGE:[^\]]+\]', re.I)
_WS_RE = re.compile(r'\s+')


@dataclass
class GroupPlan:
    import_id: int
    filename: str
    subject: str
    group_type: str
    material: str
    members: List[Tuple[dict, QuestionBank]]
    note: str = ''

    @property
    def member_ids(self) -> List[int]:
        return [int(row.question_id) for _, row in self.members]


@dataclass
class PreviewPlan:
    import_id: int
    filename: str
    subject: str
    groups: List[GroupPlan] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)


def norm_text(text: str) -> str:
    """题干/材料归一化：剥离图片标记、HTML 标签与全部空白。"""
    value = text or ''
    value = _IMG_RE.sub('', value)
    value = _TAG_RE.sub('', value)
    return _WS_RE.sub('', value)


def similarity(item_text: str, row_text: str) -> float:
    """题干相似度；DB 常在题干尾部追加“要求”，前缀命中优先。"""
    left, right = norm_text(item_text), norm_text(row_text)
    if not left or not right:
        return 0.0
    if right.startswith(left) or left.startswith(right):
        longer = max(len(left), len(right))
        return 1.0 - abs(len(left) - len(right)) / longer * 0.1
    return SequenceMatcher(None, left, right).ratio()


def load_preview(import_id: int) -> Tuple[Optional[dict], Optional[dict]]:
    pattern = os.path.join(PREVIEW_ROOT, '*', f'{import_id}.json.gz')
    paths = glob.glob(pattern)
    if not paths:
        return None, None
    with open(paths[0], 'rb') as handle:
        obj = json.loads(gzip.decompress(handle.read()).decode('utf-8'))
    if isinstance(obj, str):
        obj = json.loads(obj)
    return obj, {'path': paths[0]}


def load_import_record(db, import_id: int) -> Optional[dict]:
    row = db.execute(
        text(
            'SELECT import_id, original_filename, file_type, success_count, duplicate_count, import_status '
            'FROM question_import_record WHERE import_id=:import_id'
        ),
        {'import_id': import_id},
    ).mappings().first()
    return dict(row) if row else None


def build_row_index(db, subject_id: int) -> Dict[str, List[QuestionBank]]:
    rows = db.query(QuestionBank).filter(QuestionBank.subject_id == subject_id).all()
    index: Dict[str, List[QuestionBank]] = defaultdict(list)
    for row in rows:
        if row.question_number is not None:
            index[str(row.question_number).strip()].append(row)
    return index


def match_item(item: dict, index: Dict[str, List[QuestionBank]], year) -> Optional[QuestionBank]:
    """先按题号+年份收敛；仍有多个候选时用题干相似度消歧。

    年份已知时不再回退到其它年份（每年题号都从 1 开始，跨年会串卷）。
    唯一候选直接接受：2025 行测 q111 的 DB 题干是“资料二全文 + 首题设问”，
    与预览 item 的纯设问相似度不足 0.55，但题号+年份已足以唯一确定。
    """
    qn = str(item.get('question_number') or '').strip()
    if not qn:
        return None
    candidates = list(index.get(qn, []))
    if year is not None:
        candidates = [row for row in candidates if str(row.year) == str(year)]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    scored = sorted(((similarity(item.get('question_content') or '', row.question_content or ''), row) for row in candidates),
                    key=lambda pair: pair[0], reverse=True)
    best_score, best_row = scored[0]
    if best_score < 0.55:
        return None
    if best_score - scored[1][0] < 0.05:
        return None
    return best_row


def normalized_positions(value: str) -> List[int]:
    """返回 norm_text 每个字符在原文中的下标（跳过标签、图片标记与空白）。"""
    positions: List[int] = []
    index = 0
    length = len(value)
    while index < length:
        char = value[index]
        if char == '<':
            close = value.find('>', index)
            index = close + 1 if close >= 0 else index + 1
            continue
        image_match = _IMG_RE.match(value, index)
        if image_match:
            index = image_match.end()
            continue
        if char.isspace():
            index += 1
            continue
        positions.append(index)
        index += 1
    return positions


_SECTION_MARKER = re.compile(r'（[一二三四五六七八九十]{1,3}）')
_LEADING_IMG = re.compile(r'^\s*(?:<img\b[^>]*>\s*)+', re.I)


def strip_material_prefix(content: str, material: str) -> Tuple[str, bool]:
    """把 DB 首题题干里重复内联的材料前缀剥掉，只留设问。

    2025 行测 q106/111/116/121 入库时把“材料 + 首题设问”拼成一条题干；
    题组材料改为独立展示后若不去重，学生页会看到两遍材料。

    材料在 DB 题干中不一定位于第 0 字符：q106 前面还有“资料分析”作答说明，
    q111/q121 前面是“（二）/（四）”节标记。故先定位材料正文，再把紧邻其前的
    节标记一并切掉；图片材料（q116）norm 后为空，改按“节标记 + 前导图片”剥离。
    """
    normalized_content = norm_text(content)
    normalized_material = norm_text(material)

    if len(normalized_material) >= 20:
        offset = normalized_content.find(normalized_material)
        match_length = len(normalized_material)
        if offset < 0:
            # OCR/空白差异会让“材料正文”不是 DB 题干的严格子串；
            # 用匹配块求近似区间，覆盖 ≥70% 材料字符才认为命中。
            matcher = SequenceMatcher(None, normalized_content, normalized_material, autojunk=False)
            blocks = [block for block in matcher.get_matching_blocks() if block.size >= 4]
            if blocks:
                biggest = max(blocks, key=lambda block: block.size)
                if biggest.b <= 5 and biggest.size >= len(normalized_material) * 0.7:
                    # 只取最大连续匹配块：材料尾部若与设问用词重合，继续向后找会
                    # 把设问开头（如“2021年全国纸及纸板产量”）一起切掉。
                    offset = biggest.a
                    match_length = biggest.size
        if 0 <= offset < 120 and match_length >= 20:
            positions = normalized_positions(content)
            start_index = positions[offset]
            end_index = positions[min(offset + match_length - 1, len(positions) - 1)] + 1
            prefix = content[:start_index]
            marker = None
            for candidate in _SECTION_MARKER.finditer(prefix):
                marker = candidate
            if marker and len(prefix) - marker.end() <= 12:
                start_index = marker.start()
            remainder = (content[:start_index] + content[end_index:]).strip()
            if len(norm_text(remainder)) >= 5:
                return remainder, True
        return content, False

    # 纯图片材料：只对“（三） <img><img> 设问”这种首题形态生效。
    if '[IMAGE:' not in material and '<img' not in material:
        return content, False
    remainder = content
    marker = _SECTION_MARKER.match(remainder.lstrip())
    if marker:
        remainder = remainder.lstrip()[marker.end():]
    stripped = _LEADING_IMG.sub('', remainder)
    stripped = stripped.strip()
    if stripped != content.strip() and len(norm_text(stripped)) >= 5:
        return stripped, True
    return content, False


def material_blocks(raw_text: str) -> Dict[int, str]:
    """raw_text 重新解析：题号 -> 材料。无材料的题不会出现在结果里。"""
    result: Dict[int, str] = {}
    if not raw_text:
        return result
    try:
        blocks = extract_question_blocks_with_material_sets(raw_text)
    except Exception as exc:  # noqa: BLE001 - 单份预览解析失败不应中断整批
        print(f'  ! 解析失败: {exc}')
        return result
    for block in blocks:
        try:
            qn = int(str(block.get('question_number')).strip())
        except (TypeError, ValueError):
            continue
        material = (block.get('material_text') or '').strip()
        if material:
            result[qn] = material
    return result


def plan_shenlun(import_id: int, filename: str, items: List[dict], matched: List[Tuple[dict, QuestionBank]],
                 blocks: Dict[int, str]) -> List[GroupPlan]:
    material = ''
    for item in items:
        material = (item.get('material_text') or '').strip()
        if material:
            break
    if not material:
        for item, _row in matched:
            try:
                qn = int(str(item.get('question_number')).strip())
            except (TypeError, ValueError):
                continue
            material = blocks.get(qn, '')
            if material:
                break
    if not material or len(matched) < 2:
        return []
    return [GroupPlan(
        import_id=import_id,
        filename=filename,
        subject='申论',
        group_type='shenlun_material',
        material=material,
        members=matched,
        note='申论整卷共享材料',
    )]


def plan_xingce(import_id: int, filename: str, matched: List[Tuple[dict, QuestionBank]],
                blocks: Dict[int, str]) -> List[GroupPlan]:
    plans: List[GroupPlan] = []
    buffer: List[Tuple[dict, QuestionBank]] = []
    current_key = ''
    current_material = ''

    def flush() -> None:
        nonlocal buffer, current_key, current_material
        if len(buffer) >= 2 and current_material:
            text_key = norm_text(current_material)
            meaningful = '[IMAGE:' in current_material or len(text_key) >= 15
            if meaningful:
                group_type = 'data_analysis' if '资料' in current_material[:120] else 'material'
                plans.append(GroupPlan(
                    import_id=import_id,
                    filename=filename,
                    subject='行测',
                    group_type=group_type,
                    material=current_material,
                    members=list(buffer),
                    note=f'{buffer[0][0].get("question_number")}-{buffer[-1][0].get("question_number")}',
                ))
        buffer = []
        current_key = ''
        current_material = ''

    for item, row in matched:
        try:
            qn = int(str(item.get('question_number')).strip())
        except (TypeError, ValueError):
            continue
        material = (blocks.get(qn) or '').strip()
        key = norm_text(material)
        if material and key == current_key:
            buffer.append((item, row))
            continue
        flush()
        if material:
            current_key = key
            current_material = material
            buffer = [(item, row)]
    flush()
    return plans


def analyze_preview(db, import_id: int, year: Optional[int] = None) -> Optional[PreviewPlan]:
    preview, meta = load_preview(import_id)
    record = load_import_record(db, import_id)
    if not preview or not record:
        print(f'[{import_id}] 预览或导入记录不存在，跳过')
        return None
    items = preview.get('items') or []
    if not items:
        print(f'[{import_id}] 无 items，跳过')
        return None
    subject = str(items[0].get('subject_name') or '').strip()
    if subject not in SUBJECT_IDS:
        print(f'[{import_id}] 未知科目 {subject!r}，跳过')
        return None
    tags = preview.get('auto_detected_tags') or {}
    if year is None:
        year = tags.get('exam_year')
    index = build_row_index(db, SUBJECT_IDS[subject])
    matched: List[Tuple[dict, QuestionBank]] = []
    missing: List[str] = []
    for item in items:
        row = match_item(item, index, year)
        if row is None:
            missing.append(str(item.get('question_number')))
        else:
            matched.append((item, row))

    filename = record.get('original_filename') or f'import-{import_id}'
    plan = PreviewPlan(import_id=import_id, filename=filename, subject=subject)
    grouped = [row.question_id for _item, row in matched if int(row.group_id or 0) > 0]
    if grouped:
        plan.skipped.append(f'{len(grouped)} 题已有题组（如 {grouped[:5]}），不覆盖')
        return plan
    if len(matched) < 2:
        plan.skipped.append(f'仅匹配 {len(matched)} 题，不足以建组')
        return plan

    blocks = material_blocks(preview.get('raw_text') or '')
    if subject == '申论':
        plan.groups = plan_shenlun(import_id, filename, items, matched, blocks)
    else:
        plan.groups = plan_xingce(import_id, filename, matched, blocks)
    if missing:
        plan.skipped.append(f'未匹配题号: {",".join(missing[:20])}')
    return plan


def print_plan(plan: PreviewPlan) -> None:
    print(f'[{plan.import_id}] {plan.filename}')
    print(f'  科目={plan.subject} 计划组数={len(plan.groups)}')
    for group in plan.groups:
        strip_count = sum(1 for _item, row in group.members
                          if strip_material_prefix(row.question_content or '', group.material)[1])
        draft_count = sum(1 for _item, row in group.members
                          if int(row.status or 0) == 0 and (row.answer or '').strip())
        suffix = ''
        if strip_count:
            suffix += f' 待剥材料前缀={strip_count}题'
        if draft_count:
            suffix += f' 激活草稿={draft_count}题'
        print(f'  - {group.group_type} {group.note} 成员={group.member_ids} '
              f'材料={len(group.material)}字{suffix}')
    for reason in plan.skipped:
        print(f'  ! {reason}')


def backup_database() -> str:
    db_path = os.path.join(BACKEND_DIR, 'data', 'question_bank.db')
    backup_dir = os.path.join(BACKEND_DIR, 'data', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    target = os.path.join(backup_dir, f'question_bank_pre_composite_repair_{datetime.now():%Y%m%d_%H%M%S}.db')
    source = sqlite3.connect(db_path)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    return target


def apply_plans(db, plans: List[PreviewPlan]) -> None:
    from app.api.v1.catalog.question_import import (
        _get_or_create_group_by_material,
        _get_or_create_shenlun_material_group,
    )

    for plan in plans:
        for group in plan.groups:
            if group.subject == '申论':
                gid = _get_or_create_shenlun_material_group(db, group.material, '申论', '联考')
            else:
                gid = _get_or_create_group_by_material(
                    db, group.material, group.group_type, group.subject, '联考')
            if not gid:
                print(f'[{plan.import_id}] 建组失败，跳过 {group.member_ids}')
                continue
            activated = 0
            for order, (_item, row) in enumerate(group.members, start=1):
                stripped, changed = strip_material_prefix(row.question_content or '', group.material)
                if changed:
                    row.question_content = stripped
                # 历史草稿（status=0）若答案完整，随题组一起激活；否则保持原状。
                if int(row.status or 0) == 0 and (row.answer or '').strip():
                    row.status = 1
                    activated += 1
                row.group_id = int(gid)
                row.question_level = 1
                row.sort_order = order
            print(f'[{plan.import_id}] 已建组 #{gid} {group.group_type} 成员={group.member_ids}'
                  + (f'（激活草稿 {activated} 题）' if activated else ''))
    db.commit()


def discover_shenlun_previews() -> List[int]:
    """扫描所有带材料的申论预览，按匹配题目集合去重，返回代表 import_id。"""
    ids = []
    for path in glob.glob(os.path.join(PREVIEW_ROOT, '*', '*.json.gz')):
        import_id = os.path.basename(path).split('.')[0]
        try:
            import_id = int(import_id)
        except ValueError:
            continue
        try:
            with open(path, 'rb') as handle:
                obj = json.loads(gzip.decompress(handle.read()).decode('utf-8'))
            if isinstance(obj, str):
                obj = json.loads(obj)
        except Exception:
            continue
        items = obj.get('items') or []
        if not items or items[0].get('subject_name') != '申论':
            continue
        if any((item.get('material_text') or '').strip() for item in items):
            ids.append(import_id)
    return sorted(ids)


def main() -> int:
    parser = argparse.ArgumentParser(description='修复存量复合题材料组')
    parser.add_argument('--import-id', type=int, nargs='*', default=[], help='要修复的导入记录 ID')
    parser.add_argument('--all-shenlun', action='store_true', help='自动扫描所有带材料的申论预览')
    parser.add_argument('--apply', action='store_true', help='实际写库（默认 dry-run）')
    parser.add_argument('--skip-existing', action='store_true', default=True, help=argparse.SUPPRESS)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        ids = list(args.import_id)
        if args.all_shenlun:
            ids.extend(discover_shenlun_previews())
        ids = sorted(set(ids))
        if not ids:
            parser.error('请指定 --import-id 或 --all-shenlun')

        print(f'数据库: {engine.url}')
        plans = []
        for import_id in ids:
            plan = analyze_preview(db, import_id)
            if plan is None:
                continue
            print_plan(plan)
            if plan.groups:
                plans.append(plan)

        total_groups = sum(len(plan.groups) for plan in plans)
        total_members = sum(len(group.members) for plan in plans for group in plan.groups)
        print(f'合计: {len(plans)} 份预览 / {total_groups} 个题组 / {total_members} 道题')

        if not args.apply:
            print('DRY-RUN：未写库。确认无误后加 --apply。')
            return 0
        if not plans:
            print('没有可应用的计划。')
            return 0

        backup_path = backup_database()
        print(f'已备份: {backup_path}')
        apply_plans(db, plans)
        print('完成。')
        return 0
    finally:
        db.close()


if __name__ == '__main__':
    raise SystemExit(main())
