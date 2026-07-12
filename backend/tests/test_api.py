"""
API路由单元测试
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data

    def test_root_endpoint(self, client):
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert data["version"] == "1.0.0"

    def test_docs_endpoint(self, client):
        response = client.get("/docs")

        assert response.status_code == 200

    def test_redoc_endpoint(self, client):
        response = client.get("/redoc")

        assert response.status_code == 200

    def test_openapi_endpoint(self, client):
        response = client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data

class TestMetricsEndpoint:
    def test_get_metrics(self, client):
        response = client.get("/metrics")

        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "counters" in data
        assert "gauges" in data

    def test_get_endpoint_metrics(self, client):
        response = client.get("/metrics/endpoints")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_reset_metrics(self, client):
        response = client.post("/metrics/reset")

        assert response.status_code == 200

    def test_get_system_metrics(self, client):
        response = client.get("/metrics/system")

        assert response.status_code == 200
        data = response.json()
        assert "system" in data or "application" in data

class TestAuthEndpoints:
    def test_login_without_credentials(self, client):
        response = client.post("/api/auth/login", json={})

        assert response.status_code == 422

    def test_register_without_credentials(self, client):
        response = client.post("/api/auth/register", json={})

        assert response.status_code == 422

    def test_get_current_user_without_token(self, client):
        response = client.get("/api/auth/me")

        assert response.status_code == 401

    def test_login_with_invalid_user(self, client):
        response = client.post("/api/auth/login", json={
            "user_no": "nonexistent",
            "password": "wrongpass"
        })

        assert response.status_code == 401

    def test_register_with_existing_user(self, client, test_user):
        response = client.post("/api/auth/register", json={
            "user_no": "test001",
            "username": "Another User",
            "password": "password123",
            "phone": "13900139000",
            "user_type": "student"
        })

        assert response.status_code == 400

class TestQuestionEndpoints:
    def test_get_subjects(self, client):
        response = client.get("/api/questions/subjects")

        assert response.status_code == 200

    def test_get_types(self, client):
        response = client.get("/api/questions/types")

        assert response.status_code == 200

    def test_get_knowledge_points_without_subject(self, client):
        response = client.get("/api/questions/knowledge_points")

        assert response.status_code == 422

    def test_create_question_without_auth(self, client, test_subject, test_question_type):
        response = client.post("/api/questions/", json={
            "subject_id": test_subject.subject_id,
            "type_id": test_question_type.type_id,
            "question_content": "测试题目内容",
            "answer": "A",
            "difficulty": 3,
            "score": 5.0
        })

        assert response.status_code == 401

    def test_get_question_not_found(self, client):
        response = client.get("/api/questions/99999")

        assert response.status_code == 401

class TestPaperEndpoints:
    def test_get_papers_without_auth(self, client):
        response = client.get("/api/papers/")

        assert response.status_code == 401

    def test_create_paper_without_auth(self, client):
        response = client.post("/api/papers/", json={
            "paper_name": "Test Paper",
            "paper_code": "TEST001",
            "subject_id": 1,
            "composition_method": "MANUAL",
            "duration": 120,
            "total_score": 100.0
        })

        assert response.status_code == 401

class TestExamEndpoints:
    def test_start_exam_without_auth(self, client):
        response = client.post("/api/exam/start", json={
            "paper_id": 1,
            "exam_type": "SIMULATION"
        })

        assert response.status_code == 401

    def test_get_exam_detail_without_auth(self, client):
        response = client.get("/api/exam/1")

        assert response.status_code == 401

class TestWebSocketEndpoints:
    def test_get_online_users_requires_auth(self, client):
        response = client.get("/ws/online_users")

        assert response.status_code == 401

    def test_websocket_endpoint_exists(self, client):
        response = client.get("/ws/")

        assert response.status_code in [200, 404, 405]

class TestAuthenticationMiddleware:
    def test_request_without_authorization_header(self, client):
        response = client.get("/api/questions/subjects")

        assert response.status_code == 401

    def test_request_with_invalid_token(self, client):
        response = client.get(
            "/api/questions/subjects",
            headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401

    def test_request_with_valid_token(self, client, test_user, auth_headers):
        response = client.get("/api/auth/me", headers=auth_headers)

        assert response.status_code == 200

    def test_cors_preflight_request(self, client):
        response = client.options(
            "/api/questions/subjects",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization"
            }
        )

        assert response.status_code == 200