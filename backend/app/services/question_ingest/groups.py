"""题组建组单一入口（I-8：任务 43）

`_upsert_question_group()` 是**唯一**的 `QuestionGroup` 建组入口。它收敛了
`api/v1/question_import.py` 中原先逐字重复的三段「构造 → db.add → db.flush →
图片落盘」：

  · `_get_or_create_shenlun_material_group`（申论「给定材料」行）
  · `_detect_and_link_composite_groups` 层1（题号/材料/情境/文章标识命中）
  · `_detect_and_link_composite_groups` 层2（语义增强兜底分组）

为什么收敛：
  三处的**四步序列完全相同**，唯一差别是 `group_type` 与四个业务字段的取值。
  历史上任一步（例如图片落盘）改动都要改三处，漏一处就留下行为分叉的建组路径 ——
  J-1-1 的图片回写正是因此才要求「每个建组点都要调」。

**行为等价保证（不得放宽）**：收敛只搬走公共序列，字段取值语义**逐调用点保留**，
调用方把原来写在 `QuestionGroup(...)` 里的表达式原样传进来：

  | 调用点                    | group_type                        | title                          | subject          | source                       |
  |---------------------------|-----------------------------------|--------------------------------|------------------|------------------------------|
  | 申论给定材料              | `'shenlun_material'`（固定）      | `(subject_name + ' 给定材料')[:200]` | `subject_name or '申论'` | `source_tag or ''`            |
  | 复合题层1（规则集命中）   | `match_group_head()` 返回值       | `shared_content[:200]`（默认） | `subject_name or '公专'` | `source_tag or paper_name`    |
  | 复合题层2（语义增强兜底） | `sug.get('group_type') or 'material'` | `shared_content[:200]`（默认） | `subject_name or '公专'` | `source_tag or paper_name`    |

故 `title` 缺省才落回 `shared_content[:200]`：它**只**对应层1/层2；
申论那条走的是「科目名 + 给定材料」的专属标题，必须显式传入。

★ 依赖方向说明（架构约束，**非逻辑变更**）：
  本模块**反向依赖** `api.v1.question_import._persist_group_images`（题组图片落盘
  + 回写）。因此 `question_import.py` 对本模块的 import **必须**置于
  `_persist_group_images` 定义之后（不能提到文件头），否则 `question_ingest`
  包初始化时会撞上「半初始化的 question_import」而 ImportError
  —— 与 `upsert.py` 的同款约束，参见 `question_ingest/__init__.py` 注释。
"""
import json
import logging
from typing import Optional, Union

from sqlalchemy.orm import Session

from ...models.models import QuestionGroup
from ..rich_text import sanitize_rich_text

logger = logging.getLogger(__name__)

# `question_groups.group_type` 的合法取值（models.py:265-266 + 申论材料行）。
# 这里只做**声明与自检**，不做强制转换 —— 调用点原有的兜底表达式
# （`sug.get('group_type') or 'material'`）必须原样保留，转换会改变其语义。
VALID_GROUP_TYPES = frozenset({
    'shenlun_material',   # 申论「给定材料」
    'material',           # 材料题组（复合题兜底缺省值 / 模型列默认值）
    'scenario',           # 情境题组
    'passage',            # 文章题组
    'data_analysis',      # 数据分析题组
})


def _upsert_question_group(
    db: Session,
    group_type: str,
    shared_content: str,
    *,
    subject: str,
    source: str,
    title: Optional[str] = None,
) -> QuestionGroup:
    """建一条题组并完成图片落盘，返回已 flush 的 `QuestionGroup`（调用方拿 `.id`）。

    四步序列固定为 `db.add → db.flush → _persist_group_images`：
      · flush 必须先于图片落盘 —— 图片要落到 `{group.id}/` 子目录下；
      · 本函数**不 commit**，事务边界归调用方（与 `_upsert_xingce_question` 一致）。

    参数：
      group_type       题组类型，取值见 `VALID_GROUP_TYPES`。
      shared_content   共享材料/情境/文章正文；非空时缺省 title 取其前 200 字。
      subject          科目（行测/申论/公专），调用方自行兜底。
      source           来源（试卷名/年份），调用方自行兜底。
      title            题组标题；仅当调用点的标题**不是** `shared_content[:200]`
                       时显式传入（当前只有申论给定材料一条）。

    返回的实例已 `add`/`flush`，属性可直接读（`.id`、回写后的 `shared_content`）。
    """
    content = shared_content or ''
    group = QuestionGroup(
        group_type=group_type,
        shared_content=content,
        title=title if title is not None else content[:200],
        subject=subject,
        source=source,
    )
    db.add(group)
    db.flush()
    from ...api.v1.catalog.question_import import _persist_group_images
    _persist_group_images(group)
    return group


def upsert_question_material(
    db: Session,
    question,
    *,
    group_id: Optional[int] = None,
    shared_content: Optional[str] = None,
    shared_content_images: Optional[Union[str, list, dict]] = None,
    current_user=None,
) -> Optional[QuestionGroup]:
    """按需建组/改组/清空题组材料；不 commit，事务归调用方。

    三种生效分支：有 ``group_id`` 改组；无 ``group_id`` 但有材料新建组并回填
    ``question.group_id``；``group_id`` 与材料都为空时把题目解绑（``group_id=0``），
    旧组保留给其它成员继续使用。三个参数全为 ``None`` 时视为未修改材料。
    """
    if group_id is None and shared_content is None and shared_content_images is None:
        return _current_group(db, question)

    if current_user is not None:
        same_creator = question.creator_id == getattr(current_user, 'user_id', None)
        if not same_creator and (getattr(current_user, 'role_level', 0) or 0) < 3:
            raise PermissionError("无权修改此题目材料")

    if isinstance(shared_content_images, (list, dict)):
        shared_content_images = json.dumps(shared_content_images, ensure_ascii=False)

    # RT-7：题组材料是唯一写入口，落库前统一过浏览器信任边界清洗。
    # 只清共享材料；题干/选项/解析的清洗属 RT-7 其它写路径，不在本模块处理。
    if shared_content is not None:
        shared_content = sanitize_rich_text(shared_content)

    if not group_id:
        if not shared_content:
            question.group_id = 0
            return None

        subject_name = ''
        subject = getattr(question, 'subject', None)
        if subject is not None:
            subject_name = subject.subject_name or ''
        if not subject_name:
            subject_id = getattr(question, 'subject_id', None)
            subject_name = f"科目{subject_id}" if subject_id else ""

        group = _upsert_question_group(
            db,
            group_type="material",
            shared_content=shared_content,
            subject=subject_name,
            source=question.source or "",
            title=shared_content[:200],
        )
        if shared_content_images is not None:
            group.shared_content_images = shared_content_images
        question.group_id = group.id
        return group

    group = db.query(QuestionGroup).filter(QuestionGroup.id == group_id).first()
    if group is None:
        raise ValueError("题组不存在")

    if shared_content is not None:
        group.shared_content = shared_content
    if shared_content_images is not None:
        group.shared_content_images = shared_content_images
    question.group_id = group.id
    return group


def _current_group(db: Session, question) -> Optional[QuestionGroup]:
    gid = getattr(question, 'group_id', None) or 0
    if not gid:
        return None
    return db.query(QuestionGroup).filter(QuestionGroup.id == gid).first()