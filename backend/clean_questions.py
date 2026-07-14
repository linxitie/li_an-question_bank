"""
一次性脚本：清空所有已导入的题目及其关联数据
运行方式: cd backend && python clean_questions.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings
from app.core.database import engine, Base
from sqlalchemy import text

def clean_all_questions():
    with engine.begin() as conn:
        # 按依赖顺序删除（先删子表，再删主表）
        tables_to_clean = [
            "exam_answer_detail",       # 引用 question_bank
            "paper_question_relation",  # 引用 question_bank + exam_paper
            "wrong_question_personal",  # 引用 question_bank
            "wrong_question_class",     # 引用 question_bank
            "question_edit_log",        # 引用 question_bank
            "question_image",           # 引用 question_bank
            "question_import_record",   # 导入记录
        ]

        for table in tables_to_clean:
            result = conn.execute(text(f"DELETE FROM {table}"))
            print(f"  {table}: 删除 {result.rowcount} 条")

        # 最后删除题目主表
        result = conn.execute(text("DELETE FROM question_bank"))
        print(f"  question_bank: 删除 {result.rowcount} 条")

        # 同时清空 exams（考试记录引用 question_bank）
        conn.execute(text("DELETE FROM exam_record"))
        conn.execute(text("DELETE FROM score_analysis"))

        # 重置自增序列（SQLite）
        conn.execute(text("DELETE FROM sqlite_sequence"))

        print("\n全部题目及关联数据已清空。")

if __name__ == "__main__":
    print(f"数据库: {settings.DATABASE_URL}")
    confirm = input("确认删除所有题目数据？(yes/no): ")
    if confirm.lower() == "yes":
        clean_all_questions()
    else:
        print("已取消。")
