# -*- coding: utf-8 -*-
"""
题型合并与修正脚本
1. 将ID=971,981的单选题修正为多选题
2. 将type_id=4的349道多选题合并到type_id=3
3. 同步更新question_detail_category表
4. 清理未使用的题型定义
"""
import sqlite3
import os
import datetime
import shutil

DB_DIR = os.path.join(os.path.dirname(__file__), '..','..',  '..', 'data')
DB_PATH = os.path.join(DB_DIR, 'question_bank.db')
BACKUP_DIR = os.path.join(DB_DIR, 'backups')

def backup_db():
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(BACKUP_DIR, f'backup_pre_merge_{ts}.sqlite')
    os.makedirs(BACKUP_DIR, exist_ok=True)
    shutil.copy2(DB_PATH, backup_path)
    print(f'  数据库已备份到: {backup_path}')
    return backup_path

def main():
    print('='*60)
    print('题型合并与修正')
    print('='*60)

    # 备份
    print('\n【步骤1: 备份数据库】')
    backup_db()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 修正ID=971,981
    print('\n【步骤2: 修正ID=971,981为多选题】')
    cursor.execute("""
        UPDATE question_bank
        SET type_id = 3
        WHERE question_id IN (971, 981)
    """)
    print(f'  question_bank修正: {cursor.rowcount}条')

    # 同步question_detail_category（列名是 question_type_detail 不是 type_name）
    cursor.execute("""
        UPDATE question_detail_category
        SET question_type_detail = '多选题'
        WHERE question_id IN (971, 981)
    """)
    print(f'  question_detail_category修正: {cursor.rowcount}条')

    # 合并type_id=4到type_id=3
    print('\n【步骤3: 合并type_id=4到type_id=3】')
    cursor.execute("SELECT COUNT(*) FROM question_bank WHERE type_id = 4")
    count_4 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM question_bank WHERE type_id = 3")
    count_3_before = cursor.fetchone()[0]

    cursor.execute("UPDATE question_bank SET type_id = 3 WHERE type_id = 4")
    print(f'  question_bank合并: {cursor.rowcount}条 (type_id=4 → 3)')

    cursor.execute("""
        UPDATE question_detail_category
        SET question_type_detail = '多选题'
        WHERE question_id IN (
            SELECT question_id FROM question_bank WHERE type_id = 3
        )
    """)
    print(f'  question_detail_category同步: {cursor.rowcount}条')

    cursor.execute("SELECT COUNT(*) FROM question_bank WHERE type_id = 3")
    count_3_after = cursor.fetchone()[0]
    print(f'  type_id=3: {count_3_before}道 → {count_3_after}道')

    # 清理未使用题型
    print('\n【步骤4: 清理未使用题型】')
    cursor.execute("SELECT type_id, type_name FROM question_type WHERE type_id IN (5, 6)")
    unused = cursor.fetchall()
    if unused:
        for row in unused:
            print(f'  删除 type_id={row[0]} ("{row[1]}")')
        cursor.execute("DELETE FROM question_type WHERE type_id IN (5, 6)")
        print(f'  已删除 {cursor.rowcount} 条未使用题型定义')

    # 提交
    conn.commit()
    print('\n【提交事务完成】')

    # 最终验证
    print('\n【最终验证】')
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

    # 验证异常
    print('\n【异常检查】')
    cursor.execute("""
        SELECT COUNT(*) FROM question_bank qb
        WHERE qb.type_id = 1 AND LENGTH(qb.answer) > 1
        AND qb.answer GLOB '[A-Z][A-Z]*'
    """)
    bad_single = cursor.fetchone()[0]
    print(f'  单选题答案多字母: {bad_single}道')

    cursor.execute("""
        SELECT COUNT(*) FROM question_bank qb
        WHERE qb.type_id = 3 AND LENGTH(qb.answer) = 1
    """)
    bad_multi = cursor.fetchone()[0]
    print(f'  多选题答案单字母: {bad_multi}道')

    conn.close()
    print('\n' + '='*60)
    print('合并完成')
    print('='*60)

if __name__ == '__main__':
    main()
