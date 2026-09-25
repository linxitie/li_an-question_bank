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
from app.services.question_cascade import discover_child_tables, FALLBACK_CHILD_TABLES

def clean_all_questions():
    with engine.begin() as conn:
        # 子表改为**运行时自动发现**（任何含 question_id 列的表），
        # 不再手维护清单。
        # 历史教训：手维护清单必漏表——本库实测有 14 张子表，原清单只列了 6 张，
        # 漏掉的（含带 UNIQUE 约束的 question_detail_category）在主表清空后
        # 残留孤儿行，SQLite 复用主键时导致题目批量导入整批 500（实测残留 231 条）。
        child_tables = discover_child_tables(engine)
        print(f"自动发现子表 {len(child_tables)} 张: {', '.join(child_tables)}")

        for table in child_tables:
            result = conn.execute(text(f'DELETE FROM "{table}"'))
            print(f"  {table}: 删除 {result.rowcount} 条")

        # question_import_record 不含 question_id，需单独清（导入历史）
        result = conn.execute(text("DELETE FROM question_import_record"))
        print(f"  question_import_record: 删除 {result.rowcount} 条")

        # 最后删除题目主表
        result = conn.execute(text("DELETE FROM question_bank"))
        print(f"  question_bank: 删除 {result.rowcount} 条")

        # 同时清空 exams（考试记录引用 question_bank）
        conn.execute(text("DELETE FROM exam_record"))
        conn.execute(text("DELETE FROM score_analysis"))

        # 重置自增序列（SQLite）
        conn.execute(text("DELETE FROM sqlite_sequence"))

        # 兜底自检：不应残留任何孤儿行
        left = 0
        for table in child_tables:
            try:
                n = conn.execute(text(
                    f'SELECT COUNT(*) FROM "{table}" t '
                    f'LEFT JOIN question_bank q ON q.question_id = t.question_id '
                    f'WHERE q.question_id IS NULL')).scalar()
                left += n or 0
                if n:
                    print(f"  !! {table} 仍残留 {n} 条孤儿行")
            except Exception as e:
                print(f"  (自检跳过 {table}: {e})")

        print(f"\n全部题目及关联数据已清空。孤儿行自检: {'通过(0)' if left == 0 else f'失败({left})'}")

if __name__ == "__main__":
    print(f"数据库: {settings.DATABASE_URL}")
    confirm = input("确认删除所有题目数据？(yes/no): ")
    if confirm.lower() == "yes":
        clean_all_questions()
    else:
        print("已取消。")
