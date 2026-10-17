#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fix missing options in question_bank by re-extracting from question_content"""
import sys, os, re, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..','..',  '..'))

from app.core.database import SessionLocal
from sqlalchemy import text


def extract_options_from_content(content):
    """Extract A/B/C/D options from question text"""
    if not content:
        return None, content

    options = []
    # Match lines starting with A. / A、 / A．/ A) / A）followed by content
    # Use simple line-by-line approach
    lines = content.split('\n')
    opt_lines = []
    other_lines = []
    for line in lines:
        m = re.match(r'^\s*([A-H])\s*[.、．)）]\s*(.+)', line)
        if m:
            opt_lines.append((m.group(1).upper(), m.group(2).strip().rstrip(';；')))
        else:
            other_lines.append(line)

    if len(opt_lines) >= 2:
        for key, val in opt_lines:
            options.append({'key': key, 'value': val})
        clean = '\n'.join(other_lines).strip()
        clean = re.sub(r'\n{3,}', '\n\n', clean)
        return options, clean

    return None, content


def fix_options():
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT question_id, options, question_content, answer FROM question_bank "
            "WHERE status=1 AND options IS NOT NULL AND options != '[]' "
            "ORDER BY question_id"
        )).fetchall()

        fixed = 0
        for row in rows:
            qid, opts_raw, content, answer = row
            if not content:
                continue

            # Parse current options
            try:
                if isinstance(opts_raw, str):
                    opts = json.loads(opts_raw)
                    if isinstance(opts, str):
                        opts = json.loads(opts)
                else:
                    opts = opts_raw
            except Exception:
                continue

            if not isinstance(opts, list):
                continue

            # Skip if already has 4+ options
            if len(opts) >= 4:
                continue

            # Try re-extraction
            new_opts, clean = extract_options_from_content(content)
            if new_opts and len(new_opts) > len(opts):
                new_json = json.dumps(new_opts, ensure_ascii=False)
                if len(new_opts) >= 4:
                    db.execute(text(
                        "UPDATE question_bank SET options = :o, question_content = :c WHERE question_id = :q"
                    ), {"o": new_json, "c": clean, "q": qid})
                else:
                    db.execute(text(
                        "UPDATE question_bank SET options = :o WHERE question_id = :q"
                    ), {"o": new_json, "q": qid})
                fixed += 1
                print(f"  Q{qid}: {len(opts)}->{len(new_opts)} opts, ans={answer}")

        db.commit()
        print(f"\nFixed: {fixed} questions")
    finally:
        db.close()


if __name__ == '__main__':
    fix_options()
