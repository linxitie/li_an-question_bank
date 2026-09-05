"""
APScheduler 定时任务管理
每日 24:00（北京时间）触发新闻、招考、考试日历爬取
"""
import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# 北京时间时区
CST = timezone(timedelta(hours=8))

scheduler = BackgroundScheduler(timezone=CST, job_defaults={"misfire_grace_time": 300})


def init_scheduler():
    """初始化并启动定时任务调度器"""
    from .news_scraper import scrape_all_news
    from .recruitment_scraper import scrape_all_recruitment
    from .exam_scraper import scrape_all_exams
    from .difficulty import update_all_difficulties

    # 每日 24:00（北京时间）执行爬取
    scheduler.add_job(
        scrape_all_news,
        trigger=CronTrigger(hour=0, minute=0, timezone=CST),
        id="scrape_news",
        name="每日新闻爬取",
        replace_existing=True
    )
    scheduler.add_job(
        scrape_all_recruitment,
        trigger=CronTrigger(hour=0, minute=5, timezone=CST),
        id="scrape_recruitment",
        name="招考信息爬取",
        replace_existing=True
    )
    scheduler.add_job(
        scrape_all_exams,
        trigger=CronTrigger(hour=0, minute=0, timezone=CST),
        id="scrape_exams",
        name="考试日历爬取+清理",
        replace_existing=True
    )

    # 每日 02:00（北京时间）执行 IRT 难度更新（在爬取完成后，避开高峰期）
    scheduler.add_job(
        update_all_difficulties,
        trigger=CronTrigger(hour=2, minute=0, timezone=CST),
        id="update_difficulties",
        name="每日IRT难度更新",
        replace_existing=True
    )

    # 每日 03:00 清理过期斩题记录
    def cleanup_expired_zhanti():
        """清理过期的斩题记录（auto_delete_time < now 的记录物理删除）"""
        from ..models.models import WrongQuestionPersonal
        from ..core.database import SessionLocal
        db = SessionLocal()
        try:
            expired = db.query(WrongQuestionPersonal).filter(
                WrongQuestionPersonal.is_cut == 1,
                WrongQuestionPersonal.auto_delete_time < datetime.now()
            ).all()
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
        replace_existing=True
    )

    scheduler.start()
    logger.info("定时任务调度器已启动（每日 24:00 CST）")

    # 启动时立即执行一次（延迟 30 秒，等数据库就绪）
    def _initial_run():
        try:
            logger.info("执行首次全量爬取...")
            scrape_all_news()
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
        name="首次全量爬取"
    )


def shutdown_scheduler():
    """关闭调度器"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("定时任务调度器已关闭")
