"""
gRPC服务模块 - 提供高性能RPC通信（可选）
安装: pip install grpcio grpcio-tools
编译proto: python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. exam_service.proto
"""
import os
import sys
import logging

logger = logging.getLogger(__name__)

# 尝试导入 grpcio，失败则禁用整个模块
try:
    import grpc
    from concurrent import futures
    _GRPC_AVAILABLE = True
except ImportError:
    _GRPC_AVAILABLE = False
    logger.info("grpcio 未安装，gRPC 服务已禁用（不影响 HTTP/WebSocket 功能）")


# ==================== 安全导入 Proto 生成模块 ====================

def _safe_import_pb2(module_name: str = "exam_service_pb2"):
    """
    安全导入 Protocol Buffers 生成的模块

    Returns:
        module or None: 成功返回模块对象，失败返回 None
    """
    # protoc 生成的代码使用绝对 import（如 import exam_service_pb2），
    # 而文件位于 app/ 子目录下，需将 app/ 加入 sys.path 使其可被顶层导入
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    try:
        __import__(module_name)
        return sys.modules[module_name]
    except ImportError:
        pass

    # 如果不存在，尝试自动生成和编译 proto
    logger.warning(f"{module_name} 模块未找到，尝试自动生成...")
    try:
        generate_proto_file()
        # 生成后清理可能缓存的失败导入
        sys.modules.pop(module_name, None)
        __import__(module_name)
        return sys.modules[module_name]
    except Exception as e:
        logger.error(f"无法生成或导入 {module_name}: {e}")
        return None


def _get_pb2_class(class_name: str):
    """
    获取 Proto 生成的类

    Args:
        class_name: 类名（如 QuestionResponse）

    Returns:
        class or None: 成功返回类，失败返回 None
    """
    pb2_module = _safe_import_pb2()
    if pb2_module and hasattr(pb2_module, class_name):
        return getattr(pb2_module, class_name)
    return None


# ==================== Proto 文件生成 ====================

def generate_proto_file():
    """生成 exam_service.proto 文件"""
    proto_content = """syntax = "proto3";

package exam;

service QuestionBankService {
    rpc GetQuestion (QuestionRequest) returns (QuestionResponse);
    rpc SearchQuestions (SearchRequest) returns (QuestionsListResponse);
    rpc CreateQuestion (CreateQuestionRequest) returns (QuestionResponse);
}

service ExamService {
    rpc StartExam (StartExamRequest) returns (ExamRecordResponse);
    rpc SubmitAnswer (SubmitAnswerRequest) returns (SubmitAnswerResponse);
    rpc GetExamResult (ExamResultRequest) returns (ExamResultResponse);
}

message QuestionRequest {
    int64 question_id = 1;
}

message QuestionResponse {
    int64 question_id = 1;
    string content = 2;
    string answer = 3;
    int32 difficulty = 4;
}

message SearchRequest {
    int32 subject_id = 1;
    int32 type_id = 2;
    int32 difficulty = 3;
    int32 limit = 4;
}

message QuestionsListResponse {
    repeated QuestionResponse questions = 1;
}

message CreateQuestionRequest {
    int32 subject_id = 1;
    int32 type_id = 2;
    string content = 3;
    string answer = 4;
    int64 creator_id = 5;
}

message StartExamRequest {
    int64 paper_id = 1;
    int64 user_id = 2;
    string exam_type = 3;
}

message ExamRecordResponse {
    int64 record_id = 1;
    int64 paper_id = 2;
    int64 user_id = 3;
    string start_time = 4;
}

message SubmitAnswerRequest {
    int64 record_id = 1;
    int64 question_id = 2;
    string answer = 3;
}

message SubmitAnswerResponse {
    bool success = 1;
    string error = 2;
}

message ExamResultRequest {
    int64 record_id = 1;
}

message ExamResultResponse {
    int64 record_id = 1;
    float total_score = 2;
    bool is_completed = 3;
}
"""
    proto_path = os.path.join(os.path.dirname(__file__), "exam_service.proto")
    with open(proto_path, "w", encoding="utf-8") as f:
        f.write(proto_content.strip())

    logger.info(f"Proto file generated: {proto_path}")

    # 尝试自动编译 proto
    try:
        from grpc_tools import protoc
        proto_dir = os.path.dirname(__file__)
        result = protoc.main([
            "grpc_tools.protoc",
            f"-I{proto_dir}",
            f"--python_out={proto_dir}",
            f"--grpc_python_out={proto_dir}",
            proto_path,
        ])
        if result == 0:
            logger.info("Proto 文件编译成功")
        else:
            logger.warning(f"Proto 编译返回码: {result}")
    except ImportError:
        logger.info("grpcio-tools 未安装，跳过 proto 编译（手动运行: python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. exam_service.proto）")
    except Exception as e:
        logger.warning(f"Proto 编译失败: {e}")


# ==================== 仅在 gRPC 可用时定义服务类 ====================

if _GRPC_AVAILABLE:

    class GRPCService:
        """gRPC 服务器管理"""

        def __init__(self, host: str = "0.0.0.0", port: int = 50051):
            self.host = host
            self.port = port
            self.server = None

        def create_server(self):
            options = [
                ('grpc.so_reuseport', 0),
                ('grpc.max_send_message_length', 50 * 1024 * 1024),
                ('grpc.max_receive_message_length', 50 * 1024 * 1024),
            ]
            self.server = grpc.server(
                futures.ThreadPoolExecutor(max_workers=10),
                options=options
            )

        def start(self):
            if not self.server:
                self.create_server()

            self.server.add_insecure_port(f"{self.host}:{self.port}")
            self.server.start()
            logger.info(f"gRPC 服务已启动: {self.host}:{self.port}")

        def stop(self):
            if self.server:
                self.server.stop(grace=5)
                logger.info("gRPC 服务已停止")

        def add_service(self, service_name, service_impl):
            """动态添加 gRPC 服务"""
            if self.server:
                # _pb2_grpc 模块中的 add_*Servicer_to_server 是顶层函数，不是 server 对象的方法
                pb2_grpc_module = _safe_import_pb2("exam_service_pb2_grpc")
                if pb2_grpc_module:
                    add_func = getattr(
                        pb2_grpc_module,
                        f"add_{service_name}ServiceServicer_to_server",
                        None
                    )
                    if add_func:
                        add_func(service_impl, self.server)
                    else:
                        logger.warning(f"未找到服务注册方法: add_{service_name}ServiceServicer_to_server")
                else:
                    logger.warning(f"无法导入 exam_service_pb2_grpc 模块")


    class QuestionBankServicer:
        """题库 gRPC 服务"""

        def GetQuestion(self, request, context):
            from .core.database import SessionLocal
            from .models.models import QuestionBank

            db = SessionLocal()
            try:
                question = db.query(QuestionBank).filter(
                    QuestionBank.question_id == request.question_id
                ).first()

                if not question:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details("题目不存在")
                    return None

                # 使用安全方式获取 Proto 类
                QuestionResponse = _get_pb2_class("QuestionResponse")
                if not QuestionResponse:
                    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
                    context.set_details("Proto 模块未正确生成")
                    return None

                return QuestionResponse(
                    question_id=question.question_id,
                    content=question.question_content or "",
                    answer=question.answer or "",
                    difficulty=question.difficulty or 0
                )
            finally:
                db.close()

        def SearchQuestions(self, request, context):
            from .core.database import SessionLocal
            from .models.models import QuestionBank

            # 使用安全方式获取 Proto 类
            QuestionResponse = _get_pb2_class("QuestionResponse")
            QuestionsListResponse = _get_pb2_class("QuestionsListResponse")
            if not QuestionResponse or not QuestionsListResponse:
                context.set_code(grpc.StatusCode.UNIMPLEMENTED)
                context.set_details("Proto 模块未正确生成")
                return None

            db = SessionLocal()
            try:
                query = db.query(QuestionBank)

                if request.subject_id:
                    query = query.filter(QuestionBank.subject_id == request.subject_id)
                if request.difficulty:
                    query = query.filter(QuestionBank.difficulty == request.difficulty)

                questions = query.limit(request.limit).all()

                return QuestionsListResponse(
                    questions=[
                        QuestionResponse(
                            question_id=q.question_id,
                            content=q.question_content or "",
                            answer=q.answer or "",
                            difficulty=q.difficulty or 0
                        ) for q in questions
                    ]
                )
            finally:
                db.close()

        def CreateQuestion(self, request, context):
            from .core.database import SessionLocal
            from .models.models import QuestionBank

            # 使用安全方式获取 Proto 类
            QuestionResponse = _get_pb2_class("QuestionResponse")
            if not QuestionResponse:
                context.set_code(grpc.StatusCode.UNIMPLEMENTED)
                context.set_details("Proto 模块未正确生成")
                return None

            db = SessionLocal()
            try:
                question = QuestionBank(
                    subject_id=request.subject_id,
                    type_id=request.type_id,
                    question_content=request.content,
                    answer=request.answer,
                    creator_id=request.creator_id
                )

                db.add(question)
                db.commit()
                db.refresh(question)

                return QuestionResponse(
                    question_id=question.question_id,
                    content=question.question_content or "",
                    answer=question.answer or "",
                    difficulty=question.difficulty or 0
                )
            except Exception as e:
                db.rollback()
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
                return None
            finally:
                db.close()


    class ExamServicer:
        """考试 gRPC 服务"""

        def StartExam(self, request, context):
            from datetime import datetime
            from .core.database import SessionLocal
            from .models.models import ExamRecord, ExamPaper

            # 使用安全方式获取 Proto 类
            ExamRecordResponse = _get_pb2_class("ExamRecordResponse")
            if not ExamRecordResponse:
                context.set_code(grpc.StatusCode.UNIMPLEMENTED)
                context.set_details("Proto 模块未正确生成")
                return None

            db = SessionLocal()
            try:
                paper = db.query(ExamPaper).filter(
                    ExamPaper.paper_id == request.paper_id
                ).first()

                if not paper:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details("试卷不存在")
                    return None

                record = ExamRecord(
                    paper_id=request.paper_id,
                    user_id=request.user_id,
                    exam_type=request.exam_type,
                    start_time=datetime.now()
                )

                db.add(record)
                db.commit()
                db.refresh(record)

                return ExamRecordResponse(
                    record_id=record.record_id,
                    paper_id=record.paper_id,
                    user_id=record.user_id,
                    start_time=str(record.start_time)
                )
            finally:
                db.close()

        def SubmitAnswer(self, request, context):
            from .core.database import SessionLocal
            from .models.models import ExamAnswerDetail

            # 使用安全方式获取 Proto 类
            SubmitAnswerResponse = _get_pb2_class("SubmitAnswerResponse")
            if not SubmitAnswerResponse:
                context.set_code(grpc.StatusCode.UNIMPLEMENTED)
                context.set_details("Proto 模块未正确生成")
                return None

            db = SessionLocal()
            try:
                detail = ExamAnswerDetail(
                    record_id=request.record_id,
                    question_id=request.question_id,
                    student_answer=request.answer
                )

                db.add(detail)
                db.commit()

                return SubmitAnswerResponse(success=True)
            except Exception as e:
                db.rollback()
                return SubmitAnswerResponse(success=False, error=str(e))
            finally:
                db.close()

        def GetExamResult(self, request, context):
            from .core.database import SessionLocal
            from .models.models import ExamRecord

            # 使用安全方式获取 Proto 类
            ExamResultResponse = _get_pb2_class("ExamResultResponse")
            if not ExamResultResponse:
                context.set_code(grpc.StatusCode.UNIMPLEMENTED)
                context.set_details("Proto 模块未正确生成")
                return None

            db = SessionLocal()
            try:
                record = db.query(ExamRecord).filter(
                    ExamRecord.record_id == request.record_id
                ).first()

                if not record:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details("考试记录不存在")
                    return None

                return ExamResultResponse(
                    record_id=record.record_id,
                    total_score=record.total_score or 0.0,
                    is_completed=bool(record.is_completed)
                )
            finally:
                db.close()


    grpc_service = GRPCService()

else:
    # gRPC 不可用时的占位对象
    class _DummyGRPCService:
        """占位 gRPC 服务，所有操作均为空操作"""
        def create_server(self): pass
        def start(self): pass
        def stop(self): pass
        def add_service(self, *args, **kwargs): pass

    grpc_service = _DummyGRPCService()


# ==================== 生命周期钩子 ====================

def setup_grpc_service(app):
    """启动 gRPC 服务（main.py lifespan 中调用）"""
    if not _GRPC_AVAILABLE:
        return

    try:
        grpc_service.create_server()
        grpc_service.add_service("QuestionBank", QuestionBankServicer())
        grpc_service.add_service("Exam", ExamServicer())
        grpc_service.start()
        logger.info("gRPC 服务初始化完成")
    except Exception as e:
        logger.warning(f"gRPC 服务初始化失败（不影响 HTTP 服务）: {e}")


def stop_grpc_service():
    """停止 gRPC 服务"""
    grpc_service.stop()
