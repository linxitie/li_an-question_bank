"""单题/行测落库 + 去重检测（I-7：pure move 自 backend/app/api/v1/question_import.py，任务 42）

四个函数体逐字节原样搬迁，**零逻辑变更**：
  · `_detect_duplicate`       —— 精确匹配 + 模糊匹配（相似度 >= DEDUP_SIMILARITY_THRESHOLD）
  · `_get_duplicate_info`     —— 去重详情（前端展示用）
  · `_upsert_question_core`   —— 公专/申论单题入库核心（dedup_scope=qno_in_source 时按题号+来源，
                                 否则走文本相似度；去重口径逐字节保留）
  · `_upsert_xingce_question` —— 行测单题入库（全程不 commit，事务边界归调用方）

★ 依赖方向说明（架构约束，**非逻辑变更**）：
  本模块**反向依赖** `api.v1.question_import` 中的
  `coerce_difficulty` / `NEED_REVIEW_CONFIDENCE` / `_subcategory_tuple` /
  `_normalize_requirements` / `_get_or_create_shenlun_material_group`。
  因此 `question_import.py` 对本模块的 import **必须**置于上述符号定义之后（不能提到文件头）；
  同时 `question_ingest/__init__.py` 对本模块采用 PEP-562 惰性 re-export（见该文件注释）。
  在真实启动路径（app.main → api.v1.question_import）与门禁脚本路径下该顺序恒成立。
"""
import logging
import re
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session

from ...api.v1.catalog.question_import import (  # 反向依赖：见本模块 docstring
    NEED_REVIEW_CONFIDENCE,
    _get_or_create_shenlun_material_group,
    _normalize_requirements,
    _subcategory_tuple,
    coerce_difficulty,
)
from ...models.models import (
    QuestionBank,
    QuestionDetailCategory,
    QuestionImage,
    QuestionType,
    SysUser,
)
from ..text_parser import (
    DEDUP_SIMILARITY_THRESHOLD,
    _detect_question_type,
    clean_question_text,
    fuzzy_detect_duplicate,
    normalize_type_name,
)
from .images import _extract_and_save_images
from .links import _get_or_create_subject, _get_or_create_type, _link_knowledge_points
from .tags import SUBJECT_NAME_MAP

logger = logging.getLogger(__name__)


def _detect_duplicate(db: Session, content: str, answer: str = '', subject_id: Optional[int] = None, use_fuzzy: bool = True) -> Optional[QuestionBank]:
    """
    检测重复题目。
    - use_fuzzy=False: 仅精确匹配（兼容旧逻辑）
    - use_fuzzy=True: 精确匹配 + 模糊匹配（相似度 >= 80% 视为重复）

    返回匹配到的题目，或 None（无重复）。
    """
    if not content:
        return None

    if not use_fuzzy:
        # 精确匹配（旧逻辑）
        if answer:
            return db.query(QuestionBank).filter(
                and_(
                    QuestionBank.question_content == content,
                    QuestionBank.answer == answer,
                    QuestionBank.status != 0
                )
            ).first()
        return db.query(QuestionBank).filter(
            QuestionBank.question_content == content,
            QuestionBank.status != 0
        ).first()

    # 模糊匹配
    is_dup, matched, similarity = fuzzy_detect_duplicate(
        db, content, answer, subject_id, DEDUP_SIMILARITY_THRESHOLD
    )
    return matched if is_dup else None


def _get_duplicate_info(db: Session, content: str, answer: str = '', subject_id: Optional[int] = None) -> dict:
    """
    获取去重详情（用于前端展示）。
    返回 {'is_duplicate': bool, 'similarity': float, 'existing_id': int|null, 'existing_content': str|null}
    """
    is_dup, matched, similarity = fuzzy_detect_duplicate(
        db, content, answer, subject_id, DEDUP_SIMILARITY_THRESHOLD
    )
    return {
        'is_duplicate': is_dup,
        'similarity': round(similarity, 3),
        'existing_id': matched.question_id if matched else None,
        'existing_content': (matched.question_content[:100] + '...') if matched and matched.question_content and len(matched.question_content) > 100 else (matched.question_content if matched else None),
    }


def _upsert_question_core(db: Session, current_user: SysUser,
                          question_data: Dict[str, Any]) -> Dict[str, Any]:
    """单题入库核心逻辑（供 /single 与 /batch-parsed 复用）。

    与原 /single 函数体的差异：
      - 不创建 QuestionImportRecord（由调用方按批次汇总）
      - 不调用 db.commit()（调用方控制事务边界，批处理保证单事务）
    返回: {'import_status': 'SUCCESS'|'DUPLICATE', 'question_id': int, ...}
    """
    content = question_data.get('question_content', '').strip()
    answer = question_data.get('answer', '').strip()
    import_mode = question_data.get('import_mode', 'combined')

    # ★ 阻断闸门：解析器判定为 blocked 的题块一律拒绝入库。
    #   解析器会在下列情况置 blocked：
    #     · missing_score —— 题号行邻近找不到「（N分）」，题号可能误切
    #     · answer_block_count_mismatch —— 答案段数与题目数不等，按序硬配必然错配
    #   用户硬约束：宁可阻断报错交人工，也不允许静默丢题或按序盲配。
    #   必须在最前面拦：一旦入库，错配数据已经污染题库，事后无法区分。
    if question_data.get('blocked'):
        reasons = question_data.get('block_reasons') or ['unknown']
        raise HTTPException(
            status_code=400,
            detail='题目解析存在阻断问题，已拒绝导入（原因：%s）。'
                   '请人工核对原卷后重新导入。' % '、'.join(str(r) for r in reasons))

    if not content:
        raise HTTPException(status_code=400, detail="题目内容不能为空")
    if not answer and import_mode != 'separate':
        raise HTTPException(status_code=400, detail="题目内容和答案不能为空")
    if import_mode == 'separate' and not answer:
        # 分离模式：无答案题目标记为待补充
        answer = '待补充'

    # 统一清洗口径（问题1/T2 配套修复）：去重检测与入库存储必须使用同一
    # 清洗后的内容，否则"原始输入 vs 清洗后存储"指纹不一致会导致重复题
    # 漏检（生产库同题多副本的根因之一）。clean_question_text 移除 UTB ID、
    # "第X题："前缀并合并空白；清洗后为空则回退原文（防御极端输入）。
    content = clean_question_text(content) or content

    # 科目（在去重前获取，用于缩小候选范围）
    subject_name = question_data.get('subject_category', '行测')
    subject = _get_or_create_subject(db, subject_name)

    # 模糊去重检测
    # ── 行测专用口径（opt-in，纯增量；不传该键时行为逐字节不变）────────
    # 行测的去重主键是**题号 + 来源**，不是文本相似度。实测「国考 2023 副省级」
    # 单套131 题中有 7 题 question_content 完全相同（4 题共用「选择最合适的一个
    # 填入问号处…」、3 题共用「把下面的六个图形分为两类…」），最短 6 条是 5~9 字的
    # 类比短语如「花海：书山」。图形推理的区分信息在**图片**里，文本层只有共用
    # 指令句或碎片，故 80% 文本相似度会把不同题判成同题 —— 实测 60% 被误判重复，
    # 且**静默丢弃、不报错**（预览层 match_rate 100%、blocked 0 完全拦不住）。
    # 行测题号在卷内唯一，故按 (question_number, source) 判定既精确又不会误杀。
    _dedup_scope = question_data.get('dedup_scope')
    if _dedup_scope == 'qno_in_source':
        _qno_d = str(question_data.get('question_number') or '').strip()
        _src_d = str(question_data.get('source') or '').strip()
        existing = None
        if _qno_d and _src_d:
            existing = db.query(QuestionBank).filter(
                QuestionBank.question_number == _qno_d,
                QuestionBank.source == _src_d,
                QuestionBank.status != 0
            ).first()
    else:
        existing = _detect_duplicate(db, content, answer, subject.subject_id)
    if existing:
        # ===== A2 回填式重导入 =====
        # 已存题缺字段而新导入数据有 → 补空不覆盖（绝不破坏已有非空值）。
        # 用户重导入题目/答案文档 = 给存量题补营养，不产生新重复。
        backfilled = []
        new_analysis = (question_data.get('answer_analysis') or '').strip()
        if new_analysis and len(new_analysis) > 10 and \
                not (existing.answer_analysis or '').strip():
            existing.answer_analysis = new_analysis
            backfilled.append('answer_analysis')
        new_ans = answer
        if new_ans and (existing.answer or '').strip() in ('', '待补充'):
            existing.answer = new_ans
            backfilled.append('answer')
        new_source = (question_data.get('source') or '').strip()
        if new_source and not (existing.source or '').strip():
            existing.source = new_source
            backfilled.append('source')
        new_year = question_data.get('exam_year') or question_data.get('year')
        if new_year and not existing.year:
            try:
                existing.year = int(new_year)
                backfilled.append('year')
            except (TypeError, ValueError):
                pass
        # 题干图回填：新导入带 <img>（如看图选择题的图标条）而已存题无
        if '<img' in content and '<img' not in (existing.question_content or ''):
            existing.question_content = content
            backfilled.append('content_images')
        if backfilled:
            logger.info(f"[backfill] 题目{existing.question_id} 回填字段: {backfilled}")
        dup_info = _get_duplicate_info(db, content, answer, subject.subject_id)
        return {
            'import_status': 'DUPLICATE',
            'question_id': existing.question_id,
            'backfilled_fields': backfilled,
            'message': (f'该题目已存在（相似度 {dup_info["similarity"]*100:.0f}%，'
                        f'现有ID: {existing.question_id}）'
                        + (f'，已回填缺失字段: {",".join(backfilled)}' if backfilled else '')),
            'similarity': dup_info['similarity'],
            'existing_content_preview': dup_info.get('existing_content'),
            'error_messages': [{'error': '重复题目', 'existing_id': existing.question_id, 'similarity': dup_info['similarity']}]
        }

    # 题型
    options = question_data.get('options')
    # ★ '选择题' 是历史遗留的"泛型桶"（前端 Excel 默认值），它会让单选/多选无法区分。
    #   这里交给 text_parser 的规则优先级分类器做一次判定（P3 单一事实来源）。
    type_name = question_data.get('question_type_detail') or ''
    if not type_name or type_name == '选择题':
        type_name, _conf = _detect_question_type(content, options or [], answer or '')
    qtype = _get_or_create_type(db, type_name, subject.subject_id)

    # P3b：题型判定置信度不足 → need_review=1，交教师在「题目管理 → 待复核」确认。
    # ★ 申论豁免：_detect_question_type 是选择题分类器，申论是长文本主观题，
    #   拿它打分必然 <0.60 → 每道申论题都被标 need_review=1，
    #   前端弹「低置信度题目(建议人工核对): 第1,2,3,4题」，逼用户逐题人工确认。
    #   申论题型由解析器的体例判定直接给出（简答题/论述题），无需再猜。
    _is_essay = (question_data.get('format') == 'essay')
    if _is_essay:
        type_name = type_name or '简答题'
    need_review = 0
    if _is_essay:
        need_review = 0
    else:
        try:
            _t, _c = _detect_question_type(content, options or [], answer or '')
            if _c < NEED_REVIEW_CONFIDENCE:
                need_review = 1
        except Exception:  # noqa: BLE001 — 判定失败不能阻塞入库
            need_review = 1

    # 创建题目
    # ★ 难度必须走 coerce_difficulty：前端导入预览页用中文下拉（简单/较易/中等/较难/困难），
    #   直接 int() 会抛 `invalid literal for int() with base 10: '中等'` 并让整批导入失败。
    difficulty = coerce_difficulty(question_data.get('difficulty'))
    try:
        score = float(question_data.get('score') or 1.0)
    except (TypeError, ValueError):
        score = 1.0
    if score <= 0:
        score = 1.0

    _xingce_sc, _shenlun_sc, _gongzhuan_sc = _subcategory_tuple(
        subject.subject_id, content, type_name,
        question_data.get('subcategory') or question_data.get('子科目') or ''
    )
    # content 已在函数入口统一清洗（与去重同口径），直接入库
    # 申论「给定材料」落 question_groups 并回填 group_id：同一份材料由所有小题共享，
    # helper 内部按内容指纹去重，保证一份卷只建一行材料。
    _shenlun_gid = 0
    # ★ 键名对齐：解析器实际产出的是 `material_text`（整份给定资料正文）与
    #   `material_titles`（['材料1','材料2',...]），**不是** `material`。
    #   实测误接 `material` 导致 group_id 恒为 0、材料整份丢失。
    #   这里同时兼容 material（Excel/手工导入路径）与 material_text（解析器路径）。
    _material = (question_data.get('material_text')
                 or question_data.get('material') or '')
    if _material:
        _shenlun_gid = (_get_or_create_shenlun_material_group(
            db,
            _material,
            subject_name,
            question_data.get('source', ''),
        ) or 0)
    # 解析器已给出的题号/层级/组序，直接沿用；缺失时给安全默认值
    _group_id = _shenlun_gid or int(question_data.get('group_id') or 0)
    _qno = question_data.get('question_number')
    _qno = str(_qno).strip() if _qno not in (None, '') else None
    _qlevel = int(question_data.get('question_level') or 0) or 1
    _sort = int(question_data.get('sort_order') or 0)
    question = QuestionBank(
        group_id=_group_id,
        parent_id=int(question_data.get('parent_id') or 0),
        question_level=_qlevel,
        sort_order=_sort,
        question_number=_qno,
        subject_id=subject.subject_id,
        type_id=qtype.type_id,
        question_content=content,
        options=options,
        answer=answer,
        answer_analysis=question_data.get('answer_analysis', ''),
        difficulty=difficulty,
        need_review=need_review,
        score=score,
        year=question_data.get('exam_year') or question_data.get('year'),
        source=question_data.get('source', ''),
        tags=question_data.get('tags', ''),
        creator_id=current_user.user_id,
        audit_status=1,  # 自动通过审核
        xingce_subcategory=_xingce_sc,
        shenlun_subcategory=_shenlun_sc,
        gongzhuan_subcategory=_gongzhuan_sc,
        # 申论题目要求落库。解析器可能给 list（带编号分点）或 str（纯文本），
        # 统一按换行拼接成 TEXT 存储，检索与展示都不丢分点结构。
        requirements=_normalize_requirements(question_data.get('requirements')),
    )
    db.add(question)
    db.flush()

    # 图片提取与保存（异常不回滚整题，仅跳过图片）
    try:
        # ★ 扫描范围必须含答案与解析。
        #   实测 254 份申论语料中 118 份含真实图片，且**绝大多数在答案区**
        #   （答案逻辑思维导图 / 答案结构图）。旧实现只扫题干+选项，
        #   导致答案区的 [IMAGE:xxx] 占位符既不会被发现、也不会被替换，
        #   前端只能看到裸占位符 —— 用户实测截图里残留 [[IMAGE:f4419932_2_0]]。
        _img_scope = ' '.join([
            question_data.get('question_content') or '',
            str(question_data.get('options') or ''),
            question_data.get('answer') or '',
            question_data.get('answer_analysis') or question_data.get('analysis') or '',
        ])
        images = _extract_and_save_images(
            _img_scope,
            question.question_id,
            question_obj=question
        )
        for img_order, img_path in enumerate(images):
            db.add(QuestionImage(
                question_id=question.question_id,
                image_path=img_path,
                # 沿用既有'题干图'类型语义不变（公专/行测既有链路依赖它），
                # 答案/解析图片同样归入该类型，避免改枚举破坏既有数据
                image_type='题干图',
                image_order=img_order
            ))
    except Exception as img_err:
        logger.warning(f"图片提取失败 question_id={question.question_id}: {img_err}")

    # 详细分类
    #
    # question_id 上有 UNIQUE 约束(uk_question_category)，此处原本是**盲目 INSERT**。
    # 只要该 question_id 已存在明细行就会撞唯一约束，并因批量入库共用一个事务而
    # **整批回滚、接口 500**。
    # 真实故障：库中曾残留 231 条孤儿明细行（对应题目已被硬删除的脚本清理掉，
    #   详见 clean_questions.py 漏清 question_detail_category），
    #   SQLite 复用主键后新题分配到同 id → IntegrityError，整个导入失败。
    # 因此改为幂等 upsert：存在则更新，不存在才插入 —— 对任何残留行都免疫。
    _existing_detail = db.query(QuestionDetailCategory).filter(
        QuestionDetailCategory.question_id == question.question_id
    ).first()
    if _existing_detail is not None:
        _existing_detail.xingce_subcategory = _xingce_sc
        _existing_detail.shenlun_subcategory = _shenlun_sc
        _existing_detail.gongzhuan_subcategory = _gongzhuan_sc
        _existing_detail.question_type_detail = normalize_type_name(type_name)
        logger.debug(f"[import] 题{question.question_id} 复用已有明细分类行（残留/复用）")
    else:
        detail = QuestionDetailCategory(
            question_id=question.question_id,
            xingce_subcategory=_xingce_sc,
            shenlun_subcategory=_shenlun_sc,
            gongzhuan_subcategory=_gongzhuan_sc,
            question_type_detail=normalize_type_name(type_name),
        )
        db.add(detail)
    _link_knowledge_points(db, [question])

    return {
        'import_status': 'SUCCESS',
        'question_id': question.question_id,
        'message': '题目导入成功',
    }


def _upsert_xingce_question(db: Session, user, data: Dict[str, Any]):
    """行测题目落库（任务 16 方案 B）——**全程不 commit**，事务边界归调用方。

    为何不复用 `_upsert_question_core`：它内部调用 `_get_or_create_subject`
    （`:393` 有 `db.commit()`）与 `_get_or_create_type`（同样含 commit）。
    这两个 helper 是公专/申论链路的**隐式提交点**，动它们属红线；
    而复用它们会让驱动脚本的 `rollback()` 被中途提交抵消 ——
    实测导致「dry-run」真实写库（74 行残留），并使计划要求的
    「每 N 题 commit + 批次隔离」不可达。

    本函数因此**只组合纯函数 + 只读查询**：
      - 科目：行测 `subject_id` 固定为 1（`SUBJECT_NAME_MAP` 实测映射），直接取
      - 题型：只**查询**已有行测题型；缺失时 insert + flush（仍不 commit）
      - 去重：按 `(question_number, source)` 精确匹配
    与既有链路的清洗口径一致（`clean_question_text`），保证指纹可比。

    Returns: ``{'import_status': 'SUCCESS'|'DUPLICATE', 'question_id': int, ...}``
    """
    # ── 阻断闸门（与既有链路同口径，blocked 与 need_review 是两套语义）──
    if data.get('blocked'):
        reasons = data.get('block_reasons') or ['unknown']
        return {'import_status': 'BLOCKED', 'question_id': None,
                'message': '存在阻断问题：%s' % '、'.join(str(r) for r in reasons)}

    raw_content = (data.get('question_content') or '').strip()
    options = data.get('options') or []
    # 空题干不丢弃：数量关系/图形推理的公式与图形在原PDF 中以矢量或图片渲染，
    # 文本层只剩题号与选项骨架（实测 q31='31. \nA.13\nB.14…'、q33 题干选项皆空）。
    # 按既定口径「图片题切图入库、人工补文字」+「低质量题入库并标记待复核」，
    # 这类题须入库并强制待复核；只有连选项骨架都没有的空壳才真正拒收。
    # 绝不编造题干——占位文本明确标注来源缺失，交人工补录。
    force_review = False
    if not raw_content:
        if not options:
            return {'import_status': 'SKIPPED', 'question_id': None,
                    'message': '题干与选项均为空，无可识别内容'}
        raw_content = '【待补录：原PDF题干为图形/公式，文本层缺失】'
        force_review = True
    content = clean_question_text(raw_content) or raw_content
    need_review = 1 if (data.get('need_review') or force_review) else 0

    # ── 选项错位修复（行测专用）────────────────────────────────
    # `_extract_options` 的 L2 段落回退用 `\s*` 吞并换行；当选项字母各占一行
    # 且本无值时（图形/公式不在文本层），会把**下一个选项标记**当成当前值：
    #     A.\nB.\nC.\nD.  ->  [{'A':'B.'}, {'C':'D.'}]
    # 该形态已在库中实测 244 题，且这 244 题全部被误判为「简答题」。
    # 行测里选项值形如 'B.' 只可能是这一错位产物（真实选项值不会是裸字母+点），
    # 故按既定口径置「（见图）」占位并强制待复核，交人工补录——
    # 绝不把选项字母当作选项内容呈现给考生。
    # 只在行测落库路径生效；公专链路与 `_extract_options` 函数体一行未动。
    if options:
        _fixed_opts = []
        _degraded = False
        for _o in options:
            _v = (_o.get('value') or '').strip()
            # 分隔符**必需**：裸字母（如 'B'）是合法选项值，不能误判；
            # 只有「字母+分隔点」且无实际内容才是换行吞并错位的产物。
            if not _v:
                _degraded = True
                _fixed_opts.append({'key': _o.get('key'), 'value': '（见图）'})
            elif re.fullmatch(r'[A-H]\s*[.、．)）]', _v):
                _degraded = True
                _fixed_opts.append({'key': _o.get('key'), 'value': '（见图）'})
            else:
                _fixed_opts.append(_o)
        if _degraded:
            options = _fixed_opts
            need_review = 1

    answer = (data.get('answer') or '').strip() or '待补充'

    subject_id = SUBJECT_NAME_MAP.get('行测', 1)
    qno = str(data.get('question_number') or '').strip() or None
    source = (data.get('source') or '').strip()

    # ── 去重：行测主键是 (题号, 来源)，不是文本相似度 ──
    existing = None
    if qno and source:
        existing = db.query(QuestionBank).filter(
            QuestionBank.question_number == qno,
            QuestionBank.source == source,
            QuestionBank.status != 0
        ).first()
    if existing:
        # 回填式重导入：只补空，绝不覆盖既有非空值（沿用既有语义）
        backfilled = []
        new_an = (data.get('answer_analysis') or '').strip()
        if new_an and not (existing.answer_analysis or '').strip():
            existing.answer_analysis = new_an
            backfilled.append('answer_analysis')
        if answer and (existing.answer or '').strip() in ('', '待补充'):
            existing.answer = answer
            backfilled.append('answer')
        if backfilled:
            db.flush()
        return {'import_status': 'DUPLICATE', 'question_id': existing.question_id,
                'backfilled_fields': backfilled}

    # ── 题型：行测只有 单选 / 多选 / 判断 ──────────────────────
    # 行测不存在简答、论述、写作。若被判为简答题却带着 ≥2 个选项，
    # 说明题型判定因选项残缺而回退，按答案字母个数归位为单选/多选。
    type_name = (data.get('question_type_detail') or '').strip() or '单选题'
    if type_name in ('简答题', '简述题', '论述题', '写作题', '文章写作'):
        if len(options) >= 2:
            _ans = (data.get('answer') or '').strip().upper()
            type_name = ('多选题' if len(set(re.findall(r'[A-H]', _ans))) >= 2
                         else '单选题')
        else:
            # 行测不存在简答/论述/写作；选项不足 2 个时无法判别单/多选，
            # 归位为单选题并标记待复核，交人工确认。行测不得残留「简答题」。
            type_name = '单选题'
        need_review = 1
    qtype = db.query(QuestionType).filter(
        QuestionType.type_name == type_name,
        QuestionType.subject_id == subject_id).first()
    if qtype is None:
        qtype = QuestionType(type_name=type_name, subject_id=subject_id)
        db.add(qtype)
        db.flush()

    gid = int(data.get('group_id') or 0)
    q = QuestionBank(
        group_id=gid,
        parent_id=int(data.get('parent_id') or 0),
        question_level=int(data.get('question_level') or 0) or (2 if gid else 1),
        sort_order=int(data.get('sort_order') or 0),
        question_number=qno,
        subject_id=subject_id,
        type_id=qtype.type_id,
        question_content=content,
        options=options,
        answer=answer,
        answer_analysis=data.get('answer_analysis') or '',
        difficulty=coerce_difficulty(data.get('difficulty')),
        score=1.0,
        year=data.get('exam_year') or None,
        source=source,
        creator_id=user.user_id,
        audit_status=1,
        need_review=need_review,
        xingce_subcategory=data.get('subcategory') or '无',
    )
    db.add(q)
    db.flush()
    return {'import_status': 'SUCCESS', 'question_id': q.question_id}
