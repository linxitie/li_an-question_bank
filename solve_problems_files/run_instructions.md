# 招考信息模块修复 — 运行说明

## 修改总结

### 已完成的修改

| # | 文件 | 操作 | 状态 |
|---|------|------|------|
| 1 | `backend/app/services/recruitment_scraper.py` | 完全重写 (v4→v5) | ✅ |
| 2 | `backend/app/services/scraper_utils.py` | 增强编码检测 | ✅ |
| 3 | `.vtj/vue/app_navigation.vue` | 添加招考信息导航 | ✅ |
| 4 | `.vtj/files/app_navigation.json` | DSL同步 | ✅ |
| 5 | `solve_problems_files/recruitment_fix_v2.md` | 修复文档 | ✅ |
| 6 | Memory files | 项目记忆 | ✅ |

### v5 爬虫核心改进

1. **技术栈变更**: Playwright → requests + BeautifulSoup
2. **选择器修正**: 基于 curl 验证的真实网站结构
3. **分页支持**: 自动检测 Empire CMS 分页（最多5页/分类）
4. **数据安全**: 先收集到内存 → 原子替换（单事务删旧+入新）
5. **编码兼容**: 自动检测 GBK/UTF-8 + meta标签回退
6. **重试机制**: 3次指数退避重试

### 前端修改

导航栏 navItems 新增:
```javascript
{ name: 'recruitment', title: '招考信息', route: '/page/recruitment_info' }
```

### 爬取验证结果（curl直接测试）

| 分类 | 每页条目 | 验证状态 |
|------|---------|---------|
| 国考省考 (shengkao) | 28条 × 4页 | ✅ |
| 事业单位 (shiye) | 28条 | ✅ |
| 教师招聘 (jiaoshi) | 28条 | ✅ |
| 国企招聘 (qiye) | 28条 | ✅ |
| 医疗卫生 (yiliao) | 27条 | ✅ |
| 三支一扶 (sanzhi) | 28条 | ✅ |

## 运行步骤

### 1. 执行全量爬取（填充数据库）

```bash
cd D:\砺安题库\砺安题库\backend
python -c "from app.services.recruitment_scraper import scrape_all_recruitment; scrape_all_recruitment()"
```

预计耗时: 10-15分钟（含反爬延迟）

### 2. 启动后端验证API

```bash
cd D:\砺安题库\砺安题库\backend
python -m app.main
```

### 3. 验证API返回数据

```bash
curl http://localhost:8000/api/recruitment?limit=5
```

### 4. 前端验证

1. 启动前端开发服务器
2. 访问 `/page/recruitment_info` — 确认Accordion列表显示6个分类的招考信息
3. 导航栏应出现"招考信息"入口

### 5. 清理Vite缓存

```bash
rm -rf node_modules/.vite/
```
