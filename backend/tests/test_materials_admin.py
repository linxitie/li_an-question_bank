"""材料管理 API 测试 — 覆盖统计概览、批量操作、导入记录等新增接口"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestAdminStats:
    """统计概览接口"""

    def test_stats_returns_required_fields(self, client):
        resp = client.get("/api/materials/admin/stats")
        # 未登录应返回 401 或 403，这里仅验证路由存在
        assert resp.status_code in (200, 401, 403)


class TestBatchOperations:
    """批量操作接口"""

    def test_batch_create_empty(self, client):
        resp = client.post("/api/materials/admin/batch", json={"items": []})
        assert resp.status_code in (400, 401, 403)

    def test_batch_delete_empty(self, client):
        # httpx 0.28 起 TestClient.delete() 不再接受 json=；用 request() 显式指定方法
        resp = client.request("DELETE", "/api/materials/admin/batch", json={"ids": []})
        assert resp.status_code in (400, 401, 403)


class TestImportRecords:
    """导入记录接口"""

    def test_import_records_default_page(self, client):
        resp = client.get("/api/materials/admin/import-records")
        assert resp.status_code in (200, 401, 403)


class TestClassifier:
    """智能分类服务"""

    def test_classify_video_short(self):
        from app.services.material_classifier import classifier
        result = classifier.classify(".mp4", duration=300, title="行测入门视频")
        assert result["type"] == "video_intro"
        assert result["confidence"] >= 0.8

    def test_classify_video_long(self):
        from app.services.material_classifier import classifier
        result = classifier.classify(".mp4", duration=2000, title="进阶技巧讲解")
        assert result["type"] == "video_advanced"

    def test_classify_document_long(self):
        """B3（2026-11-07）起：文档一律判 **讲义**，不再按字数分 article/card。

        原断言是 `article`，B3 把 `_classify_document` 改成恒返回 lecture
        （卡片必须有正/背面结构，文档天然没有），但本测试没跟随，成为长期红。
        这里补上原因，避免下次又被误判成"新引入的失败"。
        """
        from app.services.material_classifier import classifier
        result = classifier.classify(".docx", content="测试" * 600, title="行测备考指南")
        assert result["type"] == "lecture"
        assert result["confidence"] > 0

    def test_classify_document_short(self):
        """短文档同样是讲义（B3 删除了「len(content) < 500 → card」的旧规则）。"""
        from app.services.material_classifier import classifier
        result = classifier.classify(".docx", content="短内容", title="知识卡片要点")
        assert result["type"] == "lecture"
        assert "讲义" in result["reason"]

    def test_classify_unknown(self):
        from app.services.material_classifier import classifier
        result = classifier.classify(".unknown")
        assert result["type"] == "article"


class TestDeduplicator:
    """去重检测服务"""

    def test_md5_calculation(self):
        from app.services.material_deduplicator import deduplicator
        md5 = deduplicator._calculate_md5("测试内容")
        assert len(md5) == 32
        assert md5 == deduplicator._calculate_md5("测试内容")

    def test_md5_different(self):
        from app.services.material_deduplicator import deduplicator
        md5_a = deduplicator._calculate_md5("内容A")
        md5_b = deduplicator._calculate_md5("内容B")
        assert md5_a != md5_b


class TestContentCleaner:
    """内容清洗服务"""

    def test_clean_phone(self):
        from app.services.material_sanitizer import content_cleaner
        text = "请联系 13812345678 获取更多资料"
        cleaned = content_cleaner.clean_text(text)
        assert "13812345678" not in cleaned

    def test_clean_copyright(self):
        from app.services.material_sanitizer import content_cleaner
        text = "版权所有 未经许可不得转载"
        cleaned = content_cleaner.clean_text(text)
        assert "版权所有" not in cleaned

    def test_clean_ad(self):
        from app.services.material_sanitizer import content_cleaner
        text = "扫码关注公众号领取资料"
        cleaned = content_cleaner.clean_text(text)
        assert "扫码关注" not in cleaned

    def test_content_hash(self):
        from app.services.material_sanitizer import content_cleaner
        h1 = content_cleaner.calculate_content_hash("测试内容")
        h2 = content_cleaner.calculate_content_hash("测试内容")
        assert h1 == h2
        assert len(h1) == 32


class TestImportMonitor:
    """监控告警服务"""

    def test_record_import(self):
        from app.services.material_monitor import ImportMonitor
        monitor = ImportMonitor()
        monitor.record_import(success=True)
        monitor.record_import(success=False)
        summary = monitor.get_metrics_summary()
        assert summary["total_imports"] == 2
        assert summary["failed_imports"] == 1
        assert summary["failure_rate"] == 0.5

    def test_record_duplicate(self):
        from app.services.material_monitor import ImportMonitor
        monitor = ImportMonitor()
        monitor.record_duplicate_match()
        summary = monitor.get_metrics_summary()
        assert summary["duplicate_matches"] == 1
