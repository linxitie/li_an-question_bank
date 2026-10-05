# 公安联考题库系统 - FastAPI 后端服务

> ⚠️ **本文档已重写（2026-10-04）**。旧版声称 MySQL 8.0 + Redis + `routers/` 目录结构，与实际不符，已废弃。

## 技术栈

- **框架**: FastAPI + Uvicorn
- **数据库**: SQLite（WAL 模式），路径 `./data/question_bank.db`
- **ORM**: SQLAlchemy 2.0
- **认证**: JWT (HS256)
- **PDF 解析**: pdfplumber（文本层）→ MinerU 3.4.5（扫描件）→ PaddleOCR（兜底）
- **Word 解析**: python-docx（含畸形 docx 容错）
- **Excel 解析**: openpyxl

## 项目结构

```
backend/
├── app/
│   ├── main.py              # 主应用入口（FastAPI app 创建、中间件、路由注册）
│   ├── core/
│   │   └── config.py        # 配置管理（pydantic-settings，读 .env）
│   ├── models/
│   │   └── models.py        # SQLAlchemy 模型（73 张表）
│   ├── api/v1/              # API 路由模块
│   │   ├── question_import.py  # 题目导入（上传/解析/预览/确认/分离匹配）
│   │   ├── questions.py        # 题目管理（CRUD/题组/图片）
│   │   ├── admin.py            # 管理员端点
│   │   ├── teacher.py          # 教师端点
│   │   └── ...
│   ├── services/            # 业务逻辑层
│   │   ├── text_parser.py      # 解析器核心（4239 行）
│   │   ├── composite_matcher.py # 复合题匹配
│   │   ├── mineru_service.py   # MinerU 子进程封装
│   │   ├── text_cache.py       # 文本提取缓存
│   │   └── question_ingest/    # 导入管线模块化拆分（进行中）
│   │       ├── magic.py        # 文件头嗅探
│   │       └── ...
│   └── middleware.py        # 请求日志/限流/熔断中间件
├── scripts/                 # 验证与运维脚本
│   ├── gate_l0_redlines.py     # L0 红线门禁
│   ├── gate_l1_parser.py       # L1 解析指纹门禁
│   ├── gate_l2_matching.py     # L2 匹配配对门禁
│   ├── gate_l3_ingest.py       # L3 落库链路门禁
│   ├── gate_l4_api_contract.py # L4 API 契约门禁
│   ├── gate_l5_frontend_contract.py # L5 前端数据契约门禁
│   ├── gate_all.py             # 一键执行全部门禁
│   ├── verify_parser_regression.py  # G1 公专零回归
│   ├── verify_xingce_regression.py  # G2/G3 行测+申论
│   └── ...
├── tests/                   # pytest 测试（基线: 16 failed / 168 passed / 52 errors）
├── data/                    # SQLite 数据库 + 备份 + 门禁基线
├── logs/                    # 日志（RotatingFileHandler, 10MB×5）
├── .env                     # 环境变量
├── start.py                 # 启动脚本（看门狗: 3s 重启, 20 次熔断）
└── requirements.txt
```

## 快速开始

```bash
cd backend
pip install -r requirements.txt
python start.py
```

- API 文档: http://localhost:8000/docs
- 前端: http://localhost:9527（Vite dev server）
- VTJ 设计器: http://localhost:9527/__vtj__/

## 门禁命令

```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING='utf-8'
cd backend

python scripts/gate_all.py            # 全量 L0-L5
python scripts/gate_all.py --quick    # L0+L1，秒级
python scripts/gate_all.py --layer L3 # 单层
```

## 数据库备份（WAL 模式，必须用 sqlite3 备份 API）

```python
import sqlite3, datetime
ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
src = sqlite3.connect('data/question_bank.db')
dst = sqlite3.connect(f'data/question_bank.db.bak_{ts}')
with dst: src.backup(dst)
dst.close(); src.close()
```

> ⚠️ **禁止** `shutil.copy2`（WAL 模式下只拷主库无法保证完整性）。
> 回滚时覆盖主库并**同时删除 `-wal` 与 `-shm`**。

## 许可证

MIT License
