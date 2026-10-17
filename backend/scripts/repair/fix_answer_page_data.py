#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复答题卡数据：>4选项去重、<4选项补全、嵌入式选项清理、双重编码解码
"""
import sys, os, re, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..','..',  '..'))

from app.core.database import SessionLocal
from sqlalchemy import text


def extract_options_from_stem(content):
    """从题干中提取A/B/C/D选项（支持同行多选项和逐行单选项）"""
    if not content:
        return None, content

    opts = []
    # 先尝试同行多选项格式: "A.xxx    B.xxx    C.xxx    D.xxx"
    # 用split在选项标记前分割
    parts = re.split(r'(?=[A-D]\s*[.、．)）])', content)
    if len(parts) >= 5:  # 首段是题干，后面4段是选项
        stem_text = parts[0]
        for part in parts[1:5]:  # 只取前4个选项
            m = re.match(r'([A-D])\s*[.、．)）]\s*(.+)', part.strip())
            if m:
                val = re.sub(r'[;；\s]+$', '', m.group(2).strip())
                if val and len(val) > 1:
                    opts.append({'key': m.group(1).upper(), 'value': val})
        if len(opts) >= 3:
            clean = stem_text.strip()
            clean = re.sub(r'\n{3,}', '\n\n', clean)
            return opts, clean

    # 回退：逐行格式
    lines = content.split('\n')
    other = []
    for line in lines:
        m = re.match(r'^\s*([A-D])\s*[.、．)）]\s*(.+)', line)
        if m:
            val = re.sub(r'[;；\s]+$', '', m.group(2).strip())
            if val and len(val) > 1 and len(opts) < 4:
                opts.append({'key': m.group(1).upper(), 'value': val})
        else:
            other.append(line)

    if len(opts) >= 2:
        clean = '\n'.join(other).strip()
        clean = re.sub(r'\n{3,}', '\n\n', clean)
        return opts, clean

    return None, content


def detect_multi_from_content(content, answer):
    """从题干/答案检测是否多选"""
    if not content:
        return False
    if answer and len(str(answer).strip()) > 1 and str(answer).strip().isalpha():
        return True
    kw = ['多选', '不定项', '至少.*个', '两项', '2个以上', '多选题',
          '哪些', '几种', '属于.*的有', '正确的有', '错误的有']
    return any(re.search(k, content) for k in kw)


def fix_all():
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT question_id, options, question_content, answer, answer_analysis "
            "FROM question_bank WHERE status=1 ORDER BY question_id"
        )).fetchall()

        fixed_excess = 0   # >4选项去重
        fixed_short = 0    # <4选项补全
        fixed_stem = 0     # 嵌入式选项清理
        fixed_double = 0   # 双重编码解码
        fixed_nested = 0   # dict内嵌套value解码
        fixed_badtype = 0  # question_type_detail乱码修复

        for row in rows:
            qid, opts_raw, content, answer, analysis = row

            # 解析当前选项
            try:
                if isinstance(opts_raw, str):
                    opts = json.loads(opts_raw)
                    if isinstance(opts, str):
                        opts = json.loads(opts)  # 双重编码解码
                        fixed_double += 1
                else:
                    opts = opts_raw
            except Exception:
                opts = []

            if not isinstance(opts, list):
                opts = []

            changed = False

            # ---- FIX 1: >4选项去重，只保留前4个唯一key ----
            if len(opts) > 4:
                seen_keys = set()
                deduped = []
                for o in opts:
                    if isinstance(o, dict):
                        k = o.get('key', '')
                        if k not in seen_keys and len(deduped) < 4:
                            seen_keys.add(k)
                            deduped.append(o)
                if len(deduped) == 4:
                    opts = deduped
                    fixed_excess += 1
                    changed = True

            # ---- FIX 2: <4选项补全 ----
            if len(opts) < 4 and content:
                extracted, clean_content = extract_options_from_stem(content)
                if extracted and len(extracted) > len(opts):
                    existing_keys = {o.get('key', '') for o in opts if isinstance(o, dict)}
                    for e in extracted:
                        if e['key'] not in existing_keys and len(opts) < 4:
                            opts.append(e)
                    if len(opts) > len(existing_keys):
                        fixed_short += 1
                        changed = True
                    # 如果也清理了题干，更新content
                    if clean_content and clean_content != content:
                        content = clean_content
                        fixed_stem += 1

            # ---- FIX 3: 嵌入式选项清理 ----
            if content and len(opts) >= 4:
                # 只在选项完整时才清理题干中的选项行
                opt_pattern = re.compile(r'^\s*[A-D]\s*[.、．)）]\s*.+$', re.MULTILINE)
                clean_content = opt_pattern.sub('', content)
                clean_content = re.sub(r'\n{3,}', '\n\n', clean_content).strip()
                if clean_content and clean_content != content:
                    content = clean_content
                    fixed_stem += 1
                    changed = True

            # ---- FIX 4: dict内嵌套value解码（支持dict对象和字符串两种格式） ----
            for o in opts:
                if isinstance(o, dict):
                    val = o.get('value', '')
                    # 格式1: value本身是dict对象 {"key":"A","value":"..."}
                    if isinstance(val, dict):
                        real_val = val.get('value', '') or val.get('text', '') or ''
                        o['value'] = real_val if real_val else str(val)
                        fixed_nested += 1
                        changed = True
                    # 格式2: value是字符串化的dict "{'key':'A','value':'...'}"
                    elif isinstance(val, str) and val.strip()[:1] == '{':
                        try:
                            inner = json.loads(val.strip().replace("'", '"'))
                            if isinstance(inner, dict):
                                real_val = inner.get('value', '') or inner.get('text', '') or val
                                o['value'] = real_val
                                fixed_nested += 1
                                changed = True
                        except Exception:
                            pass

            # ---- FIX 6: <4选项补全（从question_content提取） ----
            if len(opts) < 4 and content:
                existing_keys = {o.get('key', '') for o in opts if isinstance(o, dict)}
                fallback_re = re.compile(
                    r'(?:^|\n)\s*([A-D])\s*[.、．)）]\s*(.+?)(?=\n\s*[A-D]\s*[.、．)）]|\n\n|$)',
                    re.DOTALL
                )
                for fm in fallback_re.finditer(content):
                    k, v = fm.group(1), fm.group(2).strip()
                    if k in {'A', 'B', 'C', 'D'} and k not in existing_keys and len(v) > 1:
                        v = re.sub(r'\s*[A-D]\s*[.、．)）]\s*.+$', '', v, flags=re.DOTALL).strip()
                        if v:
                            opts.append({'key': k, 'value': v})
                            existing_keys.add(k)
                            fixed_short += 1
                            changed = True
                            if len(opts) >= 4:
                                break

            # ---- FIX 7: 选项值中嵌入其他选项标记 → 重新分割 ----
            if len(opts) > 0 and isinstance(opts[0], dict):
                first_val = opts[0].get('value', '')
                inner_markers = re.findall(r'[A-D]\s*[.、．)）]', first_val)
                if len(inner_markers) > 1:
                    parts = re.split(r'(?=[A-D]\s*[.、．)）])', first_val)
                    new_opts = []
                    for part in parts:
                        pm = re.match(r'([A-D])\s*[.、．)）]\s*(.+)', part.strip())
                        if pm:
                            new_opts.append({'key': pm.group(1), 'value': pm.group(2).strip()})
                    if len(new_opts) >= 3:
                        opts = new_opts
                        fixed_stem += 1
                        changed = True

            # ---- 应用修改 ----
            if changed:
                clean_json = json.dumps(opts, ensure_ascii=False)
                db.execute(text(
                    "UPDATE question_bank SET options = :opts, question_content = :content "
                    "WHERE question_id = :qid"
                ), {"opts": clean_json, "content": content, "qid": qid})

        db.commit()

        # ---- FIX 5: question_type_detail 乱码修复 ----
        VALID_TYPES = {
            '单选题', '多选题', '不定项', '选择题',
            '写作题', '简答题', '案例分析题', '论述题', '无'
        }
        type_rows = db.execute(text(
            "SELECT dc.question_id, dc.question_type_detail, qb.question_content, qb.answer "
            "FROM question_detail_category dc "
            "JOIN question_bank qb ON qb.question_id = dc.question_id "
            "WHERE qb.status = 1"
        )).fetchall()

        for tr in type_rows:
            qid, type_detail, q_content, q_answer = tr
            if type_detail and type_detail not in VALID_TYPES:
                new_type = '多选题' if detect_multi_from_content(q_content, q_answer) else '单选题'
                db.execute(text(
                    "UPDATE question_detail_category SET question_type_detail = :nt "
                    "WHERE question_id = :qid"
                ), {"nt": new_type, "qid": qid})
                fixed_badtype += 1

        db.commit()

        print(f"修复完成:")
        print(f"  >4选项去重:       {fixed_excess} 题")
        print(f"  <4选项补全:       {fixed_short} 题")
        print(f"  嵌入式清理:       {fixed_stem} 题")
        print(f"  双重编码:         {fixed_double} 题")
        print(f"  嵌套value解码:    {fixed_nested} 题")
        print(f"  类型乱码修复:     {fixed_badtype} 题")
        print(f"  总计影响:         {fixed_excess + fixed_short + fixed_stem + fixed_nested + fixed_badtype} 题")
    finally:
        db.close()


if __name__ == '__main__':
    fix_all()
