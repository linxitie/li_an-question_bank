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
                      SysUser, QuestionSubject, QuestionBank)
from ...schemas.schemas import (QuestionCreate, QuestionUpdate, QuestionResponse,
                       QuestionListResponse,
                       BatchImportQuestionsRequest, BatchImportResponse,
                       RandomQuestionRequest, RandomQuestionResponse,
                       ErrorResponse, SuccessResponse, BatchImportQuestionItem)


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
        audit_status=0 if current_user.role_level < 3 else 1,  # 管理员创建的直接通过
        status=1
    )

    db.add(new_question)
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
    query = db.query(QuestionBank).filter(QuestionBank.status == 1)

    # 应用筛选条件
    if subject_id:
        query = query.filter(QuestionBank.subject_id == subject_id)
    if type_id:
        query = query.filter(QuestionBank.type_id == type_id)
    if point_id:
        query = query.filter(QuestionBank.point_id == point_id)
    if difficulty:
        query = query.filter(QuestionBank.difficulty == difficulty)
    if audit_status is not None:
        query = query.filter(QuestionBank.audit_status == audit_status)
    if year:
        query = query.filter(QuestionBank.year == year)
    if keyword:
        query = query.filter(
            or_(
                QuestionBank.question_content.like(f"%{keyword}%"),
                QuestionBank.tags.like(f"%{keyword}%"),
                QuestionBank.source.like(f"%{keyword}%")
            )
        )

    # 获取总数
    total = query.count()

    # 分页查询
    questions = query.order_by(
        QuestionBank.create_time.desc()
    ).offset((page - 1) * page_size).limit(page_size).all()

    return QuestionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=questions
    )

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
                audit_status=0 if current_user.role_level < 3 else 1,
                status=1
            )

            db.add(new_question)
            db.flush()  # 获取ID但不提交
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

    # 随机抽取（使用order by rand()）
    questions = query.order_by(func.rand()).limit(draw_request.count).all()

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