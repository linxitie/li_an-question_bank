"""
APScheduler 定时任务管理
每日 24:00（北京时间）触发新闻、招考、考试日历爬取
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# 北京时间时区
CST = timezone(timedelta(hours=8))

scheduler = BackgroundScheduler(timezone=CST, job_defaults={"misfire_grace_time": 300})

# ========== 主事件循环引用（供跨线程 WebSocket 广播） ==========
# scheduler 运行在独立线程，WebSocket 对象绑定在 FastAPI 主事件循环，
# 跨线程广播必须通过 run_coroutine_threadsafe 提交到主循环。
_main_loop = None


def set_main_loop(loop):
    """由 main.py 的 lifespan 调用，传入主事件循环引用"""
    global _main_loop
    _main_loop = loop


def _broadcast_sync(message: str = "sync", data: Optional[dict] = None):
    """数据更新后广播同步事件，通知前端刷新（跨线程安全）

    Args:
        message: 面向用户/前端的简短说明（如「题目更新」）
        data: 可选的结构化补充信息（如 {"scope","subject_id","count"}）。
              只应包含统计信息，禁止放入题目正文等敏感内容。
              为 None 时保持既有行为（仅带 message），向后兼容。
    """
    _dispatch_sync(None, message, data)


def _broadcast_personal_sync(user_id: int, message: str = "sync", data: Optional[dict] = None):
    """定向广播同步事件给**单个用户**的所有连接（跨线程安全）

    与 `_broadcast_sync` 的区别：练习记录、目标进度这类数据是**私有**的，
    用 `broadcast_all` 会让全部在线用户都收到事件并各自重拉数据 ——
    既浪费带宽，也会通过「谁在练习」的刷新行为泄露他人的活跃信号。

    Args:
        user_id: 目标用户 id
        message: 面向前端的简短说明
        data: 可选的结构化补充信息，只应含统计量（如 {"scope","count"}），
              禁止放入题目正文等敏感内容。
    """
    _dispatch_sync(user_id, message, data)


def _dispatch_sync(user_id: Optional[int], message: str, data: Optional[dict]):
    """广播同步事件的共同实现

    Args:
        user_id: 为 None 时广播给所有人；为 int 时只发给该用户
    """
    try:
        from ..foundation.ws_relay import ws_relay

        payload_data = {"message": message}
        if data:
            payload_data.update(data)
        # v2：scope 由 data.scope 给出（缺省 global），便于前端按作用域去重；
        # 发送经 ws_relay，多 worker 时可跨进程送达。
        ws_relay.emit(
            "sync",
            data=payload_data,
            scope=payload_data.get("scope") or "global",
            user_ids=None if user_id is None else [user_id],
        )
    except Exception as e:
        # 广播失败绝不影响主业务流程（如题目导入、练习记录），仅记录告警
        logger.warning(f"广播同步事件失败: {e}")


def init_scheduler():
    """初始化并启动定时任务调度器"""
    from .difficulty import update_all_difficulties
    from .exam_scraper import scrape_all_exams
    from .news_collector import collect_all_sources
    from .recruitment_scraper import scrape_all_recruitment

    # 包装：爬取完成后广播同步事件（通知前端刷新）
    def _news_with_broadcast():
        from ..core.database import SessionLocal

        db = SessionLocal()
        try:
            collect_all_sources(db, limit=5, dry_run=False)
        finally:
            db.close()
        _broadcast_sync("新闻更新")

    def _recruitment_with_broadcast():
        scrape_all_recruitment()
        _broadcast_sync("招考信息更新")

    def _exams_with_broadcast():
        scrape_all_exams()
        _broadcast_sync("考试日历更新")

    # 每日 08:00 / 18:00（北京时间）采集白名单新闻
    scheduler.add_job(
        _news_with_broadcast,
        trigger=CronTrigger(hour="8,18", minute=0, timezone=CST),
        id="collect_news_8_18",
        name="每日新闻采集 08:00/18:00",
        replace_existing=True,
    )
    scheduler.add_job(
        _recruitment_with_broadcast,
        trigger=CronTrigger(hour=0, minute=5, timezone=CST),
        id="scrape_recruitment",
        name="招考信息爬取",
        replace_existing=True,
    )
    scheduler.add_job(
        _exams_with_broadcast,
        trigger=CronTrigger(hour=0, minute=0, timezone=CST),
        id="scrape_exams",
        name="考试日历爬取+清理",
        replace_existing=True,
    )

    # 每日 02:00（北京时间）执行 IRT 难度更新（在爬取完成后，避开高峰期）
    scheduler.add_job(
        update_all_difficulties,
        trigger=CronTrigger(hour=2, minute=0, timezone=CST),
        id="update_difficulties",
        name="每日IRT难度更新",
        replace_existing=True,
    )

    # 每日 03:30（北京时间）内容安全知识库自维护：
    # 红队找盲区 → 跨层对账 → 导出 Obsidian 待审队列。
    # 离线链路，任何一步失败都只告警，不影响实时审核。
    def _content_guard_maintenance():
        from ..core.database import SessionLocal
        from .content_guard import obsidian, reconcile, redteam

        db = SessionLocal()
        try:
            redteam.run(db, limit=50)
            reconcile.run(db)
            obsidian.export_all(db)
            db.commit()
            logger.info("内容安全知识库自维护完成")
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.warning(f"内容安全知识库自维护失败: {exc}")
        finally:
            db.close()

    scheduler.add_job(
        _content_guard_maintenance,
        trigger=CronTrigger(hour=3, minute=30, timezone=CST),
        id="content_guard_maintenance",
        name="敏感词知识库自维护（红队/对账/投影）",
        replace_existing=True,
    )

    # 每日 03:10（北京时间）金币到期清零（2026-11-04 M1）
    # 金币有效期 12 个月滚动清零：把 expire_at 已过的批次剩余额度扣掉并写 EXPIRE 流水。
    def _expire_coins():
        from ..core.database import SessionLocal
        from .coin_ledger import expire_due

        db = SessionLocal()
        try:
            report = expire_due(db)
            logger.info(f"金币到期清零完成: {report}")
        except Exception as exc:  # noqa: BLE001 - 定时任务失败不影响主流程
            db.rollback()
            logger.warning(f"金币到期清零失败: {exc}")
        finally:
            db.close()

    scheduler.add_job(
        _expire_coins,
        trigger=CronTrigger(hour=3, minute=10, timezone=CST),
        id="expire_coins",
        name="金币到期清零（12 个月滚动）",
        replace_existing=True,
    )

    # 每周一 00:05（北京时间）重建周任务置顶池（2026-11-05 M2）
    def _rebuild_weekly_pool():
        from ..core.database import SessionLocal
        from .weekly_tasks import ensure_week_pool

        db = SessionLocal()
        try:
            rows = ensure_week_pool(db)
            logger.info(f"周任务置顶池重建完成: {len(rows)} 条")
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.warning(f"周任务置顶池重建失败: {exc}")
        finally:
            db.close()

    scheduler.add_job(
        _rebuild_weekly_pool,
        trigger=CronTrigger(day_of_week="mon", hour=0, minute=5, timezone=CST),
        id="rebuild_weekly_pool",
        name="周任务置顶池（每周一 00:05）",
        replace_existing=True,
    )

    # 每日 03:20（北京时间）把过期的未完成周任务置为已失效
    def _expire_weekly_tasks():
        from datetime import datetime as _dt

        from ..core.database import SessionLocal
        from ..models.models import Task, UserTaskProgress
        from .weekly_tasks import week_key

        db = SessionLocal()
        try:
            week = week_key()
            rows = (
                db.query(UserTaskProgress, Task)
                .join(Task, Task.task_id == UserTaskProgress.task_id)
                .filter(
                    Task.t_type == "weekly",
                    UserTaskProgress.period_key != week,
                    UserTaskProgress.claimed == 0,
                    UserTaskProgress.expired == 0,
                )
                .all()
            )
            for prog, _task in rows:
                prog.expired = 1
            db.commit()
            if rows:
                logger.info(f"周任务失效处理: {len(rows)} 条")
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.warning(f"周任务失效处理失败: {exc}")
        finally:
            db.close()

    scheduler.add_job(
        _expire_weekly_tasks,
        trigger=CronTrigger(hour=3, minute=20, timezone=CST),
        id="expire_weekly_tasks",
        name="周任务失效处理（每日 03:20）",
        replace_existing=True,
    )

    # 每日 03:30（北京时间）自生长知识图谱热度衰减（2026-11-05 M3）
    def _decay_kg():
        from ..core.database import SessionLocal
        from .kg_growth import decay

        db = SessionLocal()
        try:
            report = decay(db)
            logger.info(f"知识图谱衰减完成: {report}")
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.warning(f"知识图谱衰减失败: {exc}")
        finally:
            db.close()

    # 每日 03:40（北京时间）摘除已过期的头像框（2026-11-05）
    def _expire_decorations():
        from ..core.database import SessionLocal
        from .decoration_expiry import expire_all

        db = SessionLocal()
        try:
            report = expire_all(db)
            if report["removed"]:
                logger.info("头像框到期处理: %s", report)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.warning("头像框到期处理失败: %s", exc)
        finally:
            db.close()

    scheduler.add_job(
        _expire_decorations,
        trigger=CronTrigger(hour=3, minute=40, timezone=CST),
        id="expire_decorations",
        name="头像框到期摘除（每日 03:40）",
        replace_existing=True,
    )

    scheduler.add_job(
        _decay_kg,
        trigger=CronTrigger(hour=3, minute=30, timezone=CST),
        id="decay_kg_heat",
        name="知识图谱热度衰减（每日 03:30）",
        replace_existing=True,
    )

    # 模块4 v2：每日 20:00 站内提醒——今日任务未完成的用户
    def _remind_unfinished_tasks():
        from datetime import datetime as _dt

        from ..core.database import SessionLocal
        from ..models.models import StudyGoal, UserNotify

        db = SessionLocal()
        try:
            today = _dt.now().strftime("%Y-%m-%d")
            rows = (
                db.query(StudyGoal)
                .filter(
                    StudyGoal.status == 1,
                    StudyGoal.task_date == today,
                    StudyGoal.is_completed == 0,
                )
                .all()
            )
            users = {}
            for r in rows:
                users.setdefault(r.user_id, 0)
                users[r.user_id] += 1
            for uid, n in users.items():
                existing = (
                    db.query(UserNotify)
                    .filter(
                        UserNotify.user_id == uid,
                        UserNotify.notify_type == "task_remind",
                        UserNotify.create_time
                        >= _dt.now().replace(hour=0, minute=0, second=0, microsecond=0),
                    )
                    .first()
                )
                if existing:
                    continue  # 当日已提醒过，不重复打扰
                db.add(
                    UserNotify(
                        user_id=uid,
                        content=f"今天还有 {n} 个学习任务未完成，快去完成并领取金币吧！",
                        notify_type="task_remind",
                    )
                )
            db.commit()
        except Exception as _e:
            import logging

            logging.getLogger(__name__).warning("每日任务提醒失败: %s", _e)
        finally:
            db.close()

    scheduler.add_job(
        _remind_unfinished_tasks,
        trigger=CronTrigger(hour=20, minute=0, timezone=CST),
        id="task_remind",
        name="每日任务未完成提醒",
        replace_existing=True,
    )

    # 每日 03:00 清理过期斩题记录
    def cleanup_expired_zhanti():
        """清理过期的斩题记录（auto_delete_time < now 的记录物理删除）"""
        from ..core.database import SessionLocal
        from ..models.models import WrongQuestionPersonal

        db = SessionLocal()
        try:
            expired = (
                db.query(WrongQuestionPersonal)
                .filter(
                    WrongQuestionPersonal.is_cut == 1,
                    WrongQuestionPersonal.auto_delete_time < datetime.now(),
                )
                .all()
            )
            for wq in expired:
                db.delete(wq)
            db.commit()
            if expired:
                logger.info(f"已清理 {len(expired)} 条过期斩题记录")
        except Exception as e:
            logger.error(f"清理斩题记录失败: {e}")
            db.rollback()
        finally:
            db.close()

    scheduler.add_job(
        cleanup_expired_zhanti,
        trigger=CronTrigger(hour=3, minute=0, timezone=CST),
        id="cleanup_zhanti",
        name="每日清理过期斩题",
        replace_existing=True,
    )

    # 每日 04:00 清理超期暂存图（F-2 配套：导入确认后暂存扁平图不再即时删除，
    # 改为按时间延迟回收，避免重复导入同一文档时 text_cache 命中而图已删）
    def cleanup_stale_staged():
        from ..services.question_ingest.images import cleanup_stale_staged_images

        cleanup_stale_staged_images(max_age_days=7)

    scheduler.add_job(
        cleanup_stale_staged,
        trigger=CronTrigger(hour=4, minute=0, timezone=CST),
        id="cleanup_staged_images",
        name="每日清理超期暂存图",
        replace_existing=True,
    )

    # 每周日 20:30 复盘提醒（长期陪伴：统计本周完成 + 提示复盘调整下周计划）
    def _weekly_review_remind():
        from datetime import datetime as _dt
        from datetime import timedelta as _td

        from ..core.database import SessionLocal
        from ..models.models import StudyGoal, UserNotify

        db = SessionLocal()
        try:
            now = _dt.now()
            monday = (now - _td(days=now.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            week_key = monday.strftime("%Y-%m-%d")
            users_with_tasks = (
                db.query(StudyGoal.user_id)
                .filter(StudyGoal.status == 1, StudyGoal.task_date >= week_key)
                .distinct()
                .all()
            )
            for (uid,) in users_with_tasks:
                done = (
                    db.query(StudyGoal)
                    .filter(
                        StudyGoal.user_id == uid,
                        StudyGoal.status == 1,
                        StudyGoal.task_date >= week_key,
                        StudyGoal.is_completed == 1,
                    )
                    .count()
                )
                total = (
                    db.query(StudyGoal)
                    .filter(
                        StudyGoal.user_id == uid,
                        StudyGoal.status == 1,
                        StudyGoal.task_date >= week_key,
                    )
                    .count()
                )
                existing = (
                    db.query(UserNotify)
                    .filter(
                        UserNotify.user_id == uid,
                        UserNotify.notify_type == "weekly_review",
                        UserNotify.create_time >= monday,
                    )
                    .first()
                )
                if existing:
                    continue
                db.add(
                    UserNotify(
                        user_id=uid,
                        content=f"【本周复盘】本周共 {total} 个任务，完成 {done} 个。周日花 30 分钟总结薄弱点，可让联考小智帮你调整下周计划。",
                        notify_type="weekly_review",
                    )
                )
            db.commit()
        except Exception as _e:
            import logging

            logging.getLogger(__name__).warning("每周复盘提醒失败: %s", _e)
        finally:
            db.close()

    scheduler.add_job(
        _weekly_review_remind,
        trigger=CronTrigger(day_of_week="sun", hour=20, minute=30, timezone=CST),
        id="weekly_review",
        name="每周复盘提醒",
        replace_existing=True,
    )

    # 每日 03:30 论坛回收站审计（只统计与写审计日志，不自动删除）
    def audit_forum_recycle():
        from ..core.database import SessionLocal
        from ..services.forum_audit import run_forum_recycle_audit

        db = SessionLocal()
        try:
            stats = run_forum_recycle_audit(db)
            logger.info(f"论坛回收站审计完成: {stats}")
        except Exception as exc:  # noqa: BLE001
            logger.error(f"论坛回收站审计失败: {exc}")
            db.rollback()
        finally:
            db.close()

    scheduler.add_job(
        audit_forum_recycle,
        trigger=CronTrigger(hour=3, minute=30, timezone=CST),
        id="audit_forum_recycle",
        name="每日论坛回收站审计",
        replace_existing=True,
    )

    def purge_forum_recycle():
        """回收站保留 30 天，超期物理删除（帖子 + 其评论）。"""
        from ..core.database import SessionLocal
        from .forum_recycle import purge_expired

        db = SessionLocal()
        try:
            result = purge_expired(db)
            logger.info("论坛回收站到期清理完成: %s", result)
        except Exception as exc:  # noqa: BLE001
            logger.error("论坛回收站到期清理失败: %s", exc)
            db.rollback()
        finally:
            db.close()

    scheduler.add_job(
        purge_forum_recycle,
        trigger=CronTrigger(hour=3, minute=40, timezone=CST),
        id="purge_forum_recycle",
        name="论坛回收站 30 天到期清理",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("定时任务调度器已启动（每日 24:00 CST）")

    # 启动时立即执行一次（延迟 30 秒，等数据库就绪）
    def _initial_run():
        try:
            logger.info("执行首次全量爬取...")
            # 新闻：v2 采集器统一走 collect_all_sources（旧的 scrape_all_news 已不存在）
            _news_with_broadcast()
            scrape_all_recruitment()
            scrape_all_exams()
            logger.info("首次全量爬取完成")
        except Exception as e:
            logger.error(f"首次爬取失败（服务继续运行）: {e}")

    scheduler.add_job(
        _initial_run,
        trigger="date",
        run_date=datetime.now(CST) + timedelta(seconds=30),
        id="initial_scrape",
        name="首次全量爬取",
    )


def shutdown_scheduler():
    """关闭调度器"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("定时任务调度器已关闭")
