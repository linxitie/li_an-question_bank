"""
中间件模块 - 限流、请求日志、性能监控、CORS
"""
import time
import uuid
import logging
from typing import Callable, Dict, Any
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .security import rate_limiter, circuit_breaker, TokenType, decode_token
from .exceptions import create_error_response, RateLimitExceededError, CircuitBreakerOpenError

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        start_time = time.time()

        logger.info(f"Request started: {request.method} {request.url.path} [Request-ID: {request_id}]")

        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Request failed: {request.method} {request.url.path} [Request-ID: {request_id}] - {str(e)}")
            raise

        process_time = time.time() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)

        logger.info(
            f"Request completed: {request.method} {request.url.path} "
            f"[Request-ID: {request_id}] - Status: {response.status_code} "
            f"- Duration: {process_time:.3f}s"
        )

        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        rate_limit_key = f"rate_limit:{client_ip}"

        if not rate_limiter.is_allowed(rate_limit_key):
            retry_after = rate_limiter.get_retry_after(rate_limit_key)
            return JSONResponse(
                status_code=429,
                content=create_error_response(
                    status_code=429,
                    message=f"请求过于频繁，请在{retry_after}秒后重试",
                    code="RATE_LIMIT_EXCEEDED",
                    details={"retry_after": retry_after}
                ),
                headers={"Retry-After": str(retry_after)}
            )

        return await call_next(request)

class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)

        if not circuit_breaker.is_available():
            return JSONResponse(
                status_code=503,
                content=create_error_response(
                    status_code=503,
                    message="服务暂时不可用，请稍后重试",
                    code="SERVICE_UNAVAILABLE",
                    details={"retry_after": 60}
                ),
                headers={"Retry-After": "60"}
            )

        try:
            response = await call_next(request)

            if response.status_code < 500:
                circuit_breaker.record_success()
            else:
                circuit_breaker.record_failure()

            return response
        except Exception as e:
            circuit_breaker.record_failure()
            raise

class AuthenticationMiddleware(BaseHTTPMiddleware):
    EXCLUDED_PATHS = [
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/auth/login",
        "/api/auth/register",
    ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if any(request.url.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return JSONResponse(
                status_code=401,
                content=create_error_response(
                    status_code=401,
                    message="未提供认证凭据",
                    code="UNAUTHORIZED"
                )
            )

        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                raise ValueError("Invalid authentication scheme")

            payload = decode_token(token)
            if payload.get("type") != TokenType.ACCESS.value:
                raise ValueError("Invalid token type")

            request.state.user_id = payload.get("user_id")
            request.state.user_no = payload.get("user_no")

        except (ValueError, AttributeError) as e:
            return JSONResponse(
                status_code=401,
                content=create_error_response(
                    status_code=401,
                    message="无效的认证凭据",
                    code="INVALID_TOKEN"
                )
            )

        return await call_next(request)

class CORSMiddleware:
    def __init__(
        self,
        allow_origins: list = None,
        allow_credentials: bool = True,
        allow_methods: list = None,
        allow_headers: list = None,
    ):
        self.allow_origins = allow_origins or ["*"]
        self.allow_credentials = allow_credentials
        self.allow_methods = allow_methods or ["*"]
        self.allow_headers = allow_headers or ["*"]

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        if "*" in self.allow_origins:
            origin = "*"
        else:
            origin = request.headers.get("origin", "")

        if origin in self.allow_origins or "*" in self.allow_origins:
            response = await call_next(request)

            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = str(self.allow_credentials).lower()
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
            response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)

            if request.method == "OPTIONS":
                response.headers["Access-Control-Max-Age"] = "3600"

            return response

        return JSONResponse(
            status_code=403,
            content=create_error_response(
                status_code=403,
                message="不允许的请求来源",
                code="CORS_FORBIDDEN"
            )
        )

def setup_middlewares(app):
    from fastapi import FastAPI

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(CircuitBreakerMiddleware)