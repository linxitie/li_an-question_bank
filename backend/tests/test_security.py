"""
安全模块单元测试
"""
import pytest
from datetime import timedelta

from app.core.security import (
    verify_password, get_password_hash, create_access_token,
    create_refresh_token, decode_token, decode_token_unverified, TokenType,
    TokenManager, RateLimiter, LeakyBucketRateLimiter, CircuitBreaker,
    check_permission, UserRole, Permission, ROLE_PERMISSIONS
)

class TestPasswordHashing:
    def test_password_hash_and_verify(self):
        password = "test_password123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("wrong_password", hashed) is False

    def test_different_passwords_different_hashes(self):
        password = "test_password"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        assert hash1 != hash2

class TestTokenManagement:
    def test_create_access_token(self):
        data = {"user_id": 1, "user_no": "test001"}
        token = create_access_token(data)

        assert token is not None
        assert isinstance(token, str)

        payload = decode_token_unverified(token)
        assert payload["user_id"] == 1
        assert payload["user_no"] == "test001"
        assert payload["type"] == TokenType.ACCESS.value

    def test_create_access_token_with_expiry(self):
        data = {"user_id": 1}
        token = create_access_token(data, expires_delta=timedelta(hours=1))

        assert token is not None

        payload = decode_token_unverified(token)
        assert "exp" in payload

    def test_create_refresh_token(self):
        data = {"user_id": 1}
        token = create_refresh_token(data)

        assert token is not None

        payload = decode_token_unverified(token)
        assert payload["type"] == TokenType.REFRESH.value

    def test_decode_valid_token(self):
        data = {"user_id": 1, "user_no": "test001"}
        token = create_access_token(data)

        payload = decode_token(token)

        assert payload["user_id"] == 1
        assert payload["user_no"] == "test001"

    def test_decode_invalid_token(self):
        with pytest.raises(Exception):
            decode_token("invalid_token")

class TestTokenManager:
    def test_store_and_validate_refresh_token(self):
        manager = TokenManager()
        user_id = 123
        token = "test_refresh_token"

        manager.store_refresh_token(token, user_id)
        result = manager.validate_refresh_token(token)

        assert result == user_id

    def test_validate_revoked_token(self):
        manager = TokenManager()
        token = "revoked_token"

        manager.store_refresh_token(token, 1)
        manager.revoke_refresh_token(token)

        result = manager.validate_refresh_token(token)
        assert result is None

class TestRateLimiter:
    def test_is_allowed_under_limit(self):
        limiter = RateLimiter(rate=10, per=60)
        key = "test_user"

        allowed_count = 0
        for _ in range(10):
            if limiter.is_allowed(key):
                allowed_count += 1

        assert allowed_count == 10

    def test_is_allowed_over_limit(self):
        limiter = RateLimiter(rate=5, per=60)
        key = "test_user_over_limit"

        for _ in range(5):
            limiter.is_allowed(key)

        assert limiter.is_allowed(key) is False

    def test_retry_after_calculation(self):
        limiter = RateLimiter(rate=2, per=60)
        key = "test_retry"

        limiter.is_allowed(key)
        limiter.is_allowed(key)

        retry_after = limiter.get_retry_after(key)
        assert retry_after > 0

class TestLeakyBucketRateLimiter:
    def test_is_allowed_under_capacity(self):
        limiter = LeakyBucketRateLimiter(capacity=10, leak_rate=1.0)
        key = "test_leaky"

        allowed_count = 0
        for _ in range(10):
            if limiter.is_allowed(key):
                allowed_count += 1

        assert allowed_count == 10

    def test_bucket_overflows(self):
        limiter = LeakyBucketRateLimiter(capacity=2, leak_rate=0.1)
        key = "test_overflow"

        limiter.is_allowed(key)
        limiter.is_allowed(key)

        assert limiter.is_allowed(key) is False

class TestCircuitBreaker:
    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(failure_threshold=3)

        assert cb.state == "CLOSED"
        assert cb.is_available() is True

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        cb.record_failure()

        assert cb.state == "OPEN"
        assert cb.is_available() is False

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        cb.record_success()

        assert cb.failure_count == 0
        assert cb.state == "CLOSED"

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0)

        cb.record_failure()
        cb.record_failure()

        assert cb.state == "OPEN"

        import time
        time.sleep(0.1)

        assert cb.is_available() is True
        assert cb.state == "HALF_OPEN"

    def test_half_open_to_closed_on_success(self):
        # recovery_timeout=0 才能立刻从 OPEN 进入 HALF_OPEN；默认 60s 下
        # is_available() 只返回 False 且不改状态（原测试漏了这个前提）
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0, half_max=2)

        cb.record_failure()
        cb.record_failure()
        assert cb.state == "OPEN"
        assert cb.is_available() is True
        assert cb.state == "HALF_OPEN"

        cb.record_success()
        cb.record_success()

        assert cb.state == "CLOSED"

class TestPermissionSystem:
    def test_student_permissions(self):
        assert Permission.QUESTION_VIEW in ROLE_PERMISSIONS[UserRole.STUDENT]
        assert Permission.EXAM_START in ROLE_PERMISSIONS[UserRole.STUDENT]
        assert Permission.QUESTION_DELETE not in ROLE_PERMISSIONS[UserRole.STUDENT]
        assert Permission.USER_MANAGE not in ROLE_PERMISSIONS[UserRole.STUDENT]

    def test_teacher_permissions(self):
        assert Permission.QUESTION_CREATE in ROLE_PERMISSIONS[UserRole.TEACHER]
        assert Permission.PAPER_CREATE in ROLE_PERMISSIONS[UserRole.TEACHER]
        assert Permission.USER_MANAGE not in ROLE_PERMISSIONS[UserRole.TEACHER]

    def test_admin_permissions(self):
        admin_perms = ROLE_PERMISSIONS[UserRole.ADMIN]
        assert Permission.USER_MANAGE in admin_perms
        assert Permission.SYSTEM_CONFIG in admin_perms
        assert Permission.PAPER_APPROVE in admin_perms

    def test_check_permission_valid(self):
        user = type('User', (), {'user_type': 'student', 'status': 1, 'role_level': 0})()
        assert check_permission(user, Permission.QUESTION_VIEW) is True

    def test_check_permission_invalid(self):
        user = type('User', (), {'user_type': 'student', 'status': 1, 'role_level': 0})()
        assert check_permission(user, Permission.USER_MANAGE) is False

    def test_check_permission_invalid_user_type(self):
        user = type('User', (), {'user_type': 'unknown', 'status': 1, 'role_level': 0})()
        assert check_permission(user, Permission.QUESTION_VIEW) is False