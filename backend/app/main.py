"""
公安联考题库系统 - FastAPI主应用入口（增强版）
  支持HTTP/HTTPS、WebSocket协议
  """
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware as FastAPICORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .core.redis_client import get_redis, close_redis
from .api.v1.platform import llm
from .api.v1.catalog import questions, papers, question_actions, wrong_questions
from .api.v1.exam import exams, stats, practice, exam_records, quick_practice, smart_exam
from .api.v1.library import videos, media
from .api.v1.growth import goals
from .api.v1.identity import auth
from .api.v1.personal import collection, notes
from .api.v1.content import news, recruitment, calendar
from .api.v1.platform import admin as admin_api
from .api.v1.platform import teacher as teacher_api
from .api.v1.platform import admin_approval
from .api.v1.community import quotes, forum
from .api.v1.library import materials
from .api.v1.identity import auth_qrcode
from .api.v1.identity import devices
from .api.v1.platform import feedback
from .api.v1.growth import achievements, checkin
from .api.v1.growth import study_plan
from .api.v1.reward import coins
from .api.v1.growth import tasks
from .api.v1.reward import shop, admin_shop
from .api.v1.platform.websocket import router as websocket_router
from .api.v1.catalog.paper_generation import router as paper_router
from .api.v1.catalog.question_import import router as question_import_router
from .core.exceptions import register_exception_handlers, ExceptionHandlers, create_error_response
from .core.middleware import setup_middlewares, RequestLoggingMiddleware, RateLimitMiddleware, CircuitBreakerMiddleware
from .core.monitoring import metrics_collector, get_system_metrics, PerformanceMonitor

import sys
import io

# 强制标准输出/错误流使用 UTF-8 编码
# 注意：必须用 reconfigure()，不能新建 TextIOWrapper 替换 sys.stdout/sys.stderr。
# 新建 wrapper 时旧 wrapper 会被 GC，析构时会关闭其底层 binary buffer，
# 新 wrapper 指向的正是已关闭的流，导致后续任何写入抛
# "ValueError: I/O operation on closed file" 并在解释器退出时打印 "lost sys.stderr"。
# 该缺陷会使 pytest 套件在收集阶段即崩溃且无任何输出。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except (ValueError, OSError):
            # 流已被外部关闭或不支持重配置时保持原样，不能影响应用启动
            pass






from logging.handlers import RotatingFileHandler

# P1-1：LOG_FILE 所在目录可能不存在（首次部署的 ./logs/ 很常见）。
# RotatingFileHandler 在打开文件时直接抛 FileNotFoundError，会让 app 模块导入即崩，
# 表现为「服务起不来」。先建目录；任何文件日志失败都降级为纯 stdout，保证可启动。
_log_handlers = [logging.StreamHandler(sys.stdout)]  # 使用已设置的UTF-8编码的stdout
try:
    _log_dir = os.path.dirname(os.path.abspath(settings.LOG_FILE)) if settings.LOG_FILE else ''
    if _log_dir:
        os.makedirs(_log_dir, exist_ok=True)
    if settings.LOG_FILE:
        _log_handlers.insert(
            0,
            RotatingFileHandler(
                settings.LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
            ),
        )
except OSError as _log_err:  # 只读文件系统、权限不足等
    print(f"[logging] 文件日志不可用，已降级为 stdout：{_log_err}", file=sys.stderr)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=_log_handlers
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("启动公安联考题库系统服务...")
    logger.info(f"服务地址: http://{settings.HOST}:{settings.PORT}")
    logger.info(f"API文档: http://{settings.HOST}:{settings.PORT}/docs")

    # 初始化Redis连接
    try:
        await get_redis()
        logger.info("Redis连接初始化完成")
    except Exception as e:
        logger.warning(f"Redis连接初始化失败（二维码登录功能将不可用）: {e}")

    # 启动期数据库守卫（2026-10-25 事故复盘）：backend/.env 缺失时 SQLITE_PATH
    # 会回落到默认值，若该默认指向旧/空库，create_all 会照常建表，表现为
    # 「题目与账号凭空消失」。这里在建表前打印真实路径并在异常时 ERROR，
    # 建表后校验关键列与行数。DB_GUARD_STRICT=1 时异常直接拒绝启动。
    from .core.db_guard import preflight as db_preflight, verify as db_verify
    db_preflight(logger, settings.DB_TYPE, settings.SQLITE_PATH)

    # 自动创建数据库表
    from .core.database import engine, Base, SessionLocal
    from .models import models  # 确保所有模型被导入
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表初始化完成")
    db_verify(engine, logger)

    # F2 通信统一：多 worker 无中继直接拒绝启动（fail-fast，避免「有时收不到」）；
    # 中继本身不可用只降级为本地扇出，不影响业务读写。
    from .foundation.ws_relay import validate_worker_config, ws_relay
    validate_worker_config(int(os.environ.get('WEB_CONCURRENCY', '1') or '1'), settings.WS_RELAY)
    ws_relay.configure(settings.WS_RELAY, settings.REDIS_URL)
    await ws_relay.start(settings.WS_RELAY, settings.REDIS_URL)

    # WS 心跳巡检：超过阈值无消息的连接关闭（码 4008），客户端重连后全量重同步。
    from .api.v1.platform.websocket import ws_connection_manager
    import asyncio as _ws_asyncio
    ws_watchdog_task = _ws_asyncio.create_task(
        ws_connection_manager.watchdog(settings.WS_HEARTBEAT_TIMEOUT_SECONDS)
    )

    # F1 一致性内核：幂等建 7 张 foundation 表 + 启动投递器。
    # FOUNDATION_ENABLED=false 时整段跳过，行为与 F0 完全一致（回滚开关）。
    dispatcher_task = None
    if settings.FOUNDATION_ENABLED:
        try:
            import asyncio as _foundation_asyncio

            from .foundation.dispatcher import Dispatcher
            from .foundation.schema import ensure_schema

            _raw = engine.raw_connection()
            try:
                _conn = getattr(_raw, "driver_connection", _raw)
                created = ensure_schema(_conn)
            finally:
                _raw.close()
            if created:
                logger.info(f"foundation 表已创建: {created}")
            _foundation_stop = _foundation_asyncio.Event()
            dispatcher_task = _foundation_asyncio.create_task(
                Dispatcher(SessionLocal).run_forever(_foundation_stop)
            )
            logger.info("一致性内核投递器已启动")
        except Exception as e:
            logger.warning(f"一致性内核启动失败（服务继续运行）: {e}")

    # 初始化成就目录（幂等）
    try:
        from .services import achievement_service
        _db = SessionLocal()
        try:
            achievement_service.seed_achievements(_db)
        finally:
            _db.close()
    except Exception as e:
        logger.warning(f"成就目录初始化失败: {e}")

    # 自动检测并添加缺失列（解决create_all不支持ALTER TABLE的问题）
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)

        # 检查 sys_user 表（学生端「我的」模块新增字段）
        if 'sys_user' in inspector.get_table_names():
            user_cols = [c['name'] for c in inspector.get_columns('sys_user')]
            for col_name, col_type in [
                ('growth_points', 'INTEGER DEFAULT 0'),
                ('settings', 'JSON'),
                ('accuracy80_streak', 'INTEGER DEFAULT 0'),
                ('perfect_streak', 'INTEGER DEFAULT 0'),
                ('avatar_frame', 'VARCHAR(50)'),
                # 徽章生成器计数字段
                ('ai_qa_total', 'INTEGER DEFAULT 0'),
                ('news_read_total', 'INTEGER DEFAULT 0'),
                ('news_read_today', 'INTEGER DEFAULT 0'),
                ('news_read_date', 'DATE'),
                ('recruit_read_total', 'INTEGER DEFAULT 0'),
                ('recruit_read_today', 'INTEGER DEFAULT 0'),
                ('recruit_read_date', 'DATE'),
                ('ai_qa_count', 'INTEGER DEFAULT 0'),
                ('news_read_count', 'INTEGER DEFAULT 0'),
                ('recruit_read_count', 'INTEGER DEFAULT 0'),
            ]:
                if col_name not in user_cols:
                    with engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE sys_user ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                    logger.info(f"自动迁移: sys_user 添加列 {col_name}")

        # 检查 achievement 表（徽章体系：隐藏成就 + 视觉参数 + 五档升级）
        if 'achievement' in inspector.get_table_names():
            ach_cols = [c['name'] for c in inspector.get_columns('achievement')]
            for col_name, col_type in [
                ('is_hidden', 'INTEGER DEFAULT 0'),
                ('style_params', 'JSON'),
                ('tier_times', 'JSON'),
            ]:
                if col_name not in ach_cols:
                    with engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE achievement ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                    logger.info(f"自动迁移: achievement 添加列 {col_name}")

        # 检查 user_achievement 表（徽章档位）
        if 'user_achievement' in inspector.get_table_names():
            ua_cols = [c['name'] for c in inspector.get_columns('user_achievement')]
            if 'tier' not in ua_cols:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE user_achievement ADD COLUMN tier INTEGER DEFAULT 1"))
                    conn.commit()
                logger.info("自动迁移: user_achievement 添加列 tier")

        # 检查 exam_calendar 表
        if 'exam_calendar' in inspector.get_table_names():
            exam_cols = [c['name'] for c in inspector.get_columns('exam_calendar')]
            for col_name, col_type in [('url', 'VARCHAR(500)'), ('description', 'TEXT')]:
                if col_name not in exam_cols:
                    with engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE exam_calendar ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                    logger.info(f"自动迁移: exam_calendar 添加列 {col_name}")

        # 检查 recruitment_info 表
        if 'recruitment_info' in inspector.get_table_names():
            rec_cols = [c['name'] for c in inspector.get_columns('recruitment_info')]
            for col_name, col_type in [('url', 'VARCHAR(500)'), ('publish_date', 'VARCHAR(20)')]:
                if col_name not in rec_cols:
                    with engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE recruitment_info ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                    logger.info(f"自动迁移: recruitment_info 添加列 {col_name}")

        # 检查 news_article 表
        if 'news_article' in inspector.get_table_names():
            news_cols = [c['name'] for c in inspector.get_columns('news_article')]
            for col_name, col_type in [('content', 'TEXT')]:
                if col_name not in news_cols:
                    with engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE news_article ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                    logger.info(f"自动迁移: news_article 添加列 {col_name}")
        # 检查 practice_record 表
        if 'practice_record' in inspector.get_table_names():
            prac_cols = [c['name'] for c in inspector.get_columns('practice_record')]
            for col_name, col_type in [
                ('subject_id', 'INTEGER'),
                ('type_id', 'INTEGER'),
                ('practice_date', 'DATE'),
            ]:
                if col_name not in prac_cols:
                    with engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE practice_record ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                    logger.info(f"自动迁移: practice_record 添加列 {col_name}")

        # 检查 question_bank 表（P1/P3b：题型人工复核标记）
        # need_review：导入时题型判定置信度不足的题目置 1，教师端「题目管理」可按此筛选复核。
        if 'question_bank' in inspector.get_table_names():
            qb_cols = [c['name'] for c in inspector.get_columns('question_bank')]
            if 'need_review' not in qb_cols:
                with engine.connect() as conn:
                    conn.execute(text(
                        "ALTER TABLE question_bank ADD COLUMN need_review INTEGER DEFAULT 0"))
                    conn.commit()
                logger.info("自动迁移: question_bank 添加列 need_review")

        # 检查 exam_paper 表(试卷管理完善:新增 publish_target 字段)
        if 'exam_paper' in inspector.get_table_names():
            paper_cols = [c['name'] for c in inspector.get_columns('exam_paper')]
            if 'publish_target' not in paper_cols:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE exam_paper ADD COLUMN publish_target VARCHAR(20)"))
                    conn.commit()
                logger.info("自动迁移: exam_paper 添加列 publish_target")

        # 检查 forum_post 表(论坛模块完善:新增 attachments 字段)
        if 'forum_post' in inspector.get_table_names():
            forum_cols = [c['name'] for c in inspector.get_columns('forum_post')]
            if 'attachments' not in forum_cols:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE forum_post ADD COLUMN attachments JSON"))
                    conn.commit()
                logger.info("自动迁移: forum_post 添加列 attachments")

        # 检查 knowledge_point 表(快速练习三级分类:新增 sub_category_id 字段)
        if 'knowledge_point' in inspector.get_table_names():
            kp_cols = [c['name'] for c in inspector.get_columns('knowledge_point')]
            if 'sub_category_id' not in kp_cols:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE knowledge_point ADD COLUMN sub_category_id INTEGER REFERENCES sub_categories(id)"))
                    conn.commit()
                logger.info("自动迁移: knowledge_point 添加列 sub_category_id")

        # 检查 study_material 表(备考资料:新增 content_hash 去重字段)
        # 根因: 模型定义了 content_hash 但历史数据库表缺该列，导致 admin_list 的 count() 查询
        #       触发 "no such column: study_material.content_hash" → 500 错误
        if 'study_material' in inspector.get_table_names():
            sm_cols = [c['name'] for c in inspector.get_columns('study_material')]
            if 'content_hash' not in sm_cols:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE study_material ADD COLUMN content_hash VARCHAR(64)"))
                    conn.commit()
                logger.info("自动迁移: study_material 添加列 content_hash")

        # 检查 study_goal 表(金币购:四维加权奖励字段)
        if 'study_goal' in inspector.get_table_names():
            sg_cols = [c['name'] for c in inspector.get_columns('study_goal')]
            for col_name, col_type in [
                ('subject_mode', 'INTEGER DEFAULT 0'),
                ('expected_minutes', 'INTEGER DEFAULT 0'),
                ('base_reward', 'INTEGER DEFAULT 20'),
                ('reward_coins', 'INTEGER DEFAULT 0'),
                ('difficulty_factor', 'FLOAT DEFAULT 1.0'),
                ('quality_score', 'FLOAT DEFAULT 0.0'),
                ('persistence_score', 'FLOAT DEFAULT 0.0'),
                ('improvement_score', 'FLOAT DEFAULT 0.0'),
                ('baseline_accuracy', 'FLOAT DEFAULT 0.0'),
                ('baseline_count', 'INTEGER DEFAULT 0'),
                # 学习计划（模块4）：AI 生成的计划归属字段
                ('plan_id', 'INTEGER'),
                ('sort_order', 'INTEGER DEFAULT 0'),
                ('plan_meta', 'TEXT'),
            ]:
                if col_name not in sg_cols:
                    with engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE study_goal ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                    logger.info(f"自动迁移: study_goal 添加列 {col_name}")

        # 检查并修复双编码JSON options（99条历史数据）
        if 'question_bank' in inspector.get_table_names():
            try:
                import json as _json
                with engine.connect() as conn:
                    rows = conn.execute(text(
                        "SELECT question_id, options FROM question_bank WHERE options LIKE '\"[%' AND status=1"
                    )).fetchall()
                    fixed = 0
                    for r in rows:
                        qid, opts = r[0], r[1]
                        if isinstance(opts, str):
                            try:
                                parsed = _json.loads(opts)
                                if isinstance(parsed, str):
                                    parsed = _json.loads(parsed)
                                if isinstance(parsed, list):
                                    conn.execute(text(
                                        "UPDATE question_bank SET options = :opts WHERE question_id = :qid"
                                    ), {"opts": _json.dumps(parsed, ensure_ascii=False), "qid": qid})
                                    fixed += 1
                            except Exception:
                                pass
                    if fixed > 0:
                        conn.commit()
                        logger.info(f"自动修复: 已修复 {fixed} 条双编码JSON options")
            except Exception as e:
                logger.warning(f"双编码JSON options修复跳过: {e}")

        # === 三端分离架构：SysUser 新增字段 ===
        if 'sys_user' in inspector.get_table_names():
            user_cols = [c['name'] for c in inspector.get_columns('sys_user')]
            for col_name, col_type, col_default in [
                ('is_disabled', 'INTEGER', '0'),
                ('disabled_reason', 'VARCHAR(255)', None),
                ('last_login_ip', 'VARCHAR(45)', None),
                ('password_reset_token', 'VARCHAR(255)', None),
                ('password_reset_expire', 'DATETIME', None),
                ('created_by', 'BIGINT', None),
                ('school_id', 'INTEGER', None),
                ('device_sessions', 'JSON', None),
            ]:
                if col_name not in user_cols:
                    default_clause = f"DEFAULT {col_default}" if col_default else ""
                    with engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE sys_user ADD COLUMN {col_name} {col_type} {default_clause}"))
                        conn.commit()
                    logger.info(f"自动迁移: sys_user 添加列 {col_name}")

        # === 每日金句收藏：quote_favorite 表结构迁移（新增 obsidian_source + quote_id 可空） ===
        # SQLite 不支持 ALTER COLUMN 修改 NOT NULL，需整表重建
        if 'quote_favorite' in inspector.get_table_names():
            qf_cols = [c['name'] for c in inspector.get_columns('quote_favorite')]
            qf_nullable = {c['name']: c.get('nullable', True) for c in inspector.get_columns('quote_favorite')}
            quote_id_notnull = qf_nullable.get('quote_id', True) is False
            if 'obsidian_source' not in qf_cols or quote_id_notnull:
                with engine.connect() as conn:
                    conn.execute(text("""
                        CREATE TABLE quote_favorite_new (
                            fav_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                            user_id BIGINT NOT NULL,
                            quote_id INTEGER,
                            obsidian_source VARCHAR(200),
                            create_time DATETIME,
                            CONSTRAINT uq_user_quote_fav UNIQUE (user_id, quote_id),
                            CONSTRAINT uq_user_obsidian_fav UNIQUE (user_id, obsidian_source),
                            FOREIGN KEY(user_id) REFERENCES sys_user (user_id),
                            FOREIGN KEY(quote_id) REFERENCES essay_quote (quote_id)
                        )
                    """))
                    conn.execute(text("""
                        INSERT INTO quote_favorite_new (fav_id, user_id, quote_id, create_time)
                        SELECT fav_id, user_id, quote_id, create_time FROM quote_favorite
                    """))
                    conn.execute(text("DROP TABLE quote_favorite"))
                    conn.execute(text("ALTER TABLE quote_favorite_new RENAME TO quote_favorite"))
                    conn.execute(text("CREATE INDEX idx_user_id_quotefavorite ON quote_favorite (user_id)"))
                    conn.commit()
                logger.info("自动迁移: quote_favorite 表重建（新增 obsidian_source + quote_id 可空）")

        # === 三端分离架构：新增 sys_config 默认配置 ===
        try:
            from .models.models import SysConfig
            db_sess = SessionLocal()
            try:
                default_configs = [
                    ('site_name', '砺安题库', '站点名称', 'STRING'),
                    ('site_logo', '/static/logo.png', '站点Logo', 'STRING'),
                    ('max_login_attempts', '5', '最大登录尝试次数', 'NUMBER'),
                    ('exam_auto_submit_minutes', '120', '考试自动提交时间(分钟)', 'NUMBER'),
                    ('maintenance_mode', 'false', '维护模式', 'BOOLEAN'),
                    ('register_open', 'true', '是否开放注册', 'BOOLEAN'),
                    ('password_min_length', '6', '密码最小长度', 'NUMBER'),
                    ('announcement_default_visible', 'all', '公告默认可见角色', 'STRING'),
                ]
                for key, val, desc, ctype in default_configs:
                    existing = db_sess.query(SysConfig).filter(SysConfig.config_key == key).first()
                    if not existing:
                        db_sess.add(SysConfig(config_key=key, config_value=val, config_desc=desc, config_type=ctype))
                db_sess.commit()
                logger.info("系统默认配置初始化完成")
            finally:
                db_sess.close()
        except Exception as e:
            logger.warning(f"默认配置初始化跳过: {e}")

    except Exception as mig_err:
        logger.warning(f"自动迁移检查失败（可忽略）: {mig_err}")

    # wrong_question_personal 表斩题字段迁移
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(wrong_question_personal)")).fetchall()]
            if 'is_cut' not in columns:
                conn.execute(text("ALTER TABLE wrong_question_personal ADD COLUMN is_cut INTEGER DEFAULT 0"))
            if 'cut_time' not in columns:
                conn.execute(text("ALTER TABLE wrong_question_personal ADD COLUMN cut_time DATETIME"))
            if 'auto_delete_time' not in columns:
                conn.execute(text("ALTER TABLE wrong_question_personal ADD COLUMN auto_delete_time DATETIME"))
            if 'correct_count' not in columns:
                conn.execute(text("ALTER TABLE wrong_question_personal ADD COLUMN correct_count INTEGER DEFAULT 0"))
            if 'user_answer' not in columns:
                conn.execute(text("ALTER TABLE wrong_question_personal ADD COLUMN user_answer TEXT"))
            conn.commit()
        logger.info("wrong_question_personal 斩题字段迁移完成")
    except Exception as e:
        logger.warning(f"wrong_question_personal 迁移: {e}")

    # 题型客观性修复：保留 question_type 独立题型（判断题/填空题/情境题不再被归一化合并）
    try:
        with engine.connect() as conn:
            # === question_detail_category 表（仅归一化该表，不影响主题型表） ===
            # 注意：'选择题'是歧义值（可能为单选也可能为多选），不可在此批量折叠为'单选题'，
            # 否则会把多选的选择题误判为单选；统一交由 repair_question_types.py 按关键词工程重检测。
            conn.execute(text("UPDATE question_detail_category SET question_type_detail='多选题' WHERE question_type_detail='不定项'"))
            conn.execute(text("UPDATE question_detail_category SET question_type_detail='论述题' WHERE question_type_detail IN ('填空题', '简答题', '案例分析题', '无')"))
            # 修复 is_objective 字段（客观题/主观题分类，含新增题型）
            conn.execute(text("UPDATE question_type SET is_objective=1 WHERE type_name IN ('单选题', '多选题', '判断题', '填空题')"))
            conn.execute(text("UPDATE question_type SET is_objective=0 WHERE type_name IN ('论述题', '写作题', '情境题')"))
            conn.commit()
        logger.info("题型客观性字段修复完成（保留独立题型：判断/填空/情境）")
    except Exception as e:
        logger.warning(f"题型客观性字段修复: {e}")

    # exam_record 表 exam_type 枚举值迁移：SIMULATION→SELF_TEST, PRACTICE→MOCK_EXAM
    # 修复模型定义枚举(Enum("SELF_TEST","MOCK_EXAM"))与历史数据(SIMULATION/PRACTICE)不一致问题
    try:
        with engine.connect() as conn:
            # SQLite 的 Enum 实际存储为 TEXT，可直接 UPDATE
            conn.execute(text("UPDATE exam_record SET exam_type='SELF_TEST' WHERE exam_type='SIMULATION'"))
            conn.execute(text("UPDATE exam_record SET exam_type='MOCK_EXAM' WHERE exam_type='PRACTICE'"))
            conn.commit()
        logger.info("exam_record 枚举值迁移完成（SIMULATION→SELF_TEST, PRACTICE→MOCK_EXAM）")
    except Exception as e:
        logger.warning(f"exam_record 枚举值迁移: {e}")

    # 申论金句种子数据初始化
    try:
        from .models.models import EssayQuote
        db_seed = SessionLocal()
        try:
            existing_count = db_seed.query(EssayQuote).count()
            if existing_count == 0:
                seed_quotes = [
                    EssayQuote(content="天下之事，不难于立法，而难于法之必行。", source="张居正", category="法治", author="张居正"),
                    EssayQuote(content="法者，天下之程式也，万事之仪表也。", source="管子", category="法治", author="管仲"),
                    EssayQuote(content="治国之道，必先富民。", source="管子", category="治国", author="管仲"),
                    EssayQuote(content="政之所兴在顺民心，政之所废在逆民心。", source="管子", category="民心", author="管仲"),
                    EssayQuote(content="苟日新，日日新，又日新。", source="大学", category="哲理", author="曾子"),
                    EssayQuote(content="天下为公，选贤与能，讲信修睦。", source="礼记", category="治国", author=""),
                    EssayQuote(content="民惟邦本，本固邦宁。", source="尚书", category="民心", author=""),
                    EssayQuote(content="德不孤，必有邻。", source="论语", category="品德", author="孔子"),
                    EssayQuote(content="己所不欲，勿施于人。", source="论语", category="品德", author="孔子"),
                    EssayQuote(content="穷则独善其身，达则兼济天下。", source="孟子", category="品德", author="孟子"),
                ]
                db_seed.add_all(seed_quotes)
                db_seed.commit()
                logger.info(f"申论金句种子数据初始化完成: {len(seed_quotes)} 条")
        finally:
            db_seed.close()
    except Exception as seed_err:
        logger.warning(f"金句种子数据初始化跳过: {seed_err}")

    # 自动修复已有题目的子科目分类（将'无'重新检测分类）
    try:
        from .api.v1.catalog.question_import import _detect_subcategory
        db = SessionLocal()
        try:
            from .models.models import QuestionBank
            uncategorized = db.query(QuestionBank).filter(
                QuestionBank.xingce_subcategory == '无',
                QuestionBank.shenlun_subcategory == '无',
                QuestionBank.gongzhuan_subcategory == '无',
                QuestionBank.status == 1
            ).all()
            if uncategorized:
                fixed_count = 0
                for q in uncategorized:
                    q.xingce_subcategory = _detect_subcategory(1, q.question_content or '', '') if q.subject_id == 1 else '无'
                    q.shenlun_subcategory = _detect_subcategory(2, q.question_content or '', '') if q.subject_id == 2 else '无'
                    q.gongzhuan_subcategory = _detect_subcategory(3, q.question_content or '', '') if q.subject_id == 3 else '无'
                    fixed_count += 1
                db.commit()
                logger.info(f"已为 {fixed_count} 道已有题目重新检测子科目分类")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"已有题目子科目修复跳过（可能表尚未创建）: {e}")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)

    # 启动定时任务调度器（新闻/招考/考试日历爬取）
    try:
        import asyncio as _asyncio
        from .services.scheduler import init_scheduler, set_main_loop
        # 传递主事件循环引用，供调度器跨线程广播 WebSocket 同步事件
        set_main_loop(_asyncio.get_running_loop())
        init_scheduler()
        logger.info("定时任务调度器已启动")
    except Exception as e:
        logger.warning(f"定时任务调度器启动失败（服务继续运行）: {e}")

    # 执行种子数据初始化（模拟用户 + 默认配置）
    try:
        from scripts.admin.seed import run_seed
        run_seed()
    except Exception as e:
        logger.warning(f"种子数据初始化失败（服务继续运行）: {e}")

    # 事件消费者：P5.2 调用点改造完成前保持关闭（配置默认 False），
    # 过早启动会与现有同步直调产生成就双写
    consumer_task = None
    if settings.EVENT_CONSUMER_ENABLED:
        import asyncio as _consumer_asyncio
        from .services.event_consumer import consume_user_actions
        consumer_task = _consumer_asyncio.create_task(consume_user_actions())
        logger.info("事件消费者已启动")

    yield

    logger.info("关闭公安联考题库系统服务...")
    if ws_watchdog_task is not None:
        import asyncio as _stop_ws_asyncio
        ws_watchdog_task.cancel()
        try:
            await ws_watchdog_task
        except _stop_ws_asyncio.CancelledError:
            logger.debug("WS 心跳巡检已停止")
        except Exception as e:
            logger.warning(f"WS 心跳巡检关闭异常: {e}")
    try:
        await ws_relay.stop()
    except Exception as e:
        logger.warning(f"WS 中继关闭异常: {e}")
    if dispatcher_task is not None:
        import asyncio as _stop_asyncio
        dispatcher_task.cancel()
        try:
            await dispatcher_task
        except _stop_asyncio.CancelledError:
            pass
        except Exception:
            pass
    if consumer_task is not None:
        import asyncio as _shutdown_asyncio
        consumer_task.cancel()
        try:
            await consumer_task
        except _shutdown_asyncio.CancelledError:
            pass
        except Exception:
            pass
    try:
        from .services.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass
    # 关闭Redis连接
    try:
        await close_redis()
    except Exception:
        pass

app = FastAPI(
    title="公安联考题库系统",
    description="""
## 公安联考题库系统 API

支持以下核心功能：

- **用户管理**: 学生、教师、管理员三种角色
- **题库管理**: 支持申论、行测、公安专业知识等题型
- **试卷管理**: 手动组卷、自动组卷、智能组卷
- **考试执行**: 实时监控、答题卡提交、自动评分
- **成绩分析**: 多维度分析、薄弱点识别、改进建议
- **视频资源**: 题目讲解视频上传与播放
- **大模型集成**: 智能问答、内容生成

## 协议支持

  - HTTP/HTTPS: 标准RESTful API
  - WebSocket: 实时通信、在线监考

  ## 认证方式

- JWT Bearer Token
- OAuth2.0 (支持密码模式、刷新令牌)
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    FastAPICORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_middlewares(app)
register_exception_handlers(app)

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
# 题目图片静态服务
import os as _os
_img_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'static', 'questions')
_os.makedirs(_img_dir, exist_ok=True)
app.mount("/static/questions", StaticFiles(directory=_img_dir), name="question_images")
# 题组图片静态服务（申论「给定材料」等共享内容里的图）
# ★ J-1-2：与 /static/questions 物理隔离 —— 题目图在 {qid}/ 下，题组图在 {gid}/ 下，
#   两者互不覆盖。缺这个挂载会让 save_images_for_group 写出的图稳定 404（裂图）。
_grp_img_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'static', 'question-groups')
_os.makedirs(_grp_img_dir, exist_ok=True)
app.mount("/static/question-groups", StaticFiles(directory=_grp_img_dir), name="question_group_images")
# 图片加载失败兜底占位图（前端 onerror 统一指向此处）
_images_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'static', 'images')
_os.makedirs(_images_dir, exist_ok=True)
app.mount("/static/images", StaticFiles(directory=_images_dir), name="static_images")

app.include_router(auth.router)
app.include_router(questions.router)
app.include_router(paper_router, tags=["试卷管理"])  # paper_generation（含mode参数，优先注册）
app.include_router(papers.router, tags=["试卷管理-基础"])
app.include_router(question_import_router)
app.include_router(exams.router)
app.include_router(videos.router)
app.include_router(llm.router)
app.include_router(study_plan.router)
app.include_router(goals.router)
app.include_router(stats.router)
app.include_router(exam_records.router, tags=["成绩记录"])
app.include_router(media.router)
app.include_router(websocket_router)
app.include_router(news.router)
app.include_router(recruitment.router)
app.include_router(calendar.router)
app.include_router(practice.router)
app.include_router(quick_practice.router)
app.include_router(smart_exam.router)
app.include_router(question_actions.router)
app.include_router(forum.router)
app.include_router(wrong_questions.router)
app.include_router(notes.router)
app.include_router(collection.router)
app.include_router(quotes.router)
app.include_router(materials.router)
app.include_router(admin_api.router, tags=["管理员端"])
app.include_router(admin_approval.router, tags=["管理员端-试卷审批"])
app.include_router(teacher_api.router, tags=["教师端"])
app.include_router(auth_qrcode.router, tags=["二维码登录"])
app.include_router(devices.router, tags=["设备管理"])
app.include_router(coins.router, tags=["金币"])
app.include_router(shop.router, tags=["金币商城"])
app.include_router(tasks.router, tags=["任务中心"])
app.include_router(admin_shop.router, tags=["管理员端-金币商城"])
app.include_router(achievements.router, tags=["成就"])
app.include_router(checkin.router, tags=["每日签到"])
app.include_router(feedback.router, tags=["意见反馈"])
app.include_router(feedback.admin_router, tags=["反馈管理"])

@app.get("/health", tags=["系统"])
async def health_check():
    """
    健康检查接口
    """
    return {
        "status": "healthy",
        "service": "公安联考题库系统",
        "version": "1.0.0"
    }

@app.get("/health/foundation", tags=["系统"])
async def foundation_health():
    """F1 一致性内核健康：outbox 积压/死信/投影延迟/最近对账（只读）。"""
    from .core.database import engine
    from .foundation.health import snapshot
    from .foundation.ws_relay import ws_relay

    return snapshot(engine, ws_relay.health())

@app.get("/metrics", tags=["系统"])
async def get_metrics():
    return metrics_collector.get_metrics_summary()

@app.get("/metrics/system", tags=["系统"])
async def get_system_metrics_endpoint():
    return get_system_metrics()

# ==================== 前端生产版本托管（SPA） ====================
import os.path as _ospath
_dist = _ospath.join(_ospath.dirname(_ospath.dirname(_ospath.dirname(_ospath.abspath(__file__)))), 'dist')
if _ospath.exists(_dist):
    # 托管 JS/CSS 等静态资源
    _assets = _ospath.join(_dist, 'assets')
    if _ospath.exists(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="spa_assets")

    # SPA fallback：非 API 路径返回 index.html
    from fastapi.responses import FileResponse as _FileResponse, JSONResponse as _JSONResponse
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """所有非 API 路径返回前端 index.html，由 Vue Router 接管路由。
        /api/* 路径返回 404 JSON，避免前端解析 HTML 出错。"""
        if full_path.startswith("api/"):
            return _JSONResponse(status_code=404, content={"detail": "Not Found"})
        file_path = _ospath.join(_dist, full_path)
        if full_path and _ospath.isfile(file_path):
            return _FileResponse(file_path)
        return _FileResponse(_ospath.join(_dist, 'index.html'))

@app.get("/metrics/endpoints", tags=["系统"])
async def get_endpoint_metrics(
    method: str = None,
    path: str = None
):
    """
    获取各端点性能指标

    - **method**: HTTP方法过滤（可选）
    - **path**: URL路径前缀过滤（可选）
    """
    return metrics_collector.get_endpoint_stats(method=method, path=path)

@app.post("/metrics/reset", tags=["系统"])
async def reset_metrics():
    """
    重置性能指标数据
    """
    metrics_collector.reset_metrics()
    return {"message": "指标已重置"}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常处理
    """
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.error(f"全局异常 [Request-ID: {request_id}]: {str(exc)}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content=create_error_response(
            status_code=500,
            message="系统内部错误，请稍后重试",
            code="INTERNAL_ERROR",
            request_id=request_id
        )
    )

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """
    性能监控中间件
    """
    with PerformanceMonitor.track_request(request.method, request.url.path):
        response = await call_next(request)
        return response

def create_app() -> FastAPI:
    return app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        # 关闭热重载：reload 模式下 worker 重启会 RST 所有已建立连接，
        # 导致前端 Vite 代理/WebSocket 报 ECONNRESET 并崩溃（详见 proxy.config.ts 注释）。
        # 需要热重载时请通过命令行显式 `uvicorn app.main:app --reload` 启动。
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
        ssl_certfile=None,
        ssl_keyfile=None
    )
