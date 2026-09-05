# 管理员端备考资料导入功能设计文档

## 文档信息

- **文档版本**：v1.0
- **编写日期**：2026年8月31日
- **主要内容**：功能模块设计、分类机制、内容识别引擎、数据过滤、去重机制、稳定性保障
- **适用对象**：前后端开发人员、系统架构师

## 1. 项目概述

### 1.1 项目背景

在原有"备考资料"设计方案的基础上，补充管理员端"备考资料导入"功能模块的完整设计。该功能模块旨在为管理员提供高效、智能的备考资料导入和管理能力。

### 1.2 项目目标

1. 实现完整的资料导入功能，支持多种文件格式
2. 实现智能分类机制，自动识别资料类型
3. 实现去重机制，避免资料冗余
4. 实现稳定性保障，确保系统可靠运行

### 1.3 实施策略

采用渐进式实现策略，分三个阶段实施：
- 阶段1：基础功能（1-2天）
- 阶段2：核心功能（2-3天）
- 阶段3：高级功能（2-3天）

## 2. 系统架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    管理员端前端                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ 资料列表页   │  │ 导入向导弹窗│  │ 编辑弹窗    │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    API网关层                             │
│  /api/materials/admin/*                                 │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    业务逻辑层                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ 资料管理    │  │ 导入处理    │  │ 智能分类    │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ 去重检测    │  │ 内容清洗    │  │ 稳定性保障  │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    数据存储层                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ 资料表      │  │ 导入记录表  │  │ 分类规则表  │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### 2.2 数据流设计

**导入流程**：
1. 用户选择文件 → 前端校验格式和大小
2. 上传文件 → 后端接收并存储临时文件
3. 解析内容 → 根据文件类型调用相应解析器
4. 智能分类 → 根据规则自动分类
5. 去重检测 → 检查是否重复
6. 数据清洗 → 过滤无关内容
7. 入库存储 → 保存到数据库

## 3. 数据模型设计

### 3.1 资料表 (study_materials)

```sql
CREATE TABLE study_materials (
    material_id INT PRIMARY KEY AUTO_INCREMENT,
    subject VARCHAR(20) NOT NULL,          -- xingce/shenlun/gongzhuan
    type VARCHAR(30) NOT NULL,             -- video_intro/video_advanced/article/card/image/table
    category VARCHAR(100),                 -- 分类标签
    title VARCHAR(200) NOT NULL,           -- 资料标题
    summary TEXT,                          -- 摘要
    content LONGTEXT,                      -- 正文内容
    card_front VARCHAR(500),               -- 卡片正面
    card_back TEXT,                        -- 卡片背面
    cover_image VARCHAR(500),              -- 封面图URL
    video_id INT,                          -- 视频ID
    duration INT,                          -- 视频时长(秒)
    read_time INT,                         -- 阅读时间(分钟)
    difficulty INT DEFAULT 1,              -- 难度 1/2/3
    badge VARCHAR(50),                     -- 徽章
    sort_order INT DEFAULT 0,              -- 排序
    status TINYINT DEFAULT 0,             -- 0下架 1上架
    view_count INT DEFAULT 0,             -- 浏览次数
    study_count INT DEFAULT 0,            -- 学习次数
    content_hash VARCHAR(64),              -- 内容MD5哈希(去重用)
    creator_id INT,                        -- 创建者ID
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### 3.2 导入记录表 (material_import_records)

```sql
CREATE TABLE material_import_records (
    import_id INT PRIMARY KEY AUTO_INCREMENT,
    file_name VARCHAR(500) NOT NULL,       -- 文件名
    file_type VARCHAR(50),                 -- 文件类型
    file_size BIGINT,                      -- 文件大小
    parse_status VARCHAR(20) DEFAULT 'pending', -- pending/processing/success/failed/consumed
    parse_mode VARCHAR(20),                -- sync/async(mineru)
    parse_result JSON,                     -- 解析结果
    error_message TEXT,                    -- 错误信息
    uploader_id INT,                       -- 上传者ID
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 3.3 分类规则表 (material_classification_rules)

```sql
CREATE TABLE material_classification_rules (
    rule_id INT PRIMARY KEY AUTO_INCREMENT,
    rule_name VARCHAR(100) NOT NULL,       -- 规则名称
    rule_type VARCHAR(50) NOT NULL,        -- format/content/keyword
    rule_config JSON,                      -- 规则配置
    priority INT DEFAULT 0,               -- 优先级
    enabled TINYINT DEFAULT 1,           -- 是否启用
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 3.4 去重记录表 (material_duplicate_records)

```sql
CREATE TABLE material_duplicate_records (
    duplicate_id INT PRIMARY KEY AUTO_INCREMENT,
    original_id INT,                       -- 原始资料ID
    duplicate_id INT,                      -- 重复资料ID
    similarity DECIMAL(5,4),              -- 相似度
    duplicate_type VARCHAR(20),           -- exact/fingerprint/semantic
    status VARCHAR(20) DEFAULT 'pending', -- pending/confirmed/ignored
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 4. API接口设计

### 4.1 管理端接口

| 接口 | 方法 | 路径 | 描述 |
|------|------|------|------|
| 管理列表 | GET | `/api/materials/admin/list` | 获取资料列表（含下架） |
| 创建资料 | POST | `/api/materials/admin` | 创建资料记录 |
| 更新资料 | PUT | `/api/materials/admin/{id}` | 编辑资料 |
| 删除资料 | DELETE | `/api/materials/admin/{id}` | 删除资料 |
| 上架/下架 | PUT | `/api/materials/admin/{id}/status` | 切换资料状态 |
| 上传图片 | POST | `/api/materials/admin/upload/image` | 上传封面/插图 |
| 导入上传 | POST | `/api/materials/admin/import/upload` | 上传文件并解析 |
| 导入状态 | GET | `/api/materials/admin/import/{id}/status` | 查询导入进度 |
| 导入预览 | GET | `/api/materials/admin/import/{id}/preview` | 获取解析预览 |
| 确认入库 | POST | `/api/materials/admin/import/{id}/confirm` | 确认导入入库 |
| 批量创建 | POST | `/api/materials/admin/batch` | 批量创建资料 |
| 批量删除 | DELETE | `/api/materials/admin/batch` | 批量删除资料 |
| 导入记录 | GET | `/api/materials/admin/import-records` | 获取导入历史 |
| 统计概览 | GET | `/api/materials/admin/stats` | 获取统计信息 |

### 4.2 接口详细设计

**管理列表接口**：
```json
GET /api/materials/admin/list?subject=xingce&type=video_intro&status=1&page=1&page_size=20

Response:
{
  "total": 156,
  "items": [
    {
      "id": 1,
      "subject": "xingce",
      "type": "video_intro",
      "title": "行测导学",
      "category": "入门讲解",
      "status": 1,
      "view_count": 123,
      "study_count": 45,
      "created_at": "2026-08-01T10:00:00"
    }
  ]
}
```

**统计概览接口**：
```json
GET /api/materials/admin/stats

Response:
{
  "total": 156,
  "by_type": {
    "video_intro": 32,
    "video_advanced": 18,
    "article": 68,
    "card": 38
  },
  "by_subject": {
    "xingce": 65,
    "shenlun": 48,
    "gongzhuan": 43
  },
  "by_status": {
    "published": 120,
    "draft": 36
  }
}
```

**批量创建接口**：
```json
POST /api/materials/admin/batch
{
  "items": [
    {
      "subject": "xingce",
      "type": "card",
      "title": "行测高频考点",
      "card_front": "南辕北辙",
      "card_back": "比喻行动和目的相反"
    }
  ]
}

Response:
{
  "created": 1,
  "material_ids": [157]
}
```

## 5. 前端设计

### 5.1 页面结构

**修改现有页面**：`admin_materials.vue`

**新增功能模块**：
- 统计概览组件
- 增强筛选和搜索
- 批量操作工具栏
- 改进的导入向导

### 5.2 统计概览组件

```
┌─────────────────────────────────────────────────────────┐
│  📊 统计概览                                            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │
│  │ 总资料数 │ │ 视频    │ │ 文档    │ │ 卡片    │     │
│  │ 156     │ │ 50     │ │ 68     │ │ 38     │     │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘     │
└─────────────────────────────────────────────────────────┘
```

### 5.3 增强筛选和搜索

**新增筛选条件**：
- 状态筛选（全部/已发布/草稿）
- 时间范围筛选
- 关键词搜索

### 5.4 批量操作工具栏

**功能**：
- 批量选择
- 批量删除
- 批量上架/下架

### 5.5 改进的导入向导

**支持格式**：
- 视频：MP4, MOV, AVI, WEBM
- 图片：JPG, PNG, GIF, WebP, SVG
- 文档：PDF, DOCX, TXT
- 表格：XLSX, CSV
- 压缩包：ZIP, RAR

**三步流程**：
1. 选择文件（拖拽上传）
2. 设置属性（标题、科目、类型等）
3. 确认导入

## 6. 智能分类和去重机制设计

### 6.1 智能分类机制

**分类决策树**：

```
导入资料
    │
    ▼
文件格式判断
    │
    ├── 视频文件 → 视频分类
    │   ├── 时长 ≤ 15分钟 → 入门讲解视频
    │   └── 时长 > 15分钟 → 深度拓展视频
    │
    ├── 图片文件 → 内容识别
    │   ├── 单一知识点 → 知识卡片
    │   └── 非知识点 → 图片资料
    │
    ├── 文档文件 → 内容结构分析
    │   ├── 短文本 < 500字 → 知识卡片
    │   └── 长文本 ≥ 500字 → 文章/文档
    │
    └── 表格文件 → 表格资料
        ├── 含卡片结构字段 → 转换为知识卡片
        └── 统计数据 → 数据资料
```

**置信度机制**：

| 置信度等级 | 阈值 | 处理方式 |
|-----------|------|---------|
| 高置信度 | ≥90% | 自动分类，无需人工干预 |
| 中置信度 | 70%-89% | 自动分类但标记"建议确认" |
| 低置信度 | <70% | 不自动分类，进入人工分类界面 |

**置信度计算公式**：
```
综合置信度 = 格式匹配度 × 40% + 内容特征匹配度 × 35% + 标题关键词匹配度 × 25%
```

### 6.2 去重机制

**三层去重策略**：

```
导入资料
    │
    ▼
第一层：精确去重（MD5哈希）
    │
    ├── 存在 → 标记为"重复-精确匹配" → 跳过导入
    │
    └── 不存在 → 第二层：指纹去重（SimHash）
                    │
                    ├── 相似度 > 95% → 标记为"重复-高度相似" → 进入审核队列
                    │
                    └── 相似度 ≤ 95% → 第三层：语义去重（Sentence-BERT）
                                        │
                                        ├── 相似度 > 95% → 标记为"重复-语义相似" → 进入审核队列
                                        │
                                        └── 相似度 ≤ 95% → 确定为新资料 → 入库存储
```

**去重算法实现**：

```python
class DuplicateDetector:
    def __init__(self):
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    def check_duplicate(self, content: str) -> dict:
        # 第一层：精确去重
        md5 = hashlib.md5(content.encode('utf-8')).hexdigest()
        if self.check_md5_exists(md5):
            return {'is_duplicate': True, 'level': 'exact'}
        
        # 第二层：指纹去重
        fingerprint = Simhash(content.split()).value
        if self.check_fingerprint_similar(fingerprint):
            return {'is_duplicate': True, 'level': 'fingerprint'}
        
        # 第三层：语义去重
        if len(content) > 50:
            similarity = self.calculate_semantic_similarity(content)
            if similarity > 0.95:
                return {'is_duplicate': True, 'level': 'semantic'}
        
        return {'is_duplicate': False}
```

### 6.3 内容清洗机制

**需要过滤的内容**：

| 过滤类型 | 识别规则 | 处理方式 |
|---------|---------|---------|
| 无关字段 | 页眉、页脚、页码、水印 | 正则匹配删除 |
| 乱码字符 | 非UTF-8字符、特殊控制字符 | 字符集校验与清理 |
| 公众号二维码 | 二维码特征识别 + URL匹配 | 图片识别后移除 |
| 广告内容 | 包含"扫码关注"、"添加微信"等关键词 | 正则匹配删除 |
| 空内容 | 内容长度为0或仅含空白字符 | 直接丢弃 |
| 版权声明 | "版权所有"、"未经许可不得转载"等 | 正则匹配删除 |
| 联系方式 | 手机号、微信号、QQ号模式 | 正则匹配脱敏或删除 |

## 7. 稳定性保障设计

### 7.1 全流程容错设计

**前端层容错**：
- 文件格式校验：上传前检查文件扩展名和MIME类型
- 文件大小限制：单个文件≤500MB，总大小≤2GB
- 网络异常处理：自动重试3次，失败后提示用户
- 上传进度显示：实时显示上传进度和状态

**后端层容错**：
- 文件完整性校验：MD5校验确保文件完整
- 异步处理队列：大文件异步处理，避免阻塞
- 超时处理：设置合理的超时时间，超时后自动重试
- 资源限制：限制并发上传数量，防止系统过载

**数据层容错**：
- 事务保证：数据库操作使用事务，失败时回滚
- 数据校验：入库前校验必填字段和数据格式
- 索引更新：异步更新搜索索引，失败后重试

### 7.2 导入失败处理机制

| 失败类型 | 识别方式 | 处理策略 | 用户感知 |
|---------|---------|---------|---------|
| 格式不支持 | 文件扩展名校验失败 | 提示支持格式列表，拒绝上传 | 明确提示"格式不支持" |
| 文件损坏 | 打开文件异常 | 记录错误，返回友好提示 | "文件可能已损坏" |
| 解析超时 | 处理时间 > 60秒 | 切换异步处理模式 | 提示"正在后台处理" |
| 内存溢出 | 文件 > 200MB | 限制文件大小，强制分片 | "文件过大，请拆分" |
| 网络中断 | 上传进度停滞 | 自动重试3次 | "网络异常，已重试" |
| 内容为空 | 解析后内容长度为0 | 标记"无效内容" | "未提取到有效内容" |
| 数据库写入失败 | 事务回滚 | 重试3次，记录待处理队列 | "系统繁忙，稍后重试" |

### 7.3 监控与告警机制

**监控项**：

| 监控项 | 告警阈值 | 告警方式 | 处理建议 |
|--------|---------|---------|---------|
| 导入失败率 | > 5% | 站内消息 + 邮件 | 检查文件格式和系统状态 |
| 解析超时率 | > 10% | 站内消息 | 优化解析引擎或增加超时时间 |
| 存储空间 | < 10%剩余 | 站内消息 | 清理临时文件或扩容 |
| 导入队列积压 | > 100个 | 站内消息 | 增加Worker处理能力 |
| 去重匹配率 | > 20% | 站内消息 | 检查是否为重复导入 |

### 7.4 降级与恢复策略

| 场景 | 降级策略 | 恢复策略 |
|------|---------|---------|
| MinerU服务不可用 | 切换至备用解析引擎（PyMuPDF + Tesseract） | 服务恢复后自动切换 |
| 数据库连接异常 | 使用本地缓存，延迟写入 | 连接恢复后自动重放 |
| 存储服务异常 | 暂时使用本地临时目录 | 服务恢复后自动同步 |
| 去重服务超时 | 跳过去重，标记"待去重" | 后台异步执行去重 |

### 7.5 数据完整性校验

**导入前校验**：

| 校验项 | 校验规则 | 校验失败处理 |
|--------|---------|-------------|
| 文件格式 | 在支持格式白名单中 | 拒绝上传，提示支持格式 |
| 文件大小 | ≤ 500MB | 拒绝上传，提示大小限制 |
| 文件完整性 | MD5校验 | 拒绝上传，提示文件可能损坏 |
| 内容有效性 | 提取内容长度 > 10字符 | 标记"无效内容"，进入人工审核 |
| 敏感词检测 | 命中敏感词库 | 标记"待审核"，进入人工审核 |

**导入后校验**：

| 校验项 | 校验规则 | 校验失败处理 |
|--------|---------|-------------|
| 必填字段 | 标题/类型/科目 非空 | 自动补充默认值，标记"待完善" |
| 数据库存储 | 确认记录已成功写入 | 失败则回滚事务，重试 |
| 索引更新 | 确认搜索索引已更新 | 异步重试 |
| 图片/附件存储 | 确认文件已成功存储 | 失败则重试，仍失败则记录待处理 |

## 8. 实施计划

### 8.1 阶段1：基础功能（1-2天）

**任务清单**：
1. 统一接口路径为 `/api/materials/admin/...`
2. 扩展文件格式支持（视频、图片、压缩包等）
3. 修改前端页面添加统计概览组件
4. 添加状态筛选和搜索功能
5. 实现批量操作工具栏

**验证标准**：
- 所有现有接口正常工作
- 前端页面显示统计概览
- 筛选和搜索功能正常
- 批量操作功能正常

### 8.2 阶段2：核心功能（2-3天）

**任务清单**：
1. 实现智能分类机制
2. 实现去重机制（MD5、SimHash、语义去重）
3. 实现内容清洗机制
4. 实现批量创建和删除接口
5. 实现导入记录查询接口

**验证标准**：
- 智能分类准确率 > 80%
- 去重机制有效检测重复内容
- 内容清洗过滤无关内容
- 批量操作接口正常工作

### 8.3 阶段3：高级功能（2-3天）

**任务清单**：
1. 实现全流程容错设计
2. 实现监控与告警机制
3. 实现降级与恢复策略
4. 实现数据完整性校验
5. 优化系统性能

**验证标准**：
- 系统容错能力正常
- 监控告警机制正常
- 降级恢复策略正常
- 数据完整性校验正常

### 8.4 技术栈确认

**前端**：
- Vue 3 + TypeScript
- Element Plus UI组件库
- VTJ框架

**后端**：
- Python FastAPI
- SQLAlchemy ORM
- MySQL数据库

**第三方库**：
- MinerU：文档解析
- PyMuPDF：PDF处理
- python-docx：Word文档解析
- openpyxl：Excel表格解析
- Pillow：图片处理
- Tesseract OCR：图片文字识别
- Simhash：指纹去重
- Sentence-BERT：语义去重

## 9. 风险评估

### 9.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| MinerU服务不稳定 | 解析失败率高 | 实现降级策略，使用备用解析引擎 |
| 数据库性能瓶颈 | 系统响应慢 | 优化查询，添加索引，使用缓存 |
| 内存溢出 | 系统崩溃 | 限制文件大小，分片处理 |
| 网络中断 | 上传失败 | 实现断点续传，自动重试 |

### 9.2 业务风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 智能分类准确率低 | 需要人工干预 | 优化分类规则，提供人工分类界面 |
| 去重机制误判 | 丢失有效内容 | 提供审核界面，支持人工确认 |
| 用户操作失误 | 数据丢失 | 实现软删除，支持数据恢复 |

## 10. 总结

本设计方案涵盖了管理员端备考资料导入功能的完整设计，包括：

1. **系统架构**：清晰的分层架构，便于维护和扩展
2. **数据模型**：完整的数据表设计，支持所有业务需求
3. **API接口**：统一的接口设计，与现有系统保持一致
4. **前端设计**：用户体验友好的界面设计
5. **智能分类**：基于规则和机器学习的分类机制
6. **去重机制**：三层去重策略，确保数据唯一性
7. **稳定性保障**：完善的容错和监控机制
8. **实施计划**：分阶段实施，降低风险

通过以上设计，备考资料导入功能将具备：
- **精准分类**：资料自动归入正确的类型
- **内容纯净**：自动过滤无关内容
- **无重复入库**：智能去重，避免资料冗余
- **稳定可靠**：完善的容错机制，确保导入不丢失、不失败