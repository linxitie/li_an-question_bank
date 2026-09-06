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
    
    # 1. 删除选项缺失的题目
    c.execute("""
        DELETE FROM question_bank 
        WHERE type_id IN (1,3,5)  -- 单选/多选/判断
        AND (options IS NULL OR options = '[]' OR options = '')
    """)
    deleted_options = c.rowcount
    print(f'删除选项缺失题目: {deleted_options}')
    
    # 2. 删除解析缺失的题目
    c.execute("""
        DELETE FROM question_bank 
        WHERE answer_analysis IS NULL OR answer_analysis = ''
    """)
    deleted_analysis = c.rowcount
    print(f'删除解析缺失题目: {deleted_analysis}')
    
    # 3. 删除含图片占位符的题目
    c.execute("""
        DELETE FROM question_bank 
        WHERE question_content LIKE '%[IMAGE:%'
    """)
    deleted_images = c.rowcount
    print(f'删除图片占位符题目: {deleted_images}')
    
    # 4. 验证删除结果
    c.execute("SELECT COUNT(*) FROM question_bank")
    remaining = c.fetchone()[0]
    print(f'剩余题目数量: {remaining}')
    
    conn.commit()
    conn.close()
    
    print(f'\n清理完成:')
    print(f'  选项缺失: {deleted_options}')
    print(f'  解析缺失: {deleted_analysis}')
    print(f'  图片占位符: {deleted_images}')
    print(f'  剩余题目: {remaining}')

if __name__ == '__main__':
    cleanup_incomplete_questions()
