# -*- coding: utf-8 -*-
"""CI 建表冒烟（替代原 alembic upgrade head 步骤）。

本项目不使用 alembic：仓库无 alembic.ini / versions 目录，也未声明 alembic
依赖；应用启动时由 ``Base.metadata.create_all`` 自动建表（见 app/main.py）。
本脚本在内存 SQLite 上导入全部 ORM 模型并执行 create_all，校验：
  1. 模型模块可被正常导入、无映射错误；
  2. 全部已注册数据表可在空库成功创建。
不连接外部 MySQL / Redis，也不读写任何磁盘数据库文件。
"""

import sys
from pathlib import Path

# 以 backend/ 为根加入 sys.path，保证 app 包可导入
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base  # noqa: E402
from app.models import models  # noqa: E402,F401  # 副作用：把全部表注册进 Base.metadata
from sqlalchemy import create_engine  # noqa: E402


def main() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    table_count = len(Base.metadata.tables)
    print(f"[smoke] create_all 完成，已注册并建表 {table_count} 张")
    if table_count == 0:
        raise SystemExit("未注册任何数据表，模型导入可能失败")


if __name__ == "__main__":
    main()
