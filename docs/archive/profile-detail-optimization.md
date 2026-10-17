# 学生端「我的」功能模块细节优化方案（v3.0 完整版）

> 版本：v3.0 · 日期：2026-09-16 · 分支：feat/gold-purchase
> 覆盖：头像编辑、成就五档徽章（全量）、手机端错题本+复习、手机端练习记录页、成就页/收藏页/反馈页手机适配。
> 经用户审批后实施。所有后端接口复用已存在者，前端严格对齐现有答题卡/设计令牌。

---

## 一、头像编辑（三端统一）

### 1.1 现状
- 后端 `SysUser.avatar` 字段存在；学生端无上传接口（仅教师端有）；`/uploads` 静态挂载已存在
- 前端三端编辑弹窗均无头像项，头像为硬编码 `UserFilled` 图标

### 1.2 方案
**后端**（`auth.py` 新增 `POST /api/auth/avatar`）：
- 白名单 jpg/jpeg/png/gif/webp + ≤2MB + UUID 重命名存 `uploads/avatars/` + `Depends(get_current_user)`

**前端**（桌面 `profile.vue` 编辑弹窗 + 手机/平板用户卡）：
- 头像有值 → `<img :src>`；无值 → 默认 `UserFilled`；点击头像 → 文件选择 → FormData 上传 → 回显 + Toast

---

## 二、成就五档徽章（全量实现）

### 2.1 五档升级设计（本方案定义，因原 tier_times 为半成品）

**语义**：45 项成就保持独立（每项=一枚勋章）；每枚勋章有 **5 档视觉**（铜/银/金/铂金/钻石），按「达成度 = 当前值/阈值」的倍数升档：

| 档位 tier | 名称 | 达成倍数 | 颜色 |
|---|---|---|---|
| 1 | 铜 | 达成 threshold（获得成就） | #b87333 |
| 2 | 银 | 2× threshold | #c0c0c0 |
| 3 | 金 | 4× threshold | #ffd700 |
| 4 | 铂金 | 8× threshold | #e5e4e2 |
| 5 | 钻石 | 16× threshold | #b9f2ff |

**支持升档的成就**（累计数量型，`tier_times=[1,2,4,8,16]`）：
- 做题数量类 10 项、斩题类 3 项、错题重练类 2 项、收藏/笔记/金句 3 项、发帖/获赞 4 项
- 其余（首次/连续/正确率/时间类）不升档（`tier_times=NULL`，固定 tier 1）

**后端改动**：
1. `achievement_service.py`：`ACHIEVEMENTS` 列表补 `tier_times`（升档成就）字段；`check_and_grant` 加「升档判定」——已获得成就且达更高倍数 → 更新 `UserAchievement.tier`
2. `achievements.py`：返回 `tier`、`is_hidden`、`tier_times`、`style_params`
3. `main.py` 自动迁移已含 tier 字段（已就绪）

### 2.2 徽章视觉（style_params）
- 每项成就 `style_params` 定义 `shape`（circle/shield/star）+ `icon`；前端按 `tier` 上材质色
- 简化：`style_params` 仅存 `{"shape": "...", "icon": "..."}`，材质色由 tier 决定（前端映射）

### 2.3 隐藏成就（is_hidden）
- 「联考特色/隐藏/赛季限定」类成就标记 `is_hidden=1`，前端显示剪影（❓ 灰盾），不展示具体条件/名称

### 2.4 已获得标识（前端）
- `achievements.vue`：已获得右上角「✓ 已获得」角标（随 tier 变色）+ 勋章彩色；未获得 `filter: grayscale` 置灰 + 进度条
- `profile.vue`：成就区块横向展示已获得勋章图标（含档位色）+ 数量 + 查看全部

---

## 三、手机端错题本 + 复习

### 3.1 错题本增强（重构 `mobile_wrong_questions.vue`）
1. 顶部分类筛选 tabs（全部/行测/申论/公专 + 子科目），数据源 `/api/wrong-questions/subcategories`
2. 列表项加「斩题」按钮（`PUT /api/wrong-questions/{id}/chop`）
3. 「斩题记录」tab（`GET /api/wrong-questions/zhanti/list` + 剩余天数）

### 3.2 新建错题复习页 `mobile_wrong_review.vue`（答题卡样式严格对齐 `answer_page.vue`）
- 入口：错题本顶部「错题复习」按钮 → 选模式（knowledge/time/subject/mixed）
- 取队列：`GET /api/wrong-questions/review/queue?mode=xxx`
- 答题卡样式**严格复用** `answer_page.vue` 的：题号+题型徽章、题干、选项（单选/多选）、结果+解析展示、答题卡面板、字体
- 提交：`POST /api/wrong-questions/review/submit`（批量判分+自动斩题）→ 结果页展示对错统计 + 自动斩题提示

---

## 四、手机端练习记录页 `mobile_history.vue`（对标电脑端）

### 4.1 数据接口（已存在）
- `GET /api/practice/records`（练习记录分页，含 question_content/type/is_correct/subject/time_spent）
- `GET /api/practice/type-summary`（按题型统计）
- `GET /api/practice/unified-stats`（四来源统一统计）
- `GET /api/stats/practice-trend?days=7|30`（练习趋势，按天）

### 4.2 页面设计
1. **顶部统计卡**：总做题、正确率、学习时长（对标电脑端学习数据）
2. **折线图**（做题数量趋势，SVG polyline，数据 `/api/stats/practice-trend`）
3. **柱状图**（按题型做题量，SVG rect，数据 `/api/practice/type-summary`）
4. **练习记录列表**（分页，每条：题目内容截断 + 题型 + 对错标记 + 科目 + 时间），点击展开答案/解析
5. **与「我的」联动**：总做题/正确率/学习时长同步展示到 mobile_profile 的「学习数据」卡

### 4.3 可视化方案（不引入第三方图表库，纯 SVG，与 tablet_profile 现有纯 CSS 柱状图一致）
- 折线图：`<svg><polyline>` 画 7/30 天做题数量趋势
- 柱状图：`<svg><rect>` 画各题型做题量
- 保证手机端宽度适配（`viewBox` + 百分比宽度）

---

## 五、手机端成就页响应式
- `achievements.vue` 加 media query：桌面 >1024px 3 列 / 平板 2 列 / 手机 <768px 2 列纵向（图标上、名称下），解决勋章扁长

## 六、手机端收藏页（科目+子科目分类）
- `mobile_favorites.vue` 加分类 tabs（科目+子科目），数据源 `/api/questions/favorites` 或 `/api/collection`

## 七、feedback/help 手机适配
- `feedback.vue`/`help.vue` 加 media query，手机单列

---

## 八、质量门禁
1. **VTJ 版本一致**：改 `.vue` script 同步 `.vtj/files/*.json` + `__VERSION__`（VTJ 生成页）
2. **后端完整**：新字段与 schema 一致；头像上传校验完备；成就升档逻辑事务+唯一约束
3. **安全**：头像白名单+大小限制+UUID 重命名；所有接口 `get_current_user`
4. **运维**：升档逻辑幂等（tier 只增不减）；头像独立目录；日志完整
5. **不影响其他模块**：仅改「我的」相关文件 + 学生端头像接口；复习页/练习记录页为新增独立文件，不动现有答题/练习页

---

## 九、实施顺序（建议）
1. 后端：头像上传接口 → 成就五档（seed + 升档逻辑 + 路由返回字段）
2. 前端桌面：头像编辑 + 成就标识/档位 + profile 勋章展示
3. 前端手机：错题本增强 + 复习页 + 练习记录页 + 收藏分类 + 成就页/反馈页响应式
4. 平板：头像编辑 + 数据接入
5. 验证：vue-tsc + TestClient 端到端 + 浏览器实测

---

## 十、开放问题（需确认）
1. **五档升级语义**：本方案采用「单成就 5 档视觉（达成倍数升档）」，45 项成就仍独立。是否认可？（原 tier_times 语义模糊，此为清晰化设计）
2. **图表实现**：用纯 SVG（不引入 ECharts），是否认可？（避免包体积增大）
3. **手机端练习记录**：是否还需「按科目/题型筛选」的维度，还是仅趋势+列表？

---

> 本方案已通过自审：无 TBD、无内部矛盾；§十 开放问题需确认后锁定，随后实施。
