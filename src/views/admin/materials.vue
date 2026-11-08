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
            <th v-if="!isRecycleView" style="width: 40px">
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
            <th style="width: 64px" title="按列表顺序倒排：最上面一行 = 当前结果总数">编号</th>
            <th>标题 / 类型</th>
            <th style="width: 60px">科目</th>
            <th style="width: 100px">分类</th>
            <th style="width: 146px">发布者</th>
            <th class="mm-sortable" style="width: 132px" @click="toggleOrder"
                title="按真实上传时间排序（NULL 恒排最后）；编号列始终按列表时间倒序">
              上传时间 {{ timeOrderArrow }}
            </th>
            <th style="width: 60px">浏览</th>
            <th style="width: 152px">上架（=审批）</th>
            <th style="width: 150px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td :colspan="isRecycleView ? 9 : 10" class="mm-loading">加载中…</td>
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
              </div>
              <!-- C1：讲义行给规模，便于一眼判断"是不是那份长讲义" -->
              <div v-else-if="row.type === 'lecture'" class="mm-sub">
                <span v-if="row.chapter_count">{{ row.chapter_count }} 章</span>
                <span v-if="row.chapter_count && row.word_count" class="mm-dot">·</span>
                <span v-if="row.word_count">{{ formatWords(row.word_count) }}</span>
                <span v-if="!row.chapter_count && !row.word_count">未解析大纲</span>
              </div>
            </td>
            <td>{{ subjectLabel(row.subject) }}</td>
            <td>{{ row.category || '—' }}</td>
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
                <a class="mm-op" @click="openMeta(row)">改信息</a>
                <a class="mm-op is-danger" @click="remove(row)">删除</a>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
      <template #footer>
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

    <MaterialBatchUpload
      :open="uploadOpen"
      :preset-type="uploadType"
      :title="uploadType === 'paper' ? '上传试卷（原件留档）' : '批量导入资料'"
      @close="uploadOpen = false"
      @done="onUploaded"
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
  MaterialMetaDialog
} from '@/components/admin';
import { MATERIAL_TYPES, materialTypeLabel } from '@/modules/library/materialTypes';
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
  type AdminMaterialListItem,
  type MaterialPreview
} from '@/modules/library/api';

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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 520px;
}
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
