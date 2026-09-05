# -*- coding: utf-8 -*-
"""当前数据库状态快照"""
import sys; sys.stdout.reconfigure(encoding='utf-8')
import os; os.chdir(os.path.dirname(os.path.abspath(__file__)))
import sys; sys.path.insert(0, '.')
from sqlalchemy import text
from app.core.database import engine

with engine.connect() as c:
    for label, sql in [
        ('活跃题数', "SELECT COUNT(*) FROM question_bank WHERE is_deleted=0"),
        ('空答案', "SELECT COUNT(*) FROM question_bank WHERE is_deleted=0 AND answer IS NULL"),
        ('空答案(空串)', "SELECT COUNT(*) FROM question_bank WHERE is_deleted=0 AND answer=''"),
        ('空解析', "SELECT COUNT(*) FROM question_bank WHERE is_deleted=0 AND analysis IS NULL"),
        ('空解析(空串)', "SELECT COUNT(*) FROM question_bank WHERE is_deleted=0 AND analysis=''"),
        ('有来源', "SELECT COUNT(*) FROM question_bank WHERE is_deleted=0 AND source != '' AND source IS NOT NULL"),
        ('来源为空', "SELECT COUNT(*) FROM question_bank WHERE is_deleted=0 AND (source IS NULL OR source='')"),
        ('题组数', "SELECT COUNT(*) FROM question_groups WHERE is_active=1"),
        ('已删除', "SELECT COUNT(*) FROM question_bank WHERE is_deleted=1"),
    ]:
        print(f'{label}: {c.execute(text(sql)).scalar()}')
