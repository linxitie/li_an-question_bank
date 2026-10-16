"""
异常处理模块单元测试
"""
import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.core.exceptions import (
    BaseAPIException, AuthenticationError, AuthorizationError,
    ResourceNotFoundError, ValidationError, DuplicateResourceError,
    RateLimitExceededError, CircuitBreakerOpenError, BusinessLogicError,
    InternalServerError, ErrorResponse, create_error_response,
    get_error_code, ERROR_CODE_MAPPING
)

class TestBaseAPIException:
    def test_basic_exception(self):
        exc = BaseAPIException(
            status_code=400,
            message="Test error",
            code="TEST_ERROR",
            details={"field": "test"}
        )

        assert exc.status_code == 400
        assert exc.message == "Test error"
        assert exc.code == "TEST_ERROR"
        assert exc.details == {"field": "test"}

    def test_exception_inherits_httpexception(self):
        exc = BaseAPIException(status_code=400, message="Test")

        assert isinstance(exc, HTTPException)

class TestAuthenticationError:
    def test_default_values(self):
        exc = AuthenticationError()

        assert exc.status_code == 401
        assert exc.message == "认证失败"
        assert exc.code == "AUTH_FAILED"

    def test_custom_values(self):
        exc = AuthenticationError(
            message="Token expired",
            code="TOKEN_EXPIRED",
            details={"expired_at": "2024-01-01"}
        )

        assert exc.message == "Token expired"
        assert exc.code == "TOKEN_EXPIRED"
        assert exc.details["expired_at"] == "2024-01-01"

class TestAuthorizationError:
    def test_default_values(self):
        exc = AuthorizationError()

        assert exc.status_code == 403
        assert exc.message == "权限不足"
        assert exc.code == "FORBIDDEN"

class TestResourceNotFoundError:
    def test_with_resource_name(self):
        exc = ResourceNotFoundError(resource="题目")

        assert exc.status_code == 404
        assert "题目不存在" in exc.message

    def test_with_resource_id(self):
        exc = ResourceNotFoundError(resource="用户", resource_id=123)

        assert exc.status_code == 404
        assert "123" in exc.message

class TestValidationError:
    def test_default_values(self):
        exc = ValidationError()

        assert exc.status_code == 422
        assert exc.message == "数据验证失败"

    def test_with_details(self):
        exc = ValidationError(
            message="Invalid input",
            details={"errors": [{"field": "name", "error": "required"}]}
        )

        assert exc.details["errors"][0]["field"] == "name"

class TestDuplicateResourceError:
    def test_message_format(self):
        exc = DuplicateResourceError(resource="用户")

        assert exc.status_code == 409
        assert "用户已存在" in exc.message

class TestRateLimitExceededError:
    def test_retry_after_in_detail(self):
        exc = RateLimitExceededError(retry_after=120)

        assert exc.status_code == 429
        assert exc.details["retry_after"] == 120

class TestCircuitBreakerOpenError:
    def test_service_unavailable(self):
        exc = CircuitBreakerOpenError(retry_after=60)

        assert exc.status_code == 503
        assert exc.code == "SERVICE_UNAVAILABLE"

class TestBusinessLogicError:
    def test_custom_business_error(self):
        exc = BusinessLogicError(
            message="Cannot delete active user",
            code="USER_ACTIVE",
            details={"user_id": 1}
        )

        assert exc.status_code == 400
        assert exc.code == "USER_ACTIVE"

class TestErrorCodeMapping:
    def test_known_codes(self):
        assert get_error_code(400) == "BAD_REQUEST"
        assert get_error_code(401) == "UNAUTHORIZED"
        assert get_error_code(403) == "FORBIDDEN"
        assert get_error_code(404) == "NOT_FOUND"
        assert get_error_code(500) == "INTERNAL_SERVER_ERROR"

    def test_unknown_code(self):
        assert get_error_code(999) == "UNKNOWN_ERROR"

class TestCreateErrorResponse:
    def test_basic_response(self):
        response = create_error_response(
            status_code=400,
            message="Bad request"
        )

        assert response["success"] is False
        assert response["error"]["message"] == "Bad request"
        assert "request_id" in response

    def test_with_all_fields(self):
        response = create_error_response(
            status_code=422,
            message="Validation failed",
            code="VALIDATION_ERROR",
            details={"errors": []},
            request_id="test-123"
        )

        assert response["success"] is False
        assert response["error"]["code"] == "VALIDATION_ERROR"
        assert response["error"]["details"] == {"errors": []}
        assert response["request_id"] == "test-123"

class TestErrorResponse:
    def test_success_response(self):
        response = ErrorResponse.success(
            data={"id": 1},
            message="Created successfully"
        )

        assert response["success"] is True
        assert response["message"] == "Created successfully"
        assert response["data"]["id"] == 1

    def test_error_response(self):
        response = ErrorResponse.error(
            message="Something went wrong",
            code="INTERNAL_ERROR",
            details={"reason": "Database connection failed"}
        )

        assert response["success"] is False
        assert response["error"]["code"] == "INTERNAL_ERROR"