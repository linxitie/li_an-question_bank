# 每日金句大完善 - 正式规格说明

> 版本: v1.0 | 分支: obsidian-quote-favorite | 日期: 2026-08-16

---

## 1. 功能名称

Obsidian 每日金句收藏功能完善

## 2. 问题陈述

### 2.1 核心问题

Obsidian 知识库的每日金句（`/api/quotes/quote/daily`）返回 `quote_id: 0`（哨兵值），导致前端 `toggleQuoteFavorite()` 方法在第 203 行静默退出：

```javascript
if (!this.state.quoteId) return;  // quoteId=0 时直接返回，无任何提示
```

用户点击收藏按钮毫无反应，无法收藏 Obsidian 金句。

### 2.2 数据流问题

- Obsidian 金句从文件系统实时读取，不存入数据库
- `QuoteFavorite` 表的 `quote_id` 是 NOT NULL 外键，引用 `essay_quote.quote_id`
- 后端 `toggle_quote_favorite` 按 `quote_id` 查 `EssayQuote`，0 查不到 → 404

### 2.3 收藏页数据不一致

`/api/collection/news-favorites` 接口只查询 `QuoteFavorite JOIN EssayQuote`，只返回数据库金句，Obsidian 金句即使能收藏也不会出现在收藏页。

---

## 3. 解决方案

### 3.1 设计原则

| 原则 | 说明 |
|------|------|
| 稳定性优先 | Obsidian 金句 ID 必须稳定，不随内容变化 |
| 数据一致性 | 收藏页必须能显示所有已收藏的金句（数据库 + Obsidian） |
| 最小侵入 | 只修改必要文件，不创建新 Vue 文件 |
| VTJ 合规 | 严格遵守 VTJ 设计规则，只修改 script 部分 |
| 向后兼容 | 不影响现有数据库金句的收藏功能 |

### 3.2 核心方案

**基于文件名的稳定 ID + 收藏表扩展**

1. Obsidian 金句使用**文件名**作为稳定 ID（文件名不变，ID 就不变）
2. 扩展 `QuoteFavorite` 表，增加 `obsidian_source` 字段标识来源
3. 修改后端收藏接口，支持 Obsidian 金句收藏
4. 修改收藏页接口，合并返回数据库金句和 Obsidian 金句收藏

### 3.3 ID 稳定性分析

| ID 生成方式 | 稳定性 | 问题 |
|-------------|--------|------|
| 内容哈希 (MD5/SHA) | ❌ 不稳定 | 内容变化 → ID 变化 → 收藏丢失 |
| 文件名 | ✅ 稳定 | 文件名不变，ID 就不变 |
| 文件路径 | ✅ 稳定 | 但路径过长，不美观 |
| 随机 UUID | ✅ 稳定 | 但无法从文件反查 |

**推荐**：使用**文件名**作为 Obsidian 金句的稳定 ID。

文件名格式：`2026-08-14-金句-050.md` → ID = `obsidian_2026-08-14-金句-050`

---

## 4. 文件变更清单

### 4.1 后端文件

#### `backend/app/models/models.py`

**变更位置**: 第 1473-1487 行（QuoteFavorite 类）

**变更内容**:
```python
class QuoteFavorite(Base):
    """金句收藏表"""
    __tablename__ = "quote_favorite"
    fav_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False)
    quote_id = Column(Integer, ForeignKey("essay_quote.quote_id"), nullable=True)  # 改为可空
    obsidian_source = Column(String(200), nullable=True, comment="Obsidian 金句来源标识（文件名）")  # 新增
    create_time = Column(DateTime, default=datetime.now)

    user = relationship("SysUser")
    quote = relationship("EssayQuote")

    __table_args__ = (
        UniqueConstraint("user_id", "quote_id", name="uq_user_quote_fav"),
        UniqueConstraint("user_id", "obsidian_source", name="uq_user_obsidian_fav"),  # 新增
        Index("idx_user_id_quotefavorite", user_id),
    )
```

**关键变更**:
1. `quote_id` 改为 `nullable=True`（支持 Obsidian 金句无数据库 ID）
2. 新增 `obsidian_source` 字段（存储 Obsidian 金句的文件名）
3. 新增唯一约束 `uq_user_obsidian_fav`（同一用户对同一 Obsidian 金句只能收藏一次）

#### `backend/app/api/v1/quotes.py`

**变更位置 1**: 第 253-287 行（get_daily_quote 方法）

**变更内容**:
```python
@router.get("/quote/daily", summary="每日金句（从 Obsidian 知识库读取）")
async def get_daily_quote(
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    # 1. 尝试从 Obsidian 读取
    obsidian_quotes = _read_obsidian_quotes()
    if obsidian_quotes:
        selected = _select_daily_quote(obsidian_quotes)
        if selected:
            # 使用文件名作为稳定 ID
            obsidian_id = f"obsidian_{selected['filename']}"

            favorited = False
            if current_user:
                # 按 obsidian_source 查询收藏状态
                fav = db.query(QuoteFavorite).filter(
                    QuoteFavorite.user_id == current_user.user_id,
                    QuoteFavorite.obsidian_source == selected['filename']
                ).first()
                favorited = fav is not None

            return {
                'quote_id': 0,  # 保持兼容，前端仍用 0
                'obsidian_id': obsidian_id,  # 新增：稳定的 Obsidian 金句 ID
                'content': selected['content'],
                'source': selected['source'],
                'category': ', '.join(selected['topics'][:2]) if selected['topics'] else '',
                'author': selected['author'],
                'favorited': favorited,
                'source_type': 'obsidian',
                'obsidian_source': selected['filename'],  # 新增：文件名标识
            }

    # 2. 回退到 SQLite 数据库
    # ... 保持不变
```

**变更位置 2**: 新增端点（在 toggle_quote_favorite 之后）

**变更内容**:
```python
@router.post("/obsidian/{obsidian_source}/favorite", summary="切换 Obsidian 金句收藏")
async def toggle_obsidian_quote_favorite(
    obsidian_source: str,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加或取消 Obsidian 金句收藏"""
    import re

    # 校验参数格式（只允许文件名，不允许路径分隔符）
    if not re.match(r'^[\w\-\.]+\.md$', obsidian_source):
        raise HTTPException(status_code=400, detail="无效的金句来源标识")

    # 检查是否已收藏
    existing = db.query(QuoteFavorite).filter(
        QuoteFavorite.user_id == current_user.user_id,
        QuoteFavorite.obsidian_source == obsidian_source
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        return {"favorited": False, "message": "已取消收藏"}

    # 新增收藏（quote_id 为空）
    fav = QuoteFavorite(
        user_id=current_user.user_id,
        quote_id=None,  # Obsidian 金句无数据库 ID
        obsidian_source=obsidian_source,
    )
    db.add(fav)
    db.commit()
    return {"favorited": True, "message": "已收藏"}
```

#### `backend/app/api/v1/collection.py`

**变更位置**: 第 182-247 行（get_news_favorites 方法）

**变更内容**:
```python
@router.get("/news-favorites", summary="金句/新闻收藏列表")
async def get_news_favorites(
    type: str = Query("all", description="all/quote/news"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """合并查询金句收藏和新闻收藏"""
    from ...models.models import QuoteFavorite, NewsFavorite, EssayQuote, NewsArticle

    all_items = []

    # 金句收藏（数据库金句）
    if type in ["all", "quote"]:
        quote_favs = db.query(QuoteFavorite).filter(
            QuoteFavorite.user_id == current_user.user_id,
            QuoteFavorite.quote_id.isnot(None)  # 只查数据库金句
        ).order_by(desc(QuoteFavorite.create_time)).all()

        for fav in quote_favs:
            quote = db.query(EssayQuote).filter(
                EssayQuote.quote_id == fav.quote_id,
                EssayQuote.status == 1
            ).first()
            if quote:
                all_items.append({
                    'fav_type': 'quote',
                    'fav_id': fav.fav_id,
                    'quote_id': quote.quote_id,
                    'content': quote.content,
                    'source': quote.source or '',
                    'category': quote.category or '',
                    'author': quote.author or '',
                    'create_time': fav.create_time.isoformat() if fav.create_time else '',
                    'source_type': 'database',
                })

    # Obsidian 金句收藏
    if type in ["all", "quote"]:
        obsidian_favs = db.query(QuoteFavorite).filter(
            QuoteFavorite.user_id == current_user.user_id,
            QuoteFavorite.obsidian_source.isnot(None)  # 只查 Obsidian 金句
        ).order_by(desc(QuoteFavorite.create_time)).all()

        for fav in obsidian_favs:
            # 从 Obsidian 知识库读取金句内容
            obsidian_quote = _read_obsidian_quote_by_filename(fav.obsidian_source)
            if obsidian_quote:
                all_items.append({
                    'fav_type': 'quote',
                    'fav_id': fav.fav_id,
                    'quote_id': 0,
                    'obsidian_id': f"obsidian_{fav.obsidian_source}",
                    'content': obsidian_quote['content'],
                    'source': obsidian_quote['source'],
                    'category': ', '.join(obsidian_quote['topics'][:2]) if obsidian_quote.get('topics') else '',
                    'author': obsidian_quote['author'],
                    'create_time': fav.create_time.isoformat() if fav.create_time else '',
                    'source_type': 'obsidian',
                    'obsidian_source': fav.obsidian_source,
                })

    # 新闻收藏
    if type in ["all", "news"]:
        # ... 保持不变

    # 按收藏时间倒序
    all_items.sort(key=lambda x: x.get('create_time', ''), reverse=True)

    total = len(all_items)
    start = (page - 1) * page_size
    end = start + page_size
    items = all_items[start:end]

    return {'total': total, 'page': page, 'page_size': page_size, 'items': items}
```

**新增辅助函数**（在 get_news_favorites 之前）:
```python
def _read_obsidian_quote_by_filename(filename: str) -> Optional[dict]:
    """根据文件名读取 Obsidian 金句"""
    import os
    from ...config import settings

    if not filename or not os.path.exists(settings.OBSIDIAN_QUOTE_DIR):
        return None

    fpath = os.path.join(settings.OBSIDIAN_QUOTE_DIR, filename)
    if not os.path.exists(fpath):
        return None

    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        return _parse_obsidian_quote(content)
    except Exception as e:
        logger.warning(f"Failed to read Obsidian quote {filename}: {e}")
        return None
```

### 4.2 前端文件

#### `.vtj/vue/quote_banner.vue`

**变更位置 1**: 第 180-195 行（refreshQuote 方法）

**变更内容**:
```javascript
async refreshQuote() {
  if (this.state.quoteLoading) return;
  this.state.quoteLoading = true;
  try {
    const auth = window.__VTJ_AUTH__;
    const headers = {};
    if (auth && auth.isLoggedIn && auth.isLoggedIn()) {
      Object.assign(headers, auth.getJsonHeaders());
    }
    // 优先从 Obsidian 知识库获取每日金句，失败时回退到随机金句
    let res = await fetch('/api/quotes/quote/daily', { headers });
    if (!res.ok) {
      // 回退到原有的随机金句接口
      res = await fetch('/api/quotes/random', { headers });
    }
    if (!res.ok) throw new Error('获取金句失败');
    const data = await res.json();
    this.state.quote = data.content || '暂无金句';
    this.state.author = data.author || data.source || '佚名';
    this.state.quoteId = data.quote_id || 0;
    this.state.quoteFavorited = !!data.favorited;
    // 新增：存储 Obsidian 金句信息
    this.state.obsidianId = data.obsidian_id || '';
    this.state.obsidianSource = data.obsidian_source || '';
    this.state.sourceType = data.source_type || 'database';
  } catch (e) {
    console.warn('获取金句失败:', e);
    // 失败时使用兜底金句，避免空白
    if (!this.state.quote || this.state.quote === '正在加载今日金句...') {
      this.state.quote = '忠诚是公安队伍代代相传的政治基因，是融入血脉的人民警察之魂。';
      this.state.author = '人民公安报';
    }
  } finally {
    this.state.quoteLoading = false;
  }
},
```

**变更位置 2**: 第 197-212 行（toggleQuoteFavorite 方法）

**变更内容**:
```javascript
async toggleQuoteFavorite() {
  const auth = window.__VTJ_AUTH__;
  if (!auth || !auth.isLoggedIn || !auth.isLoggedIn()) {
    ElMessage.warning('请先登录后再收藏金句');
    return;
  }

  // 数据库金句收藏
  if (this.state.quoteId) {
    try {
      const res = await auth.apiFetch('/api/quotes/' + this.state.quoteId + '/favorite', { method: 'POST' });
      const data = await res.json();
      this.state.quoteFavorited = data.favorited;
      ElMessage.success(data.favorited ? '已收藏金句' : '已取消收藏');
    } catch (e) {
      console.error('收藏金句失败:', e);
    }
    return;
  }

  // Obsidian 金句收藏
  if (this.state.obsidianSource) {
    try {
      const res = await auth.apiFetch('/api/quotes/obsidian/' + encodeURIComponent(this.state.obsidianSource) + '/favorite', { method: 'POST' });
      const data = await res.json();
      this.state.quoteFavorited = data.favorited;
      ElMessage.success(data.favorited ? '已收藏金句' : '已取消收藏');
    } catch (e) {
      console.error('收藏金句失败:', e);
    }
    return;
  }

  ElMessage.warning('无法收藏当前金句');
},
```

**变更位置 3**: state 定义（约第 150-170 行）

**变更内容**:
```javascript
const state = reactive({
  quote: '正在加载今日金句...',
  author: '',
  quoteId: 0,
  quoteFavorited: false,
  quoteLoading: false,
  currentDate: '',
  newsItems: [],
  showNewsModal: false,
  selectedNews: {},
  isFavorited: false,
  notes: [],
  selectionMenuVisible: false,
  selectionMenuPos: { x: 0, y: 0 },
  selectedText: '',
  highlightColor: '#FFD700',
  lineStyle: 'wavy',
  showHint: false,
  noteInputVisible: false,
  noteText: '',
  // 新增：Obsidian 金句相关字段
  obsidianId: '',
  obsidianSource: '',
  sourceType: 'database',
});
```

#### `.vtj/vue/favorites.vue`

**变更位置 1**: viewNewsDetail 方法

**变更内容**:
```javascript
async viewNewsDetail(item) {
  if (item.fav_type === 'quote') {
    // 金句直接展示
    this.state.newsDetail = {
      id: 0,
      title: '申论金句',
      source: item.source || '',
      category: item.category || '',
      publish_date: '',
      content: '<p style="font-size:18px; line-height:2; color:#333;">' + item.content + '</p>',
      images: [],
      url: ''
    };
    this.state.showNewsModal = true;
    return;
  }
  // 新闻调用详情接口
  // ... 保持不变
},
```

**变更位置 2**: removeNewsFavorite 方法

**变更内容**:
```javascript
async removeNewsFavorite(item) {
  if (item.fav_type === 'quote') {
    // 数据库金句取消收藏
    if (item.quote_id) {
      try {
        await window.__VTJ_AUTH__.apiFetch('/api/quotes/' + item.quote_id + '/favorite', { method: 'POST', headers: this.getJsonHeaders() });
        this.state.showNewsModal = false;
        this.loadFavorites();
        this.loadStats();
      } catch(e) { console.warn('取消收藏失败:', e); }
      return;
    }
    // Obsidian 金句取消收藏
    if (item.obsidian_source) {
      try {
        await window.__VTJ_AUTH__.apiFetch('/api/quotes/obsidian/' + encodeURIComponent(item.obsidian_source) + '/favorite', { method: 'POST', headers: this.getJsonHeaders() });
        this.state.showNewsModal = false;
        this.loadFavorites();
        this.loadStats();
      } catch(e) { console.warn('取消收藏失败:', e); }
      return;
    }
  }
  // 新闻取消收藏
  // ... 保持不变
},
```

### 4.3 DSL JSON 文件

#### `.vtj/files/quote_banner.json`

**变更内容**:
```json
{
  "state": {
    "quote": "'正在加载今日金句...'",
    "author": "''",
    "quoteId": "0",
    "quoteFavorited": "false",
    "quoteLoading": "false",
    "currentDate": "''",
    "newsItems": "[]",
    "showNewsModal": "false",
    "selectedNews": "{}",
    "isFavorited": "false",
    "notes": "[]",
    "selectionMenuVisible": "false",
    "selectionMenuPos": "{ x: 0, y: 0 }",
    "selectedText": "''",
    "highlightColor": "'#FFD700'",
    "lineStyle": "'wavy'",
    "showHint": "false",
    "noteInputVisible": "false",
    "noteText": "''",
    "obsidianId": "''",
    "obsidianSource": "''",
    "sourceType": "'database'"
  },
  "methods": {
    "refreshQuote": { "type": "asyncMethod", "params": [] },
    "toggleQuoteFavorite": { "type": "asyncMethod", "params": [] }
  }
}
```

---

## 5. 数据库迁移

### 5.1 迁移 SQL

```sql
-- 1. 修改 quote_id 为可空
ALTER TABLE quote_favorite MODIFY COLUMN quote_id INTEGER NULL;

-- 2. 新增 obsidian_source 字段
ALTER TABLE quote_favorite ADD COLUMN obsidian_source VARCHAR(200) NULL COMMENT 'Obsidian 金句来源标识（文件名）';

-- 3. 新增唯一约束
ALTER TABLE quote_favorite ADD UNIQUE INDEX uq_user_obsidian_fav (user_id, obsidian_source);

-- 4. 验证
DESCRIBE quote_favorite;
SHOW INDEX FROM quote_favorite;
```

### 5.2 迁移步骤

1. 备份数据库：`mysqldump -u root -p police_exam > backup_before_migration.sql`
2. 执行迁移 SQL
3. 验证表结构

---

## 6. API 契约变更

### 6.1 新增端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/quotes/obsidian/{obsidian_source}/favorite` | 切换 Obsidian 金句收藏 |

### 6.2 修改端点

| 方法 | 路径 | 变更 |
|------|------|------|
| GET | `/api/quotes/quote/daily` | 返回新增 `obsidian_id`、`obsidian_source`、`source_type` 字段 |
| GET | `/api/collection/news-favorites` | 合并返回 Obsidian 金句收藏 |

### 6.3 响应格式

#### GET /api/quotes/quote/daily

```json
{
  "quote_id": 0,
  "obsidian_id": "obsidian_2026-08-14-金句-050.md",
  "content": "金句内容",
  "source": "来源",
  "category": "分类",
  "author": "作者",
  "favorited": false,
  "source_type": "obsidian",
  "obsidian_source": "2026-08-14-金句-050.md"
}
```

#### POST /api/quotes/obsidian/{obsidian_source}/favorite

```json
{
  "favorited": true,
  "message": "已收藏"
}
```

---

## 7. 安全考虑

### 7.1 路径遍历防护

使用正则校验 `obsidian_source` 参数：`^[\w\-\.]+\.md$`

### 7.2 SQL 注入防护

使用 SQLAlchemy ORM 参数化查询，天然防注入。

### 7.3 权限控制

- `toggle_obsidian_quote_favorite` 使用 `get_current_user`（强制登录）
- 前端 `toggleQuoteFavorite` 检查 `auth.isLoggedIn()`

### 7.4 数据一致性

唯一约束 `uq_user_obsidian_fav` 防止重复收藏。

---

## 8. 测试要求

### 8.1 单元测试

| 测试用例 | 预期结果 |
|----------|----------|
| 数据库金句收藏 | 返回 `favorited: true`，数据库插入记录 |
| 数据库金句取消收藏 | 返回 `favorited: false`，数据库删除记录 |
| Obsidian 金句收藏 | 返回 `favorited: true`，数据库插入记录（`obsidian_source` 非空） |
| Obsidian 金句取消收藏 | 返回 `favorited: false`，数据库删除记录 |
| 未登录收藏 | 返回 401 |
| 无效 obsidian_source | 返回 400 |

### 8.2 集成测试

| 测试用例 | 预期结果 |
|----------|----------|
| 首页金句展示 | 正常显示 Obsidian 金句或数据库金句 |
| 点击收藏按钮 | 收藏状态更新，显示提示 |
| 点击"换一句" | 金句更新，收藏状态更新 |
| 收藏页展示 | 显示所有已收藏的金句（数据库 + Obsidian） |
| 收藏页取消收藏 | 收藏列表更新 |

### 8.3 端到端测试

| 测试场景 | 步骤 |
|----------|------|
| 新用户收藏金句 | 1. 登录 2. 浏览首页 3. 点击收藏 4. 访问收藏页 5. 验证显示 |
| 老用户取消收藏 | 1. 登录 2. 访问收藏页 3. 点击取消收藏 4. 验证列表更新 |
| Obsidian 金句更新 | 1. 修改 Obsidian 文件 2. 刷新首页 3. 验证金句更新 4. 验证收藏状态 |

---

## 9. 回滚计划

### 9.1 回滚步骤

1. 恢复数据库：`mysql -u root -p police_exam < backup_before_migration.sql`
2. 恢复代码：`git checkout main -- backend/app/models/models.py backend/app/api/v1/quotes.py backend/app/api/v1/collection.py .vtj/vue/quote_banner.vue .vtj/vue/favorites.vue`
3. 重启服务

### 9.2 回滚影响

- Obsidian 金句收藏功能失效
- 现有数据库金句收藏不受影响

---

## 10. 实施步骤

| 步骤 | 内容 | 耗时 |
|------|------|------|
| 1 | 数据库迁移 | 5 分钟 |
| 2 | 后端修改（models.py, quotes.py, collection.py） | 15 分钟 |
| 3 | 前端修改（quote_banner.vue, favorites.vue） | 10 分钟 |
| 4 | DSL JSON 同步 | 5 分钟 |
| 5 | 测试验证 | 10 分钟 |
| **总计** | | **45 分钟** |

---

> 本文档基于砺安题库项目实际代码和 VTJ 设计规范编写，确保可落地、可维护、安全可靠。
