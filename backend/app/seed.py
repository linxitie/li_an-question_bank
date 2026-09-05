"""
Seed 脚本 — 初始化模拟用户和系统配置
仅 DEBUG 模式自动执行，生产环境需手动运行
"""
import logging
from datetime import datetime

from .core.config import settings
from .core.database import SessionLocal
from .core.security import get_password_hash
from .models.models import SysUser, SysConfig, SubCategory, KnowledgePoint

logger = logging.getLogger(__name__)

# 模拟用户种子数据
SEED_USERS = [
    {
        "user_no": "ycc5678",
        "username": "ycc5678",
        "password": "ycc5678",
        "user_type": "teacher",
        "role_level": 1,
        "phone": "13800001001",
        "school": "中国人民警察大学",
        "department": "公安基础教研部",
        "title": "讲师",
        "email": "ycc5678@example.com",
    },
    {
        "user_no": "cbrycc",
        "username": "cbrycc",
        "password": "cbrycc",
        "user_type": "admin",
        "role_level": 3,  # 超级管理员
        "phone": "13800001002",
        "school": "中国人民警察大学",
        "email": "cbrycc@example.com",
    },
]

# 系统默认配置
DEFAULT_CONFIGS = [
    ("site_name", "砺安题库", "站点名称", "STRING"),
    ("max_login_attempts", "5", "最大登录尝试次数", "NUMBER"),
    ("exam_auto_submit_minutes", "120", "考试自动提交时间(分钟)", "NUMBER"),
    ("maintenance_mode", "false", "维护模式", "BOOLEAN"),
    ("register_open", "true", "是否开放注册", "BOOLEAN"),
    ("password_min_length", "6", "密码最小长度", "NUMBER"),
    ("announcement_default_visible", "all", "公告默认可见角色", "STRING"),
]


def seed_users():
    """创建模拟用户（幂等：已存在则跳过）"""
    db = SessionLocal()
    created_count = 0
    try:
        for user_data in SEED_USERS:
            existing = db.query(SysUser).filter(
                SysUser.user_no == user_data["user_no"]
            ).first()
            if existing:
                logger.info(f"Seed: 用户 {user_data['username']} 已存在，跳过")
                continue

            new_user = SysUser(
                user_no=user_data["user_no"],
                username=user_data["username"],
                password=get_password_hash(user_data["password"]),
                user_type=user_data["user_type"],
                role_level=user_data["role_level"],
                phone=user_data["phone"],
                school=user_data.get("school", "中国人民警察大学"),
                department=user_data.get("department"),
                title=user_data.get("title"),
                email=user_data.get("email"),
                status=1,
                is_disabled=0,
                register_time=datetime.now(),
            )
            db.add(new_user)
            created_count += 1
            logger.info(
                f"Seed: 创建{user_data['user_type']}用户 "
                f"{user_data['username']} (role_level={user_data['role_level']})"
            )

        db.commit()
        if created_count > 0:
            logger.info(f"Seed: 共创建 {created_count} 个模拟用户")
    except Exception as e:
        db.rollback()
        logger.error(f"Seed: 创建用户失败 - {e}")
        raise
    finally:
        db.close()


def seed_configs():
    """初始化系统默认配置（幂等：已存在则跳过）"""
    db = SessionLocal()
    try:
        created = 0
        for key, value, desc, ctype in DEFAULT_CONFIGS:
            existing = db.query(SysConfig).filter(
                SysConfig.config_key == key
            ).first()
            if existing:
                continue
            db.add(SysConfig(
                config_key=key,
                config_value=value,
                config_desc=desc,
                config_type=ctype,
            ))
            created += 1

        db.commit()
        if created > 0:
            logger.info(f"Seed: 初始化 {created} 个系统默认配置")
    except Exception as e:
        db.rollback()
        logger.warning(f"Seed: 配置初始化失败（可忽略） - {e}")
    finally:
        db.close()


# ============================================================
# 快速练习 — 子科目 & 考点种子数据
# ============================================================

# 子科目定义：(subject_id, name, description, sort_order)
SUB_CATEGORIES = [
    # === 行测 (subject_id=1) ===
    (1, "政治理论", "习近平新时代中国特色社会主义思想、党的二十大精神等", 1),
    (1, "常识判断", "经济、文化、社会、生态、法律、科技常识及时政热点", 2),
    (1, "言语理解与表达", "逻辑填空、片段阅读、语句表达、中心理解等", 3),
    (1, "数量关系", "数字推理、数学运算（工程/行程/排列组合等）", 4),
    (1, "判断推理", "图形推理、逻辑判断、类比推理、定义判断", 5),
    (1, "资料分析", "文字/图形/表格资料分析、统计术语、速算技巧", 6),
    (1, "知觉速度与准确性", "同符查找、数字区间定位、字符替换", 7),
    # === 申论 (subject_id=2) ===
    (2, "归纳概括", "问题/原因/影响/对策/特点/过程概括", 1),
    (2, "综合分析", "观点分析、现象分析、词句理解、评析辨析", 2),
    (2, "提出对策", "问题识别、对策建议、方案设计、应急处理", 3),
    (2, "应用文写作", "公文写作、事务文书、案例分析、宣传文稿", 4),
    (2, "议论文写作", "命题/话题/材料作文、政论文、策论文", 5),
    # === 公专 (subject_id=3) ===
    (3, "职业素养", "政治立场、警察核心价值观、职业道德与纪律", 1),
    (3, "基础知识", "法学基础、宪法、民法、人民警察法、公安基础", 2),
    (3, "基本警务能力", "宣传教育、沟通协调、巡逻接警、安全检查等", 3),
]

# 考点定义：(sub_category_index, point_name, sort_order)
# sub_category_index 对应 SUB_CATEGORIES 列表的索引
KNOWLEDGE_POINTS = [
    # === 行测 ===
    # 政治理论 (sub_cat idx=0)
    (0, "习近平新时代中国特色社会主义思想", 1),
    (0, "党的二十大精神", 2),
    (0, "马克思主义基本原理", 3),
    (0, "党和国家方针政策", 4),
    (0, "政治立场与政治敏锐性", 5),
    # 常识判断 (sub_cat idx=1)
    (1, "经济常识", 1),
    (1, "文化常识", 2),
    (1, "社会常识", 3),
    (1, "生态常识", 4),
    (1, "法律常识", 5),
    (1, "科技常识", 6),
    (1, "时政热点", 7),
    # 言语理解与表达 (sub_cat idx=2)
    (2, "逻辑填空", 1),
    (2, "片段阅读", 2),
    (2, "语句表达", 3),
    (2, "中心理解", 4),
    (2, "词语理解", 5),
    (2, "态度意图", 6),
    # 数量关系 (sub_cat idx=3)
    (3, "数字推理", 1),
    (3, "数学运算", 2),
    # 判断推理 (sub_cat idx=4)
    (4, "图形推理", 1),
    (4, "逻辑判断", 2),
    (4, "类比推理", 3),
    (4, "定义判断", 4),
    # 资料分析 (sub_cat idx=5)
    (5, "文字资料分析", 1),
    (5, "图形资料分析", 2),
    (5, "表格资料分析", 3),
    (5, "混合型资料", 4),
    (5, "统计术语", 5),
    (5, "速算技巧", 6),
    # 知觉速度与准确性 (sub_cat idx=6)
    (6, "同符查找", 1),
    (6, "数字区间定位", 2),
    (6, "字符替换", 3),
    (6, "知觉准确性", 4),

    # === 申论 ===
    # 归纳概括 (sub_cat idx=7)
    (7, "问题概括", 1),
    (7, "原因概括", 2),
    (7, "影响概括", 3),
    (7, "对策概括", 4),
    (7, "特点概括", 5),
    (7, "过程概括", 6),
    # 综合分析 (sub_cat idx=8)
    (8, "观点分析", 1),
    (8, "现象分析", 2),
    (8, "词句理解", 3),
    (8, "评析辨析", 4),
    (8, "比较分析", 5),
    # 提出对策 (sub_cat idx=9)
    (9, "问题识别", 1),
    (9, "对策建议", 2),
    (9, "方案设计", 3),
    (9, "应急处理", 4),
    (9, "长效机制", 5),
    # 应用文写作 (sub_cat idx=10)
    (10, "公文写作", 1),
    (10, "事务文书", 2),
    (10, "案例分析", 3),
    (10, "宣传文稿", 4),
    # 议论文写作 (sub_cat idx=11)
    (11, "命题作文", 1),
    (11, "话题作文", 2),
    (11, "材料作文", 3),
    (11, "政论文", 4),
    (11, "策论文", 5),

    # === 公专 ===
    # 职业素养 (sub_cat idx=12)
    (12, "政治立场与忠诚度", 1),
    (12, "政治敏锐性与鉴别力", 2),
    (12, "人民警察核心价值观", 3),
    (12, "人民警察职业道德", 4),
    (12, "人民警察职业纪律", 5),
    # 基础知识 (sub_cat idx=13)
    (13, "中国特色社会主义法治理论", 1),
    (13, "法学基础理论", 2),
    (13, "宪法基础知识", 3),
    (13, "民法基础知识", 4),
    (13, "人民警察法基础知识", 5),
    (13, "行政执法基础知识", 6),
    (13, "刑事执法基础知识", 7),
    (13, "公安机关性质与职能", 8),
    (13, "公安工作根本原则", 9),
    (13, "公安队伍建设", 10),
    (13, "公安执法监督", 11),
    # 基本警务能力 (sub_cat idx=14)
    (14, "宣传教育", 1),
    (14, "沟通协调", 2),
    (14, "组织动员", 3),
    (14, "服务群众", 4),
    (14, "调查研究", 5),
    (14, "纠纷化解", 6),
    (14, "风险识别", 7),
    (14, "风险防范", 8),
    (14, "信息收集", 9),
    (14, "信息分析", 10),
    (14, "信息应用", 11),
    (14, "巡逻", 12),
    (14, "接警与处警", 13),
    (14, "安全检查", 14),
    (14, "安全保护", 15),
    (14, "事态研判", 16),
    (14, "信息上报", 17),
    (14, "合理处置", 18),
    (14, "善后恢复", 19),
]


def seed_sub_categories_and_points():
    """初始化子科目和考点数据（幂等：已存在则跳过）"""
    db = SessionLocal()
    try:
        # --- 1. 创建子科目 ---
        sub_cat_map = {}  # (subject_id, name) → SubCategory obj
        for (subj_id, name, desc, order) in SUB_CATEGORIES:
            existing = db.query(SubCategory).filter(
                SubCategory.subject_id == subj_id,
                SubCategory.name == name
            ).first()
            if existing:
                sub_cat_map[(subj_id, name)] = existing
                continue
            sc = SubCategory(
                subject_id=subj_id,
                name=name,
                description=desc,
                sort_order=order,
                status=1,
            )
            db.add(sc)
            db.flush()  # 获取自增ID
            sub_cat_map[(subj_id, name)] = sc

        db.commit()
        logger.info(f"Seed: 子科目数据就绪（共 {len(SUB_CATEGORIES)} 条）")

        # --- 2. 创建考点 ---
        created_kp = 0
        for (sc_idx, point_name, order) in KNOWLEDGE_POINTS:
            subj_id, sc_name, _, _ = SUB_CATEGORIES[sc_idx]
            sc = sub_cat_map.get((subj_id, sc_name))
            if not sc:
                continue

            existing = db.query(KnowledgePoint).filter(
                KnowledgePoint.subject_id == subj_id,
                KnowledgePoint.sub_category_id == sc.id,
                KnowledgePoint.point_name == point_name
            ).first()
            if existing:
                continue

            kp = KnowledgePoint(
                point_name=point_name,
                subject_id=subj_id,
                sub_category_id=sc.id,
                level=2,
                sort_order=order,
            )
            db.add(kp)
            created_kp += 1

        db.commit()
        if created_kp > 0:
            logger.info(f"Seed: 创建 {created_kp} 个考点")

    except Exception as e:
        db.rollback()
        logger.warning(f"Seed: 子科目/考点初始化失败（可忽略） - {e}")
    finally:
        db.close()


def run_seed():
    """执行所有 Seed 任务"""
    logger.info("=" * 50)
    logger.info("Seed: 开始执行数据初始化...")
    logger.info("=" * 50)

    # 仅在 DEBUG 模式自动执行
    if not settings.DEBUG:
        logger.info("Seed: 非 DEBUG 模式，跳过自动种子数据。手动执行: python -m app.seed")
        return

    seed_configs()
    seed_users()
    seed_sub_categories_and_points()

    logger.info("Seed: 数据初始化完成")
    logger.info("=" * 50)
    logger.info("模拟用户:")
    logger.info("  教师端: ycc5678 / ycc5678 (teacher, role_level=1)")
    logger.info("  管理员端: cbrycc / cbrycc (admin, role_level=3)")
    logger.info("=" * 50)


if __name__ == "__main__":
    run_seed()
