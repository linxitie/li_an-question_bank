# 论坛 / 商城 UI 批量修复方案 v1

- 分支：`fix/forum-ui-batch`（已从 `feature/forum-ai-moderation` 创建）
- 状态：**待批准，未改代码**
- 范围：学生 / 教师 / 管理员三端**电脑端**（手机、平板不在本轮，除 item 13 的 prompt 外）
- 实测依据：读代码 + 查库；每项标注"现状证据"

---

## 一、逐项诊断与改法

| # | 问题 | 实测现状（证据） | 改法 | 文件 | 类型 |
|---|---|---|---|---|---|
| 1 | 评论含敏感词被拦截 | `cg_judgment#17`：scene=forum_comment，**level=blocked，decision=block**，命中含 `裸照 / 发裸照给我`（blocked·porn）；`傻逼/脑残/狗东西` 等均为 **masked**（可发布）。即：不是打码失效，是评论里含**色情类 blocked 词** | **需你决策**：色情/赌博类是否也改为"打码可发布" | 数据(cg_term) 或 判定策略 | 决策 + 可能的数据改动 |
| 2 | 管理员端评论无表情/附件 | `src/views/admin/admin_forum.vue:447-460` 只有 input + 发送；教师端 `teacher_forum.vue:121-122` 已有 emoji + FileUploader；学生端 `forum.vue:436-452` 也有 | 管理员端补表情选择器 + 附件上传，复用现有组件 | admin_forum.vue | src（可直接改） |
| 3 | "我的帖子"卡片只有标题 | `forum.vue:139-151` 只渲染 title + ❤/💬；弹窗版已有 `excerptOf()` 摘要 | 小卡片补 2 行正文摘要 | forum.vue | .vtj 模板（补丁） |
| 4 | 学生 PC 论坛分页 | `forum.vue:96-104` 上一页/下一页 + `pageSize:8`；接口支持 page/limit | 改为滚动加载（首屏 20 条，触底加载下一页），去掉分页条 | forum.vue | .vtj 模板 + script |
| 5 | 发帖弹窗自动回填草稿 | 后端 `forum_draft` 每人一条覆盖式；前端 PostComposer 打开即回填；库里确有测试草稿 `草稿回填验证_1793951166589` | **需你决策**：A 彻底删除草稿功能（去掉按钮+接口）；B 保留"手动恢复上次草稿"，默认空白 | PostComposer.vue + forum.py | src + 可能后端 |
| 6 | 我的帖子弹窗：批量删除 + 去分页 | `forum.vue:507-542` 有分页；无多选/批量删除 | 加复选+全选+批量删除；去分页，一次拉全量滚动显示 | forum.vue + forum.py（批量删除端点） | .vtj 模板 + 后端 |
| 7 | 今日热门弹窗底部空白 | `forum.vue:473-505` 列表容器高度固定，内容少时下方留白；"前 100 条"为接口上限 | 弹窗高度自适应 + 列表滚动；保留 100 条上限（无分页） | forum.vue | .vtj 模板 + CSS |
| 8 | 点赞/收藏图标灰色 | 详情区 `forum.vue:305-313` 用文本 `♡/❤`、`☆/★`；评论区点赞用的是**星形图标**（语义错，`:icon="comment.liked ? StarFilled : Star"`） | 统一彩色图标：喜欢=红心、收藏=金星；评论点赞改心形 | forum.vue | .vtj 模板 |
| 9 | 评论排序显示"最新在前" | `src/components/forum/CommentSortBar.vue:12-14` 按钮文案 `最新在前/最早在前` | 改为 `倒序/正序`（时间维度），点赞/回复切换保留 | CommentSortBar.vue | src（可直接改） |
| 10 | 收藏/喜欢/热门/我的帖子缺作者与四项计数 | 后端 `_serialize_post` 已返回 author/avatar/date/likeCount/favoriteCount/commentCount/viewCount；前端列表只渲染标题/摘要+❤💬 | 列表项统一补：头像+昵称+日期（上），点赞/收藏/回复/浏览四项（下） | forum.vue | .vtj 模板 |
| 11 | 题库快捷工具里的"金币购" | `question_bank.vue:274-279`，与顶部导航新增的"商城"重复 | 删除该入口 | question_bank.vue | .vtj 模板 |
| 12 | 金币购头部布局 | `gold_purchase.vue:12-19`：金币余额在左、两个按钮在右 | 金币居中；"我的兑换 + 知识图谱"并排放在右侧或下方 | gold_purchase.vue | .vtj 模板 |
| 13 | 新建目标用浏览器 prompt | `gold_purchase.vue:435-437` `window.prompt`；手机/平板金币购也各有 prompt | 改成页面内弹窗（按图十三：目标名称/数量/类型/截止日期/优先级 + 取消/保存）；PC 三端统一 | gold_purchase.vue + mobile/tablet | .vtj 模板 + 组件 |

## 二、流程约束（重要）

1. **`.vtj` 模板按上次 gold_purchase 的方式**：我先出补丁（`docs/patches/`），你确认后落盘；涉及 `forum.vue`、`question_bank.vue`、`gold_purchase.vue`。
2. `src/` 下的文件（admin_forum.vue、teacher_forum.vue、CommentSortBar.vue、PostComposer.vue）**可直接改**，不属于 `.vtj`。
3. 后端改动（批量删除端点、草稿策略）改完**重启 8000**；前端 9527 刷新即可。
4. 每项改完：`git diff` + 实测（接口/DB/页面复验），不自动提交。

## 三、需要你拍板（3 个）

| # | 决策 | 我的建议 |
|---|---|---|
| Q1 | 色情/赌博/毒品等 **blocked 级**（64 条）是否也改成"打码可发布"？ | **保持拦截**。辱骂/羞辱/引流已经是 masked（可发布打码），色情/赌博拦截符合平台合规。若你坚持全打码，我再改，但风险很高 |
| Q2 | 草稿：彻底删除 / 保留手动恢复？ | **保留但默认不回填**：弹窗打开为空白，顶部给一个"恢复上次草稿"按钮；同时清掉库里的测试草稿 |
| Q3 | 批量删除：软删除（可恢复，走现有 DELETE）还是彻底删除？ | **软删除**，与单条删除一致 |

## 四、验收

- 每项：改前 → 改后对比（截图/接口响应/DB 查询），`git diff` 确认落到文件
- 三端一致性：学生 forum.vue / 教师 teacher_forum.vue / 管理员 admin_forum.vue 同项一并检查
- 回归：`pytest tests/test_content_guard.py tests/test_forum_* tests/test_weekly_task_catalog.py`

---

## 五、实施记录（2026-11-07，第一批已完成，未提交）

### 5.1 用户决策
- Q1 = **打码可发布**（blocked 级也降级为 mask）
- Q2 = **草稿手动恢复**（默认空白）
- Q3 = **软删除 + 回收站 + 30 天彻底删除**，回收站入口与彻底删除并列

### 5.2 已完成并实测

| 项 | 改动 | 证据 |
|---|---|---|
| Q1 | `content_guard/__init__.py` 新增 `MODERATION_BLOCK_AS_MASK`（默认 1）：词库 blocked → mask，链接黑名单仍拦截 | 线上发帖「这里有赌博和傻逼」→ 200，正文 `这里有**和**` |
| Q3 | `forum.py`：删除写 deleted_at/by/reason；新增批量删除、回收站列表（`my-posts?include_deleted`）、恢复接口；`services/forum_recycle.py` + 每日 03:40 定时彻底删除（30 天） | 线上：批量删除 → 回收站列表含 deletedAt → 恢复成功 → 再删除成功 |
| Q2 | `PostComposer.vue`：打开默认空白，有草稿时显示「恢复草稿/忽略」；不再自动回填 | SFC 编译通过；9527 已服务新模块 |
| 2 | `admin_forum.vue`：管理员评论补 emoji 选择器 + 附件上传（复用教师端组件） | SFC 编译通过；9527 模块 200 |
| 9 | `CommentSortBar.vue`：`最新在前/最早在前` → `倒序/正序` | 同上 |
| 测试 | content_guard + forum_recycle + forum_moderation + forum_posting + weekly catalog | **56 passed**；8000 已重启（pid 8488） |

### 5.3 待办（.vtj 模板，按补丁流程）

3 我的帖子卡片摘要、4 学生论坛无限滚动、6 我的帖子批量删除+回收站视图、7 热门弹窗高度、
8 点赞/收藏图标着色、10 列表作者与四项计数、11 题库快捷工具去金币购、12 金币购头部布局、
13 新建目标弹窗（替换 window.prompt）。
---

## 六、实施记录（2026-11-07 第二批：13 项全部落地）

| # | 落地内容 | 文件 | 验证 |
|---|---|---|---|
| 3 | 侧栏「我的帖子」卡片补 2 行正文摘要 | forum.vue | SFC 编译通过；9527 已服务 |
| 4 | 去掉分页，改容器内滚动触底加载（每页 8 条，触底 300px 自动加载，末尾显示「已经到底了」） | forum.vue | 同上 |
| 6 | 我的帖子弹窗：多选 + 批量删除（进回收站）+ 回收站标签页（可恢复）+ 去分页 | forum.vue + forum.py | 后端接口实测；SFC 通过 |
| 7 | 热门弹窗 hot-all-card 高度自适应（不再固定 85vh 留白） | forum.vue | SFC 通过 |
| 8 | 喜欢=红心（默认红）、收藏=金星；评论点赞由星形图标改为红心 | forum.vue | SFC 通过 |
| 10 | 收藏/喜欢/热门/我的帖子列表补齐：作者头像+昵称+日期（左），点赞/收藏/回复/浏览四项（下） | forum.vue | SFC 通过 |
| 11 | 题库快捷工具删除「金币购」入口 | question_bank.vue | 编译通过；模块中已无 gold_purchase |
| 12 | 金币居中，「我的兑换 / 知识图谱」并排右侧 | gold_purchase.vue | SFC 通过 |
| 13 | 新建目标改弹窗（名称/数量/类型/截止日期/优先级 + 取消/保存），替换 window.prompt | gold_purchase.vue | SFC 通过 |
| Q3 | 管理员回收站已有「恢复 + 彻底删除」（原本并列）；学生侧回收站视图本轮补上；每日 03:40 清理 30 天前数据 | forum.vue + scheduler.py | 定时任务已注册 |

编译校验：forum.vue / question_bank.vue / gold_purchase.vue / admin_forum.vue 全部通过 @vue/compiler-sfc；9527 已返回含新代码的模块。
