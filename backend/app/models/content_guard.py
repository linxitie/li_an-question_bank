"""评论内容安全（敏感词）自生长知识库模型。

设计边界（与 AGENTS.md §2 红线一致）：
- 事实源仍是 SQLite；向量/图谱只是可重建投影，不新增外部强依赖；
- 本模块只新增 `cg_*` 前缀表，不改既有表结构（补列由 content_guard_schema 幂等完成）；
- 词条判定实例、审核任务、知识提案、审计事件全部落库，导出到 Obsidian 的是投影。

分层：
  政策层 cg_policy      —— 违规类别/等级/优先级/法律依据，变化慢、权重高
  运行层 cg_term/variant —— 词条与变体，DFA 引擎的唯一事实源
  判定层 cg_judgment/task —— 每次审核的命中、证据链、人工复核状态机
  治理层 cg_proposal/case/audit —— 知识变更提案、案例、追加式哈希链审计
  图谱层 cg_edge/stat_daily/redteam —— 三层本体关系、趋势、红队样本
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from ..core.database import Base

# ------------------------------
# 政策层
# ------------------------------
class CgPolicy(Base):
    """政策条款：审核判定的最终锚点（可回溯，不黑箱）。"""

    __tablename__ = "cg_policy"

    clause_id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(40), nullable=False, unique=True, comment="条款编号，如 PG-01-01")
    title = Column(String(200), nullable=False, comment="条款标题")
    category = Column(String(40), nullable=False, comment="违规域")
    level = Column(String(20), nullable=False, default="reviewed", comment="blocked/masked/reviewed")
    severity = Column(Integer, nullable=False, default=3, comment="严重度 1-5")
    priority = Column(Integer, nullable=False, default=50, comment="仲裁优先级，越大越优先")
    status = Column(String(20), nullable=False, default="active", comment="active/draft/archived")
    legal_basis = Column(Text, comment="法律/校规依据")
    content = Column(Text, comment="条款正文")
    version = Column(Integer, nullable=False, default=1)
    effective_from = Column(DateTime, comment="生效时间")
    effective_to = Column(DateTime, comment="失效时间")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("ix_cg_policy_cat_status", "category", "status"),
    )


# ------------------------------
# 运行层：词条 / 变体
# ------------------------------
class CgTerm(Base):
    """敏感词条。status=active 才进入 DFA；candidate 等待人工确认后生效。"""

    __tablename__ = "cg_term"

    term_id = Column(Integer, primary_key=True, autoincrement=True)
    term = Column(String(200), nullable=False, comment="展示词")
    normalized = Column(String(200), nullable=False, comment="归一化去重键")
    level = Column(String(20), nullable=False, default="masked", comment="blocked/masked/reviewed")
    category = Column(String(40), nullable=False, default="other", comment="违规域")
    weight = Column(Float, nullable=False, default=0.8, comment="基础置信度 0-1")
    confidence = Column(Float, nullable=False, default=0.8, comment="经人工反馈校准后的置信度 0-1")
    status = Column(String(20), nullable=False, default="active", comment="active/candidate/deprecated")
    source = Column(String(20), nullable=False, default="manual", comment="seed/manual/auto/redteam/appeal/import")
    policy_clause_id = Column(Integer, ForeignKey("cg_policy.clause_id"), comment="主政策条款")
    hit_count = Column(Integer, nullable=False, default=0)
    block_count = Column(Integer, nullable=False, default=0)
    mask_count = Column(Integer, nullable=False, default=0)
    review_count = Column(Integer, nullable=False, default=0)
    false_positive_count = Column(Integer, nullable=False, default=0)
    first_seen_at = Column(DateTime, default=datetime.now)
    last_hit_at = Column(DateTime)
    note = Column(Text)
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(Integer, comment="创建人 user_id，系统种子为 0")
    updated_by = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint("normalized", name="uq_cg_term_normalized"),
        Index("ix_cg_term_level_status", "level", "status"),
        Index("ix_cg_term_category", "category"),
    )


class CgVariant(Base):
    """词条变体：同音/拆字/插符号/全半角/繁体等对抗写法。"""

    __tablename__ = "cg_variant"

    variant_id = Column(Integer, primary_key=True, autoincrement=True)
    term_id = Column(Integer, ForeignKey("cg_term.term_id"), nullable=False)
    variant = Column(String(200), nullable=False, comment="变体展示形式")
    normalized = Column(String(200), nullable=False, comment="归一化去重键")
    kind = Column(String(20), nullable=False, default="symbol", comment="pinyin/homophone/split/symbol/traditional/leet/fullwidth")
    status = Column(String(20), nullable=False, default="active", comment="active/candidate")
    hit_count = Column(Integer, nullable=False, default=0)
    created_by = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("term_id", "normalized", name="uq_cg_variant_term_norm"),
        Index("ix_cg_variant_status", "status"),
    )


# ------------------------------
# 判定层
# ------------------------------
class CgJudgment(Base):
    """一次审核判定实例：命中、政策条款、证据链、处置结论。"""

    __tablename__ = "cg_judgment"

    judgment_id = Column(Integer, primary_key=True, autoincrement=True)
    scene = Column(String(40), nullable=False, default="forum_post", comment="forum_post/forum_comment/profile/import")
    source_id = Column(Integer, comment="帖子/评论 ID，可为空（发布前拦截）")
    user_id = Column(Integer, comment="被审核用户")
    content_hash = Column(String(64), nullable=False, comment="原文 sha256，不存原文")
    content_snippet = Column(String(200), comment="脱敏摘要（命中词替换为 *）")
    level = Column(String(20), nullable=False, default="pass")
    decision = Column(String(20), nullable=False, default="pass", comment="block/mask/review/pass")
    confidence = Column(Float, nullable=False, default=0.0)
    hits = Column(JSON, nullable=False, default=list, comment="命中列表")
    policy_ids = Column(JSON, nullable=False, default=list)
    evidence = Column(JSON, nullable=False, default=list, comment="判定依据链")
    engine_version = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Float, nullable=False, default=0.0)
    human_override = Column(String(20), comment="confirm/reject/modify，空表示未复核")
    overridden_by = Column(Integer)
    override_reason = Column(String(500))
    overridden_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("ix_cg_judgment_created", "created_at"),
        Index("ix_cg_judgment_scene_source", "scene", "source_id"),
        Index("ix_cg_judgment_decision", "decision"),
    )


class CgTask(Base):
    """审核任务状态机：pending 才进人工队列，auto_* 为自动处置留痕。"""

    __tablename__ = "cg_task"

    task_id = Column(Integer, primary_key=True, autoincrement=True)
    judgment_id = Column(Integer, ForeignKey("cg_judgment.judgment_id"), nullable=False)
    scene = Column(String(40), nullable=False)
    source_id = Column(Integer)
    state = Column(String(20), nullable=False, default="pending", comment="pending/auto_blocked/auto_masked/approved/rejected/appealing/closed")
    priority = Column(Integer, nullable=False, default=50)
    assignee_id = Column(Integer)
    reviewer_id = Column(Integer)
    note = Column(String(500))
    due_at = Column(DateTime)
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("ix_cg_task_state_created", "state", "created_at"),
        Index("ix_cg_task_judgment", "judgment_id"),
    )


# ------------------------------
# 治理层：提案 / 案例 / 审计
# ------------------------------
class CgProposal(Base):
    """知识变更提案：AI/红队/主动学习只能提案，人工确认后才写入知识库。"""

    __tablename__ = "cg_proposal"

    proposal_id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(String(30), nullable=False, comment="add_term/add_variant/update_level/deprecate_term/new_policy/merge_terms/consistency")
    title = Column(String(200), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    evidence = Column(JSON, nullable=False, default=list)
    proposer = Column(String(30), nullable=False, default="agent", comment="agent/redteam/active_learning/human/system")
    status = Column(String(20), nullable=False, default="pending", comment="pending/approved/rejected/applied/conflict")
    dedupe_key = Column(String(160), nullable=False, comment="防重复提案")
    reviewer_id = Column(Integer)
    review_note = Column(String(500))
    reviewed_at = Column(DateTime)
    applied_ref_type = Column(String(30))
    applied_ref_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_cg_proposal_dedupe"),
        Index("ix_cg_proposal_status_created", "status", "created_at"),
    )


class CgCase(Base):
    """案例库：人工确认后的判定沉淀为可检索案例，供类比与 few-shot。"""

    __tablename__ = "cg_case"

    case_id = Column(Integer, primary_key=True, autoincrement=True)
    judgment_id = Column(Integer, ForeignKey("cg_judgment.judgment_id"))
    title = Column(String(200), nullable=False)
    category = Column(String(40), nullable=False, default="other")
    level = Column(String(20), nullable=False, default="reviewed")
    verdict = Column(String(20), nullable=False, default="confirmed", comment="confirmed/false_positive/overridden")
    narrative = Column(Text, comment="案例叙述")
    tags = Column(JSON, nullable=False, default=list)
    source = Column(String(20), nullable=False, default="human", comment="human/auto")
    created_by = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("ix_cg_case_category", "category"),
    )


class CgAuditEvent(Base):
    """追加式审计事件：prev_hash + hash 形成哈希链，外部存储可作信任锚。"""

    __tablename__ = "cg_audit_event"

    event_id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, default=datetime.now, nullable=False)
    actor = Column(String(100), nullable=False, default="system")
    actor_role = Column(String(30), nullable=False, default="system")
    action = Column(String(60), nullable=False)
    target_type = Column(String(30))
    target_id = Column(String(60))
    before_hash = Column(String(64))
    after_hash = Column(String(64))
    payload = Column(JSON, nullable=False, default=dict)
    prev_hash = Column(String(64), nullable=False, default="GENESIS")
    hash = Column(String(64), nullable=False, unique=True)
    ip = Column(String(45))

    __table_args__ = (
        Index("ix_cg_audit_ts", "ts"),
        Index("ix_cg_audit_action", "action"),
    )


# ------------------------------
# 图谱层 / 趋势 / 红队
# ------------------------------
class CgEdge(Base):
    """三层本体关系边（政策/词条/判定/案例/事件）。"""

    __tablename__ = "cg_edge"

    edge_id = Column(Integer, primary_key=True, autoincrement=True)
    src_type = Column(String(30), nullable=False)
    src_id = Column(String(60), nullable=False)
    rel = Column(String(40), nullable=False)
    dst_type = Column(String(30), nullable=False)
    dst_id = Column(String(60), nullable=False)
    weight = Column(Float, nullable=False, default=1.0)
    props = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("src_type", "src_id", "rel", "dst_type", "dst_id", name="uq_cg_edge"),
        Index("ix_cg_edge_src", "src_type", "src_id"),
        Index("ix_cg_edge_dst", "dst_type", "dst_id"),
    )


class CgStatDaily(Base):
    """按天聚合的审核趋势，防止每次看板都扫全表。"""

    __tablename__ = "cg_stat_daily"

    stat_id = Column(Integer, primary_key=True, autoincrement=True)
    stat_date = Column(Date, nullable=False)
    scene = Column(String(40), nullable=False, default="all")
    total = Column(Integer, nullable=False, default=0)
    blocked = Column(Integer, nullable=False, default=0)
    masked = Column(Integer, nullable=False, default=0)
    reviewed = Column(Integer, nullable=False, default=0)
    passed = Column(Integer, nullable=False, default=0)
    false_positive = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("stat_date", "scene", name="uq_cg_stat_date_scene"),
    )


class CgRedteamSample(Base):
    """红队规避样本：记录生成文本、是否被当前规则拦截。"""

    __tablename__ = "cg_redteam_sample"

    sample_id = Column(Integer, primary_key=True, autoincrement=True)
    term_id = Column(Integer, ForeignKey("cg_term.term_id"))
    text = Column(String(500), nullable=False)
    kind = Column(String(30), nullable=False, default="symbol")
    detected = Column(Boolean, nullable=False, default=False)
    judgment_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("ix_cg_redteam_detected", "detected", "created_at"),
    )


class CgSyncState(Base):
    """键值状态：引擎版本、Obsidian 清单版本、最近对账摘要。"""

    __tablename__ = "cg_sync_state"

    key = Column(String(80), primary_key=True)
    value = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
