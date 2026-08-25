import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query,UploadFile,File
from sqlalchemy.orm import Session
from sqlalchemy import and_,or_,func

from ...core.database import get_db
from ...models.models import (QuestionBank as QuestionModel, QuestionSubject as SubjectModel,
                      QuestionType, KnowledgePoint, QuestionEditLog,
                      SysUser, QuestionSubject, QuestionBank, QuestionDetailCategory,
                      QuestionGroup)
from ...schemas.schemas import (QuestionCreate, QuestionUpdate, QuestionResponse,
                       QuestionListResponse,
                       BatchImportQuestionsRequest, BatchImportResponse,
                       RandomQuestionRequest, RandomQuestionResponse,
                       ErrorResponse, SuccessResponse, BatchImportQuestionItem)
from ...services.image_service import sanitize_content_images, sanitize_options_images
from ...services.option_utils import render_image_placeholder
from ...services.text_parser import canonical_answer


from ...core.security import get_current_user,require_teacher_or_admin

router = APIRouter(prefix="/api/questions",tags=["题库管理"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=QuestionResponse, summary="创建题目")
async def create_question(
        question_data: QuestionCreate,
        current_user: SysUser = Depends(require_teacher_or_admin),
        db: Session = Depends(get_db)
):
    """
    创建新题目

    - **subject_id**: 科目ID
    - **type_id**: 题型ID
    - **question_content**: 题目内容
    - **options**: 选项列表（选择题需要）
    - **answer**: 正确答案
    - **difficulty**: 难度等级(1-5)
    """
    # 验证科目是否存在
    subject = db.query(QuestionSubject).filter(
        QuestionSubject.subject_id == question_data.subject_id
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在")

    # 验证题型是否存在
    qtype = db.query(QuestionType).filter(
        QuestionType.type_id == question_data.type_id
    ).first()
    if not qtype:
        raise HTTPException(status_code=404, detail="题型不存在")

    # 验证知识点（如果提供）
    if question_data.point_id:
        point = db.query(KnowledgePoint).filter(
            KnowledgePoint.point_id == question_data.point_id
        ).first()
        if not point:
            raise HTTPException(status_code=404, detail="知识点不存在")

    # 转换选项为JSON
    options_json = None
    if question_data.options:
        options_json = [opt.dict() for opt in question_data.options]

    # 创建题目
    new_question = QuestionBank(
        subject_id=question_data.subject_id,
        type_id=question_data.type_id,
        question_content=question_data.question_content,
        options=options_json,
        answer=question_data.answer,
        answer_analysis=question_data.answer_analysis,
        point_id=question_data.point_id,
        difficulty=question_data.difficulty.value if isinstance(question_data.difficulty,
                                                                int) else question_data.difficulty,
        score=question_data.score,
        year=question_data.year,
        source=question_data.source,
        tags=question_data.tags,
        video_url=question_data.video_url,
        creator_id=current_user.user_id,
        audit_status=1,  # 教师/管理员创建的题目自动审核通过
        status=1
    )

    db.add(new_question)
    db.flush()

    # 创建详细分类记录（题型分类入库）
    detail = QuestionDetailCategory(
        question_id=new_question.question_id,
        question_type_detail=qtype.type_name or '选择题',
    )
    db.add(detail)

    db.commit()
    db.refresh(new_question)

    # 记录编辑日志
    edit_log = QuestionEditLog(
        question_id=new_question.question_id,
        editor_id=current_user.user_id,
        action_type="CREATE",
        new_data={
            "subject_id": new_question.subject_id,
            "type_id": new_question.type_id,
            "content": new_question.question_content[:100]
        },
        remark="创建题目"
    )
    db.add(edit_log)
    db.commit()

    logger.info(f"用户 {current_user.username} 创建题目 ID: {new_question.question_id}")

    return new_question


@router.get("/", response_model=QuestionListResponse,summary="查询题目列表")
async def get_questions(
        subject_id: Optional[int] = Query(None, description="科目ID"),
        type_id: Optional[int] = Query(None, description="题型ID"),
        point_id: Optional[int] = Query(None, description="知识点ID"),
        difficulty: Optional[int] = Query(None, ge=1, le=5, description="难度等级"),
        audit_status: Optional[int] = Query(None, description="审核状态"),
        year: Optional[int] = Query(None, description="考试年份"),
        keyword: Optional[str] = Query(None, max_length=100, description="搜索关键词"),
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=100, description="每页数量"),
        db: Session = Depends(get_db)
):
    """
       分页查询题目列表，支持多条件筛选
       """
    base_query = db.query(QuestionBank).filter(QuestionBank.status == 1)

    # 应用筛选条件
    if subject_id:
        base_query = base_query.filter(QuestionBank.subject_id == subject_id)
    if type_id:
        base_query = base_query.filter(QuestionBank.type_id == type_id)
    if point_id:
        base_query = base_query.filter(QuestionBank.point_id == point_id)
    if difficulty:
        base_query = base_query.filter(QuestionBank.difficulty == difficulty)
    if audit_status is not None:
        base_query = base_query.filter(QuestionBank.audit_status == audit_status)
    if year:
        base_query = base_query.filter(QuestionBank.year == year)
    if keyword:
        base_query = base_query.filter(
            or_(
                QuestionBank.question_content.like(f"%{keyword}%"),
                QuestionBank.tags.like(f"%{keyword}%"),
                QuestionBank.source.like(f"%{keyword}%")
            )
        )

    # 获取总数（无ORDER BY）
    total = base_query.count()

    # 分页查询（独立排序 + tiebreaker）
    questions = base_query.order_by(
        QuestionBank.create_time.desc(),
        QuestionBank.question_id.desc()
    ).offset((page - 1) * page_size).limit(page_size).all()

    return QuestionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=questions
    )

def _normalize_options(raw_opts, content=''):
    """归一化选项为 ['A. xxx', 'B. xxx', ...]，递归解析嵌套dict字符串"""
    import json as _json

    # 第1层：解析外层JSON字符串/双重编码
    opts = raw_opts
    if isinstance(opts, str):
        for _ in range(3):
            try:
                parsed = _json.loads(opts)
                if not isinstance(parsed, str):
                    opts = parsed
                    break
                opts = parsed
            except Exception:
                break
    if not isinstance(opts, list):
        opts = []

    # 第2层：递归提取真实值
    def _extract(o, depth=0):
        if depth > 3:
            return ('', str(o)[:200])
        if isinstance(o, dict):
            key = str(o.get('key', '')).strip()
            val = o.get('value', '') or o.get('text', '') or ''
            # 如果value本身是dict（嵌套对象），递归提取
            if isinstance(val, dict):
                return _extract(val, depth + 1)
            # 如果value是字符串化的dict，解析后递归
            if isinstance(val, str) and val.strip()[:1] == '{':
                try:
                    inner = _json.loads(val.strip().replace("'", '"'))
                    if isinstance(inner, dict):
                        return _extract(inner, depth + 1)
                except Exception:
                    pass
            return (key, str(val) if val else '(空)')
        if isinstance(o, str):
            s = o.strip()
            if s[:1] == '{':
                try:
                    inner = _json.loads(s.replace("'", '"'))
                    if isinstance(inner, dict):
                        return _extract(inner, depth + 1)
                except Exception:
                    pass
            return ('', o)
        return ('', str(o))

    result = []
    seen = set()
    VALID_KEYS = {'A', 'B', 'C', 'D'}
    for o in opts[:6]:
        key, val = _extract(o)
        if key and key in VALID_KEYS and key not in seen:
            seen.add(key)
            result.append(f"{key}. {val}")
            if len(result) == 4:
                break

    # 补全：不足4个时先从content提取，最后才用占位符
    if len(result) < 4 and content:
        import re as _re2
        existing_keys = {r[0] for r in result if r and r[0] in VALID_KEYS}
        for m in _re2.finditer(
            r'(?:^|\n)\s*([A-D])\s*[.、．)）]\s*(.+?)(?=\n\s*[A-D]\s*[.、．)）]|\n\n|$)',
            content, _re2.DOTALL
        ):
            k, v = m.group(1), m.group(2).strip()
            if k in VALID_KEYS and k not in existing_keys and len(v) > 1:
                v = _re2.sub(r'\s*[A-D]\s*[.、．)）]\s*.+$', '', v, flags=_re2.DOTALL).strip()
                if v:
                    result.append(f"{k}. {v}")
                    existing_keys.add(k)
                    if len(result) == 4:
                        break

    while len(result) < 4:
        result.append(f"{chr(65 + len(result))}. (待补充)")

    return result[:4]

def _detect_multi_from_content(content, answer):
    """从题干/答案检测是否多选"""
    if not content:
        return False
    import re
    # 归一化答案（A、B → AB；对/错 → A/B），修复 isalpha() 对分隔符答案失效的问题
    norm = canonical_answer(answer)
    if norm and len(norm) >= 2:
        return True
    kw = ['多选', '不定项', '至少.*个', '两项', '2个以上', '多选题',
          '哪些', '几种', '属于.*的有', '正确的有', '错误的有']
    return any(re.search(k, content) for k in kw)


VALID_QUESTION_TYPES = (
    '单选题', '多选题', '不定项', '选择题',
    '写作题', '简答题', '案例分析题', '论述题', '无'
)


@router.get("/random", response_model=Dict[str, Any], summary="随机获取题目")
async def get_random_questions(
    subject_id: Optional[int] = Query(None, description="科目ID"),
    type_id: Optional[int] = Query(None, description="题型ID"),
    count: int = Query(10, ge=1, le=50, description="获取数量"),
    difficulty: Optional[int] = Query(None, ge=1, le=5, description="难度等级"),
    db: Session = Depends(get_db),
):
    """随机获取指定条件的题目"""
    query = db.query(QuestionBank, QuestionDetailCategory).outerjoin(
        QuestionDetailCategory,
        QuestionBank.question_id == QuestionDetailCategory.question_id
    ).filter(QuestionBank.status == 1, QuestionBank.audit_status == 1)
    if subject_id: query = query.filter(QuestionBank.subject_id == subject_id)
    if type_id: query = query.filter(QuestionBank.type_id == type_id)
    if difficulty is not None: query = query.filter(QuestionBank.difficulty == difficulty)
    total_available = query.count()
    if total_available == 0: return {"total": 0, "questions": []}
    results = query.order_by(func.random()).limit(min(count, total_available)).all()

    items = []
    for q, q_detail_cat in results:
        detail = q_detail_cat.question_type_detail if q_detail_cat else ''
        # 乱码检测 — 如果值不合法，通过题干答案二次检测
        if not detail or detail not in VALID_QUESTION_TYPES:
            detail = '多选题' if _detect_multi_from_content(q.question_content, q.answer) else '单选题'
        # 图片预检+恢复（先用 render_image_placeholder 转换 IMAGE 占位符，再用 sanitize_content_images 预检）
        _q_content = render_image_placeholder(q.question_content or '')
        _q_content = sanitize_content_images(_q_content, q.question_id, db)
        _opts = _normalize_options(q.options, q.question_content)
        _opts = [sanitize_content_images(render_image_placeholder(o), q.question_id, db) for o in _opts]
        _analysis = sanitize_content_images(
            render_image_placeholder(q.answer_analysis or ''), q.question_id, db
        ) or '暂未提供解析，请参考题目来源'
        items.append({
            "question_id": q.question_id,
            "subject_id": q.subject_id,
            "type_id": q.type_id,
            "group_id": q.group_id or 0,
            "question_content": _q_content,
            "options": _opts,
            "answer": q.answer,
            "answer_analysis": _analysis,
            "question_type_detail": detail,
            "difficulty": q.difficulty,
            "score": float(q.score) if q.score else 0,
            "year": q.year,
            "source": q.source,
            "tags": q.tags,
        })

    # 去重：移除内容高度相似的题目（>85%相似度）
    import re as _dedup_re
    from difflib import SequenceMatcher
    filtered = []
    for item in items:
        is_dup = False
        item_text = item['question_content'] or ''
        if not item_text.strip():
            filtered.append(item)
            continue
        item_norm = _dedup_re.sub(r'\s+', '', item_text)[:200]
        if len(item_norm) < 5:
            filtered.append(item)
            continue
        for existing in filtered:
            exist_text = existing['question_content'] or ''
            if not exist_text.strip():
                continue
            exist_norm = _dedup_re.sub(r'\s+', '', exist_text)[:200]
            if len(exist_norm) < 5:
                continue
            # 长度差距太大直接跳过
            len_ratio = min(len(item_norm), len(exist_norm)) / max(len(item_norm), len(exist_norm))
            if len_ratio < 0.5:
                continue
            if SequenceMatcher(None, item_norm, exist_norm).ratio() > 0.75:
                is_dup = True
                break
        if not is_dup:
            filtered.append(item)

    return {"total": len(filtered), "questions": filtered}

@router.get("/count-by-category", response_model=Dict[str, Any], summary="按分类统计题目数量")
async def count_questions_by_category(db: Session = Depends(get_db)):
    """获取题目按科目和题型分类的数量统计"""
    subject_counts = db.query(QuestionBank.subject_id, QuestionSubject.subject_name, func.count(QuestionBank.question_id).label("count")).join(QuestionSubject, QuestionBank.subject_id == QuestionSubject.subject_id).filter(QuestionBank.status == 1).group_by(QuestionBank.subject_id, QuestionSubject.subject_name).all()
    type_counts = db.query(QuestionBank.type_id, QuestionType.type_name, func.count(QuestionBank.question_id).label("count")).join(QuestionType, QuestionBank.type_id == QuestionType.type_id).filter(QuestionBank.status == 1).group_by(QuestionBank.type_id, QuestionType.type_name).all()
    return {"total": sum(s.count for s in subject_counts), "by_subject": [{"subject_id": s.subject_id, "subject_name": s.subject_name, "count": s.count} for s in subject_counts], "by_type": [{"type_id": t.type_id, "type_name": t.type_name, "count": t.count} for t in type_counts]}

@router.get("/subcategory-stats", response_model=Dict[str, Any], summary="按子科目统计题目数量")
async def subcategory_stats(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取三大科目（行测/申论/公专）下各子科目的题目数量统计。
    用于前端题库页面的子科目卡片展示。
    """
    # 行测子科目统计
    xc_subs = db.query(
        QuestionBank.xingce_subcategory,
        func.count(QuestionBank.question_id).label('count')
    ).filter(
        QuestionBank.subject_id == 1,
        QuestionBank.status == 1,
        QuestionBank.xingce_subcategory != '无'
    ).group_by(QuestionBank.xingce_subcategory).all()

    # 申论子科目统计
    sl_subs = db.query(
        QuestionBank.shenlun_subcategory,
        func.count(QuestionBank.question_id).label('count')
    ).filter(
        QuestionBank.subject_id == 2,
        QuestionBank.status == 1,
        QuestionBank.shenlun_subcategory != '无'
    ).group_by(QuestionBank.shenlun_subcategory).all()

    # 公专子科目统计
    ga_subs = db.query(
        QuestionBank.gongzhuan_subcategory,
        func.count(QuestionBank.question_id).label('count')
    ).filter(
        QuestionBank.subject_id == 3,
        QuestionBank.status == 1,
        QuestionBank.gongzhuan_subcategory != '无'
    ).group_by(QuestionBank.gongzhuan_subcategory).all()

    # 题型分布
    type_counts = db.query(
        QuestionType.type_name,
        func.count(QuestionBank.question_id).label('count')
    ).join(QuestionBank, QuestionBank.type_id == QuestionType.type_id)\
        .filter(QuestionBank.status == 1)\
        .group_by(QuestionType.type_name).all()

    # 总数
    total = db.query(func.count(QuestionBank.question_id)).filter(
        QuestionBank.status == 1
    ).scalar() or 0

    def _fmt(rows):
        return [{'name': r[0], 'count': r[1] or 0} for r in rows]

    return {
        'total': total,
        'xingce': _fmt(xc_subs),
        'shenlun': _fmt(sl_subs),
        'gongzhuan': _fmt(ga_subs),
        'by_type': _fmt(type_counts),
    }


@router.get("/exercise/questions", summary="获取练习题目列表")
async def get_exercise_questions(
    subject: str = Query(..., description="科目: xc/sl/ga"),
    subcategory: str = Query('', description="子科目名称"),
    count: int = Query(10, ge=1, le=50, description="题目数量"),
    db: Session = Depends(get_db)
):
    """
    按科目和子科目获取练习题目。

    - subject: xc(行测)、sl(申论)、ga(公专)
    - subcategory: 可选子科目过滤
    - count: 返回题目数量(1-50)
    """
    subject_map = {'xc': 1, 'sl': 2, 'ga': 3}
    subject_id = subject_map.get(subject)
    if not subject_id:
        raise HTTPException(status_code=400, detail=f"无效的科目: {subject}，可选: xc/sl/ga")

    subcat_col = {
        1: QuestionBank.xingce_subcategory,
        2: QuestionBank.shenlun_subcategory,
        3: QuestionBank.gongzhuan_subcategory,
    }

    # 构建基础过滤条件
    base_filter = [
        QuestionBank.status == 1,
        QuestionBank.subject_id == subject_id
    ]
    if subcategory and subcategory.strip():
        col = subcat_col.get(subject_id)
        if col is not None:
            base_filter.append(col == subcategory.strip())

    # 按题干内容去重（保留 question_id 最小的，避免同一题目在综合练习中重复出现）
    dedup_sub = db.query(
        func.min(QuestionBank.question_id).label('min_id')
    ).filter(*base_filter).group_by(QuestionBank.question_content).subquery()

    dedup_ids = [r[0] for r in db.query(dedup_sub.c.min_id).all()]
    total = len(dedup_ids)
    if total == 0:
        return {
            'questions': [],
            'total': 0,
            'subject': subject,
            'subcategory': subcategory,
            'message': '该分类暂无题目，请先导入题目'
        }

    # 查询去重后的题目（带detail），按创建顺序排列
    questions_with_detail = db.query(QuestionBank).outerjoin(
        QuestionDetailCategory,
        QuestionBank.question_id == QuestionDetailCategory.question_id
    ).filter(
        QuestionBank.question_id.in_(dedup_ids)
    ).distinct().order_by(QuestionBank.question_id.asc()).limit(min(count, total)).all()

    result = []
    import re as _img_re
    for item in questions_with_detail:
        # SQLAlchemy outerjoin returns Row objects; access by attribute
        q = item.QuestionBank if hasattr(item, 'QuestionBank') else (item[0] if isinstance(item, (tuple, list)) else item)
        detail_row = getattr(item, 'QuestionDetailCategory', None) if hasattr(item, 'QuestionDetailCategory') else (item[1] if isinstance(item, (tuple, list)) and len(item) > 1 else None)

        # Fallback: get detail from DB directly if join didn't work
        qtype = ''
        if detail_row and detail_row.question_type_detail:
            qtype = str(detail_row.question_type_detail)
        if not qtype:
            detail_fallback = db.query(QuestionDetailCategory).filter(QuestionDetailCategory.question_id == q.question_id).first()
            if detail_fallback and detail_fallback.question_type_detail:
                qtype = str(detail_fallback.question_type_detail)

        # IMAGE标记转img标签 + 图片预检+恢复
        stem = render_image_placeholder(q.question_content or '')
        stem = sanitize_content_images(stem, q.question_id, db)

        opts = q.options
        if isinstance(opts, str):
            try:
                opts = json.loads(opts)
            except:
                opts = []
        # 选项补全到4个
        if isinstance(opts, list):
            existing_keys = {o.get('key','') for o in opts if isinstance(o, dict)}
            for label in ['A','B','C','D']:
                if label not in existing_keys:
                    opts.append({'key': label, 'value': '(待补充)'})
            # 选项IMAGE替换 + 预检
            _opts = []
            for o in opts:
                if isinstance(o, dict):
                    val = render_image_placeholder(str(o.get('value', '')))
                    val = sanitize_content_images(val, q.question_id, db)
                    _opts.append({'key': o.get('key',''), 'value': val})
                else:
                    _opts.append(str(o))
            opts = sorted(_opts, key=lambda x: x.get('key','') if isinstance(x, dict) else '')
        result.append({
            'question_id': q.question_id,
            'question_content': stem,
            'question_type_detail': qtype,
            'options': opts,
            'answer': q.answer,
            'answer_analysis': sanitize_content_images(
                render_image_placeholder(q.answer_analysis or ''), q.question_id, db
            ),
            'difficulty': q.difficulty,
            'score': q.score,
            'year': q.year,
            'source': q.source,
        })

    return {
        'questions': result,
        'total': total,
        'subject': subject,
        'subcategory': subcategory,
    }


@router.get("/group/{group_id}", summary="获取题组聚合详情（共享材料+小题）")
async def get_question_group(
        group_id: int,
        db: Session = Depends(get_db)
):
    """复合题组聚合视图（方案 v1.1 §7 API）。

    返回共享材料 + 全部小题（按 sort_order/题号排序），小题字段与 /random
    同一净化链路（IMAGE占位符→<img> + 图片预检），前端可直接渲染。
    题组仅为展示聚合——组卷/答题/计分仍按扁平小题进行。
    """
    group = db.query(QuestionGroup).filter(QuestionGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="题组不存在")

    members = db.query(QuestionBank).filter(
        QuestionBank.group_id == group_id,
        QuestionBank.status == 1,
    ).order_by(
        QuestionBank.sort_order.asc(), QuestionBank.question_id.asc()
    ).all()

    items = []
    for q in members:
        _content = render_image_placeholder(q.question_content or '')
        _content = sanitize_content_images(_content, q.question_id, db)
        _opts = q.options
        if isinstance(_opts, str):
            try:
                _opts = json.loads(_opts)
            except Exception:
                _opts = []
        if isinstance(_opts, list):
            _opts = [sanitize_content_images(
                render_image_placeholder(str(o.get('value', '')) if isinstance(o, dict) else str(o)),
                q.question_id, db) if isinstance(o, dict) else o for o in _opts]
        detail_row = db.query(QuestionDetailCategory).filter(
            QuestionDetailCategory.question_id == q.question_id).first()
        items.append({
            'question_id': q.question_id,
            'question_number': q.question_number or '',
            'sort_order': q.sort_order or 0,
            'question_content': _content,
            'options': _opts,
            'answer': q.answer,
            'answer_analysis': sanitize_content_images(
                render_image_placeholder(q.answer_analysis or ''), q.question_id, db),
            'question_type_detail': (detail_row.question_type_detail if detail_row else '选择题'),
            'difficulty': q.difficulty,
            'score': float(q.score) if q.score else 0,
        })

    shared = sanitize_content_images(
        render_image_placeholder(group.shared_content or ''), 0, db)
    return {
        'group': {
            'id': group.id,
            'group_type': group.group_type,
            'title': group.title,
            'shared_content': shared,
            'subject': group.subject,
            'source': group.source,
        },
        'members': items,
        'total': len(items),
    }


@router.get("/{question_id}", response_model=QuestionResponse,summary="获取单个题目详情")
async def get_question_detail(
        question_id: int,
        db: Session = Depends(get_db)
):
    """
    获取单个题目的详细信息
    """
    question = db.query(QuestionBank).filter(
        QuestionBank.question_id == question_id,
        QuestionBank.status == 1
    ).first()

    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    # 增加访问频率统计
    question.exam_frequency += 1
    db.commit()

    return question


@router.put("/{question_id}", response_model=QuestionResponse,summary="更新题目")
async def update_question(
    question_id: int,
    question: QuestionUpdate,
    current_user: SysUser = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db)
, question_data=None):
    """更新题目信息"""
    question = db.query(QuestionBank).filter(
        QuestionBank.question_id == question_id
    ).first()

    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    # 权限检查：只有创建者或管理员可以修改
    if question.creator_id != current_user.user_id and current_user.role_level < 3:
        raise HTTPException(status_code=403, detail="无权修改此题目")

    # 保存旧数据用于日志
    old_data = {
        "subject_id": question.subject_id,
        "type_id": question.type_id,
        "content": question.question_content[:100],
        "answer": question.answer
    }

    # 更新字段
    update_data = question_data.dict(exclude_unset=True)

    if "options" in update_data and update_data["options"]:
        update_data["options"] = [opt.dict() for opt in update_data["options"]]

    if "difficulty" in update_data:
        update_data["difficulty"] = (
            update_data["difficulty"].value
            if hasattr(update_data["difficulty"], 'value')
            else update_data["difficulty"]
        )

    for key, value in update_data.items():
        setattr(question, key, value)

    question.update_time = datetime.now()
    question.version += 1

    # 如果修改了关键内容，重置审核状态
    if any(k in update_data for k in ["question_content", "answer", "options"]):
        if current_user.role_level < 3:
            question.audit_status = 0

    db.commit()
    db.refresh(question)

    # 记录编辑日志
    edit_log = QuestionEditLog(
        question_id=question_id,
        editor_id=current_user.user_id,
        action_type="UPDATE",
        old_data=old_data,
        new_data={k: str(v)[:100] for k, v in update_data.items()},
        remark="更新题目"
    )
    db.add(edit_log)
    db.commit()

    logger.info(f"用户 {current_user.username} 更新题目 ID: {question_id}")

    return question


@router.delete("/{question_id}")
async def delete_question(
    question_id: int,
    current_user: SysUser = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db)
):
    """删除题目（软删除）"""
    question = db.query(QuestionBank).filter(
        QuestionBank.question_id == question_id
    ).first()

    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    # 权限检查
    if question.creator_id != current_user.user_id and current_user.role_level < 3:
        raise HTTPException(status_code=403, detail="无权删除此题目")

    # 软删除
    question.status = 0
    question.update_time = datetime.now()
    db.commit()

    # 记录编辑日志
    edit_log = QuestionEditLog(
        question_id=question_id,
        editor_id=current_user.user_id,
        action_type="DELETE",
        remark="删除题目"
    )
    db.add(edit_log)
    db.commit()

    logger.info(f"用户 {current_user.username} 删除题目 ID: {question_id}")

    return SuccessResponse(message="题目删除成功")


@router.post("/batch-import", response_model=BatchImportResponse, summary="批量导入题目")
async def batch_import_questions(
        import_data: BatchImportQuestionsRequest,
        current_user: SysUser = Depends(require_teacher_or_admin),
        db: Session = Depends(get_db)
):
    """
    批量导入题目及内容

    - 支持一次导入最多100道题目
    - 可选择是否覆盖已存在的题目
    - 返回导入结果统计
    """
    success_count = 0
    failed_count = 0
    errors = []

    # 批量查询题型名称（用于创建详细分类记录）
    type_ids = {q.type_id for q in import_data.questions}
    type_name_map = {}
    if type_ids:
        types = db.query(QuestionType).filter(QuestionType.type_id.in_(type_ids)).all()
        type_name_map = {t.type_id: t.type_name for t in types}

    from ...services.question_classifier import detect_subcategory_enhanced

    for idx, q_data in enumerate(import_data.questions):
        try:
            # 验证必填字段
            if not q_data.question_content or not q_data.answer:
                errors.append({
                    "index": idx,
                    "error": "题目内容和答案不能为空"
                })
                failed_count += 1
                continue

            # 转换选项
            options_json = None
            if q_data.options:
                options_json = [opt.dict() for opt in q_data.options]

            # 子科目归类（按 subject_id 写对应字段，其余保持「无」）
            _sc = detect_subcategory_enhanced(q_data.subject_id, q_data.question_content, '')
            _xingce_sc = _sc if q_data.subject_id == 1 else '无'
            _shenlun_sc = _sc if q_data.subject_id == 2 else '无'
            _gongzhuan_sc = _sc if q_data.subject_id == 3 else '无'

            # 创建题目
            new_question = QuestionBank(
                subject_id=q_data.subject_id,
                type_id=q_data.type_id,
                question_content=q_data.question_content,
                options=options_json,
                answer=q_data.answer,
                answer_analysis=q_data.answer_analysis,
                point_id=q_data.point_id,
                difficulty=q_data.difficulty.value if hasattr(q_data.difficulty, 'value') else q_data.difficulty,
                score=q_data.score,
                year=q_data.year,
                source=q_data.source,
                tags=q_data.tags,
                video_url=q_data.video_url,
                creator_id=current_user.user_id,
                audit_status=1,  # 教师/管理员创建的题目自动审核通过
                xingce_subcategory=_xingce_sc,
                shenlun_subcategory=_shenlun_sc,
                gongzhuan_subcategory=_gongzhuan_sc,
                status=1
            )

            db.add(new_question)
            db.flush()  # 获取ID但不提交

            # 创建详细分类记录
            detail = QuestionDetailCategory(
                question_id=new_question.question_id,
                xingce_subcategory=_xingce_sc,
                shenlun_subcategory=_shenlun_sc,
                gongzhuan_subcategory=_gongzhuan_sc,
                question_type_detail=type_name_map.get(q_data.type_id, '选择题'),
            )
            db.add(detail)

            success_count += 1

        except Exception as e:
            db.rollback()
            failed_count += 1
            errors.append({
                "index": idx,
                "error": str(e)
            })
            logger.error(f"导入第{idx + 1}道题目失败: {str(e)}")

    # 全部成功才提交
    if failed_count == 0:
        db.commit()

        # 记录批量导入日志
        edit_log = QuestionEditLog(
            question_id=0,
            editor_id=current_user.user_id,
            action_type="CREATE",
            new_data={"batch_import_count": success_count},
            remark=f"批量导入{success_count}道题目"
        )
        db.add(edit_log)
        db.commit()
    else:
        db.rollback()

    logger.info(f"用户 {current_user.username} 批量导入: 成功{success_count}, 失败{failed_count}")

    return BatchImportResponse(
        success_count=success_count,
        failed_count=failed_count,
        errors=errors
    )


@router.post("/random-draw", response_model=RandomQuestionResponse, summary="随机抽题")
async def random_draw_questions(
        draw_request: RandomQuestionRequest,
        db: Session = Depends(get_db)
):
    """
    随机抽取题目

    支持按科目、题型、知识点、难度等条件随机抽题
    """
    query = db.query(QuestionBank).filter(
        QuestionBank.status == 1,
        QuestionBank.audit_status == 1  # 只抽取已审核通过的题目
    )

    # 应用筛选条件
    if draw_request.subject_id:
        query = query.filter(QuestionBank.subject_id == draw_request.subject_id)
    if draw_request.type_id:
        query = query.filter(QuestionBank.type_id == draw_request.type_id)
    if draw_request.point_id:
        query = query.filter(QuestionBank.point_id == draw_request.point_id)
    if draw_request.difficulty:
        diff_value = (
            draw_request.difficulty.value
            if hasattr(draw_request.difficulty, 'value')
            else draw_request.difficulty
        )
        query = query.filter(QuestionBank.difficulty == diff_value)

    # 排除指定题目
    if draw_request.exclude_question_ids:
        query = query.filter(
            ~QuestionBank.question_id.in_(draw_request.exclude_question_ids)
        )

    # 获取符合条件的总数
    total_available = query.count()

    if total_available == 0:
        raise HTTPException(status_code=404, detail="没有符合条件的题目")

    if total_available < draw_request.count:
        raise HTTPException(
            status_code=400,
            detail=f"符合条件的题目仅有{total_available}道，不足{draw_request.count}道"
        )

    # 随机抽取（使用order by random()）
    questions = query.order_by(func.random()).limit(draw_request.count).all()

    return RandomQuestionResponse(
        questions=questions,
        total_available=total_available
    )


@router.post("/file-import", response_model=BatchImportResponse, summary="从文件导入题目")
async def import_questions_from_file(
        file: UploadFile = File(..., description="Excel/CSV/JSON文件"),
        overwrite: bool = Query(False, description="是否覆盖已存在的题目"),
        current_user: SysUser = Depends(require_teacher_or_admin),
        db: Session = Depends(get_db)
):
    """
    从文件批量导入题目

    支持格式：
    - Excel (.xlsx, .xls)
    - CSV (.csv)
    - JSON (.json)
    """
    import pandas as pd
    import json

    try:
        # 读取文件
        content = await file.read()
        filename = file.filename.lower()

        if filename.endswith('.json'):
            data = json.loads(content)
            if isinstance(data, dict) and 'questions' in data:
                questions_data = data['questions']
            else:
                questions_data = data
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(content)
            questions_data = df.to_dict('records')
        elif filename.endswith('.csv'):
            df = pd.read_csv(content)
            questions_data = df.to_dict('records')
        else:
            raise HTTPException(status_code=400, detail="不支持的文件格式")

        # 限制导入数量
        if len(questions_data) > 100:
            raise HTTPException(status_code=400, detail="单次导入不能超过100道题目")

        # 转换为Pydantic模型
        questions_list = []
        for q_data in questions_data:
            try:
                q_item = BatchImportQuestionItem(**q_data)
                questions_list.append(q_item)
            except Exception as e:
                logger.warning(f"跳过无效题目数据: {str(e)}")

        if not questions_list:
            raise HTTPException(status_code=400, detail="没有有效的题目数据")

        # 调用批量导入逻辑
        import_request = BatchImportQuestionsRequest(
            questions=questions_list,
            overwrite=overwrite
        )

        # 复用批量导入逻辑
        return await batch_import_questions(import_request, current_user, db)

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON格式错误")
    except Exception as e:
        logger.error(f"文件导入失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


# ============================================================
# 题目重分类 API
# ============================================================

@router.post("/{question_id}/reclassify", summary="单题重新分类")
async def reclassify_question(
    question_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """对单道题目运行分类引擎，更新子科目和考点关联"""
    from ...services.question_classifier import QuestionClassifier

    question = db.query(QuestionBank).filter(
        QuestionBank.question_id == question_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    classifier = QuestionClassifier()
    result = classifier.classify_with_db(
        question.question_content or "",
        question.subject_id,
        db
    )

    # 更新子科目
    if result.sub_category_name and result.sub_category_name != "无法分类":
        if question.subject_id == 1:
            question.xingce_subcategory = result.sub_category_name
        elif question.subject_id == 2:
            question.shenlun_subcategory = result.sub_category_name
        elif question.subject_id == 3:
            question.gongzhuan_subcategory = result.sub_category_name

        # 更新 question_detail_category
        detail = db.query(QuestionDetailCategory).filter(
            QuestionDetailCategory.question_id == question_id
        ).first()
        if detail:
            if question.subject_id == 1:
                detail.xingce_subcategory = result.sub_category_name
            elif question.subject_id == 2:
                detail.shenlun_subcategory = result.sub_category_name
            elif question.subject_id == 3:
                detail.gongzhuan_subcategory = result.sub_category_name

    # 创建考点关联
    if result.knowledge_point_id:
        existing = db.query(QuestionKnowledge).filter(
            QuestionKnowledge.question_id == question_id,
            QuestionKnowledge.knowledge_point_id == result.knowledge_point_id
        ).first()
        if not existing:
            from ...models.models import QuestionKnowledge
            db.add(QuestionKnowledge(
                question_id=question_id,
                knowledge_point_id=result.knowledge_point_id
            ))

    db.commit()

    return {
        "question_id": question_id,
        "subject_id": result.subject_id,
        "sub_category_name": result.sub_category_name,
        "knowledge_point_name": result.knowledge_point_name,
        "confidence": result.confidence,
    }


@router.post("/batch-reclassify", summary="批量重分类")
async def batch_reclassify(
    subject_id: Optional[int] = Query(None, description="限定科目ID"),
    limit: int = Query(100, ge=1, le=500, description="单次最大处理数"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """批量对题目运行分类引擎"""
    from ...services.question_classifier import QuestionClassifier

    query = db.query(QuestionBank).filter(QuestionBank.status == 1)
    if subject_id:
        query = query.filter(QuestionBank.subject_id == subject_id)
    questions = query.limit(limit).all()

    classifier = QuestionClassifier()
    results = []
    kp_linked = 0

    for q in questions:
        result = classifier.classify_with_db(
            q.question_content or "", q.subject_id, db
        )

        if result.sub_category_name and result.sub_category_name != "无法分类":
            if q.subject_id == 1:
                q.xingce_subcategory = result.sub_category_name
            elif q.subject_id == 2:
                q.shenlun_subcategory = result.sub_category_name
            elif q.subject_id == 3:
                q.gongzhuan_subcategory = result.sub_category_name

        if result.knowledge_point_id:
            from ...models.models import QuestionKnowledge
            existing = db.query(QuestionKnowledge).filter(
                QuestionKnowledge.question_id == q.question_id,
                QuestionKnowledge.knowledge_point_id == result.knowledge_point_id
            ).first()
            if not existing:
                db.add(QuestionKnowledge(
                    question_id=q.question_id,
                    knowledge_point_id=result.knowledge_point_id
                ))
                kp_linked += 1

        results.append({
            "question_id": q.question_id,
            "sub_category": result.sub_category_name,
            "knowledge_point": result.knowledge_point_name,
            "confidence": result.confidence,
        })

    db.commit()

    return {
        "processed": len(results),
        "kp_linked": kp_linked,
        "results": results,
    }


@router.get("/unclassified", summary="获取未分类/低置信度题目")
async def get_unclassified(
    subject_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取没有考点关联的题目列表"""
    # 查询没有 question_knowledge 关联的题目
    from ...models.models import QuestionKnowledge
    subquery = db.query(QuestionKnowledge.question_id).distinct().subquery()

    query = db.query(QuestionBank).filter(
        QuestionBank.status == 1,
        ~QuestionBank.question_id.in_(db.query(subquery.c.question_id))
    )
    if subject_id:
        query = query.filter(QuestionBank.subject_id == subject_id)

    questions = query.limit(limit).all()

    return {
        "total": len(questions),
        "items": [
            {
                "question_id": q.question_id,
                "subject_id": q.subject_id,
                "content_preview": (q.question_content or "")[:100],
                "current_sc": (
                    q.xingce_subcategory if q.subject_id == 1
                    else q.shenlun_subcategory if q.subject_id == 2
                    else q.gongzhuan_subcategory
                ),
            }
            for q in questions
        ],
    }


# ==================== 新增批量操作接口 ====================

@router.patch("/{question_id}/type", response_model=dict, summary="修改单题题型")
async def update_question_type(
    question_id: int,
    type_id: int,
    current_user: SysUser = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db)
):
    """修改单道题目的题型"""
    question = db.query(QuestionBank).filter(
        QuestionBank.question_id == question_id
    ).first()
    
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    
    # 验证题型存在
    qtype = db.query(QuestionType).filter(QuestionType.type_id == type_id).first()
    if not qtype:
        raise HTTPException(status_code=404, detail="题型不存在")
    
    old_type = question.type.type_name if question.type else "未知"
    question.type_id = type_id
    question.update_time = datetime.now()
    
    # 记录编辑日志
    log = QuestionEditLog(
        question_id=question_id,
        editor_id=current_user.user_id,
        action_type="UPDATE",
        old_data={"type_name": old_type},
        new_data={"type_name": qtype.type_name},
        remark="修改题型"
    )
    db.add(log)
    
    # 更新详细分类表
    from ...models.models import QuestionDetailCategory
    detail = db.query(QuestionDetailCategory).filter(
        QuestionDetailCategory.question_id == question_id
    ).first()
    if detail:
        detail.question_type_detail = qtype.type_name
    
    db.commit()
    
    return {"message": "修改成功", "question_id": question_id, "new_type": qtype.type_name}


@router.patch("/batch-type", response_model=dict, summary="批量修改题型")
async def batch_update_question_type(
    question_ids: List[int],
    type_id: int,
    current_user: SysUser = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db)
):
    """批量修改题目题型"""
    # 验证题型存在
    qtype = db.query(QuestionType).filter(QuestionType.type_id == type_id).first()
    if not qtype:
        raise HTTPException(status_code=404, detail="题型不存在")
    
    updated = 0
    for qid in question_ids:
        question = db.query(QuestionBank).filter(
            QuestionBank.question_id == qid
        ).first()
        if question:
            old_type = question.type.type_name if question.type else "未知"
            question.type_id = type_id
            question.update_time = datetime.now()
            
            # 记录编辑日志
            log = QuestionEditLog(
                question_id=qid,
                editor_id=current_user.user_id,
                action_type="UPDATE",
                old_data={"type_name": old_type},
                new_data={"type_name": qtype.type_name},
                remark="批量修改题型"
            )
            db.add(log)
            
            # 更新详细分类表
            from ...models.models import QuestionDetailCategory
            detail = db.query(QuestionDetailCategory).filter(
                QuestionDetailCategory.question_id == qid
            ).first()
            if detail:
                detail.question_type_detail = qtype.type_name
            
            updated += 1
    
    # 记录操作日志
    from ...models.models import OperationLog
    op_log = OperationLog(
        user_id=current_user.user_id,
        action="batch_update_type",
        target_type="question",
        details=f"批量修改 {updated} 道题目题型为: {qtype.type_name}"
    )
    db.add(op_log)
    
    db.commit()
    
    return {"message": f"成功修改 {updated} 道题目", "updated": updated}


@router.patch("/{question_id}/explanation", response_model=dict, summary="更新题目解析")
async def update_question_explanation(
    question_id: int,
    explanation: str,
    current_user: SysUser = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db)
):
    """更新题目答案解析"""
    question = db.query(QuestionBank).filter(
        QuestionBank.question_id == question_id
    ).first()
    
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    
    old_explanation = question.answer_analysis or ""
    question.answer_analysis = explanation
    question.update_time = datetime.now()
    
    # 记录编辑日志
    log = QuestionEditLog(
        question_id=question_id,
        editor_id=current_user.user_id,
        action_type="UPDATE",
        old_data={"answer_analysis": old_explanation[:200]},
        new_data={"answer_analysis": explanation[:200]},
        remark="更新答案解析"
    )
    db.add(log)
    
    db.commit()
    
    return {"message": "更新成功", "question_id": question_id}


@router.post("/batch-explanation", response_model=dict, summary="批量添加解析")
async def batch_add_explanation(
    items: List[Dict],  # [{"question_id": 123, "explanation": "xxx"}, ...]
    current_user: SysUser = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db)
):
    """批量为题目添加/更新解析"""
    updated = 0
    for item in items:
        qid = item.get("question_id")
        explanation = item.get("explanation", "")
        
        question = db.query(QuestionBank).filter(
            QuestionBank.question_id == qid
        ).first()
        if not question:
            continue
        
        old_explanation = question.answer_analysis or ""
        question.answer_analysis = explanation
        question.update_time = datetime.now()
        
        log = QuestionEditLog(
            question_id=qid,
            editor_id=current_user.user_id,
            action_type="UPDATE",
            old_data={"answer_analysis": old_explanation[:200]},
            new_data={"answer_analysis": explanation[:200]},
            remark="批量更新答案解析"
        )
        db.add(log)
        updated += 1
    
    # 记录操作日志
    from ...models.models import OperationLog
    op_log = OperationLog(
        user_id=current_user.user_id,
        action="batch_add_explanation",
        target_type="question",
        details=f"批量更新 {updated} 道题目答案解析"
    )
    db.add(op_log)
    
    db.commit()
    
    return {"message": f"成功更新 {updated} 道题目解析", "updated": updated}