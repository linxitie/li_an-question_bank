<template>
  <div class="mm-page">
    <AdminPageHeader
      title="资料管理"
      desc="唯一入口：卡片 / 文章 / 视频 / 讲义 / 试卷 · 试卷「上架」即审批通过，未上架即未通过"
    >
      <template #actions>
        <button class="adm-btn adm-btn--line" :disabled="loading" @click="reload">刷新</button>
        <router-link class="adm-btn adm-btn--line" to="/admin/materials/legacy">旧版（临时）</router-link>
        <button class="adm-btn" :disabled="loading" @click="openUpload('paper')">＋ 上传试卷</button>
        <button class="adm-btn adm-btn--primary" :disabled="loading" @click="openUpload('lecture')">
          批量导入
        </button>
        <!-- L4（2026-11-09）：文章要正文，走"解析导入"链路（逐条上传→解析→入库） -->
        <button class="adm-btn adm-btn--line" :disabled="loading" @click="articleUploadOpen = true">
          批量上传文章
        </button>
      </template>
    </AdminPageHeader>

    <!-- 统计行：5 格（2026-11-07 定） -->
    <div class="mm-stats">
      <AdminStatCard label="总资料" :value="stats.total" icon="📚" />
      <AdminStatCard label="试卷" :value="stats.paper" icon="📄" tone="warn" />
      <AdminStatCard label="文章/讲义" :value="stats.article" :value2="stats.lecture" icon="📘" />
      <AdminStatCard label="卡片" :value="stats.card" icon="🗂️" />
      <AdminStatCard
        label="已上架/未上架"
        :value="stats.published"
        :value2="stats.draft"
        icon="✅"
        tone="ok"
        value2-tone="warn"
      />
    </div>

    <AdminToolbar>
      <select v-model="filters.subject" class="adm-select" @change="applyFilter">
        <option value="">全部科目</option>
        <option value="xingce">行测</option>
        <option value="shenlun">申论</option>
        <option value="gongzhuan">公专</option>
      </select>
      <select v-model="filters.type" class="adm-select" @change="applyFilter">
        <option value="">全部类型</option>
        <option v-for="t in MATERIAL_TYPES" :key="t.key" :value="t.key">{{ t.label }}</option>
      </select>
      <select v-model="filters.status" class="adm-select" @change="applyFilter">
        <option value="">全部状态</option>
        <option value="1">已上架（=通过）</option>
        <option value="0">未上架（=未通过）</option>
        <option value="-1">回收站（已删除）</option>
      </select>
      <!-- C3：试卷专属筛选（年份/地区/卷别）——只在「类型=试卷」时出现，
           因为只有试卷带这套元数据；选回其它类型时自动清空，避免"筛了却看不到原因" -->
      <template v-if="filters.type === 'paper'">
        <select v-model="filters.paperYear" class="adm-select" @change="applyFilter">
          <option value="">全部年份</option>
          <option v-for="y in yearOptions" :key="y" :value="String(y)">{{ y }} 年</option>
        </select>
        <select v-model="filters.region" class="adm-select" @change="applyFilter">
          <option value="">全部地区</option>
          <option v-for="r in PAPER_REGIONS" :key="r.code" :value="r.code">{{ r.name }}</option>
        </select>
        <select v-model="filters.bookKind" class="adm-select" @change="applyFilter">
          <option value="">全部卷别</option>
          <option v-for="k in BOOK_KINDS" :key="k.code" :value="k.code">{{ k.name }}</option>
        </select>
      </template>
      <select v-model="filters.createdWithin" class="adm-select" @change="applyFilter">
        <option value="">全部时间</option>
        <option value="7d">最近 7 天</option>
        <option value="30d">最近 30 天</option>
      </select>
      <input
        v-model="filters.keyword"
        class="adm-input"
        style="width: 200px"
        placeholder="搜索标题 / 分类…"
        @keyup.enter="applyFilter"
      />
      <template #actions>
        <span v-if="filters.status === '-1'" class="mm-chip">
          回收站：只看已删除资料，点「恢复」可还原
        </span>
        <span v-if="filters.createdWithin" class="mm-chip">
          最近 {{ filters.createdWithin === '7d' ? 7 : 30 }} 天：{{ total }} 条
        </span>
        <button class="adm-btn" @click="applyFilter">搜索</button>
        <button class="adm-btn adm-btn--line" @click="resetFilters">重置</button>
      </template>
    </AdminToolbar>

    <!-- A7（2026-11-08）：批量操作条。只作用于**当前页**已勾选的行；
         回收站视图不显示勾选（那边的动作是「恢复」，不是批量增删）。 -->
    <div v-if="selected.length > 0" class="mm-batchbar">
      <span class="mm-batchbar__count">已选 <b>{{ selected.length }}</b> 条</span>
      <button class="adm-btn adm-btn--sm" :disabled="batchRunning" @click="batchSetStatus(1)">批量上架</button>
      <button class="adm-btn adm-btn--sm adm-btn--line" :disabled="batchRunning" @click="batchSetStatus(0)">批量下架</button>
      <button class="adm-btn adm-btn--sm adm-btn--danger" :disabled="batchRunning" @click="batchRemove">批量删除</button>
      <button class="adm-btn adm-btn--sm adm-btn--line" :disabled="batchRunning" @click="clearSelection">取消选择</button>
      <span v-if="batchRunning" class="mm-batchbar__hint">处理中…</span>
      <span v-else class="mm-batchbar__hint">删除=移入回收站（可恢复）；上/下架会同步影响学生端可见性</span>
    </div>

    <AdminTable :empty="!loading && rows.length === 0" empty-text="暂无数据 · 换个筛选条件试试">
      <table>
        <thead>
          <tr>
            <th v-if="!isRecycleView" style="width: 36px">
              <input
                type="checkbox"
                class="mm-check"
                :checked="isAllSelected(rows, selected)"
                :indeterminate="isPartialSelected(rows, selected)"
                aria-label="全选当前页"
                @change="toggleSelectAll"
              />
            </th>
            <!-- ID 方案 A（2026-11-08）：这里显示的是**连续序号**（当前筛选内倒序名次，
                 首行 = 总数），不是数据库主键。真实主键在单元格 title 里（悬停可见）。
                 回收站视图不参与编号，显示「—」。 -->
            <th style="width: 52px" title="按列表顺序倒排：最上面一行 = 当前结果总数">编号</th>
            <th>标题 / 类型</th>
            <th style="width: 48px">科目</th>
            <th style="width: 78px">分类</th>
            <!-- L4（2026-11-09）：投放位（仅试卷有意义）——上架后"进考试页/进资料库/两边都进" -->
            <th style="width: 70px" title="仅试卷类有意义：考试=只在考试页；资料=只在资料库；都投=两边都放">投放位</th>
            <!-- P2（2026-11-09）：考试开关 + 定时。与「上架」独立：
                 上架=资料在不在库里；这里=学生能不能进考试（关闭不影响历史成绩） -->
            <th
              style="width: 140px"
              title="开关=学生能不能进这场考试；与「上架」独立。定时=只在时间窗内可进（到点自动，不靠后台任务）"
            >考试（可进入）</th>
            <th style="width: 104px">发布者</th>
            <th class="mm-sortable" style="width: 100px" @click="toggleOrder"
                title="按真实上传时间排序（NULL 恒排最后）；编号列始终按列表时间倒序">
              上传时间 {{ timeOrderArrow }}
            </th>
            <th style="width: 44px">浏览</th>
            <th style="width: 116px">上架（=审批）</th>
            <th style="width: 150px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td :colspan="isRecycleView ? 11 : 12" class="mm-loading">加载中…</td>
          </tr>
          <tr v-for="row in rows" :key="row.id">
            <td v-if="!isRecycleView">
              <input
                type="checkbox"
                class="mm-check"
                :checked="selected.includes(row.id)"
                :aria-label="`选择 ${row.title}`"
                @change="onToggleRow(row.id)"
              />
            </td>
            <td class="adm-mono" :title="`内部 ID: ${row.id}`">
              {{ filters.status === '-1' ? '—' : (row.seq ?? row.id) }}
            </td>
            <td>
              <div class="mm-title">
                <b>{{ row.title }}</b>
                <AdminTag :type="row.type">{{ materialTypeLabel(row.type) }}</AdminTag>
              </div>
              <div v-if="row.type === 'paper'" class="mm-sub">
                <span class="adm-mono">{{ paperCodeOf(row) || '—' }}</span>
                <span v-if="row.category" class="mm-dot">·</span>
                <span v-if="row.category">{{ row.category }}</span>
                <!-- 2026-11-09 修：管理端列表此前没算原件数（恒 0），后端补上后这里才有意义 -->
                <span v-if="row.file_count" class="mm-dot">·</span>
                <span v-if="row.file_count">原件 {{ row.file_count }}</span>
                <!-- P3：解析草稿状态（点一下进「导题确认」） -->
                <span
                  v-if="parseChip(row)"
                  class="mm-parse"
                  :class="`is-${row.parse_draft?.status}`"
                  :title="parseChipTitle(row)"
                  @click="openDraft(row)"
                >{{ parseChip(row) }}</span>
              </div>
              <!-- C1：讲义行给规模，便于一眼判断"是不是那份长讲义" -->
              <div v-else-if="row.type === 'lecture'" class="mm-sub">
                <span v-if="row.chapter_count">{{ row.chapter_count }} 章</span>
                <span v-if="row.chapter_count && row.word_count" class="mm-dot">·</span>
                <span v-if="row.word_count">{{ formatWords(row.word_count) }}</span>
                <span v-if="!row.chapter_count && !row.word_count">
                  {{ row.file_count ? `原件 ${row.file_count}` : '未解析大纲' }}
                </span>
                <template v-else>
                  <span v-if="row.file_count" class="mm-dot">·</span>
                  <span v-if="row.file_count">原件 {{ row.file_count }}</span>
                </template>
              </div>
            </td>
            <td>{{ subjectLabel(row.subject) }}</td>
            <td>{{ row.category || '—' }}</td>
            <td>
              <AdminTag v-if="row.type === 'paper'" :tone="placementTone(row.placement)">
                {{ placementLabel(row.placement) }}
              </AdminTag>
              <span v-else>—</span>
            </td>
            <!-- P2：考试开关。仅「试卷 + 投放位含考试页」显示；0 题时开关灰掉并说明原因 -->
            <td class="mm-exam-cell">
              <template v-if="examSwitchVisible(row)">
                <div class="mm-exam">
                  <button
                    class="mm-switch"
                    :class="{ 'is-on': examSwitchOn(row.exam) }"
                    :disabled="!examSwitchEnabled(row.exam) || examBusyId === row.id"
                    :title="examSwitchHint(row.exam)"
                    :aria-label="examSwitchOn(row.exam) ? '关闭考试' : '打开考试'"
                    @click="toggleExam(row)"
                  >
                    <i />
                  </button>
                  <span class="mm-exam__text">
                    <AdminTag :tone="examStatusTone(row.exam)">{{ examStatusLabel(row.exam) }}</AdminTag>
                    <span class="mm-exam__sub">{{ examTimingText(row.exam) }}</span>
                  </span>
                </div>
                <!-- 0 题没有定时可设（开了也进不去），但保留入口让人看得到"为什么" -->
                <a
                  class="mm-exam__timer"
                  :class="{ 'is-muted': !row.exam?.known }"
                  :title="row.exam?.known ? '只在时间窗内允许学生进入；留空=不限' : '还没有可作答卷'"
                  @click="openExamWindow(row)"
                >设置定时</a>
              </template>
              <span v-else>—</span>
            </td>
            <td class="mm-pub-cell">
              <span v-if="row.publisher" class="mm-pub">
                {{ row.publisher.name }}<span class="mm-role">（{{ row.publisher.role_label }}）</span>
              </span>
              <span v-else>—</span>
            </td>
            <td class="adm-mono mm-time">{{ fmtTime(row.created_at) }}</td>
            <td>{{ row.view_count || 0 }}</td>
            <td class="mm-status-cell">
              <template v-if="row.status === -1">
                <AdminTag tone="danger">已删除</AdminTag>
              </template>
              <template v-else>
                <button
                  class="mm-switch"
                  :class="{ 'is-on': row.status === 1 }"
                  :aria-label="row.status === 1 ? '下架' : '上架（=审批通过）'"
                  @click="toggleStatus(row)"
                >
                  <i />
                </button>
                <AdminTag :tone="row.status === 1 ? 'ok' : 'muted'" style="margin-left: 6px">
                  {{ row.status === 1 ? '已通过' : '未通过' }}
                </AdminTag>
              </template>
            </td>
            <td class="mm-ops">
              <a class="mm-op" @click="openPreview(row)">预览</a>
              <template v-if="row.status === -1">
                <a class="mm-op is-restore" @click="restore(row)">恢复</a>
              </template>
              <template v-else>
                <!-- A2（2026-11-08）：试卷资料 → 题库里的可作答卷（DRAFT；上架后经 P5 自动 PUBLISHED）。
                     没有编号的试卷资料不显示；已有卷时不显示（P1 起上传即建卷，重复建没有意义）。 -->
                <a
                  v-if="row.type === 'paper' && paperCodeOf(row) && !row.exam?.known"
                  class="mm-op"
                  title="在题库里为这份试卷资料建一张可作答卷（草稿；资料上架后学生即可考）"
                  @click="ensurePaper(row)"
                >建卷</a>
                <!-- P3（2026-11-09）：导题。有草稿 → 打开确认页；没草稿 → 直接解析原件 -->
                <a
                  v-if="row.type === 'paper' && row.file_count"
                  class="mm-op"
                  :title="row.parse_draft?.status === 'pending'
                    ? `打开导题确认（已拆出 ${row.parse_draft.item_count} 题）`
                    : '解析原件里的题目（docx/pdf），先出待确认清单再入库'"
                  @click="openDraft(row)"
                >{{ row.parse_draft?.status === 'pending' ? '待确认' : '导题' }}</a>
                <!-- P4（2026-11-09）：补答案（需要已有可作答卷，且卷里有题） -->
                <a
                  v-if="row.type === 'paper' && row.exam?.known && row.exam.question_count"
                  class="mm-op"
                  :title="`上传答案 PDF 补这 ${row.exam.question_count} 题的答案与解析`"
                  @click="openAnswer(row)"
                >补答案</a>
                <a class="mm-op" @click="openMeta(row)">改信息</a>
                <a class="mm-op is-danger" @click="remove(row)">删除</a>
              </template>
            </td>
          </tr>
        </tbody>
      </table>      <template #footer>
        <div class="mm-pager">
          <span>共 {{ total }} 条 · 每页 {{ pageSize }}</span>
          <button class="adm-btn adm-btn--sm adm-btn--line" :disabled="page <= 1" @click="goto(page - 1)">上一页</button>
          <span class="adm-mono">{{ page }} / {{ maxPage }}</span>
          <button class="adm-btn adm-btn--sm adm-btn--line" :disabled="page >= maxPage" @click="goto(page + 1)">下一页</button>
        </div>
      </template>
    </AdminTable>

    <MaterialPreviewDrawer
      :open="drawerOpen"
      :preview="preview"
      :loading="previewLoading"
      :error="previewError"
      @close="drawerOpen = false"
    />

    <MaterialMetaDialog
      :open="metaOpen"
      :material-id="metaId"
      :type-label="metaTypeLabel"
      @close="metaOpen = false"
      @saved="onMetaSaved"
    />

    <!-- P2（2026-11-09）：考试定时弹层（开关在列表里点，这里只设时间窗） -->
    <ExamGateDialog
      :open="examWinOpen"
      :material-id="examWinId"
      :paper-code="examWinCode"
      :paper-name="examWinName"
      :exam="examWinExam"
      @close="examWinOpen = false"
      @saved="onExamWindowSaved"
    />

    <MaterialBatchUpload
      :open="uploadOpen"
      :preset-type="uploadType"
      :title="uploadType === 'paper' ? '上传试卷（原件留档）' : '批量导入资料'"
      @close="uploadOpen = false"
      @done="onUploaded"
    />

    <!-- L4：文章批量上传（走解析导入，正文可读） -->
    <ArticleBatchUpload
      :open="articleUploadOpen"
      :default-subject="articleDefaultSubject"
      @close="articleUploadOpen = false"
      @done="onUploaded"
    />

    <!-- P3（2026-11-09）：导题确认抽屉（拆题结果逐题核对 → 确认入库） -->
    <ParseDraftDrawer
      :open="draftOpen"
      :draft-id="draftId"
      :material-id="draftMaterialId"
      @close="draftOpen = false"
      @confirmed="onDraftConfirmed"
      @discarded="onDraftDiscarded"
    />

    <!-- P4（2026-11-09）：补答案抽屉（上传答案 PDF → 逐题核对 → 写入答案/解析） -->
    <AnswerDraftDrawer
      :open="answerOpen"
      :paper-id="answerPaperId"
      :paper-code="answerPaperCode"
      :paper-name="answerPaperName"
      @close="answerOpen = false"
      @applied="onAnswerApplied"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * 资料管理（A4 · 2026-11-07）—— 替换 `.vtj/vue/admin_materials.vue` 的手写页
 *
 * 为什么替换：R3 禁止改 `.vtj` 模板，而本轮要加 6 类筛选、发布者列、上传时间列（可排序）、
 * 时间范围、每行预览、试卷列、上架即审批——这些都在表格结构里，低代码页做不了。
 * 旧页**不删不改**（R1），保留在 `/admin/materials/legacy` 供「智能导入 / 富文本编辑 / 批量操作」
 * 过渡使用，B 批用新页重建后下线。
 *
 * 本版（v1）范围：列表/筛选/排序/分页 + 5 格统计 + 上架（=审批）+ 删除 + 预览抽屉。
 * 未在 v1：上传试卷（等 B 批 material_file）、改信息（C 批）、批量操作、智能导入向导。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { ElMessage } from 'element-plus';
import {
  AdminPageHeader,
  AdminStatCard,
  AdminTable,
  AdminTag,
  AdminToolbar,
  MaterialPreviewDrawer,
  MaterialBatchUpload,
  MaterialMetaDialog,
  ArticleBatchUpload,
  ExamGateDialog,
  ParseDraftDrawer,
  AnswerDraftDrawer
} from '@/components/admin';
import {
  MATERIAL_PLACEMENTS,
  MATERIAL_TYPES,
  materialTypeLabel,
  normalizePlacement,
  placementLabel,
  placementTone
} from '@/modules/library/materialTypes';
import { BOOK_KINDS, PAPER_REGIONS } from '@/utils/paperRegions';
import { parseListQuery } from '@/utils/materialListQuery';
import { errorMessage } from '@/utils/apiError';
import { confirmOverlay, notify } from '@/utils/overlay';
import {
  batchSummary,
  isAllSelected,
  isPartialSelected,
  pickSelected,
  targetsForStatus,
  toggleAll,
  toggleOne,
  type BatchStatus
} from '@/utils/materialBatch';
import {
  fetchAdminMaterialList,
  fetchAdminMaterialStats,
  fetchMaterialPreview,
  libraryClient,
  parseMaterialPaper,
  setMaterialExamOpen,
  type AdminMaterialListItem,
  type LibraryExamState,
  type MaterialPreview
} from '@/modules/library/api';
import {
  examStatusLabel,
  examStatusTone,
  examSwitchEnabled,
  examSwitchHint,
  examSwitchOn,
  examSwitchVisible,
  examTimingText,
  mergeExamState,
  nextExamOpen
} from '@/utils/examGate';

const SUBJECT_LABEL: Record<string, string> = { xingce: '行测', shenlun: '申论', gongzhuan: '公专' };
const subjectLabel = (s: string): string => SUBJECT_LABEL[s] || s;

const loading = ref(false);
const rows = ref<AdminMaterialListItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const maxPage = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

// ---------------- 批量操作（A7，2026-11-08） ----------------
/** 当前页已勾选的资料 ID（不跨页；换页/换筛选即清空） */
const selected = ref<number[]>([]);
/** 批量请求进行中：禁用按钮，避免连点重复提交 */
const batchRunning = ref(false);
/** 回收站视图不显示勾选（那边的动作是单条「恢复」） */
const isRecycleView = computed(() => filters.status === '-1');

function clearSelection(): void {
  selected.value = [];
}

function toggleSelectAll(): void {
  selected.value = toggleAll(rows.value, selected.value);
}

function onToggleRow(id: number): void {
  selected.value = toggleOne(selected.value, id);
}

type ListOrder = 'id_desc' | 'id_asc' | 'created_desc' | 'created_asc';

const filters = reactive({
  subject: '',
  type: '',
  status: '',
  createdWithin: '' as '' | '7d' | '30d',
  keyword: '',
  // ID 方案 A（2026-11-08）：默认按「列表时间」倒序（== 上传顺序，恢复的置顶）。
  // 「上传时间」列点击后才切到 created_desc/created_asc（真实上传时间，NULL 排最后）。
  order: 'id_desc' as ListOrder,
  // C3：试卷专属筛选（空串=不筛）
  paperYear: '',
  region: '',
  bookKind: ''
});

/** 「上传时间」列头箭头：只有按时间排序时才显示方向，按列表时间排序时不误导 */
const timeOrderArrow = computed(() => {
  if (filters.order === 'created_asc') return '↑';
  if (filters.order === 'created_desc') return '↓';
  return '';
});

/** 年份下拉：从今年往前 12 年（真题目录基本落在这个区间；用户也可用地址栏传别的年份） */
const yearOptions = computed(() => {
  const now = new Date().getFullYear();
  return Array.from({ length: 12 }, (_, i) => now - i);
});

const stats = reactive({
  total: 0,
  paper: 0,
  article: 0,
  lecture: 0,
  card: 0,
  published: 0,
  draft: 0
});

/** `2026-11-05T21:12:37+08:00` → `2026-11-05 21:12`（空值显示 —） */
function fmtTime(iso?: string | null): string {
  if (!iso) return '—';
  return iso.replace('T', ' ').slice(0, 16);
}

/** 试卷编号：约定写在 badge 字段（C 批会迁到 paper_code 列） */
function paperCodeOf(row: AdminMaterialListItem): string {
  return row.badge || '';
}

/** 字数展示：`1.2 万字` / `8600 字`（后端也给了同口径的 label，列表这里只需数值） */
function formatWords(n?: number | null): string {
  if (!n) return '—';
  return n >= 10000 ? `${(n / 10000).toFixed(1)} 万字` : `${n} 字`;
}

function notYet(name: string): void {
  ElMessage.info(`${name} 随 C 批接入（纸面上已排期，不是没实现）`);
}

async function loadStats(): Promise<void> {
  try {
    const s = await fetchAdminMaterialStats();
    stats.total = s.total ?? 0;
    stats.paper = s.by_type?.paper ?? 0;
    stats.article = s.by_type?.article ?? 0;
    stats.lecture = s.by_type?.lecture ?? 0;
    stats.card = s.by_type?.card ?? 0;
    stats.published = s.by_status?.published ?? 0;
    stats.draft = s.by_status?.draft ?? 0;
  } catch {
    ElMessage.error('统计加载失败（后端未启动或无权限）');
  }
}

async function loadList(): Promise<void> {
  loading.value = true;
  try {
    const res = await fetchAdminMaterialList({
      subject: filters.subject as never,
      type: filters.type as never,
      status: filters.status === '' ? null : Number(filters.status),
      keyword: filters.keyword,
      created_within: filters.createdWithin,
      order: filters.order,
      // C3：只在试卷类型下带上，避免误伤其它类型（后端也会强制排除非试卷）
      paper_year: filters.type === 'paper' && filters.paperYear ? Number(filters.paperYear) : null,
      region: filters.type === 'paper' ? filters.region : '',
      book_kind: filters.type === 'paper' ? filters.bookKind : '',
      page: page.value,
      pageSize
    });
    rows.value = res.items || [];
    total.value = res.total || 0;
    // A7：换页/换筛选后清空勾选——勾选只对"当前页这几行"有意义，
    // 留着会让批量条上的数字与屏幕上的行对不上。
    clearSelection();
  } catch (e) {
    rows.value = [];
    total.value = 0;
    clearSelection();
    ElMessage.error(errorMessage(e, '列表加载失败'));
  } finally {
    loading.value = false;
  }
}

function applyFilter(): void {
  page.value = 1;
  void loadList();
}

function resetFilters(): void {
  filters.subject = '';
  filters.type = '';
  filters.status = '';
  filters.createdWithin = '';
  filters.paperYear = '';
  filters.region = '';
  filters.bookKind = '';
  filters.keyword = '';
  filters.order = 'id_desc';
  applyFilter();
}

function toggleOrder(): void {
  // 只在两种"按上传时间"之间切换；再点一次也不会回到列表时间（列表时间是默认态，
  // 需要回到默认就点「重置」或刷新页面——避免三态循环让用户分不清当前是哪种排序）。
  filters.order = filters.order === 'created_desc' ? 'created_asc' : 'created_desc';
  applyFilter();
}

function goto(p: number): void {
  if (p < 1 || p > maxPage.value) return;
  page.value = p;
  void loadList();
}

async function reload(): Promise<void> {
  await Promise.all([loadList(), loadStats()]);
}

/**
 * 上架 / 下架（= 审批通过 / 撤销通过）。
 * P0 裁定：上传默认未上架，**上架这一个动作就是审批**，所以这里做二次确认并说明后果。
 */
async function toggleStatus(row: AdminMaterialListItem): Promise<void> {
  const next = row.status === 1 ? 0 : 1;
  const isOn = next === 1;
  try {
    await confirmOverlay(
      isOn
        ? '上架后学生端立即可见；若该试卷已关联可作答卷，会同步开放考试用卷。'
        : '下架后学生端立即不可见；已关联的可作答卷会同步关闭（进行中的考试不受影响）。',
      isOn ? '上架（=审批通过）' : '下架（=未通过）',
      { confirmButtonText: isOn ? '确认上架' : '确认下架', cancelButtonText: '取消', type: isOn ? 'success' : 'warning' }
    );
  } catch {
    return; // 用户取消
  }
  try {
    await libraryClient.request({
      url: `/api/materials/admin/${row.id}/status`,
      method: 'PUT',
      baseURL: '',
      data: { status: next }
    });
    row.status = next;
    ElMessage.success(isOn ? '已上架（=审批通过）' : '已下架（=未通过）');
    await loadStats();
  } catch (e) {
    ElMessage.error(errorMessage(e, '操作失败'));
  }
}

async function remove(row: AdminMaterialListItem): Promise<void> {
  try {
    await confirmOverlay(
      `移入回收站后学生端立即不可见，数据保留、学习进度保留，可随时恢复。确认删除「${row.title}」？`,
      '移入回收站',
      { confirmButtonText: '移入回收站', cancelButtonText: '取消', type: 'warning' }
    );
  } catch {
    return;
  }
  try {
    await libraryClient.request({
      url: `/api/materials/admin/${row.id}`,
      method: 'DELETE',
      baseURL: ''
    });
    ElMessage.success('已移入回收站（可在「回收站（已删除）」恢复）');
    if (rows.value.length === 1 && page.value > 1) page.value -= 1;
    await reload();
  } catch (e) {
    ElMessage.error(errorMessage(e, '删除失败'));
  }
}

/**
 * A2（2026-11-08）：为试卷资料在题库里建一张可作答卷。
 * 后端幂等（同编号已存在则复用、不会覆盖状态），所以可以放心点第二次。
 * 新卷是 DRAFT：资料上架后由 P5 联动自动变 PUBLISHED，学生才看得到。
 */
async function ensurePaper(row: AdminMaterialListItem): Promise<void> {
  const code = paperCodeOf(row);
  if (!code) return;
  try {
    await confirmOverlay(
      `将在题库里为「${row.title}」建一张可作答卷（编号 ${code}，草稿状态）。\n`
        + '建好后还需要导入题目，并把资料「上架」，学生才能考。',
      '生成可作答卷',
      { confirmButtonText: '生成', cancelButtonText: '取消', type: 'success' }
    );
  } catch {
    return;
  }
  try {
    const res = (await libraryClient.request({
      url: `/api/materials/admin/${row.id}/ensure-paper`,
      method: 'POST',
      baseURL: ''
    })) as unknown as { data?: { created?: boolean; paper_id?: number; paper_code?: string; paper_type?: string } };
    const data = res?.data || {};
    if (data.created) {
      ElMessage.success(`已生成可作答卷 #${data.paper_id}（${data.paper_type}），接下来请导入题目`);
    } else {
      ElMessage.info(`该编号已有可作答卷 #${data.paper_id}（${data.paper_type}），未重复创建`);
    }
  } catch (e) {
    ElMessage.error(errorMessage(e, '生成可作答卷失败'));
  }
}

// ---------------- 考试开关 / 定时（P2，2026-11-09） ----------------
/** 正在提交开关的行 id（只禁那一行，别把整表冻住） */
const examBusyId = ref<number | null>(null);
const examWinOpen = ref(false);
const examWinId = ref<number | null>(null);
const examWinCode = ref('');
const examWinName = ref('');
const examWinExam = ref<LibraryExamState | null>(null);

/**
 * 开/关一场考试。
 * 语义（方案 §4.4）：与「上架」独立，关闭只影响"能不能新进入"，历史成绩一条都不动 ——
 * 所以这里**不提示"会影响成绩"**，反而要说明"不影响"，否则管理员不敢点。
 */
async function toggleExam(row: AdminMaterialListItem): Promise<void> {
  if (!examSwitchEnabled(row.exam) || examBusyId.value === row.id) return;
  // 2026-11-12 修：以前用 `row.exam?.manual_open === 0` 直接算下一步。
  // 一旦回包缺 `manual_open`（写端点曾漏字段），这里恒为 false → 永远发"关闭"，开关再也打不开。
  // 现在统一走 `nextExamOpen`（与视觉 `examSwitchOn` 同源，缺字段时按 reason 兜底）。
  const nextOpen = nextExamOpen(row.exam);
  examBusyId.value = row.id;
  try {
    const state = await setMaterialExamOpen(row.id, nextOpen);
    // 合并而不是整体替换：保留 paper_code/paper_id 等列表字段，并用本次意图补 manual_open
    const merged = mergeExamState(row.exam, state, nextOpen);
    row.exam = merged;
    if (nextOpen) {
      ElMessage.success(merged?.ready
        ? '已打开：学生现在可以进入这场考试'
        : `已打开，但学生现在还进不去（${examStatusLabel(merged)}）——${examTimingText(merged)}`);
    } else {
      ElMessage.success('已关闭：学生不能再新开这场考试（进行中的仍可交卷，历史成绩保留）');
    }
  } catch (e) {
    ElMessage.error(errorMessage(e, '开关失败'));
  } finally {
    examBusyId.value = null;
  }
}

/** 打开定时弹层：把当前行状态一起带进去，弹层里能显示"现在能不能进" */
function openExamWindow(row: AdminMaterialListItem): void {
  examWinId.value = row.id;
  examWinCode.value = paperCodeOf(row);
  examWinName.value = row.title;
  examWinExam.value = row.exam || null;
  examWinOpen.value = true;
}

/** 保存定时成功：合并后端回的新状态（保留行内字段；不整表刷新，避免页码/滚动位置乱跳） */
function onExamWindowSaved(state: LibraryExamState): void {
  const target = rows.value.find((r) => r.id === examWinId.value);
  // 2026-11-12：同样用 merge，不能整体替换（写端点回包缺 manual_open 会把开关打回"未知"）
  if (target) target.exam = mergeExamState(target.exam, state);
  examWinOpen.value = false;
}

// ---------------- 导题（P3，2026-11-09） ----------------
const draftOpen = ref(false);
const draftId = ref<number | null>(null);
const draftMaterialId = ref<number | null>(null);
/** 正在解析的行（禁用重复点击） */
const parsingId = ref<number | null>(null);

/** 标题下那枚状态小标签：待确认 N 题 / 解析失败 / 已入库 N 题 */
function parseChip(row: AdminMaterialListItem): string {
  const d = row.parse_draft;
  if (!d) return '';
  if (d.status === 'pending') return `待确认 ${d.item_count} 题`;
  if (d.status === 'failed') return '解析失败';
  if (d.status === 'confirmed') return `已入库 ${d.item_count} 题`;
  return '';
}

function parseChipTitle(row: AdminMaterialListItem): string {
  const d = row.parse_draft;
  if (!d) return '';
  if (d.status === 'pending') return `点开核对这 ${d.item_count} 题，确认后才写进题库`;
  if (d.status === 'failed') return d.message || '解析失败，可点「导题」重试';
  if (d.status === 'confirmed') return d.message || '这些题已经入库';
  return '';
}

/** 「导题」入口：有 pending 草稿 → 打开确认页；否则先解析再打开 */
async function openDraft(row: AdminMaterialListItem): Promise<void> {
  const d = row.parse_draft;
  if (d && d.status === 'pending') {
    draftId.value = d.draft_id;
    draftMaterialId.value = row.id;
    draftOpen.value = true;
    return;
  }
  if (d && d.status === 'confirmed') {
    // 已入库：允许"再解析一遍"（改版原件时用），但要说清楚会发生什么
    try {
      await confirmOverlay(
        '这套卷的题已经入库了。重新解析会生成一份新的待确认清单，不会动已入库的题；'
          + '确认入库时才会问你要不要覆盖。继续？',
        '重新解析',
        { confirmButtonText: '重新解析', cancelButtonText: '取消', type: 'warning' }
      );
    } catch {
      return;
    }
  }
  if (parsingId.value === row.id) return;
  parsingId.value = row.id;
  try {
    const brief = await parseMaterialPaper(row.id);
    row.parse_draft = brief;
    if (brief.status === 'pending') {
      draftId.value = brief.draft_id;
      draftMaterialId.value = row.id;
      draftOpen.value = true;
      ElMessage.success(`已拆出 ${brief.item_count} 题，请核对后点「确认入库」`);
    } else {
      ElMessage.error(brief.message || '解析失败，请检查原件是不是题本');
    }
  } catch (e) {
    ElMessage.error(errorMessage(e, '解析失败'));
  } finally {
    parsingId.value = null;
  }
}

/** 入库成功：刷新列表（卷题量、考试状态都会变） */
async function onDraftConfirmed(payload: { draftId: number; created: number }): Promise<void> {
  draftOpen.value = false;
  await reload();
  ElMessage.success(`已入库 ${payload.created} 题；若资料已上架，这张卷现在学生就能考了`);
}

async function onDraftDiscarded(): Promise<void> {
  draftOpen.value = false;
  await reload();
}

// ---------------- 补答案（P4，2026-11-09） ----------------
const answerOpen = ref(false);
const answerPaperId = ref<number | null>(null);
const answerPaperCode = ref('');
const answerPaperName = ref('');

/** 「补答案」入口：只有"已有可作答卷且有题"的试卷行才显示（没题补了也没用） */
function openAnswer(row: AdminMaterialListItem): void {
  const paperId = row.exam?.paper_id;
  if (!paperId) return;
  answerPaperId.value = paperId;
  answerPaperCode.value = paperCodeOf(row);
  answerPaperName.value = row.title;
  answerOpen.value = true;
}

/** 写入成功：刷新列表（答案变了但列表不展示答案数，主要是保持一致） */
async function onAnswerApplied(payload: { paperId: number; filled: number }): Promise<void> {
  answerOpen.value = false;
  await reload();
  ElMessage.success(`已写入 ${payload.filled} 题的答案与解析`);
}

/** 从回收站恢复：status -1 → 0（未上架），需管理员再点「上架」才对学生可见 */
async function restore(row: AdminMaterialListItem): Promise<void> {
  try {
    await confirmOverlay(
      `恢复后为「未上架」状态，学生仍不可见；需要再点「上架（=审批通过）」才可见。确认恢复「${row.title}」？`,
      '恢复资料',
      { confirmButtonText: '恢复', cancelButtonText: '取消', type: 'success' }
    );
  } catch {
    return;
  }
  try {
    await libraryClient.request({
      url: `/api/materials/admin/${row.id}/status`,
      method: 'PUT',
      baseURL: '',
      data: { status: 0 }
    });
    ElMessage.success('已恢复为未上架');
    await reload();
  } catch (e) {
    ElMessage.error(errorMessage(e, '恢复失败'));
  }
}

// ---------------- 批量操作（A7） ----------------

/**
 * 批量上架/下架：**逐条**调 `PUT /admin/{id}/status`（不新增批量端点，API 面保持 343）。
 * 为什么逐条：条数是"当前页勾选"（≤20），逐条能让每条独立成败，
 * 服务端也就能为每条单独写审计、单独联动可作答卷（P5）。
 */
async function batchSetStatus(status: BatchStatus): Promise<void> {
  const picked = pickSelected(rows.value, selected.value);
  const targets = targetsForStatus(picked, status);
  if (targets.length === 0) {
    ElMessage.info('选中的资料都已是该状态，无需操作');
    return;
  }
  const label = status === 1 ? '上架' : '下架';
  try {
    await confirmOverlay(
      status === 1
        ? `将把 ${targets.length} 条资料上架，学生端立即可见；已关联的可作答卷会同步开放。`
        : `将把 ${targets.length} 条资料下架，学生端立即不可见；已关联的可作答卷会同步关闭（进行中的考试不受影响）。`,
      `批量${label}（=审批）`,
      {
        confirmButtonText: `确认批量${label}`,
        cancelButtonText: '取消',
        type: status === 1 ? 'success' : 'warning'
      }
    );
  } catch {
    return; // 用户取消
  }

  batchRunning.value = true;
  let ok = 0;
  const fails: string[] = [];
  for (const row of targets) {
    try {
      await libraryClient.request({
        url: `/api/materials/admin/${row.id}/status`,
        method: 'PUT',
        baseURL: '',
        data: { status }
      });
      ok += 1;
    } catch (e) {
      fails.push(`${row.title.slice(0, 12)}：${errorMessage(e, `${label}失败`)}`);
    }
  }
  batchRunning.value = false;

  const summary = batchSummary(label, { ok, fails });
  if (summary.level === 'success') ElMessage.success(summary.text);
  else ElMessage.warning(summary.text);
  clearSelection();
  await reload();
}

/**
 * 批量删除 = 批量**软删**（走 `DELETE /admin/batch`，服务端逐条置 -1 并联动卷 DRAFT）。
 * 与单条删除同语义：进回收站、可恢复、学习进度保留。
 */
async function batchRemove(): Promise<void> {
  const targets = pickSelected(rows.value, selected.value);
  if (targets.length === 0) return;
  try {
    await confirmOverlay(
      `将把 ${targets.length} 条资料移入回收站：学生端立即不可见，数据与学习进度保留，可随时恢复。`,
      '批量删除',
      { confirmButtonText: '移入回收站', cancelButtonText: '取消', type: 'warning' }
    );
  } catch {
    return;
  }

  batchRunning.value = true;
  try {
    const res = (await libraryClient.request({
      url: '/api/materials/admin/batch',
      method: 'DELETE',
      baseURL: '',
      data: { ids: targets.map((row) => row.id) }
    })) as unknown as { data?: { deleted?: number } };
    const deleted = Number(res?.data?.deleted ?? targets.length);
    ElMessage.success(`已移入回收站 ${deleted} 条（可在「回收站（已删除）」恢复）`);
    clearSelection();
    if (rows.value.length === deleted && page.value > 1) page.value -= 1;
    await reload();
  } catch (e) {
    ElMessage.error(errorMessage(e, '批量删除失败'));
  } finally {
    batchRunning.value = false;
  }
}

// ---------------- 批量导入（B2） ----------------
const uploadOpen = ref(false);
/** L4：文章批量上传（解析链路） */
const articleUploadOpen = ref(false);
/** 文章批量上传的默认科目：跟当前筛选走（没筛就公专） */
const articleDefaultSubject = computed(() => (filters.subject || 'gongzhuan') as 'xingce' | 'shenlun' | 'gongzhuan');
const uploadType = ref<'article' | 'lecture' | 'paper'>('lecture');

/** 「＋ 上传试卷」预置 paper，「批量导入」预置 lecture（对话框里仍可改） */
function openUpload(type: 'article' | 'lecture' | 'paper'): void {
  uploadType.value = type;
  uploadOpen.value = true;
}

/** 导入完成 → 刷新列表与统计（新资料是未上架，落在默认视图里） */
async function onUploaded(payload: { created: number }): Promise<void> {
  uploadOpen.value = false;
  page.value = 1;
  await reload();
  if (payload.created) ElMessage.success(`已导入 ${payload.created} 条，可在列表里预览并上架`);
}

// ---------------- 改信息（C2b） ----------------
const metaOpen = ref(false);
const metaId = ref<number | null>(null);
const metaTypeLabel = ref('资料');

function openMeta(row: AdminMaterialListItem): void {
  metaId.value = row.id;
  metaTypeLabel.value = materialTypeLabel(row.type);
  metaOpen.value = true;
}

/** 保存成功：标题/分类可能变了，刷新当前页 */
async function onMetaSaved(): Promise<void> {
  metaOpen.value = false;
  await reload();
}

// ---------------- 预览抽屉 ----------------
const drawerOpen = ref(false);
const previewLoading = ref(false);
const previewError = ref('');
const preview = ref<MaterialPreview | null>(null);

async function openPreview(row: AdminMaterialListItem): Promise<void> {
  drawerOpen.value = true;
  previewLoading.value = true;
  previewError.value = '';
  preview.value = null;
  try {
    preview.value = await fetchMaterialPreview(row.id);
  } catch (e) {
    previewError.value = errorMessage(e, '预览加载失败');
  } finally {
    previewLoading.value = false;
  }
}

const route = useRoute();

/**
 * 地址栏 query → 筛选项（A4 补充）。
 * 场景：`/admin/papers` redirect 到 `?type=paper`（旧书签不 404），以及手写的
 * `?status=-1`（直接进回收站）、`?created_within=7d`。
 * 首版漏了这一步，实测跳转后类型仍为「全部类型」、列表仍 112 条 —— 跳对了但没筛。
 */
function syncFromQuery(): void {
  const q = parseListQuery(route.query as Record<string, unknown>);
  filters.subject = q.subject;
  filters.type = q.type;
  filters.status = q.status;
  filters.createdWithin = q.createdWithin;
  filters.paperYear = q.paperYear;
  filters.region = q.region;
  filters.bookKind = q.bookKind;
}

syncFromQuery(); // setup 阶段 route.query 已就绪，首屏请求就带上筛选
// 页面已打开时再点旧链接（hash query 变化）也要跟着筛，而不是"点了没反应"
watch(
  () => route.query,
  () => {
    syncFromQuery();
    page.value = 1;
    void loadList();
  }
);

onMounted(reload);
</script>

<style scoped>
.mm-page {
  padding: var(--adm-s5) var(--adm-s6) var(--adm-s6);
  background: var(--adm-bg);
  min-height: 100%;
  font-family: var(--adm-font);
}
.mm-stats {
  display: flex;
  gap: var(--adm-s2);
  margin-bottom: var(--adm-s2);
}
.mm-chip {
  font-size: 11.5px;
  font-weight: 700;
  color: var(--adm-ok);
  background: var(--adm-ok-weak);
  border: 1px solid #bfe6d2;
  border-radius: 999px;
  padding: 5px 10px;
}
.mm-title {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
/* A7：批量操作条 + 勾选框 */
.mm-batchbar {
  display: flex;
  align-items: center;
  gap: var(--adm-s2);
  flex-wrap: wrap;
  margin-bottom: var(--adm-s2);
  padding: 9px 12px;
  background: var(--adm-primary-weak);
  border: 1px solid var(--adm-primary-line);
  border-radius: var(--adm-r-ctl);
}
.mm-batchbar__count {
  font-size: 12.5px;
  color: var(--adm-primary-dark);
}
.mm-batchbar__count b { font-weight: 700; }
.mm-batchbar__hint {
  font-size: 11px;
  color: var(--adm-text-sub);
}
.adm-btn--danger {
  background: var(--adm-danger-weak);
  color: var(--adm-danger);
  border-color: #f3d3c2;
}
.adm-btn--danger:hover { background: #ffeede; }
.mm-check {
  width: 15px;
  height: 15px;
  cursor: pointer;
  accent-color: var(--adm-primary);
  vertical-align: middle;
}
.mm-title b {
  font-weight: 700;
  color: var(--adm-text);
  /* P2：列数到 12 后标题只剩 ~130px（1440 宽）。原来只给 nowrap+省略号 → 只剩「2024年...」；
     改成最多两行，至少能认出是哪一套卷。超长仍会裁切，不会把行高撑爆。 */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-all;
  max-width: 100%;
}
/* P2：列数已满（12 列）。用固定表布局让"标题"吃掉剩余宽度；
   并给表身留横向滚动兜底（1440 桌面勉强够，更窄的窗口可横向拖，不至于把「操作」列吃掉）。 */
.mm-page :deep(table) { table-layout: fixed; min-width: 1040px; }
.mm-page :deep(.adm-table__body) { overflow-x: auto; }
.mm-title { overflow: hidden; }
.mm-sub {
  margin-top: 3px;
  font-size: 10.5px;
  color: var(--adm-text-weak);
}
.mm-dot { margin: 0 4px; }
.mm-pub { color: var(--adm-text-mid); }
.mm-role { color: var(--adm-text-weak); font-size: 10.5px; }
.mm-time { color: var(--adm-muted); font-size: 11px; }
.mm-loading {
  text-align: center;
  color: var(--adm-text-weak);
  padding: 24px 0;
}
.mm-sortable {
  cursor: pointer;
  user-select: none;
}
.mm-sortable:hover { color: var(--adm-primary); }

/* 上架开关：上架=审批通过 */
.mm-switch {
  position: relative;
  width: 36px;
  height: 20px;
  border-radius: 999px;
  border: none;
  background: #dfe4f0;
  cursor: pointer;
  vertical-align: middle;
  transition: background 0.16s ease;
}
.mm-switch i {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  transition: left 0.16s ease;
}
.mm-switch.is-on { background: var(--adm-primary); }
.mm-switch.is-on i { left: 18px; }

.mm-ops { white-space: nowrap; }
.mm-status-cell { white-space: nowrap; }
.mm-pub-cell { white-space: nowrap; }

/* P2：考试开关列（开关 + 状态 + 定时摘要 + 设置定时） */
.mm-exam-cell { white-space: nowrap; vertical-align: middle; }
.mm-exam {
  display: flex;
  align-items: center;
  gap: 8px;
}
.mm-exam .mm-switch:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.mm-exam__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.mm-exam__sub {
  font-size: 10.5px;
  color: var(--adm-text-weak);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 92px;
}
.mm-exam__timer {
  display: inline-block;
  margin-top: 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--adm-primary);
  cursor: pointer;
}
.mm-exam__timer:hover { text-decoration: underline; }
.mm-exam__timer.is-muted { color: var(--adm-text-weak); }

/* P3：解析草稿小标签（点开 = 导题确认） */
.mm-parse {
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 700;
  cursor: pointer;
}
.mm-parse.is-pending { background: #fff2e2; color: #b4620a; }
.mm-parse.is-failed { background: var(--adm-danger-weak, #fdeceb); color: var(--adm-danger, #d9463b); }
.mm-parse.is-confirmed { background: #eafaf1; color: var(--adm-ok, #12a150); }
.mm-parse:hover { text-decoration: underline; }
.mm-op {
  color: var(--adm-primary);
  font-weight: 600;
  cursor: pointer;
  margin-right: 10px;
}
.mm-op:hover { text-decoration: underline; }
.mm-op.is-danger { color: var(--adm-danger); margin-right: 0; }
.mm-op.is-restore { color: var(--adm-ok); margin-right: 0; }
.mm-op.is-muted { color: var(--adm-text-weak); font-weight: 600; }

.mm-pager {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  justify-content: flex-end;
  font-size: 11.5px;
  color: var(--adm-text-sub);
}
</style>
