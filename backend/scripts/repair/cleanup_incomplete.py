#!/usr/bin/env python3
"""
清理不完整题目脚本
删除选项缺失、解析缺失、图片占位符的题目
"""
import sqlite3
import os
import sys
import shutil

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def cleanup_incomplete_questions():
    """清理不完整题目"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'question_bank.db')
    
    # 备份数据库
    backup_path = db_path + '.backup'
    if not os.path.exists(backup_path):
        shutil.copy2(db_path, backup_path)
        print(f'已备份数据库到: {backup_path}')
    else:
        print(f'备份已存在: {backup_path}')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 0. 自动发现所有引用 question_id 的子表
    #    历史教训：本脚本原先只硬删 question_bank、**一张子表都没清**，
    #    残留的孤儿行在 question_detail_category(question_id 带 UNIQUE 约束)
    #    上会于 SQLite 复用主键时导致题目批量导入整批 500。
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    all_tables = [r[0] for r in c.fetchall()]
    child_tables = []
    for t in all_tables:
        if t == 'question_bank' or t.startswith('sqlite_'):
            continue
        cols = [r[1] for r in c.execute(f'PRAGMA table_info("{t}")').fetchall()]
        if 'question_id' in cols:
            child_tables.append(t)
    print(f'自动发现子表 {len(child_tables)} 张: {", ".join(sorted(child_tables))}')

    def _delete_with_cascade(where_clause, params=()):
        """先收集待删 id → 清子表 → 删主表，避免残留孤儿行"""
        q = f'SELECT question_id FROM question_bank WHERE {where_clause}'
        ids = [r[0] for r in c.execute(q, params).fetchall()]
        if not ids:
            return 0
        marks = ','.join('?' * len(ids))
        for t in child_tables:
            c.execute(f'DELETE FROM "{t}" WHERE question_id IN ({marks})', tuple(ids))
        c.execute(f'DELETE FROM question_bank WHERE question_id IN ({marks})', tuple(ids))
        return len(ids)

    # 1. 删除选项缺失的题目
    deleted_options = _delete_with_cascade(
        "type_id IN (1,3,5) AND (options IS NULL OR options = '[]' OR options = '')"
    )
    print(f'删除选项缺失题目: {deleted_options}')

    # 2. 删除解析缺失的题目
    deleted_analysis = _delete_with_cascade(
        "answer_analysis IS NULL OR answer_analysis = ''"
    )
    print(f'删除解析缺失题目: {deleted_analysis}')

    # 3. 删除含图片占位符的题目
    deleted_images = _delete_with_cascade("question_content LIKE '%[IMAGE:%'")
    print(f'删除图片占位符题目: {deleted_images}')

    # 4. 验证删除结果 + 孤儿行自检
    c.execute("SELECT COUNT(*) FROM question_bank")
    remaining = c.fetchone()[0]
    print(f'剩余题目数量: {remaining}')

    left = 0
    for t in child_tables:
        try:
            n = c.execute(
                f'SELECT COUNT(*) FROM "{t}" x '
                f'LEFT JOIN question_bank q ON q.question_id = x.question_id '
                f'WHERE q.question_id IS NULL').fetchone()[0]
            left += n or 0
            if n:
                print(f'  !! {t} 仍残留 {n} 条孤儿行')
        except Exception as e:
            print(f'  (自检跳过 {t}: {e})')

    conn.commit()
    conn.close()

    print(f'\n清理完成:')
    print(f'  选项缺失: {deleted_options}')
    print(f'  解析缺失: {deleted_analysis}')
    print(f'  图片占位符: {deleted_images}')
    print(f'  剩余题目: {remaining}')
    print(f'  孤儿行自检: {"通过(0)" if left == 0 else f"失败({left})"}')

if __name__ == '__main__':
    cleanup_incomplete_questions()
