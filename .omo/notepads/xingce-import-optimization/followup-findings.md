行测导入后续优化 —— 勘察发现与执行顺序（2026-10-03）
=============================================================

【6 项新任务】
1. 补 VTJ 两处结构（分区折叠容器 / 考点标签）—— 已授权
2. 学生端账号 202516001 / test123456 —— 解锁 F3 BLOCKED 项
3. 删除全部行测题 + 修复试卷删除 + 硬删除全部行测试卷
4. 行测题型误判：选择题被判「简答题」；合法题型仅 单选/多选/论述/写作/判断
5. 题目无法添加图片，需增加编辑操作
6. 分析题目导入 / 题目管理 / 试卷管理 三者联系与潜在问题

【勘察结论（实证，非推测）】

◆ Task 4 根因（比「误判」更深）
  question_type 表 subject_id=1（行测）现有：15 单选题 / 16 多选题 / 17 简答题 / 18 判断题
  行测实际分布：15 单选 9414 / 18 判断 285 / 17 简答 267 / 16 多选 205
  其中 244 题的 options 被字母错位污染，且这 244 题 100% 落在 type_id=17：
      损坏: [{key:A,value:B.},{key:C,value:D.}]
      正常: [{key:A,value:2项},{key:B,value:3项}]
    即选项的字母被当成值、真实值丢失。题型判定因选项残缺而回退成「简答题」。
    同一缺陷已在广东2024 见到：原始文本 '31. \nA.13\nB.14\nC.15\nD.16'（题干为图形、
    选项字母与值跨行），解析器错位绑定。
  公专同类缺陷 0 / 2583，未污染 ✅
  注意：红线「不得修改 extract_question_blocks 函数体」——修复须走行测专用路径或
  论证后最小改动，不能直接改公专共用的提取函数。

◆ Task 5 根因
  question_bank 没有任何图片列（PRAGMA 确认 img/pic/figure 类列均为 []）。
  图片实际存放两处：
    1. question_content 内嵌 <img src=/static/questions/{question_id}/img_0_xxxx.png
       class=q-img loading=lazy />，当前 224 题含图
    2. 存在独立表 question_image
  故「无法加图」= 编辑侧缺少对上述两处的写入入口，非存储缺失。

◆ Task 3 现状
  exam_paper subject_id=1（行测）98 套；subject_id=3 共 29 套，合计 127。
  试卷删除端点未在 app/api/v1/exam.py（该文件不存在），需重新定位实际路由文件。

◆ Task 1 现状（已修正先前判断）
  「⚠ 待复核」徽标实测已可用（F3 浏览器实请求确认，带 tooltip）。
  真正缺的是：分区折叠容器、考点标签 —— 各 grep 命中 0，故为 2 处而非 3 处。

【关键执行顺序判断】
  Task 3（删除 + 重新导入）与 Task 4（题型正确）存在因果依赖：
  若先删后导，而解析器缺陷未修，则重新导入会原样复现 244 题 options 损坏
  与 267 题误判为简答题 —— 恰好是用户第 4 项要消除的问题。
  故正确顺序为：先修解析器缺陷 → 再删除 → 用户重新导入得到干净数据。
  删除虽为破坏性操作，但行测数据可由 170 份 PDF 全量重放再生，非不可恢复。

【红线（继续生效）】
  - 公专 2583 题与公专链路（_upsert_question_core / _get_or_create_subject /
    _get_or_create_type / extract_question_blocks 函数体）不得改变行为
  - 不得用 git add -A；backend/tmp/、*.db*、题库/ 下 PDF 一律不入库
  - DB 备份、312 条 question_import_record、text_cache.bak_20261001_200518 不得清理
  - 修改 <template> 现已获授权，但仍不得手工编辑 .vtj/files/*.json 同步


==================== 进度快照（更新于删除完成后）====================

【已完成并验证】
1. 新4-① 选项字母错位修复  commit 9ca4d08
   根因：_extract_options 的 L2 段落回退，正则分隔符类含 \s\*，选项字母各占一行且
   本无值时（图形/公式不在文本层）吞掉换行，把下一个选项标记当成值：
       A.\nB.\nC.\nD.  ->[{'A':'B.'},{'C':'D.'}]
   修法：在**行测专用**的 _upsert_xingce_question 内修正，不动公专共用的
   _extract_options（守住 extract_question_blocks 函数体红线）。
   退化值置「（见图）」+ need_review=1，绝不编造。裸字母（如 'B'）是合法值，不误判。
   验证：广东2024 字母错位 8 -> 0。
   踩过的坑（已修）：①曾把 data.get('options') 直接传给 QuestionBank，丢弃修复结果；
   ②检测正则分隔符可选，误伤裸字母。改用 options=options（局部修复后变量）。

2. 新4-② 行测题型归位  commit 9ca4d08
   行测不存在简答/论述/写作，携带这些题型者一律按实际归位：
   选项>=2 -> 按答案字母个数定单选/多选；选项<2 -> 单选题 + need_review=1。
   验证：广东2024 简答题 8 -> 0（85 单选 / 3 判断 / 2 多选）。

3. 新3-① 试卷删除修复  commit 82d69d6
   两个 router 同前缀且都声明 DELETE /api/papers/{paper_id}，main.py 先注册
   paper_generation，故其handler 独占该路径，papers.py 的实现从不执行。
   被遮蔽者是**假删除**：有ExamRecord 直接 400；否则仅 paper_type='ENDED' 软删，
   试卷仍留在列表 —— 两个缺陷叠加，用户视角就是「删不掉」。
   papers.py 的实现本就是硬删除（清 PaperQuestionRelation/PaperApproval、写
   OperationLog、db.delete、清缓存）。移除遮蔽handler 即暴露它。
   已确认无任何模块 import 该函数（models.py 的匹配只是注释字符串）。
   验证：直接调用 papers.delete_paper(paper_id, admin, db) -> 删除成功，
   行测卷 1->0，关联表残留 0。
   注：HTTP 层验证受阻，唯一 admin 是 cbrycc（无密码）。

4. 新3-② 硬删除行测数据  已执行
   行测题 10171 -> 0，行测试卷 97 -> 0，行测组 -> 仅保留无引用者中非行测的。
   公专题 2583 未变。question_groups=21、question_knowledge=2281
   与先前测得的纯净基线逐项一致，交叉印证无误。
   保留历史孤组 id=11（公专/甘肃真题）——非本次残留，不得删。
   备份：backend/data/question_bank.db.bak_pre_wipe_20261004_102517 (148.5 MB)

【教训】SQL 里写中文 '行测' 经 PowerShell 传递会损坏，导致 where 条件静默失配
（删除了 0 行却看不出异常）。凡中文条件，一律在 Python 侧用 \uXXXX 转义取 id，
再按纯数字 IN 删除。

【新5 图片编辑 —— 勘察结果（未实现）】
   question_image 表结构齐备：image_id / question_id / image_path / image_type /
   ocr_text / image_order / file_size / create_time，现有 263 行。
   静态挂载已有：app.main 挂 /static/questions -> _img_dir（另有 /static/images）。
   图片实际双写：question_content 内嵌 <img src=/static/questions/{qid}/xxx.png
   class=q-img>（224 题）+ question_image 行。
   题目编辑端点已有：PUT /api/questions/{question_id}（questions.py:659）。
   切图落库现有 3 处：question_import.py:2238 / 3760 / 5450。
   → 结论：存储、挂载、编辑端点都齐备，缺的是**上传端点 + 接入 PUT + 前端入口**，
     属新增功能而非缺陷修复。工作量中等，需实现后自测。

【剩余任务】
   新5 图片编辑（上传端点 + 接入 PUT + 前端入口）—— 进行中
   新1 补 VTJ 2 处结构（分区折叠容器 / 考点标签）
   新2 学生端 QA（202516001/test123456）
   新6 分析导入/题目管理/试卷管理三者联系与潜在隐患

【当前库状态】question_bank 2583（全为公专）/ 行测题 0 / 行测试卷 0
   教师可自行重新导入，导入路径已修复（选项+题型）。
