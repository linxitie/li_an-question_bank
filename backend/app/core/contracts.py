"""跨域公开契约的类型与注册表。

约束（设计规格 §3.2）：十个业务域之间**不得互相直接调用**。跨域交互只有两条合法路径：

1. **写操作**必须经本模块登记的契约；
2. **读操作**在 :data:`OPEN_READS` 内可直接放行，其余仍需登记。

本模块只定义与登记契约，不含业务逻辑，也不 import 任何业务模块——
它必须能在不触发业务导入链的情况下被单独加载。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Access(str, Enum):
    """跨域访问方式。"""

    OPEN_READ = "open_read"          # 读，免登记
    VIA_CONTRACT = "via_contract"    # 写，须走契约


@dataclass(frozen=True)
class Contract:
    """一条跨域契约。

    ``producer`` 声明谁拥有这份数据，``consumers`` 是被允许读取的域。
    刻意不含 ``payload`` —— 契约描述「谁能读什么」，具体形状由 P4 契约改造补齐。
    """

    name: str
    producer: str
    consumers: tuple[str, ...]
    access: Access = Access.VIA_CONTRACT
    description: str = ""

    def permits(self, domain: str) -> bool:
        return domain in self.consumers


# ── 免登记的跨域读 ────────────────────────────────────────
# 题库是全域公共只读数据源，任何域都可读；写仍须经契约。
OPEN_READS: tuple[str, ...] = (
    "catalog.question.read",     # 题目内容：三端全域只读
    "catalog.paper.read",        # 试卷元信息
    "identity.user.read",        # 用户基础信息（昵称/头像等公开字段）
)


# ── 跨域写契约 ────────────────────────────────────────────
_CONTRACTS: tuple[Contract, ...] = (
    Contract(
        name="exam.submit_result",
        producer="exam",
        consumers=("reward", "growth"),
        description="交卷后触发金币结算与任务进度更新",
    ),
    Contract(
        name="exam.grade_result",
        producer="exam",
        consumers=("growth",),
        description="判分完成后推进成就",
    ),
    Contract(
        name="catalog.import_completed",
        producer="catalog",
        consumers=("exam", "library"),
        description="题目导入完成，考试域可据此重建题库索引",
    ),
    Contract(
        name="catalog.paper_published",
        producer="catalog",
        consumers=("exam", "personal"),
        description="试卷发布后可被练习与收藏引用",
    ),
    Contract(
        name="reward.coins_granted",
        producer="reward",
        consumers=("growth",),
        description="金币变动后刷新任务进度",
    ),
    Contract(
        name="library.material_published",
        producer="library",
        consumers=("exam",),
        description="备考资料发布后可作为练习素材",
    ),
    Contract(
        name="identity.user_updated",
        producer="identity",
        consumers=("personal", "growth"),
        description="用户资料变更影响个人中心与成长体系",
    ),
)

_REGISTRY: dict[str, Contract] = {c.name: c for c in _CONTRACTS}


def register(contract: Contract) -> None:
    """登记一条新契约。重复登记同名契约会直接报错，避免静默覆盖。"""
    if contract.name in _REGISTRY:
        raise ValueError(f"契约重复登记: {contract.name}")
    _REGISTRY[contract.name] = contract


def get(name: str) -> Contract | None:
    return _REGISTRY.get(name)


def all_contracts() -> tuple[Contract, ...]:
    return tuple(_REGISTRY.values())


def is_open_read(name: str) -> bool:
    return name in OPEN_READS


def permits(contract_name: str, domain: str) -> bool:
    """``domain`` 是否有权经该契约读取数据。未知契约一律拒绝。"""
    c = _REGISTRY.get(contract_name)
    return bool(c and c.permits(domain))


def by_producer(domain: str) -> tuple[Contract, ...]:
    return tuple(c for c in _REGISTRY.values() if c.producer == domain)


def validate_registry() -> list[str]:
    """自检注册表一致性。返回问题清单，空列表表示健康。

    当前不引入域清单（那在 module_registry），故只查最基本的两条：
    重名与消费者自身。
    """
    problems: list[str] = []
    seen: set[str] = set()
    for c in _REGISTRY.values():
        if c.name in seen:
            problems.append(f"重复契约名: {c.name}")
        seen.add(c.name)
        if c.producer in c.consumers:
            problems.append(f"{c.name}: 生产者 {c.producer} 同时是消费者")
    overlap = set(OPEN_READS) & set(_REGISTRY)
    if overlap:
        problems.append(f"同时出现在开放读与契约中: {sorted(overlap)}")
    return problems


def consumers_of(names: Iterable[str]) -> set[str]:
    """给出一组契约的全部消费者，用于装配时做依赖闭包。"""
    out: set[str] = set()
    for n in names:
        c = _REGISTRY.get(n)
        if c:
            out.update(c.consumers)
    return out