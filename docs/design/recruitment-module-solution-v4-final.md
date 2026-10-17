# 招考信息模块全面改造方案（v4 最终版）

> 生成日期：2026-07-17 | 状态：已实施完成

---

## 一、改造范围

```
招考信息模块 v4
├── 爬虫层：recruitment_scraper.py（完全重写）
│   ├── 6分类独立URL → Playwright导航到各分类列表页
│   ├── 从 div.channel-main-left.f1 提取列表条目
│   └── 详情页精确提取：h1（标题）+ div.channel-text.pb30（正文HTML）
│
├── 前端展示：home_page.vue recruit-section（优化）
│   ├── 卡片标题列表：默认显示前6条 → 卡片内 max-height:400px 滚动查看更多
│   ├── 删除展开/收起逻辑（toggleCardExpand / expanded 属性）
│   ├── 详情弹窗：max-width: 680px → 860px（增加宽度）
│   ├── 详情弹窗内容区：50vh → 65vh（增加可视区域）
│   └── HTML正文渲染优化（img居中、table自适应等CSS重置）
│
├── 前端展示：footer_info.vue（改造）
│   ├── 删除 "展开全部" 按钮（expand-toggle）
│   ├── 删除箭头展开/收起交互（toggleCategory / expandedCats）
│   ├── 卡片列表：全部显示 → max-height:400px 卡片内滚动
│   └── 卡片头部箭头和展开交互样式移除
│
└── 数据层
    ├── 先清空全表 → 再爬取6个分类（保证每日更新效果）
    └── content_html 保存完整HTML（不截断10000字符）
```

## 二、爬虫详细设计

### 6分类独立URL配置

| 分类 | 独立URL |
|------|---------|
| 国考省考 | https://www.rszk.net/shengkao/ |
| 事业单位 | https://www.rszk.net/shiye/ |
| 教师招聘 | https://www.rszk.net/jiaoshi/ |
| 国企招聘 | https://www.rszk.net/qiye/ |
| 医疗卫生 | https://www.rszk.net/yiliao/ |
| 三支一扶 | https://www.rszk.net/sanzhi/ |

### 爬取流程

```
scrape_all_recruitment()
  1. DELETE FROM recruitment_info（清空全表）
  2. for 每个分类:
     a. 启动 Playwright headless chromium
     b. 导航到分类列表页（networkidle）
     c. 等待 div.channel-main-left.f1 出现
     d. 提取所有 a[href] 链接（标题+URL）
     e. 逐个进入详情页
        - 提取 div.channel-main-left.f1 > h1 → 标题
        - 提取 div.channel-main-left.f1 > div.channel-text.pb30 → 正文HTML（完整）
        - 正文中提取：报名时间、考试方式、联系方式、发布单位、地区
        - 检测状态标签（报名结束/正在报名/即将报名）
     f. 写入DB（按title+category去重）
     g. 每个分类之间等待2-3.5秒（反爬）
```

### 反爬策略
- Playwright 反检测：隐藏 webdriver、注入 chrome.runtime
- UA轮换（固定Chrome 131）
- 请求间隔随机化（0.8-3.5秒）
- 每分类完成后额外等待2-3.5秒

## 三、前端展示变更对照

### home_page.vue

| 变化项 | 修改前 | 修改后 |
|--------|--------|--------|
| 标题列表截取 | `slice(0, item.expanded ? 10 : 5)` | `slice(0, 6)`（固定前6条） |
| 展开/收起 | toggleCardExpand + expanded 属性 | **已删除** |
| 卡片头部点击 | 切换展开/收起 | scrollToTop（滚动到卡片顶部） |
| 箭头动态class | `arrow-expanded` + rotate(90deg) | **已删除**，仅保留静态箭头图标 |
| 卡片列表容器 | 无滚动 | `.recruit-title-list-scroll` max-height:400px + overflow-y:auto |
| 弹窗宽度 | max-width: 680px | **max-width: 860px** |
| 弹窗内容区高度 | max-height: 50vh | **max-height: 65vh** |
| HTML正文渲染 | 纯文本 p 标签 | `v-html` 渲染 + CSS重置（img/table） |

### footer_info.vue

| 变化项 | 修改前 | 修改后 |
|--------|--------|--------|
| 展开全部按钮 | exist | **已删除** |
| 箭头展开交互 | toggleCategory + expandedCats | **已删除全部展开逻辑** |
| 列表可见条目 | `getVisibleItems` → slice(0,6) 或全部 | `getVisibleItems` → **直接返回全部** |
| 滚动支持 | 无 | `.card-list-scroll` max-height:400px + overflow-y:auto |

## 四、关键文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend/app/services/recruitment_scraper.py` | **完全重写** | Playwright导航+6分类独立URL+精确提取 |
| `.vtj/vue/home_page.vue` | 模板+样式+脚本 | 卡片滚动+弹窗优化+删除展开逻辑 |
| `.vtj/vue/footer_info.vue` | 模板+样式+脚本 | 删除展开全部+卡片滚动+删除箭头交互 |
| `.vtj/files/home_page.json` | DSL同步 | 方法变更同步 |
| `.vtj/files/footer_info.json` | DSL同步 | 方法/状态变更同步 |

## 五、验证清单

| # | 验证项 | 状态 |
|---|--------|------|
| 1 | 爬虫语法检查通过 | ✅ |
| 2 | Playwright可启动chromium | ✅ |
| 3 | 前端构建成功 | ✅ |
| 4 | home_page.vue 卡片内可以滚动查看更多 | ✅ |
| 5 | home_page.vue 详情弹窗宽度860px | ✅ |
| 6 | home_page.vue 内容区65vh | ✅ |
| 7 | home_page.vue 删除展开/收起逻辑 | ✅ |
| 8 | footer_info.vue 删除展开全部按钮 | ✅ |
| 9 | footer_info.vue 卡片内400px滚动 | ✅ |
| 10 | footer_info.vue 删除箭头展开交互 | ✅ |
| 11 | 爬虫6分类独立URL配置正确 | ✅ |
| 12 | 爬虫先清空再爬取 | ✅ |
| 13 | 爬虫content_html完整保存 | ✅ |