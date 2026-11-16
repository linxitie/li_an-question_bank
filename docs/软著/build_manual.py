from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from pathlib import Path

OUT = Path(__file__).resolve().parent / "砺安题库系统_每日新闻_每日金句_招考信息_软件说明书_V1.0.docx"

doc = Document()
sec = doc.sections[0]
sec.top_margin = Cm(2.2)
sec.bottom_margin = Cm(2.2)
sec.left_margin = Cm(2.4)
sec.right_margin = Cm(2.2)

def set_font(run, name="宋体", size=10.5, bold=False, color=None):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)

def style_init(name, font, size, bold=False, color=None):
    st = doc.styles[name]
    st.font.name = font
    st.font.size = Pt(size)
    st.font.bold = bold
    if color:
        st.font.color.rgb = RGBColor(*color)
    st._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), font)

style_init("Normal", "宋体", 10.5)
style_init("Heading 1", "黑体", 16, True, (22, 58, 95))
style_init("Heading 2", "黑体", 13, True, (47, 93, 80))
style_init("Heading 3", "黑体", 11.5, True, (31, 45, 61))

for name in ("Heading 1", "Heading 2", "Heading 3"):
    doc.styles[name].paragraph_format.space_before = Pt(12)
    doc.styles[name].paragraph_format.space_after = Pt(6)

def p(text="", style=None, size=10.5, bold=False, color=None, align=None, first_line=True):
    para = doc.add_paragraph(style=style) if style else doc.add_paragraph()
    if align is not None:
        para.alignment = align
    else:
        para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    para.paragraph_format.line_spacing = 1.5
    para.paragraph_format.space_after = Pt(4)
    if first_line and not style:
        para.paragraph_format.first_line_indent = Cm(0.74)
    run = para.add_run(text)
    set_font(run, size=size, bold=bold, color=color)
    return para

def bullet(text, level=0):
    para = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    para.paragraph_format.line_spacing = 1.4
    run = para.add_run(text)
    set_font(run, size=10.5)

def h1(text):
    doc.add_page_break()
    doc.add_heading(text, level=1)

def h2(text):
    doc.add_heading(text, level=2)

def h3(text):
    doc.add_heading(text, level=3)

def table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        set_font(run, "黑体", 10, True)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for row in rows:
        cells = t.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(value))
            set_font(run, "宋体", 9.5)
            cells[i].paragraphs[0].paragraph_format.line_spacing = 1.25
    doc.add_paragraph()

def figure(caption):
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run("【此处插入实际界面截图】")
    set_font(run, "宋体", 9, color=(150, 150, 150))
    para2 = doc.add_paragraph()
    para2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = para2.add_run(caption)
    set_font(run2, "宋体", 9)

def add_page_number(section):
    footer = section.footer
    para = footer.paragraphs[0]
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run("第 ")
    set_font(run, size=9)
    fldChar = OxmlElement("w:fldChar")
    fldChar.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fldChar2 = OxmlElement("w:fldChar")
    fldChar2.set(qn("w:fldCharType"), "end")
    run._r.append(fldChar)
    run._r.append(instr)
    run._r.append(fldChar2)
    run2 = para.add_run(" 页")
    set_font(run2, size=9)

# ===== Cover =====
cover = doc.add_paragraph()
cover.alignment = WD_ALIGN_PARAGRAPH.CENTER
cover.paragraph_format.space_before = Pt(80)
r = cover.add_run("软件说明书")
set_font(r, "黑体", 30, True, (22, 58, 95))

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub.paragraph_format.space_before = Pt(28)
r = sub.add_run("砺安题库系统 V1.0")
set_font(r, "黑体", 22, True, (47, 93, 80))

sub2 = doc.add_paragraph()
sub2.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub2.add_run("——每日新闻、每日金句与招考信息模块")
set_font(r, "宋体", 15, False, (80, 90, 100))

line = doc.add_paragraph()
line.alignment = WD_ALIGN_PARAGRAPH.CENTER
line.paragraph_format.space_before = Pt(28)
r = line.add_run("版本：V1.0    编制日期：2026年11月")
set_font(r, "宋体", 11)

info = doc.add_paragraph()
info.alignment = WD_ALIGN_PARAGRAPH.CENTER
info.paragraph_format.space_before = Pt(110)
r = info.add_run("申请人：____________________\n\n软件著作权人：____________________")
set_font(r, "宋体", 11)
info.paragraph_format.line_spacing = 2

doc.add_page_break()

# ===== 文档信息 =====
h1("文档信息")
table(
    ["项目", "内容"],
    [
        ("软件名称", "砺安题库系统"),
        ("版本号", "V1.0"),
        ("说明书名称", "每日新闻、每日金句与招考信息模块软件说明书"),
        ("适用模块", "每日新闻、每日金句、招考信息"),
        ("开发语言", "Python、TypeScript、SQL"),
        ("运行形态", "B/S 架构，浏览器访问"),
        ("编制日期", "2026年11月"),
        ("文档状态", "用于软件著作权申请"),
    ],
)
p("本说明书用于说明“砺安题库系统”中每日新闻、每日金句和招考信息三个业务模块的设计、功能、运行环境、操作方法与技术特点。文档中的界面截图位置已预留，提交前应替换为系统实际运行截图。")

h2("目录")
for item in [
    "1 引言",
    "2 软件概述",
    "3 运行环境",
    "4 系统架构与技术路线",
    "5 功能总览",
    "6 每日新闻模块",
    "7 每日金句模块",
    "8 招考信息模块",
    "9 数据库与数据结构",
    "10 主要接口",
    "11 界面与操作说明",
    "12 异常处理、安全与合规",
    "13 部署与运维",
    "14 版本、范围与声明",
    "附录 A 术语表",
]:
    p(item, first_line=False)

# ===== 1 =====
h1("1 引言")
h2("1.1 编写目的")
p("本说明书面向软件著作权登记、项目验收、运维交接和用户培训，说明砺安题库系统中每日新闻、每日金句与招考信息三个模块的业务目标、功能组成、运行环境、数据流程和操作方式。")
p("本说明书不包含系统全部题库、练习、论坛、支付等其他模块的完整说明；涉及这些模块时，仅说明与三个内容模块的接口关系。")

h2("1.2 适用范围")
p("本说明书适用于系统管理员、内容运营人员、审核人员、前端使用者和软件著作权审查人员。普通考生主要通过浏览器访问每日新闻、每日金句和招考信息；内容运营人员通过采集任务、审核卡片或管理端完成内容治理。")

h2("1.3 术语与缩略语")
table(
    ["术语", "说明"],
    [
        ("每日新闻", "按日采集、清洗、AI 处理、人工审核后展示的时政与公安资讯模块。"),
        ("每日金句", "面向申论素材的格言、论述、评论摘句模块，含来源、标签、收藏与质量审核。"),
        ("招考信息", "公务员、事业单位、教师、国企、医疗、三支一扶等考试与招聘公告模块。"),
        ("AI 摘要", "通过大模型对新闻正文生成摘要、申论考点、实体与风险提示。"),
        ("FTS", "SQLite FTS5 全文检索能力，用于金句内容、作者和出处检索。"),
        ("Obsidian", "本地 Markdown 知识库，用作新闻审核卡片与金句素材的编辑与审核工作台。"),
    ],
)

# ===== 2 =====
h1("2 软件概述")
h2("2.1 建设背景")
p("公安联考备考不仅需要题库训练，还需要持续、稳定、可追溯的时政与申论素材。每日新闻、每日金句和招考信息分别解决“时事素材”“规范表达”和“考试机会”三类信息需求。系统将采集、清洗、AI 处理、人工审核、发布和检索串成一条可运营的内容流水线。")

h2("2.2 模块目标")
bullet("每日新闻：从权威来源采集新闻，清洗正文和图片，生成 AI 摘要与申论考点，经人工审核后发布，并支持时间线、搜索、收藏和笔记。")
bullet("每日金句：从 Obsidian 素材库和授权外部来源获取金句，完成质量审核、来源标注、分类标签、全文检索、去重和每日稳定下发。")
bullet("招考信息：按分类采集公务员、事业单位、教师、国企、医疗和三支一扶信息，过滤噪音，按源站发布日期排序，提供列表、分类筛选和详情查看。")

h2("2.3 用户角色")
table(
    ["角色", "主要操作"],
    [
        ("考生/学生", "浏览新闻、金句和招考信息；收藏、搜索、划线、写想法。"),
        ("内容审核人员", "审核 Obsidian 新闻卡片、管理端金句审核、处理重复金句。"),
        ("内容运营人员", "维护来源配置、执行采集任务、处理采集异常。"),
        ("系统管理员", "部署服务、配置大模型、维护数据库、执行备份和回滚。"),
    ],
)

h2("2.4 模块边界")
p("三个模块共享内容来源、审核、检索和定时任务基础设施，但数据表、接口和页面相互独立。新闻正文不进入金句库，金句不参与新闻时间线，招考信息不与新闻、金句混排。")
figure("图 2-1 三个内容模块的关系示意")

# ===== 3 =====
h1("3 运行环境")
h2("3.1 服务端")
table(
    ["项目", "建议配置"],
    [
        ("操作系统", "Windows 10/11 或 Windows Server；支持 Linux 部署"),
        ("运行时", "Python 3.11 及以上"),
        ("Web 框架", "FastAPI + Uvicorn"),
        ("数据库", "SQLite（WAL 模式），支持后续迁移到 MySQL"),
        ("任务调度", "APScheduler BackgroundScheduler"),
        ("网络", "可访问配置的新闻、金句和招考来源站点；可访问大模型 API"),
        ("磁盘", "用于数据库、新闻图片、Obsidian 知识库和备份文件"),
    ],
)

h2("3.2 客户端")
table(
    ["项目", "建议配置"],
    [
        ("浏览器", "Chrome、Edge 等现代浏览器"),
        ("分辨率", "PC 建议 1366×768 以上；手机端自适应"),
        ("网络", "可访问系统 Web 服务"),
    ],
)

h2("3.3 开发与运行组件")
table(
    ["层级", "组件"],
    [
        ("前端", "Vue 3、TypeScript、Vite、Element Plus、VTJ 低代码页面、Pinia、Vue Router"),
        ("后端", "FastAPI、SQLAlchemy 2.x、Pydantic、APScheduler"),
        ("采集解析", "Requests、BeautifulSoup、可选的 Playwright（仅对需要浏览器渲染的来源）"),
        ("AI", "OpenAI Chat Completions 兼容接口的大模型服务"),
        ("数据", "SQLite WAL、FTS5、本地 JSON/图片存储、Obsidian Markdown 文件"),
    ],
)

# ===== 4 =====
h1("4 系统架构与技术路线")
h2("4.1 总体架构")
p("系统采用 B/S 架构。浏览器通过 Vue 前端调用 FastAPI 接口；后端按内容域组织 API、模型、采集服务、审核服务和定时任务；SQLite 保存结构化数据；本地文件系统保存新闻图片和 Obsidian 知识库；大模型负责摘要与质量辅助判断。")
figure("图 4-1 系统总体架构图")

h2("4.2 内容流水线")
p("三个模块共用“来源配置—采集—解析清洗—结构化入库—AI 辅助—人工审核—发布—检索/展示”的内容流水线。新闻增加 Obsidian 审核卡片与投影；金句增加每日快照、质量审核、标签和 FTS；招考信息增加分类、分页与源站发布日期排序。")

h2("4.3 定时任务")
table(
    ["时间（北京时间）", "任务", "说明"],
    [
        ("00:05", "招考信息采集", "采集六类招考信息，按源站发布日期排序入库。"),
        ("00:05", "每日金句预生成", "生成 daily_quote 当日快照，保证三端同日一致。"),
        ("00:10", "金句 Obsidian 同步与质量审核", "同步素材库，审核待处理金句。"),
        ("06:00", "外部金句采集", "采集五个授权外部来源，候选金句先进入待审。"),
        ("08:00 / 18:00", "每日新闻采集", "每个来源最多扫描 15 条，每日每源最多入库 5 条。"),
    ],
)

# ===== 5 =====
h1("5 功能总览")
table(
    ["模块", "核心功能", "主要用户"],
    [
        ("每日新闻", "来源采集、正文清洗、图片过滤、AI 摘要/考点/实体/风险、Obsidian 审核、发布、时间线、日报、搜索、收藏、笔记、AI 卡片", "考生、审核人员"),
        ("每日金句", "Obsidian 同步、外部来源采集、每日快照、AI 质量审核、来源/标签、FTS、去重、收藏、金句库、管理端审核", "考生、审核人员"),
        ("招考信息", "六类来源采集、分页、噪音过滤、发布日期排序、分类筛选、详情查看、移动端", "考生、内容运营"),
    ],
)

# ===== 6 =====
h1("6 每日新闻模块")
h2("6.1 功能概述")
p("每日新闻模块面向公安联考时政与法治素材，提供从权威站点的列表发现、正文解析、图片治理、AI 加工、人工审核到前端展示的完整链路。")

h2("6.2 来源与采集")
p("新闻来源以配置形式维护，包含来源代码、名称、入口地址、列表地址、分类、地区、可信度、启停状态和适配方式。采集器按来源抓取列表，提取文章链接，解析标题、正文、发布时间与图片。")
bullet("每日 08:00 和 18:00 执行采集任务。")
bullet("每个来源最多扫描 15 条列表链接，跳过已存在新闻，最多入库 5 条新新闻。")
bullet("按 URL、标题和正文内容哈希去重。")
bullet("对部分需要浏览器渲染的来源使用 Playwright；其余使用普通 HTTP。")

h2("6.3 正文与图片清洗")
p("解析器优先定位 article、content_main、正文容器等语义节点，移除 footer、aside、相关新闻、推荐阅读、版权、ICP 备案、举报电话、服务邮箱等非正文内容。正文按段落输出，段间保留空行；图片按正文顺序生成 [[IMG:n]] 标记，前端按标记位置内联渲染。")

h2("6.4 AI 处理")
p("对未处理新闻调用大模型，输出结构化 JSON：摘要、申论考点、官方表述、实体、风险提示和置信度。摘要要求完整成句，长度上限 400 字，避免旧版 100 字截断。命中高风险规则时进入 high_risk 审核状态。")
table(
    ["AI 字段", "用途"],
    [
        ("ai_summary", "新闻摘要，用于列表、详情和审核卡片。"),
        ("ai_exam_points", "申论考点，用于详情 AI 面板。"),
        ("ai_entities", "人物、组织、政策、地域等实体标签。"),
        ("ai_risk_flags", "需要人工核对的风险提示。"),
        ("ai_status", "ok/fallback/high_risk 等处理状态。"),
    ],
)

h2("6.5 人工审核与发布")
p("AI 处理后的新闻保持 pending 状态，导出为 Obsidian Markdown 审核卡片，卡片包含摘要、申论考点、实体、正文、图片、风险提示和审核勾选项。审核人员在 Obsidian 中勾选通过、拒绝或退回修改；执行同步命令后回写数据库并重建投影。")
p("审核通过后才进入 published 状态；前端只展示已发布新闻。审核过程不自动发布，确保内容安全。")

h2("6.6 前端功能")
bullet("新闻时间线：按发布日期分组，左侧日期与浅色竖线形成时间轴。")
bullet("新闻详情：标题、来源、分类、日期、AI 摘要、申论考点、实体、正文、图片和收藏。")
bullet("搜索：按标题、摘要和正文关键词查询。")
bullet("收藏：收藏新闻并在新闻收藏页集中展示。")
bullet("笔记：选中正文可划线、写想法，支持删除；移动端同步。")
bullet("移动端：每日新闻卡片展示摘要、分类、日期、收藏和更多入口。")

h2("6.7 数据表")
table(
    ["数据表", "作用"],
    [
        ("news_article", "新闻主表，含标题、正文、AI 字段、审核状态、来源、发布时间。"),
        ("news_image", "新闻图片表，记录图片路径和顺序。"),
        ("news_favorite", "用户新闻收藏。"),
        ("news_read", "用户新闻已读记录。"),
        ("news_note", "新闻划线、想法与笔记。"),
    ],
)

h2("6.8 操作流程")
p("运营人员维护来源配置 → 定时或手动触发采集 → 系统清洗并调用 AI → 生成 Obsidian 待审卡片 → 审核人员勾选 → 执行同步 → 复核投影 → 考生在新闻时间线和详情页浏览。")
figure("图 6-1 每日新闻时间线界面")
figure("图 6-2 新闻详情 AI 卡片与正文界面")

# ===== 7 =====
h1("7 每日金句模块")
h2("7.1 功能概述")
p("每日金句模块为申论提供短小、规范、可引用的素材，覆盖古典名句、公安专题、政治、法治、民生、文化、生态、经济等类别。系统同时支持 Obsidian 素材库和授权外部来源。")

h2("7.2 来源")
table(
    ["来源", "接入方式", "说明"],
    [
        ("Obsidian 金句素材库", "本地 Markdown 同步", "读取 frontmatter 中的 quote、author、source、topics、status。"),
        ("人民网·理论频道", "外部网页采集", "理论、评论类文章。"),
        ("光明网·时评频道", "外部网页采集", "评论员文章。"),
        ("求是网", "外部网页采集", "理论、党建文章。"),
        ("中央纪委国家监委网站", "外部网页采集", "党建、理论、评论文章。"),
        ("共产党员网", "外部网页采集", "党建、讲话、教材原文。"),
    ],
)

h2("7.3 每日快照")
p("系统在每日 00:05 生成 daily_quote 记录，以日期为键保存当天 quote_id。每日金句接口优先读取该快照，保证同一天不同设备、不同端看到同一句；快照不存在时按日期种子选择并幂等补生成。")

h2("7.4 质量审核与隔离")
p("金句不是“同步即可发布”。系统先执行规则检查，再调用大模型判断内容完整度、出处可靠性、是否适合作为申论素材。审核结果写入 ai_quality、ai_quality_reason、quality_score 和 quote_review。")
bullet("approved：status=1，允许展示。")
bullet("rejected：status=0，从列表、每日金句和随机池隔离。")
bullet("pending：等待审核，不直接展示。")
bullet("伪作者（引号、破折号、佚名等）归一为空；古典名句允许只有书名/篇名出处。")

h2("7.5 来源、标签与检索")
p("每条金句关联 content_source 来源记录；分类写入 topic，并通过 quote_tag 建立多对多标签；quote_fts 使用 FTS5 建立内容、作者、来源全文索引。前台金句库支持关键词、作者/出处和分类组合检索。")

h2("7.6 去重与关系")
p("系统对内容做归一化哈希，建立 quote_relation 的 duplicate_of 关系。管理端按重复分组展示 canonical 金句和重复项，审核人员确认后可合并；合并会把重复项下线并写入审核流水。")

h2("7.7 前端功能")
bullet("每日金句卡：分类标签、金句正文、作者/出处、收藏、换一句、金句库入口。")
bullet("金句库：关键词、作者/出处、分类筛选、收藏、分页。")
bullet("金句收藏：独立路径，不与新闻收藏混排。")
bullet("移动端：每日金句卡、金句库、搜索、收藏和分类标签。")

h2("7.8 管理端")
p("管理端 /admin/quotes 提供待审核、已通过、已拒绝、重复金句、来源分布和标签分布。审核操作写入 quote_review，保留管理员、原因、前后状态和质量分。")
figure("图 7-1 金句库界面")
figure("图 7-2 管理端金句审核界面")

# ===== 8 =====
h1("8 招考信息模块")
h2("8.1 功能概述")
p("招考信息模块汇总公务员、事业单位、教师、国企、医疗和三支一扶等考试与招聘公告，帮助考生集中查看报名时间、岗位要求、考试方式和原始链接。")

h2("8.2 来源与分类")
table(
    ["分类", "采集入口", "说明"],
    [
        ("国考省考", "国考、省考列表", "公务员考试公告与相关通知。"),
        ("事业单位", "事业单位列表", "事业单位招聘公告。"),
        ("教师招聘", "教师招聘列表", "教师岗位招聘。"),
        ("国企招聘", "国企招聘列表", "国有企业招聘。"),
        ("医疗卫生", "医疗卫生列表", "医院与卫生系统招聘。"),
        ("三支一扶", "三支一扶列表", "基层服务项目招募。"),
    ],
)

h2("8.3 采集与清洗")
p("采集器按分类独立抓取列表，解析标题、详情链接、源站发布日期、发布单位、地区、正文、要求、联系方式、考试方式、附件和图片。支持 Empire CMS 分页识别，单分类最多抓取 5 页。")
p("系统过滤准考证打印、成绩查询、报名指南、考试大纲、咨询电话等操作类噪音；按源站发布日期排序，避免使用入库时间导致旧内容排在前面。")

h2("8.4 接口与前端")
table(
    ["接口", "用途"],
    [
        ("GET /api/recruitment", "招考列表，支持分类、地区、关键词和状态筛选。"),
        ("GET /api/recruitment/categories", "分类及数量。"),
        ("GET /api/recruitment/{id}", "招考详情。"),
    ],
)
p("前端提供招考列表、分类标签、截止状态、详情页和移动端页面；列表展示标题、发布单位、地区、分类、报名时间和标签，详情展示正文、要求、联系方式与原文链接。")
figure("图 8-1 招考信息列表界面")
figure("图 8-2 招考信息详情界面")

h2("8.5 定时任务")
p("每日 00:05 执行招考采集任务；首次启动时也会执行一次初始化采集。采集失败保留历史数据，避免因单个来源不可用导致列表清空。")

# ===== 9 =====
h1("9 数据库与数据结构")
h2("9.1 新闻数据")
table(
    ["字段/表", "说明"],
    [
        ("news_article.title", "新闻标题。"),
        ("news_article.content", "清洗后的正文，可含 [[IMG:n]] 标记。"),
        ("news_article.ai_summary", "AI 摘要。"),
        ("news_article.ai_exam_points", "申论考点 JSON。"),
        ("news_article.ai_entities", "实体 JSON。"),
        ("news_article.ai_risk_flags", "风险提示 JSON。"),
        ("news_article.review_status", "pending/published/rejected/high_risk。"),
    ],
)
h2("9.2 金句数据")
table(
    ["字段/表", "说明"],
    [
        ("essay_quote.content", "金句正文。"),
        ("essay_quote.author/source/category", "作者、出处、分类。"),
        ("essay_quote.ai_quality", "质量审核状态。"),
        ("essay_quote.source_id", "来源表外键。"),
        ("essay_quote.normalized_hash", "去重哈希。"),
        ("daily_quote", "每日快照。"),
        ("quote_review", "审核流水。"),
        ("quote_tag/topic", "标签关联。"),
        ("quote_fts", "FTS5 全文索引。"),
        ("quote_relation", "重复关系。"),
    ],
)
h2("9.3 招考数据")
p("recruitment_info 保存标题、发布单位、分类、地区、正文、HTML 正文、要求、图片、报名时间、考试方式、联系方式、标签、浏览量、原文链接、源站发布日期和状态。")

# ===== 10 =====
h1("10 主要接口")
table(
    ["接口", "方法", "用途"],
    [
        ("/api/news", "GET", "新闻列表，支持分类、关键词、来源、分页。"),
        ("/api/news/{id}", "GET", "新闻详情与 AI 字段。"),
        ("/api/news/{id}/favorite", "POST", "收藏/取消收藏。"),
        ("/api/news/{id}/note", "POST", "新闻划线或想法。"),
        ("/api/news/timeline", "GET", "新闻时间线。"),
        ("/api/quotes", "GET", "金句列表，支持分类、关键词、作者。"),
        ("/api/quotes/quote/daily", "GET", "每日金句快照。"),
        ("/api/quotes/search", "GET", "FTS 全文检索。"),
        ("/api/quotes/{id}/favorite", "POST", "金句收藏。"),
        ("/api/admin/quotes/review", "GET", "管理端待审金句。"),
        ("/api/admin/quotes/{id}/review", "POST", "管理端人工审核。"),
        ("/api/admin/quotes/duplicates", "GET", "重复金句分组。"),
        ("/api/recruitment", "GET", "招考列表。"),
        ("/api/recruitment/categories", "GET", "招考分类。"),
        ("/api/recruitment/{id}", "GET", "招考详情。"),
    ],
)

# ===== 11 =====
h1("11 界面与操作说明")
h2("11.1 新闻时间线")
p("进入“新闻时间线”后，页面按日期展示已发布新闻。左侧日期和浅色竖线构成时间轴；右侧卡片显示标题、摘要、来源和分类。点击卡片进入详情。")
figure("图 11-1 新闻时间线")
h2("11.2 新闻详情")
p("详情页展示标题、来源、分类、发布日期、AI 摘要、申论考点、实体、正文和图片。右上角可收藏；选中正文后出现 5 色划线和“写想法”菜单；下方显示笔记列表。")
figure("图 11-2 新闻详情 AI 面板")
h2("11.3 金句库")
p("进入“金句库”后，可按分类切换，输入关键词或作者/出处检索。金句卡片显示分类、正文、作者/出处和收藏星标；点击收藏后星标变为金色。")
figure("图 11-3 金句库")
h2("11.4 金句管理端")
p("管理员进入 /admin/quotes，可按待审核、已通过、已拒绝、重复金句、来源和标签查看。待审核卡片可填写备注并点击通过或拒绝；重复项可合并到 canonical 金句。")
figure("图 11-4 金句管理端")
h2("11.5 招考信息")
p("进入招考信息页面后，按分类查看公告。列表显示标题、发布单位、地区、分类、报名时间和标签；点击进入详情，可查看正文、要求、联系方式和原文链接。")
figure("图 11-5 招考信息列表")

# ===== 12 =====
h1("12 异常处理、安全与合规")
h2("12.1 采集异常")
bullet("单个来源失败记录错误，不影响其他来源和已有数据。")
bullet("图片下载失败不阻断新闻入库；图片过滤失败回退文本展示。")
bullet("招考采集整体失败时保留历史数据，避免列表清空。")
bullet("大模型调用失败时记录 fallback，新闻仍保留正文，待后续重试。")

h2("12.2 审核安全")
bullet("新闻默认不自动发布；必须经过人工审核回写。")
bullet("金句默认 pending/status=0，经过质量审核后才进入展示。")
bullet("审核操作写入独立流水，保留管理员、时间、原因和状态变化。")

h2("12.3 数据安全")
bullet("数据库使用 SQLite WAL；批量修改前使用 sqlite3.backup() 备份。")
bullet("密钥、数据库连接信息不写入说明书。")
bullet("外部采集遵守来源 robots、服务条款和引用规范，保留来源与作者。")
bullet("用户收藏、笔记只对本人可见；管理接口校验管理员角色。")

h2("12.4 合规说明")
p("外部金句来源须经申请人确认授权；采集器使用固定 User-Agent、串行请求和请求间隔，不绕过登录、验证码或访问控制。引用内容保留来源和作者署名，不将他人长文作为自有内容发布。")

# ===== 13 =====
h1("13 部署与运维")
h2("13.1 启动")
p("后端在 backend 目录启动 FastAPI 服务，前端构建后由 Web 服务托管或使用 Vite 开发服务访问。首次启动自动创建数据表、初始化必要索引和调度任务。")
h2("13.2 配置")
p("配置项包括数据库路径、新闻来源、外部金句来源、Obsidian 路径、大模型接口地址与密钥、调度时区等。敏感配置通过环境变量或本地配置文件管理，不纳入版本库。")
h2("13.3 日常运维")
bullet("查看日志中的采集数量、AI 成功/失败数量、审核数量和任务异常。")
bullet("定期执行数据库备份，保留回滚文件。")
bullet("监控外部来源可达性和 robots 变化；来源失效时停用而不是强行绕过。")
bullet("人工抽检 AI 摘要、金句质量和招考信息排序。")

# ===== 14 =====
h1("14 版本、范围与声明")
h2("14.1 版本")
p("本说明书对应砺安题库系统 V1.0，覆盖每日新闻、每日金句和招考信息三个模块。")
h2("14.2 范围声明")
p("本说明书仅描述上述三个模块，不包含题库练习、试卷生成、论坛、支付、成就等模块的完整功能。系统实际界面和字段以运行版本为准；截图提交前需替换为实际运行截图。")
h2("14.3 著作权声明")
p("本说明书及所述软件模块的著作权归申请人/著作权人所有。未经书面许可，任何单位或个人不得复制、传播或用于商业用途。")
p("申请人：____________________")
p("日期：______年____月____日")

# ===== 附录 =====
h1("附录 A 术语表")
table(
    ["术语", "解释"],
    [
        ("B/S", "Browser/Server，浏览器/服务器架构。"),
        ("API", "应用程序编程接口。"),
        ("FTS5", "SQLite 全文检索扩展。"),
        ("WAL", "SQLite 预写日志模式。"),
        ("fallback", "AI 调用失败时的降级结果。"),
        ("canonical", "重复组中保留的主金句。"),
    ],
)

# header/footer
for section in doc.sections:
    add_page_number(section)
    header = section.header.paragraphs[0]
    header.text = "砺安题库系统 V1.0  软件说明书"
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in header.runs:
        set_font(run, size=9, color=(120, 120, 120))

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
print(OUT)
