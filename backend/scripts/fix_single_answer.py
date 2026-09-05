# -*- coding: utf-8 -*-
"""
修正152道答案单字母的多选题回单选题
这些题有4个选项但答案只有1个字母，应该是单选题
"""
import sqlite3
import os
import datetime
import shutil

DB_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
DB_PATH = os.path.join(DB_DIR, 'question_bank.db')
BACKUP_DIR = os.path.join(DB_DIR, 'backups')

def main():
    print('='*60)
    print('修正152道单字母答案的多选题 → 单选题')
    print('='*60)

    # 备份
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(BACKUP_DIR, f'backup_pre_fix_single_{ts}.sqlite')
    os.makedirs(BACKUP_DIR, exist_ok=True)
    shutil.copy2(DB_PATH, backup_path)
    print(f'\n数据库已备份到: {backup_path}')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 查找需要修正的题目
    cursor.execute("""
        SELECT question_id, answer, SUBSTR(question_content, 1, 40)
        FROM question_bank
        WHERE type_id = 3 AND LENGTH(answer) = 1
    """)
    to_fix = cursor.fetchall()
    print(f'\n找到 {len(to_fix)} 道需要修正的题目')

    # 修正question_bank
    cursor.execute("""
        UPDATE question_bank
        SET type_id = 1
        WHERE type_id = 3 AND LENGTH(answer) = 1
    """)
    print(f'question_bank修正: {cursor.rowcount}条 (type_id=3→1)')

    # 同步question_detail_category
    cursor.execute("""
        UPDATE question_detail_category
        SET question_type_detail = '单选题'
        WHERE question_id IN (
            SELECT question_id FROM question_bank WHERE type_id = 1
            AND question_id IN (
                SELECT question_id FROM question_bank
                WHERE type_id = 1 AND LENGTH(answer) = 1
            )
        )
    """)
    # 更简单的方式：直接用上面修正的题目ID
    fixed_ids = [r[0] for r in to_fix]
    if fixed_ids:
        placeholders = ','.join(['?' for _ in fixed_ids])
        cursor.execute(f"""
            UPDATE question_detail_category
            SET question_type_detail = '单选题'
            WHERE question_id IN ({placeholders})
        """, fixed_ids)
        print(f'question_detail_category修正: {cursor.rowcount}条')

    conn.commit()

    # 验证
    print('\n【修正后验证】')
    cursor.execute("""
        SELECT qb.type_id, qt.type_name, COUNT(*) as cnt
        FROM question_bank qb
        LEFT JOIN question_type qt ON qb.type_id = qt.type_id
        GROUP BY qb.type_id, qt.type_name
        ORDER BY qb.type_id
    """)
    total = 0
    for row in cursor.fetchall():
        print(f'  type_id={row[0]:2d} ({row[1]}): {row[2]:5d}道')
        total += row[2]
    print(f'  {"总计":20s}{total:5d}道')

    # 异常检查
    print('\n【异常检查】')
    cursor.execute("""
        SELECT COUNT(*) FROM question_bank
        WHERE type_id = 1 AND LENGTH(answer) > 1
        AND answer GLOB '[A-Z][A-Z]*'
    """)
    print(f'  单选题答案多字母: {cursor.fetchone()[0]}道')

    cursor.execute("""
        SELECT COUNT(*) FROM question_bank
        WHERE type_id = 3 AND LENGTH(answer) = 1
    """)
    print(f'  多选题答案单字母: {cursor.fetchone()[0]}道')

    conn.close()
    print('\n' + '='*60)
    print('修正完成')
    print('='*60)

if __name__ == '__main__':
    main()
