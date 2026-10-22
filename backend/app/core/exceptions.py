"""
统一异常处理模块
"""
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import logging
import traceback

logger = logging.getLogger(__name__)

class BaseAPIException(HTTPException):
    def __init__(
        self,
        status_code: int,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        self.message = message
        self.code = code or f"ERR_{status_code}"
        self.details = details or {}
        super().__init__(status_code=status_code, detail=self.message, headers=headers)

class AuthenticationError(BaseAPIException):
    def __init__(self, message: str = "认证失败", code: str = "AUTH_FAILED", details: Optional[Dict[str, Any]] = None):
        super().__init__(status_code=401, message=message, code=code, details=details)

class AuthorizationError(BaseAPIException):
    def __init__(self, message: str = "权限不足", code: str = "FORBIDDEN", details: Optional[Dict[str, Any]] = None):
        super().__init__(status_code=403, message=message, code=code, details=details)

class ResourceNotFoundError(BaseAPIException):
    def __init__(self, resource: str = "资源", resource_id: Optional[Any] = None):
        message = f"{resource}{f' (ID: {resource_id})' if resource_id else ''}不存在"
        super().__init__(status_code=404, message=message, code="RESOURCE_NOT_FOUND")

class ValidationError(BaseAPIException):
    def __init__(self, message: str = "数据验证失败", details: Optional[Dict[str, Any]] = None):
        super().__init__(status_code=422, message=message, code="VALIDATION_ERROR", details=details)

class DuplicateResourceError(BaseAPIException):
    def __init__(self, resource: str = "资源"):
        super().__init__(status_code=409, message=f"{resource}已存在", code="DUPLICATE_RESOURCE")

class RateLimitExceededError(BaseAPIException):
    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=429,
            message=f"请求过于频繁，请在{retry_after}秒后重试",
            code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after}
        )

class CircuitBreakerOpenError(BaseAPIException):
    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=503,
            message=f"服务暂时不可用，请在{retry_after}秒后重试",
            code="SERVICE_UNAVAILABLE",
            details={"retry_after": retry_after}
        )

class BusinessLogicError(BaseAPIException):
    def __init__(self, message: str, code: str = "BUSINESS_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(status_code=400, message=message, code=code, details=details)

class InternalServerError(BaseAPIException):
    def __init__(self, message: str = "系统内部错误"):
        super().__init__(status_code=500, message=message, code="INTERNAL_ERROR")

ERROR_CODE_MAPPING: Dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "UNPROCESSABLE_ENTITY",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_SERVER_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}

def get_error_code(status_code: int) -> str:
    return ERROR_CODE_MAPPING.get(status_code, "UNKNOWN_ERROR")

def create_error_response(
    status_code: int,
    message: str,
    code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    return {
        "success": False,
        "detail": message,
        "error": {
            "code": code or get_error_code(status_code),
            "message": message,
            "details": details or {},
        },
        "request_id": request_id,
    }

class ExceptionHandlers:
    @staticmethod
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID", "unknown")

        if isinstance(exc, BaseAPIException):
            return JSONResponse(
                status_code=exc.status_code,
                content=create_error_response(
                    status_code=exc.status_code,
                    message=exc.message,
                    code=exc.code,
                    details=exc.details,
                    request_id=request_id
                ),
                headers=getattr(exc, "headers", None)
            )

        return JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(
                status_code=exc.status_code,
                message=exc.detail,
                code=get_error_code(exc.status_code),
                request_id=request_id
            )
        )

    @staticmethod
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID", "unknown")

        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            errors.append({
                "field": field,
                "message": error["msg"],
                "type": error["type"]
            })

        return JSONResponse(
            status_code=422,
            content=create_error_response(
                status_code=422,
                message="请求参数验证失败",
                code="VALIDATION_ERROR",
                details={"errors": errors},
                request_id=request_id
            )
        )

    @staticmethod
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID", "unknown")
        logger.error(f"Unhandled exception: {str(exc)}\n{traceback.format_exc()}")

        return JSONResponse(
            status_code=500,
            content=create_error_response(
                status_code=500,
                message="系统内部错误，请稍后重试",
                code="INTERNAL_ERROR",
                request_id=request_id
            )
        )

def register_exception_handlers(app):
    from fastapi import FastAPI
    app.add_exception_handler(HTTPException, ExceptionHandlers.http_exception_handler)
    app.add_exception_handler(RequestValidationError, ExceptionHandlers.validation_exception_handler)
    app.add_exception_handler(Exception, ExceptionHandlers.general_exception_handler)

class ErrorResponse:
    @staticmethod
    def success(data: Any = None, message: str = "操作成功") -> Dict[str, Any]:
        return {
            "success": True,
            "message": message,
            "data": data
        }

    @staticmethod
    def error(
        message: str,
        code: str = "ERROR",
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        return create_error_response(
            status_code=400,
            message=message,
            code=code,
            details=details,
            request_id=request_id
        )