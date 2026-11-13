# 第四批 UI/功能修复方案 v1

- 分支：`fix/forum-shop-ui-batch3`（继续使用）
- 状态：**分批实施中**
- 本轮 12 项

## 逐项拆解

| # | 需求 | 定位 | 做法 | 状态 |
|---|---|---|---|---|
| 1 | 首页任务列表三个筛选字体缩小、保持一行 | `goal_card.vue` `.goal-tabs/.goal-tab` | 字号 11px、flex 均分、nowrap | ✅ 已完成 |
| 2 | 商城知识图谱改力导向图 | `KnowledgeGraphPanel.vue` | 现为环形布局；改 d3-force 或自写力导向（斥力+弹簧+阻尼），拖拽保留 | 待做 |
| 3 | 评论输入框参数 + 全屏按钮（学生/教师/管理员一致） | `forum.vue`、`teacher_forum.vue`、`admin_forum.vue` | margin-bottom:-35px；radius:16px；gap:13px；min-height:50px；左右贴边；右侧全屏按钮 + 同尺寸弹窗（含 emoji/表情包/上传/发送） | 待做 |
| 4 | 教师端帖子详情顺序与学生端一致 | `teacher_forum.vue` | 调整为：标题 → 头像/作者/时间 → 正文 → 点赞/收藏/评论/浏览 | 待做 |
| 5 | 教师端进入评论区后不能给帖子点赞/收藏 | `teacher_forum.vue` | 详情弹窗头部补点赞/收藏按钮，复用 `toggleForumPostLike/Favorite` | 待做 |
| 6 | 热门"当天无人发帖显示近 7 天"在别的电脑变成"还没有帖子" | 后端 hot 接口 + 前端空态 | 复现：换库/换时区；统一后端兜底（当天 0 帖自动返回近 7 天），前端不再显示空态 | 待诊断 |
| 7 | 打码词表手动维护 + Obsidian MCP 同步 | `content_guard` + MCP | 方案：管理端词条 CRUD 已有；新增 MCP 工具读 Obsidian 词表文件 → 调 `content_guard` 导入接口；本机 obsidian 变更后同步 cg_term | 待方案确认 |
| 8 | 手机端商城知识图谱布局拥挤 | `mobile_*` 图谱页/面板 | 手机专用紧凑布局：单列、缩小画布、折叠统计、横向滚动详情 | 待做 |
| 9 | 手机端商城底部导航消失 | `mobile` 布局/页面 | 统一使用手机底部 TabBar 组件，商城页显式挂载 | 待查 |
| 10 | 手机端论坛点赞/收藏无特效；评论只能点赞不能收藏 | 手机论坛页 | 补图标动效；评论操作补收藏（复用 `/comments/{id}/favorite`） | 待做 |
| 11 | 管理员铃铛消息点击不跳转 | `AdminLayout.vue` | 已加 fallback：feedback→/admin/feedback、approval→/admin/papers、forum→/admin/forum、security→/admin/logs | ✅ 已改（刷新验证） |
| 12 | 继续做抠图 | 管理端商品上传 | 按《商城商品图片一键抠图方案 v1》：浏览器端 AI + Canvas 白底兜底 | 待实施 |

## 实施顺序

3（评论区输入框三端）→ 4/5（教师详情）→ 6（热门兜底）→ 9/10（手机端）→ 8（手机图谱）→ 2（力导向）→ 12（抠图）→ 7（Obsidian MCP 方案）

每完成一组给验证；全部完成后跑 typecheck + 后端测试。
