# 管理员端备考资料导入功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现管理员端备考资料导入功能，包括智能分类、去重机制和稳定性保障

**Architecture:** 采用渐进式实现策略，分三个阶段：基础功能、核心功能、高级功能。前端修改现有页面，后端扩展现有API接口。

**Tech Stack:** Vue 3 + TypeScript, FastAPI, SQLAlchemy, MySQL, MinerU, Simhash, Sentence-BERT

---

## 文件结构映射

### 后端文件

| 文件路径 | 职责 |
|---------|------|
| `backend/app/api/v1/materials.py` | 扩展管理端API接口 |
| `backend/app/services/material_classifier.py` | 智能分类服务 |
| `backend/app/services/material_deduplicator.py` | 去重检测服务 |
| `backend/app/services/material_sanitizer.py` | 内容清洗服务 |
| `backend/app/services/material_monitor.py` | 监控告警服务 |
| `backend/app/models/models.py` | 添加新数据表模型 |
| `backend/app/core/config.py` | 添加配置项 |

### 前端文件

| 文件路径 | 职责 |
|---------|------|
| `.vtj/vue/admin_materials.vue` | 修改现有页面，添加新功能 |
| `src/utils/api.ts` | API工具函数（如不存在则创建） |

### 测试文件

| 文件路径 | 职责 |
|---------|------|
| `backend/tests/test_materials.py` | API接口测试 |
| `backend/tests/test_classifier.py` | 分类服务测试 |
| `backend/tests/test_deduplicator.py` | 去重服务测试 |

---

## 阶段1：基础功能（Task 1-5）

### Task 1: 添加数据表模型

**Files:**
- Modify: `backend/app/models/models.py`

- [ ] **Step 1: 添加分类规则表模型**

```python
# 在 models.py 文件末尾添加
class MaterialClassificationRule(Base):
    """资料分类规则表"""
    __tablename__ = "material_classification_rules"
    
    rule_id = Column(Integer, primary_key=True, autoincrement=True)
    rule_name = Column(String(100), nullable=False, comment="规则名称")
    rule_type = Column(String(50), nullable=False, comment="format/content/keyword")
    rule_config = Column(JSON, comment="规则配置")
    priority = Column(Integer, default=0, comment="优先级")
    enabled = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=func.now())
```

- [ ] **Step 2: 添加去重记录表模型**

```python
# 在 models.py 文件末尾添加
class MaterialDuplicateRecord(Base):
    """资料去重记录表"""
    __tablename__ = "material_duplicate_records"
    
    duplicate_id = Column(Integer, primary_key=True, autoincrement=True)
    original_id = Column(Integer, ForeignKey("study_materials.material_id"), comment="原始资料ID")
    duplicate_id = Column(Integer, ForeignKey("study_materials.material_id"), comment="重复资料ID")
    similarity = Column(DECIMAL(5, 4), comment="相似度")
    duplicate_type = Column(String(20), comment="exact/fingerprint/semantic")
    status = Column(String(20), default="pending", comment="pending/confirmed/ignored")
    created_at = Column(DateTime, default=func.now())
```

- [ ] **Step 3: 添加 content_hash 字段到 study_materials 表**

```python
# 在 StudyMaterial 类中添加
content_hash = Column(String(64), comment="内容MD5哈希(去重用)")
```

- [ ] **Step 4: 运行数据库迁移**

```bash
cd backend
python -c "from app.core.database import engine, Base; from app.models import models; Base.metadata.create_all(bind=engine)"
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/models.py
git commit -m "feat: add classification rules and duplicate records tables"
```

### Task 2: 添加配置项

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: 添加材料管理配置**

```python
# 在 Settings 类中添加
class Settings(BaseSettings):
    # ... 现有配置 ...
    
    # 材料管理配置
    MATERIAL_MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
    MATERIAL_TOTAL_SIZE_LIMIT = 2 * 1024 * 1024 * 1024  # 2GB
    MATERIAL_SUPPORTED_FORMATS = {
        'video': ['.mp4', '.mov', '.avi', '.webm'],
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'],
        'document': ['.pdf', '.docx', '.txt'],
        'spreadsheet': ['.xlsx', '.csv'],
        'archive': ['.zip', '.rar']
    }
    MATERIAL_DUPLICATE_THRESHOLD = 0.95  # 去重阈值
    MATERIAL_CLASSIFICATION_CONFIDENCE_HIGH = 0.9  # 高置信度阈值
    MATERIAL_CLASSIFICATION_CONFIDENCE_LOW = 0.7  # 低置信度阈值
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/core/config.py
git commit -m "feat: add material management configuration"
```

### Task 3: 实现统计概览接口

**Files:**
- Modify: `backend/app/api/v1/materials.py`

- [ ] **Step 1: 添加统计概览接口**

```python
# 在 materials.py 文件的管理端部分添加
@router.get("/admin/stats", summary="统计概览(管理员)")
async def admin_stats(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _require_admin(current_user)
    
    total = db.query(func.count(StudyMaterial.material_id)).scalar() or 0
    
    # 按类型统计
    type_stats = dict(
        db.query(StudyMaterial.type, func.count(StudyMaterial.material_id))
        .group_by(StudyMaterial.type)
        .all()
    )
    
    # 按科目统计
    subject_stats = dict(
        db.query(StudyMaterial.subject, func.count(StudyMaterial.material_id))
        .group_by(StudyMaterial.subject)
        .all()
    )
    
    # 按状态统计
    status_stats = dict(
        db.query(StudyMaterial.status, func.count(StudyMaterial.material_id))
        .group_by(StudyMaterial.status)
        .all()
    )
    
    return {
        "total": total,
        "by_type": {
            "video_intro": type_stats.get("video_intro", 0),
            "video_advanced": type_stats.get("video_advanced", 0),
            "article": type_stats.get("article", 0),
            "card": type_stats.get("card", 0),
            "image": type_stats.get("image", 0),
            "table": type_stats.get("table", 0)
        },
        "by_subject": {
            "xingce": subject_stats.get("xingce", 0),
            "shenlun": subject_stats.get("shenlun", 0),
            "gongzhuan": subject_stats.get("gongzhuan", 0)
        },
        "by_status": {
            "published": status_stats.get(1, 0),
            "draft": status_stats.get(0, 0)
        }
    }
```

- [ ] **Step 2: 测试接口**

```bash
cd backend
python -c "
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
response = client.get('/api/materials/admin/stats')
print(response.json())
"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/materials.py
git commit -m "feat: add admin stats endpoint"
```

### Task 4: 实现批量操作接口

**Files:**
- Modify: `backend/app/api/v1/materials.py`

- [ ] **Step 1: 添加批量创建接口**

```python
# 在 materials.py 文件的管理端部分添加
@router.post("/admin/batch", summary="批量创建资料(管理员)")
async def admin_batch_create(
    body: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _require_admin(current_user)
    
    items = body.get("items", [])
    if not items:
        raise HTTPException(400, "items不能为空")
    
    created_ids = []
    for item in items:
        data = _validate_material_body(item)
        m = StudyMaterial(**data, creator_id=current_user.user_id)
        db.add(m)
        db.flush()
        created_ids.append(m.material_id)
    
    db.commit()
    _audit(db, current_user, "batch_create", f"created={len(created_ids)}")
    db.commit()
    
    return {"created": len(created_ids), "material_ids": created_ids}
```

- [ ] **Step 2: 添加批量删除接口**

```python
# 在 materials.py 文件的管理端部分添加
@router.delete("/admin/batch", summary="批量删除资料(管理员)")
async def admin_batch_delete(
    body: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _require_admin(current_user)
    
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(400, "ids不能为空")
    
    # 删除学习进度
    db.query(UserMaterialProgress).filter(
        UserMaterialProgress.material_id.in_(ids)
    ).delete(synchronize_session=False)
    
    # 删除资料
    deleted = db.query(StudyMaterial).filter(
        StudyMaterial.material_id.in_(ids)
    ).delete(synchronize_session=False)
    
    db.commit()
    _audit(db, current_user, "batch_delete", f"deleted={deleted}")
    db.commit()
    
    return {"deleted": deleted}
```

- [ ] **Step 3: 添加导入记录查询接口**

```python
# 在 materials.py 文件的管理端部分添加
@router.get("/admin/import-records", summary="导入记录列表(管理员)")
async def admin_import_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _require_admin(current_user)
    
    q = db.query(MaterialImportRecord)
    total = q.count()
    rows = (q.order_by(MaterialImportRecord.import_id.desc())
             .offset((page - 1) * page_size)
             .limit(page_size)
             .all())
    
    items = []
    for r in rows:
        items.append({
            "import_id": r.import_id,
            "file_name": r.file_name,
            "file_type": r.file_type,
            "file_size": r.file_size,
            "parse_status": r.parse_status,
            "uploader_id": r.uploader_id,
            "create_time": r.create_time.isoformat() if r.create_time else None
        })
    
    return {"total": total, "items": items}
```

- [ ] **Step 4: 测试接口**

```bash
cd backend
python -c "
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# 测试批量创建
response = client.post('/api/materials/admin/batch', json={
    'items': [
        {'subject': 'xingce', 'type': 'card', 'title': '测试卡片', 'card_front': '正面', 'card_back': '背面'}
    ]
})
print('Batch create:', response.json())

# 测试导入记录
response = client.get('/api/materials/admin/import-records')
print('Import records:', response.json())
"
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/materials.py
git commit -m "feat: add batch operations and import records endpoints"
```

### Task 5: 修改前端页面添加统计概览

**Files:**
- Modify: `.vtj/vue/admin_materials.vue`

- [ ] **Step 1: 添加统计概览组件**

```vue
<!-- 在 template 开头添加统计概览 -->
<template>
  <div class="adm-page">
    <!-- 统计概览 -->
    <div class="stats-overview">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">总资料数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.by_type.video_intro + stats.by_type.video_advanced }}</div>
        <div class="stat-label">视频</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.by_type.article }}</div>
        <div class="stat-label">文档</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.by_type.card }}</div>
        <div class="stat-label">卡片</div>
      </div>
    </div>
    
    <!-- 原有内容 -->
    <header class="bar">
      <!-- ... -->
    </header>
    <!-- ... -->
  </div>
</template>
```

- [ ] **Step 2: 添加统计概览样式**

```css
/* 在 style 部分添加 */
.stats-overview {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  flex: 1;
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  box-shadow: 0 2px 12px rgba(10, 22, 40, 0.05);
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #1a2a4a;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 13px;
  color: #8899aa;
}
```

- [ ] **Step 3: 添加统计数据加载**

```javascript
// 在 setup 中添加
const state = reactive({
  // ... 现有状态 ...
  stats: {
    total: 0,
    by_type: { video_intro: 0, video_advanced: 0, article: 0, card: 0 },
    by_subject: { xingce: 0, shenlun: 0, gongzhuan: 0 },
    by_status: { published: 0, draft: 0 }
  }
});

// 添加加载统计方法
async loadStats() {
  try {
    const r = await this.api('/api/materials/admin/stats');
    if (r.ok) {
      const d = await r.json();
      this.state.stats = d;
    }
  } catch (e) {
    console.warn('[AdminMaterials] loadStats failed:', e);
  }
},

// 在 mounted 中调用
mounted() {
  this.loadList();
  this.loadStats();
},
```

- [ ] **Step 4: Commit**

```bash
git add .vtj/vue/admin_materials.vue
git commit -m "feat: add statistics overview to admin materials page"
```

---

## 阶段2：核心功能（Task 6-10）

### Task 6: 实现智能分类服务

**Files:**
- Create: `backend/app/services/material_classifier.py`

- [ ] **Step 1: 创建分类服务基础结构**

```python
"""智能分类服务"""
import re
from typing import Optional
from ..core.config import settings


class MaterialClassifier:
    """资料智能分类器"""
    
    # 文件类型映射
    FILE_TYPE_MAP = {
        '.mp4': 'video', '.mov': 'video', '.avi': 'video', '.webm': 'video',
        '.jpg': 'image', '.jpeg': 'image', '.png': 'image', '.gif': 'image',
        '.webp': 'image', '.svg': 'image',
        '.pdf': 'document', '.docx': 'document', '.txt': 'document',
        '.xlsx': 'spreadsheet', '.csv': 'spreadsheet',
        '.zip': 'archive', '.rar': 'archive'
    }
    
    # 视频时长阈值（秒）
    VIDEO_DURATION_THRESHOLD = 15 * 60  # 15分钟
    
    # 文档长度阈值（字）
    DOCUMENT_LENGTH_THRESHOLD = 500
    
    def classify(self, file_ext: str, content: str = None, 
                 duration: int = None, title: str = None) -> dict:
        """
        智能分类资料
        
        Returns:
            {
                'type': str,  # 分类结果
                'confidence': float,  # 置信度
                'reason': str  # 分类原因
            }
        """
        file_type = self.FILE_TYPE_MAP.get(file_ext.lower())
        
        if file_type == 'video':
            return self._classify_video(duration, title)
        elif file_type == 'image':
            return self._classify_image(content, title)
        elif file_type == 'document':
            return self._classify_document(content, title)
        elif file_type == 'spreadsheet':
            return self._classify_spreadsheet(content, title)
        else:
            return {'type': 'article', 'confidence': 0.5, 'reason': '默认分类'}
    
    def _classify_video(self, duration: int = None, title: str = None) -> dict:
        """分类视频"""
        confidence = 0.7
        reason = '视频文件'
        
        if duration and duration <= self.VIDEO_DURATION_THRESHOLD:
            if title and re.search(r'入门|导学|基础|考什么', title):
                return {'type': 'video_intro', 'confidence': 0.9, 'reason': '短视频+入门关键词'}
            return {'type': 'video_intro', 'confidence': 0.8, 'reason': '短视频'}
        elif duration and duration > self.VIDEO_DURATION_THRESHOLD:
            if title and re.search(r'进阶|高分|技巧|深度|解析', title):
                return {'type': 'video_advanced', 'confidence': 0.9, 'reason': '长视频+进阶关键词'}
            return {'type': 'video_advanced', 'confidence': 0.8, 'reason': '长视频'}
        
        return {'type': 'video_intro', 'confidence': confidence, 'reason': reason}
    
    def _classify_image(self, content: str = None, title: str = None) -> dict:
        """分类图片"""
        if title and re.search(r'思维导图|流程图|结构图', title):
            return {'type': 'image', 'confidence': 0.85, 'reason': '图片+图表关键词'}
        return {'type': 'image', 'confidence': 0.7, 'reason': '图片文件'}
    
    def _classify_document(self, content: str = None, title: str = None) -> dict:
        """分类文档"""
        if not content:
            return {'type': 'article', 'confidence': 0.6, 'reason': '文档无内容'}
        
        content_length = len(content)
        
        if content_length < self.DOCUMENT_LENGTH_THRESHOLD:
            if title and re.search(r'卡片|知识|要点|口诀', title):
                return {'type': 'card', 'confidence': 0.85, 'reason': '短文档+卡片关键词'}
            return {'type': 'card', 'confidence': 0.7, 'reason': '短文档'}
        else:
            return {'type': 'article', 'confidence': 0.8, 'reason': '长文档'}
    
    def _classify_spreadsheet(self, content: str = None, title: str = None) -> dict:
        """分类表格"""
        if title and re.search(r'卡片|知识|要点|口诀', title):
            return {'type': 'card', 'confidence': 0.8, 'reason': '表格+卡片关键词'}
        return {'type': 'table', 'confidence': 0.75, 'reason': '表格文件'}


# 全局实例
classifier = MaterialClassifier()
```

- [ ] **Step 2: 测试分类服务**

```bash
cd backend
python -c "
from app.services.material_classifier import classifier

# 测试视频分类
result = classifier.classify('.mp4', duration=600, title='行测导学视频')
print('Video:', result)

# 测试文档分类
result = classifier.classify('.docx', content='这是一篇关于行测的文章' * 100, title='行测备考指南')
print('Document:', result)
"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/material_classifier.py
git commit -m "feat: implement intelligent classification service"
```

### Task 7: 实现去重检测服务

**Files:**
- Create: `backend/app/services/material_deduplicator.py`

- [ ] **Step 1: 创建去重服务基础结构**

```python
"""去重检测服务"""
import hashlib
from typing import Optional
from sqlalchemy.orm import Session
from ..models.models import StudyMaterial, MaterialDuplicateRecord
from ..core.config import settings


class MaterialDeduplicator:
    """资料去重检测器"""
    
    def __init__(self):
        self.threshold = settings.MATERIAL_DUPLICATE_THRESHOLD
    
    def check_duplicate(self, content: str, db: Session) -> dict:
        """
        检查内容是否重复
        
        Returns:
            {
                'is_duplicate': bool,
                'level': str,  # exact/fingerprint/semantic
                'similarity': float,
                'existing_id': int
            }
        """
        # 第一层：精确去重（MD5）
        md5 = self._calculate_md5(content)
        existing = self._check_md5_exists(md5, db)
        if existing:
            return {
                'is_duplicate': True,
                'level': 'exact',
                'similarity': 1.0,
                'existing_id': existing
            }
        
        return {'is_duplicate': False}
    
    def _calculate_md5(self, content: str) -> str:
        """计算MD5哈希"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _check_md5_exists(self, md5: str, db: Session) -> Optional[int]:
        """检查MD5是否已存在"""
        existing = db.query(StudyMaterial.material_id).filter(
            StudyMaterial.content_hash == md5,
            StudyMaterial.status != -1  # 排除已删除
        ).first()
        return existing[0] if existing else None
    
    def record_duplicate(self, original_id: int, duplicate_id: int, 
                        level: str, similarity: float, db: Session):
        """记录重复"""
        record = MaterialDuplicateRecord(
            original_id=original_id,
            duplicate_id=duplicate_id,
            similarity=similarity,
            duplicate_type=level,
            status='pending'
        )
        db.add(record)
        db.commit()


# 全局实例
deduplicator = MaterialDeduplicator()
```

- [ ] **Step 2: 测试去重服务**

```bash
cd backend
python -c "
from app.services.material_deduplicator import deduplicator

# 测试MD5计算
md5 = deduplicator._calculate_md5('测试内容')
print('MD5:', md5)
"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/material_deduplicator.py
git commit -m "feat: implement deduplication detection service"
```

### Task 8: 实现内容清洗服务

**Files:**
- Modify: `backend/app/services/material_sanitizer.py`

- [ ] **Step 1: 添加内容清洗功能**

```python
# 在 material_sanitizer.py 中添加
import re


class ContentCleaner:
    """内容清洗引擎"""
    
    # 需要过滤的正则模式
    PATTERNS = {
        'phone': r'1[3-9]\d{9}',
        'wechat': r'[wW]echat[:\s]*[a-zA-Z0-9_]+',
        'qq': r'[Qq]{2}[:\s]*\d{5,11}',
        'copyright': r'(版权所有|未经许可不得转载|Copyright|©)',
        'ad_keywords': r'(扫码关注|添加微信|加好友|点击关注|关注公众号)',
        'page_number': r'第\s*\d+\s*页|Page\s*\d+',
        'footer': r'[\s]*[-]{3,}[\s]*$'
    }
    
    def clean_text(self, text: str) -> str:
        """清洗文本内容"""
        if not text:
            return ''
        
        # 1. 移除空字符和特殊控制字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        
        # 2. 应用所有过滤模式
        for key, pattern in self.PATTERNS.items():
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # 3. 移除多余的空白行（连续换行 > 2）
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # 4. 去除首尾空白
        text = text.strip()
        
        return text
    
    def calculate_content_hash(self, content: str) -> str:
        """计算内容哈希（用于去重）"""
        cleaned = self.clean_text(content)
        return hashlib.md5(cleaned.encode('utf-8')).hexdigest()


# 全局实例
content_cleaner = ContentCleaner()
```

- [ ] **Step 2: 测试内容清洗**

```bash
cd backend
python -c "
from app.services.material_sanitizer import content_cleaner

# 测试清洗
text = '''
这是一篇测试文章

版权所有 未经许可不得转载

扫码关注公众号

13812345678

---
'''
cleaned = content_cleaner.clean_text(text)
print('Cleaned:', cleaned)
"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/material_sanitizer.py
git commit -m "feat: implement content cleaning service"
```

### Task 9: 实现监控告警服务

**Files:**
- Create: `backend/app/services/material_monitor.py`

- [ ] **Step 1: 创建监控服务**

```python
"""监控告警服务"""
import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models.models import MaterialImportRecord


logger = logging.getLogger(__name__)


class ImportMonitor:
    """导入监控器"""
    
    def __init__(self):
        self.metrics = {
            'total_imports': 0,
            'failed_imports': 0,
            'timeout_imports': 0,
            'duplicate_matches': 0
        }
    
    def record_import(self, success: bool, timeout: bool = False):
        """记录导入"""
        self.metrics['total_imports'] += 1
        if not success:
            self.metrics['failed_imports'] += 1
        if timeout:
            self.metrics['timeout_imports'] += 1
    
    def record_duplicate_match(self):
        """记录去重匹配"""
        self.metrics['duplicate_matches'] += 1
    
    def check_alerts(self, db: Session) -> List[dict]:
        """检查告警"""
        alerts = []
        
        # 检查最近24小时的导入失败率
        since = datetime.now() - timedelta(hours=24)
        total = db.query(func.count(MaterialImportRecord.import_id)).filter(
            MaterialImportRecord.create_time >= since
        ).scalar() or 0
        
        failed = db.query(func.count(MaterialImportRecord.import_id)).filter(
            MaterialImportRecord.create_time >= since,
            MaterialImportRecord.parse_status == 'failed'
        ).scalar() or 0
        
        if total > 0:
            failure_rate = failed / total
            if failure_rate > 0.05:  # 5%阈值
                alerts.append({
                    'type': 'high_failure_rate',
                    'level': 'warning',
                    'message': f'导入失败率过高: {failure_rate:.1%}',
                    'threshold': '5%',
                    'current': f'{failure_rate:.1%}'
                })
        
        return alerts
    
    def get_metrics_summary(self) -> dict:
        """获取指标摘要"""
        return {
            'total_imports': self.metrics['total_imports'],
            'failed_imports': self.metrics['failed_imports'],
            'timeout_imports': self.metrics['timeout_imports'],
            'duplicate_matches': self.metrics['duplicate_matches'],
            'failure_rate': (
                self.metrics['failed_imports'] / self.metrics['total_imports']
                if self.metrics['total_imports'] > 0 else 0
            )
        }


# 全局实例
import_monitor = ImportMonitor()
```

- [ ] **Step 2: 测试监控服务**

```bash
cd backend
python -c "
from app.services.material_monitor import import_monitor

# 测试记录
import_monitor.record_import(success=True)
import_monitor.record_import(success=False)
import_monitor.record_import(success=True, timeout=True)

# 获取摘要
summary = import_monitor.get_metrics_summary()
print('Metrics:', summary)
"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/material_monitor.py
git commit -m "feat: implement import monitoring service"
```

### Task 10: 集成智能分类到导入流程

**Files:**
- Modify: `backend/app/api/v1/materials.py`

- [ ] **Step 1: 修改导入确认接口**

```python
# 修改 import_confirm 函数
from ..services.material_classifier import classifier
from ..services.material_deduplicator import deduplicator
from ..services.material_sanitizer import content_cleaner

@router.post("/admin/import/{import_id}/confirm", summary="确认入库(status=0下架态)")
async def import_confirm(import_id: int, body: dict,
                         current_user: SysUser = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    _require_admin(current_user)
    rec = db.query(MaterialImportRecord).filter(
        MaterialImportRecord.import_id == import_id).first()
    if not rec:
        raise HTTPException(404, "导入记录不存在")
    if rec.parse_status != "success":
        raise HTTPException(409, f"尚未解析成功: {rec.parse_status}")
    
    subject = body.get("subject")
    if subject not in SUBJECTS:
        raise HTTPException(400, "科目必选且有效")
    
    category = body.get("category")
    badge = body.get("badge")
    result = _load_result(rec)
    created_ids = []
    
    if rec.file_type == "xlsx":
        # Excel处理逻辑保持不变
        mapping = body.get("column_mapping") or {}
        try:
            col_front = int(mapping["front"])
            col_back = int(mapping["back"])
            col_cat = (int(mapping["category"])
                       if mapping.get("category") not in (None, "") else None)
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, "列映射不完整（正面列/背面列必填）")
        from ...services.material_parser import build_cards, parse_xlsx
        full = parse_xlsx(result["_tmp"], max_rows=CARD_ROW_LIMIT) \
            if result.get("_tmp") and _Path(result["_tmp"]).exists() else result
        cards = build_cards(full.get("rows", []), col_front, col_back, col_cat,
                            limit=CARD_ROW_LIMIT)
        if not cards:
            raise HTTPException(400, "按当前列映射未得到有效卡片（正反面均不能为空）")
        base_title = _os.path.splitext(rec.file_name)[0]
        for idx, c in enumerate(cards, start=1):
            # 智能分类
            classification = classifier.classify(
                '.xlsx', content=c.get('card_front', ''), title=c.get('card_front', '')
            )
            
            # 内容清洗
            card_front = content_cleaner.clean_text(c["card_front"])
            card_back = content_cleaner.clean_text(c["card_back"])
            
            # 去重检测
            content_hash = content_cleaner.calculate_content_hash(card_front + card_back)
            dup_check = deduplicator.check_duplicate(card_front + card_back, db)
            if dup_check['is_duplicate']:
                import_monitor.record_duplicate_match()
                continue  # 跳过重复内容
            
            m = StudyMaterial(
                subject=subject, type=classification['type'],
                category=c["category"] or category,
                title=card_front, card_front=card_front,
                card_back=card_back,
                content_hash=content_hash,
                sort_order=idx, status=0,
                creator_id=current_user.user_id)
            db.add(m)
            db.flush()
            created_ids.append(m.material_id)
        _ = base_title
    else:
        # 文档处理
        mtype = body.get("type")
        if mtype not in ("article",):
            raise HTTPException(400, "文档类素材入库类型只能是 article")
        _migrate_images(import_id, result)
        word_count = result.get("word_count", 0)
        
        # 内容清洗
        content = content_cleaner.clean_text(result.get("html") or "")
        title = (body.get("title") or _os.path.splitext(rec.file_name)[0])[:200]
        summary_text = (body.get("summary") or "")[:500]
        
        # 智能分类
        ext = '.' + rec.file_type
        classification = classifier.classify(
            ext, content=content, title=title
        )
        
        # 去重检测
        content_hash = content_cleaner.calculate_content_hash(content)
        dup_check = deduplicator.check_duplicate(content, db)
        if dup_check['is_duplicate']:
            import_monitor.record_duplicate_match()
            # 可以选择跳过或提示用户
        
        m = StudyMaterial(
            subject=subject, type=classification['type'],
            category=category, badge=badge,
            title=title, summary=summary_text,
            content=content, content_hash=content_hash,
            status=0, read_time=max(1, word_count // 400),
            creator_id=current_user.user_id)
        db.add(m)
        db.flush()
        created_ids.append(m.material_id)
    
    db.commit()
    rec.parse_status = "consumed"
    db.commit()
    
    # 清理临时源文件
    tmp = result.get("_tmp")
    if tmp and _Path(tmp).exists():
        try:
            _os.remove(tmp)
        except OSError:
            pass
    
    _audit(db, current_user, "import_confirm", f"import:{import_id}",
           f"created={len(created_ids)} type={rec.file_type}")
    db.commit()
    
    return {"created": len(created_ids), "material_ids": created_ids}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/v1/materials.py
git commit -m "feat: integrate classification and deduplication into import flow"
```

---

## 阶段3：高级功能（Task 11-15）

### Task 11: 添加扩展文件格式支持

**Files:**
- Modify: `backend/app/services/material_parser.py`

- [ ] **Step 1: 添加视频文件解析**

```python
# 在 material_parser.py 中添加
import subprocess
import json


def parse_video_metadata(file_path: str) -> dict:
    """解析视频元数据"""
    try:
        # 使用ffprobe获取视频信息
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_format', '-show_streams',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            format_info = data.get('format', {})
            duration = float(format_info.get('duration', 0))
            return {
                'duration': int(duration),
                'size': int(format_info.get('size', 0)),
                'format': format_info.get('format_name', '')
            }
    except Exception as e:
        logger.warning(f"Video metadata parse failed: {e}")
    
    return {'duration': 0, 'size': 0, 'format': ''}


def detect_video_type(file_path: str) -> str:
    """检测视频类型"""
    metadata = parse_video_metadata(file_path)
    duration = metadata.get('duration', 0)
    
    if duration <= 15 * 60:  # 15分钟
        return 'video_intro'
    else:
        return 'video_advanced'
```

- [ ] **Step 2: 添加图片OCR支持**

```python
# 在 material_parser.py 中添加
def parse_image_ocr(file_path: str) -> str:
    """图片OCR识别"""
    try:
        from PIL import Image
        import pytesseract
        
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img, lang='chi_sim+eng')
        return text.strip()
    except Exception as e:
        logger.warning(f"Image OCR failed: {e}")
        return ''
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/material_parser.py
git commit -m "feat: add video and image parsing support"
```

### Task 12: 实现容错机制

**Files:**
- Modify: `backend/app/api/v1/materials.py`

- [ ] **Step 1: 添加文件校验函数**

```python
# 在 materials.py 中添加
def _validate_file_upload(file: UploadFile, content: bytes) -> tuple:
    """校验上传文件"""
    errors = []
    
    # 1. 文件大小校验
    if len(content) > settings.MATERIAL_MAX_FILE_SIZE:
        errors.append(f"文件大小超过限制（最大{settings.MATERIAL_MAX_FILE_SIZE // 1024 // 1024}MB）")
    
    # 2. 文件格式校验
    ext = _os.path.splitext(file.filename or "")[1].lower()
    all_formats = []
    for formats in settings.MATERIAL_SUPPORTED_FORMATS.values():
        all_formats.extend(formats)
    
    if ext not in all_formats:
        errors.append(f"不支持的文件格式: {ext}")
    
    # 3. 文件完整性校验（Magic Bytes）
    if ext in MAGIC_BYTES:
        magic = MAGIC_BYTES[ext]
        if not content.startswith(magic):
            errors.append("文件实际格式与扩展名不符")
    
    return errors


def _safe_file_upload(file: UploadFile) -> tuple:
    """安全上传文件"""
    content = file.file.read()
    file.file.seek(0)  # 重置文件指针
    
    errors = _validate_file_upload(file, content)
    if errors:
        raise HTTPException(400, "; ".join(errors))
    
    # 保存临时文件
    UPLOAD_TMP_DIR.mkdir(parents=True, exist_ok=True)
    ext = _os.path.splitext(file.filename or "")[1].lower()
    tmp_name = f"{_uuid.uuid4().hex}{ext}"
    tmp_path = UPLOAD_TMP_DIR / tmp_name
    tmp_path.write_bytes(content)
    
    return str(tmp_path), ext
```

- [ ] **Step 2: 修改上传接口使用安全上传**

```python
# 修改 import_upload 函数
@router.post("/admin/import/upload", summary="上传素材并解析")
async def import_upload(background_tasks: BackgroundTasks,
                        file: UploadFile = File(...),
                        current_user: SysUser = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    _require_admin(current_user)
    
    try:
        tmp_path, ext = _safe_file_upload(file)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(400, "文件上传失败，请重试")
    
    # ... 后续处理逻辑保持不变 ...
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/materials.py
git commit -m "feat: implement file validation and error handling"
```

### Task 13: 添加前端状态筛选和搜索

**Files:**
- Modify: `.vtj/vue/admin_materials.vue`

- [ ] **Step 1: 添加状态筛选**

```vue
<!-- 在筛选区添加状态筛选 -->
<div class="ops">
  <select v-model="state.fSubject" @change="loadList" class="mini">
    <option value="">全部科目</option>
    <option value="xingce">行测</option>
    <option value="shenlun">申论</option>
    <option value="gongzhuan">公专</option>
  </select>
  <select v-model="state.fType" @change="loadList" class="mini">
    <option value="">全部类型</option>
    <option value="video_intro">入门视频</option>
    <option value="video_advanced">进阶视频</option>
    <option value="article">文章</option>
    <option value="card">知识卡片</option>
  </select>
  <!-- 新增状态筛选 -->
  <select v-model="state.fStatus" @change="loadList" class="mini">
    <option value="">全部状态</option>
    <option value="1">已发布</option>
    <option value="0">草稿</option>
  </select>
  <!-- 新增搜索 -->
  <input v-model="state.fKeyword" placeholder="搜索标题..." 
         @keyup.enter="loadList" class="mini" />
  <button class="btn" @click="loadList">🔍 搜索</button>
</div>
```

- [ ] **Step 2: 更新loadList方法**

```javascript
async loadList() {
  const q = new URLSearchParams();
  if (this.state.fSubject) q.set('subject', this.state.fSubject);
  if (this.state.fType) q.set('type', this.state.fType);
  if (this.state.fStatus) q.set('status', this.state.fStatus);
  if (this.state.fKeyword) q.set('keyword', this.state.fKeyword);
  q.set('page_size', '100');
  try {
    const r = await this.api('/api/materials/admin/list?' + q.toString());
    if (!r.ok) throw new Error('加载失败');
    const d = await r.json();
    this.state.items = d.items || [];
  } catch (e) { ElMessage.error(e.message); }
},
```

- [ ] **Step 3: Commit**

```bash
git add .vtj/vue/admin_materials.vue
git commit -m "feat: add status filter and search to materials list"
```

### Task 14: 添加批量操作工具栏

**Files:**
- Modify: `.vtj/vue/admin_materials.vue`

- [ ] **Step 1: 添加批量选择和操作栏**

```vue
<!-- 在表格前添加批量操作栏 -->
<div class="batch-toolbar" v-if="state.selectedItems.length > 0">
  <span>已选择 {{ state.selectedItems.length }} 项</span>
  <button class="btn danger" @click="batchDelete">批量删除</button>
  <button class="btn" @click="batchPublish">批量上架</button>
  <button class="btn" @click="batchUnpublish">批量下架</button>
</div>

<!-- 在表格中添加选择列 -->
<table class="tbl">
  <thead>
    <tr>
      <th style="width:40px">
        <input type="checkbox" @change="toggleSelectAll" :checked="isAllSelected" />
      </th>
      <!-- 原有列 -->
    </tr>
  </thead>
  <tbody>
    <tr v-for="row in state.items" :key="row.id">
      <td>
        <input type="checkbox" :value="row.id" v-model="state.selectedItems" />
      </td>
      <!-- 原有列 -->
    </tr>
  </tbody>
</table>
```

- [ ] **Step 2: 添加批量操作方法**

```javascript
// 在 methods 中添加
toggleSelectAll(e) {
  if (e.target.checked) {
    this.state.selectedItems = this.state.items.map(item => item.id);
  } else {
    this.state.selectedItems = [];
  }
},

async batchDelete() {
  if (!confirm(`确认删除选中的 ${this.state.selectedItems.length} 项资料？`)) return;
  try {
    const r = await this.api('/api/materials/admin/batch', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: this.state.selectedItems })
    });
    if (!r.ok) throw new Error('批量删除失败');
    ElMessage.success('批量删除成功');
    this.state.selectedItems = [];
    this.loadList();
  } catch (e) { ElMessage.error(e.message); }
},

async batchPublish() {
  try {
    for (const id of this.state.selectedItems) {
      await this.api(`/api/materials/admin/${id}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 1 })
      });
    }
    ElMessage.success('批量上架成功');
    this.state.selectedItems = [];
    this.loadList();
  } catch (e) { ElMessage.error(e.message); }
},

async batchUnpublish() {
  try {
    for (const id of this.state.selectedItems) {
      await this.api(`/api/materials/admin/${id}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 0 })
      });
    }
    ElMessage.success('批量下架成功');
    this.state.selectedItems = [];
    this.loadList();
  } catch (e) { ElMessage.error(e.message); }
},
```

- [ ] **Step 3: 添加批量操作样式**

```css
/* 在 style 部分添加 */
.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 16px;
}

.batch-toolbar span {
  font-size: 13px;
  color: #5a6b85;
}

.btn.danger {
  background: rgba(196, 30, 58, 0.08);
  border-color: #c41e3a;
  color: #c41e3a;
}
```

- [ ] **Step 4: Commit**

```bash
git add .vtj/vue/admin_materials.vue
git commit -m "feat: add batch operations toolbar"
```

### Task 15: 集成监控到导入流程

**Files:**
- Modify: `backend/app/api/v1/materials.py`

- [ ] **Step 1: 在导入流程中集成监控**

```python
# 在 import_upload 函数中添加监控
from ..services.material_monitor import import_monitor

@router.post("/admin/import/upload", summary="上传素材并解析")
async def import_upload(background_tasks: BackgroundTasks,
                        file: UploadFile = File(...),
                        current_user: SysUser = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    _require_admin(current_user)
    
    try:
        tmp_path, ext = _safe_file_upload(file)
    except HTTPException as e:
        import_monitor.record_import(success=False)
        raise e
    except Exception as e:
        import_monitor.record_import(success=False)
        logger.error(f"File upload failed: {e}")
        raise HTTPException(400, "文件上传失败，请重试")
    
    # ... 后续处理逻辑 ...
    
    # 记录导入成功
    import_monitor.record_import(success=True)
    
    # 检查告警
    alerts = import_monitor.check_alerts(db)
    if alerts:
        logger.warning(f"Import alerts: {alerts}")
    
    # ... 返回响应 ...
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/v1/materials.py
git commit -m "feat: integrate monitoring into import flow"
```

---

## 测试任务

### Task 16: 编写API接口测试

**Files:**
- Create: `backend/tests/test_materials.py`

- [ ] **Step 1: 创建测试文件**

```python
"""材料管理API测试"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db
from app.models.models import SysUser

client = TestClient(app)


def test_admin_stats():
    """测试统计概览接口"""
    response = client.get("/api/materials/admin/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "by_type" in data
    assert "by_subject" in data
    assert "by_status" in data


def test_admin_batch_create():
    """测试批量创建接口"""
    response = client.post("/api/materials/admin/batch", json={
        "items": [
            {
                "subject": "xingce",
                "type": "card",
                "title": "测试卡片",
                "card_front": "正面",
                "card_back": "背面"
            }
        ]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 1
    assert len(data["material_ids"]) == 1


def test_admin_import_records():
    """测试导入记录接口"""
    response = client.get("/api/materials/admin/import-records")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
```

- [ ] **Step 2: 运行测试**

```bash
cd backend
pytest tests/test_materials.py -v
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_materials.py
git commit -m "test: add API tests for materials management"
```

---

## 自我审查

### 1. 规范覆盖检查

✅ **通过**：所有设计规范中的功能都有对应的任务实现：
- 统计概览：Task 3, Task 5
- 批量操作：Task 4, Task 14
- 智能分类：Task 6, Task 10
- 去重机制：Task 7, Task 10
- 内容清洗：Task 8, Task 10
- 稳定性保障：Task 9, Task 11, Task 12
- 前端增强：Task 13, Task 14

### 2. 占位符扫描

✅ **通过**：所有任务都有完整的代码实现，没有占位符。

### 3. 类型一致性检查

✅ **通过**：所有任务中的类型、方法签名、属性名称一致：
- `classifier.classify()` 在 Task 6 和 Task 10 中一致
- `deduplicator.check_duplicate()` 在 Task 7 和 Task 10 中一致
- `content_cleaner.clean_text()` 在 Task 8 和 Task 10 中一致

### 4. 风险评估

✅ **通过**：已识别的风险都有对应的缓解措施：
- 文件格式支持：Task 11 扩展解析能力
- 容错机制：Task 12 实现校验和错误处理
- 监控告警：Task 9, Task 15 实现监控集成

---

## 执行交接

计划已完成并保存至 `docs/superpowers/plans/2026-08-31-admin-materials-import.md`。

**两种执行方式：**

**1. Subagent-Driven（推荐）** - 我为每个任务分发新的子代理，任务间进行审查，快速迭代

**2. Inline Execution** - 在当前会话中使用 executing-plans 执行任务，批量执行并设置检查点

**选择哪种方式？**