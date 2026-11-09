<template>
  <div class="mp" :style="{ '--c': theme.color }">
    <!-- 头部：三科切换 + 进度 -->
    <header class="mp-head">
      <div class="mp-title">
        <h1>{{ theme.label }} · 备考资料</h1>
        <p class="mp-sub">讲义看原件，试卷给原卷；能不能在线考，看它有没有投到「考试」页。</p>
      </div>
      <nav class="mp-tabs">
        <button
          v-for="s in SUBJECTS"
          :key="s.key"
          :class="['mp-tab', { on: s.key === subject }]"
          @click="switchSubject(s.key)"
        >
          {{ s.label }}
        </button>
      </nav>
      <div v-if="summary" class="mp-progress">
        <span>进度 {{ summary.studied }} / {{ summary.total }}</span>
        <div class="mp-bar"><i :style="{ width: summary.percentage + '%' }" /></div>
      </div>
    </header>

    <!-- 骨架 -->
    <div v-if="loading" class="mp-skeleton">
      <div v-for="i in 3" :key="i" class="mp-skeleton-row" />
    </div>

    <!-- 空 -->
    <div v-else-if="pageEmpty" class="mp-empty">
      <div class="mp-empty-icon">📚</div>
      <p>{{ theme.label }}的备考资料正在加紧制作中，敬请期待…</p>
      <div class="mp-empty-btns">
        <button @click="go('/home')">返回首页</button>
        <button class="ghost" @click="switchSubject('xingce')">去看行测</button>
      </div>
    </div>

    <!-- 六个分区 -->
    <template v-else>
      <section v-for="sec in sections" :key="sec.key" class="mp-section" v-show="itemsOf(sec.key).length">
        <div class="mp-sec-head">
          <h2><span class="mp-sec-icon">{{ sec.icon }}</span>{{ sec.title }}</h2>
          <div class="mp-sec-tools">
            <span v-if="sec.key === 'lecture'" class="mp-hint">原件可下载 · 有正文时可在线阅读</span>
            <span v-else-if="sec.key === 'paper'" class="mp-hint">只放原卷；能不能在线考看投放位</span>
            <button
              v-if="itemsOf(sec.key).length > COLLAPSED"
              class="mp-more"
              @click="toggleFold(sec.key)"
            >
              {{ folded[sec.key] ? `展开全部 ${itemsOf(sec.key).length} 条` : '收起' }}
            </button>
          </div>
        </div>

        <!-- 视频：两列卡 -->
        <div v-if="sec.kind === 'video'" class="mp-grid mp-grid--video">
          <article v-for="it in visible(sec.key)" :key="it.id" class="mp-card" @click="openVideo(it)">
            <div class="mp-card-cover">🎬</div>
            <h3>{{ it.title }}</h3>
            <p class="mp-card-meta">{{ fmtDuration(it.duration) }} · 难度 {{ '⭐'.repeat(it.difficulty || 1) }}</p>
          </article>
        </div>

        <!-- 文章 / 讲义 / 试卷：三列卡 -->
        <div v-else-if="sec.kind !== 'card'" class="mp-grid">
          <article
            v-for="it in visible(sec.key)"
            :key="it.id"
            :class="['mp-card', 'mp-card--doc', `mp-card--${sec.kind}`]"
          >
            <div class="mp-card-top">
              <span v-if="it.category" class="mp-tag">{{ it.category }}</span>
              <span v-if="it.type === 'paper' && it.paper?.book_kind_label" class="mp-tag mp-tag--kind">
                {{ it.paper.book_kind_label }}
              </span>
            </div>
            <h3 :title="it.title">{{ it.title }}</h3>

            <!-- 试卷元数据行 -->
            <p v-if="it.type === 'paper'" class="mp-card-meta mp-meta-line">
              {{ paperMetaLine(it) }}
            </p>
            <!-- 讲义摘要 + 字数 -->
            <template v-else>
              <p class="mp-card-meta">{{ it.summary || '—' }}</p>
              <p v-if="it.type === 'lecture' && lectureMetaLine(it)" class="mp-card-meta mp-meta-line">
                {{ lectureMetaLine(it) }}
              </p>
            </template>

            <p class="mp-file-line">
              <span v-if="it.has_files">共 {{ it.file_count }} 份原件</span>
              <span v-else class="mp-no-file">暂无原件</span>
            </p>

            <div class="mp-actions">
              <!-- 讲义：在线阅读（正文存在时）+ 下载原件 -->
              <template v-if="it.type === 'lecture'">
                <button class="mp-btn mp-btn--primary" :disabled="!it.has_files && !it.read_time" @click="openReader(it)">
                  在线阅读
                </button>
                <button class="mp-btn" :disabled="!it.has_files" @click="download(it)">下载原件</button>
              </template>
              <!-- 试卷：下载原卷 + 去考试 -->
              <template v-else-if="it.type === 'paper'">
                <button class="mp-btn mp-btn--primary" :disabled="!it.has_files" @click="download(it)">
                  下载原卷
                </button>
                <button
                  :class="['mp-btn', canExam(it) ? 'mp-btn--go' : 'mp-btn--off']"
                  :disabled="!canExam(it)"
                  :title="canExam(it) ? '去考试页开始作答' : examHint(it)"
                  @click="goExam(it)"
                >
                  {{ canExam(it) ? '去考试' : '暂不可考' }}
                </button>
              </template>
              <!-- 文章 -->
              <template v-else>
                <button class="mp-btn mp-btn--primary" @click="openReader(it)">阅读全文</button>
              </template>
            </div>

            <p v-if="it.type === 'paper' && !canExam(it)" class="mp-off-note">{{ examHint(it) }}</p>
          </article>
        </div>

        <!-- 卡片：3D 翻转 -->
        <div v-else class="mp-cards">
          <div
            v-for="it in visible(sec.key)"
            :key="it.id"
            :class="['mp-flip', { flipped: flipped[it.id] }]"
            @click="flipped[it.id] = !flipped[it.id]"
          >
            <div class="mp-flip-inner">
              <div class="mp-flip-face front">
                <span class="mp-tag">{{ it.category || '知识点' }}</span>
                <p>{{ it.card_front || it.title }}</p>
                <i>👆 点击翻转</i>
              </div>
              <div class="mp-flip-face back">
                <p>{{ it.card_back || '暂无背面内容' }}</p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </template>

    <!-- 阅读器（文章 / 讲义）
         为什么用自绘弹层而不是 <el-dialog>：本项目的 Element Plus 只按需 import
         （main.ts 里没有 app.use(ElementPlus)），`el-dialog` 会退化成未知元素、
         把插槽内容直接摊在页面底部（实测无头截图可见）。自绘一层 mask 最稳，
         也和手写管理端页的抽屉风格一致。 -->
    <Teleport to="body">
      <div v-if="reader.open" class="mp-mask" @click.self="reader.open = false">
        <section class="mp-modal" role="dialog" aria-modal="true">
          <header class="mp-modal-head">
            <h3>{{ reader.title || '阅读' }}</h3>
            <button class="mp-modal-x" aria-label="关闭" @click="reader.open = false">×</button>
          </header>
          <div class="mp-modal-body">
            <div v-if="reader.loading" class="mp-reader-loading">加载中…</div>
            <template v-else>
              <div v-if="reader.meta" class="mp-reader-meta">{{ reader.meta }}</div>
              <div v-if="reader.html" class="mp-article" v-html="sanitizeHtml(reader.html)" />
              <div v-else class="mp-reader-empty">
                这篇资料只有原件、没有正文。点下面的「下载原件」拿到 PDF/Word 后阅读。
              </div>
              <div v-if="reader.files.length" class="mp-reader-files">
                <p class="mp-reader-files-title">原件（{{ reader.files.length }}）</p>
                <ul>
                  <li v-for="f in reader.files" :key="f.file_id">
                    <span>{{ f.file_name }}</span>
                    <em>{{ f.size_label }}</em>
                    <button class="mp-btn mp-btn--mini" @click="downloadFile(f)">下载</button>
                  </li>
                </ul>
              </div>
            </template>
          </div>
          <footer class="mp-modal-foot">
            <button class="mp-btn" @click="reader.open = false">关闭</button>
            <button
              v-if="reader.materialId"
              class="mp-btn mp-btn--primary"
              :disabled="reader.marked"
              @click="markStudied()"
            >
              {{ reader.marked ? '已标记学完' : '标记已学完' }}
            </button>
          </footer>
        </section>
      </div>
    </Teleport>

    <!-- 视频播放 -->
    <Teleport to="body">
      <div v-if="video.open" class="mp-mask" @click.self="video.open = false">
        <section class="mp-modal mp-modal--wide" role="dialog" aria-modal="true">
          <header class="mp-modal-head">
            <h3>{{ video.title || '视频学习' }}</h3>
            <button class="mp-modal-x" aria-label="关闭" @click="video.open = false">×</button>
          </header>
          <div class="mp-modal-body">
            <video
              v-if="video.url"
              controls
              autoplay
              playsinline
              style="width:100%;border-radius:8px;background:#000;max-height:60vh"
              :src="video.url"
            />
            <p v-else class="mp-reader-empty">该视频暂时无法播放。</p>
          </div>
        </section>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
/**
 * 学生端「备考资料」新页（L2，2026-11-08）。
 *
 * 为什么新写这一页而不是改 `.vtj/vue/materials_*.vue`：
 *   R3 禁止 AI 改 `.vtj` 页的 `<template>`，且实测 `.vtj/files/materials_*.json`
 *   的 DSL 与 `.vtj/vue` 里的真实模板并不同步，改模板会被设计器回存覆盖。
 *   因此本页是普通 Vue 组件，三条既有路由指向它（**不新增路由**，L6/L7 105 不变），
 *   旧 `.vtj` 页保留在仓库里 —— 回滚只需把路由改回去。
 *
 * 分区：视频×2 / 备考指南（文章）/ 讲义 / 试卷资料 / 知识卡片。
 * 后两类是本批新增，数据依赖 L1 的 `placement / has_files / file_count / paper / files / doc_meta`。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import {
  downloadMaterialFile,
  fetchLibraryDetail,
  fetchLibraryList,
  fetchLibraryProgressSummary,
  reportLibraryProgress,
  type LibraryMaterial,
  type LibraryMaterialDetail,
  type LibraryMaterialType,
  type LibrarySubject,
  type MaterialFileItem
} from '@/modules/library/api';
import { sanitizeHtml } from '@/utils/questionRender';
import {
  COLLAPSED,
  canExam,
  examHint,
  fmtDuration,
  lectureMetaLine,
  paperMetaLine,
  visibleItems
} from '@/utils/materialShelf';

const SUBJECTS: Array<{ key: LibrarySubject; label: string; color: string }> = [
  { key: 'xingce', label: '行测', color: '#3B82F6' },
  { key: 'shenlun', label: '申论', color: '#10B981' },
  { key: 'gongzhuan', label: '公专', color: '#F59E0B' }
];

type SectionKind = 'video' | 'article' | 'lecture' | 'paper' | 'card';
const SECTIONS: Array<{ key: LibraryMaterialType; kind: SectionKind; title: string; icon: string }> = [
  { key: 'video_intro', kind: 'video', title: '入门讲解视频', icon: '🎬' },
  { key: 'video_advanced', kind: 'video', title: '深度拓展视频', icon: '🎯' },
  { key: 'article', kind: 'article', title: '备考指南', icon: '📋' },
  { key: 'lecture', kind: 'lecture', title: '讲义', icon: '📘' },
  { key: 'paper', kind: 'paper', title: '试卷资料', icon: '📄' },
  { key: 'card', kind: 'card', title: '知识卡片', icon: '🃏' }
];

const route = useRoute();
const router = useRouter();

const subject = computed<LibrarySubject>(() => {
  const m = /\/materials\/(xingce|shenlun|gongzhuan)/.exec(route.path);
  const v = (m?.[1] || (route.query.subject as string) || 'xingce') as LibrarySubject;
  return SUBJECTS.some((s) => s.key === v) ? v : 'xingce';
});
const theme = computed(() => SUBJECTS.find((s) => s.key === subject.value) || SUBJECTS[0]);

const sections = SECTIONS;
const loading = ref(true);
const data = reactive<Record<string, LibraryMaterial[]>>({});
const folded = reactive<Record<string, boolean>>({
  video_intro: true,
  video_advanced: true,
  article: false,
  lecture: false,
  paper: false,
  card: false
});
const flipped = reactive<Record<number, boolean>>({});
const summary = ref<{ studied: number; total: number; percentage: number } | null>(null);

const pageEmpty = computed(() => SECTIONS.every((s) => !(data[s.key] || []).length));

function itemsOf(key: string): LibraryMaterial[] {
  return data[key] || [];
}
function visible(key: string): LibraryMaterial[] {
  return visibleItems(itemsOf(key), Boolean(folded[key]));
}
function toggleFold(key: string) {
  folded[key] = !folded[key];
}

async function loadAll() {
  loading.value = true;
  const s = subject.value;
  await Promise.all(
    SECTIONS.map(async (sec) => {
      try {
        const res = await fetchLibraryList({ subject: s, type: sec.key, pageSize: 50 });
        data[sec.key] = res.items || [];
      } catch (e) {
        console.warn('[Materials] 分区加载失败:', sec.key, e);
        data[sec.key] = [];
      }
    })
  );
  loading.value = false;
  loadSummary();
}

async function loadSummary() {
  const token = (window as any).__VTJ_AUTH__;
  if (!token?.isLoggedIn?.()) {
    summary.value = null;
    return;
  }
  try {
    summary.value = await fetchLibraryProgressSummary(subject.value);
  } catch (e) {
    console.warn('[Materials] 进度加载失败:', e);
    summary.value = null;
  }
}

function switchSubject(key: LibrarySubject) {
  router.push(`/materials/${key}`);
}
function go(path: string) {
  router.push(path);
}

/** 打开阅读器：拉详情补正文/原件/大纲（列表不含正文，避免列表响应过大） */
const reader = reactive({
  open: false,
  loading: false,
  title: '',
  html: '',
  meta: '',
  files: [] as MaterialFileItem[],
  materialId: 0,
  marked: false
});

async function openReader(it: LibraryMaterial) {
  reader.open = true;
  reader.loading = true;
  reader.title = it.title;
  reader.html = '';
  reader.meta = '';
  reader.files = [];
  reader.materialId = it.id;
  reader.marked = Boolean(it.is_studied);
  try {
    const d: LibraryMaterialDetail = await fetchLibraryDetail(it.id);
    reader.html = d.content || '';
    reader.files = d.files || [];
    if (it.type === 'lecture') {
      const doc = d.doc_meta;
      const bits: string[] = [];
      if (doc?.chapter_count) bits.push(`${doc.chapter_count} 章`);
      if (doc?.word_count) bits.push(`${doc.word_count} 字`);
      reader.meta = bits.join(' · ');
    }
    if (!d.content && !reader.files.length) {
      reader.meta = '这份资料暂时没有可读内容。';
    }
  } catch (e: any) {
    ElMessage.error('打开失败：' + (e?.message || '网络异常'));
  } finally {
    reader.loading = false;
  }
}

async function markStudied() {
  if (!reader.materialId) return;
  try {
    await reportLibraryProgress({ materialId: reader.materialId, progressPercent: 100, completed: true });
    reader.marked = true;
    ElMessage.success('已标记学完，学习进度 +1');
    loadSummary();
  } catch (e: any) {
    ElMessage.error('标记失败：' + (e?.message || '网络异常'));
  }
}

/** 下载：走后端鉴权端点（原件不在公开目录），失败给明确提示 */
async function download(it: LibraryMaterial) {
  try {
    const d = await fetchLibraryDetail(it.id);
    const files = d.files || [];
    if (!files.length) {
      ElMessage.warning('这份资料没有原件');
      return;
    }
    for (const f of files) await downloadMaterialFile(f);
  } catch (e: any) {
    ElMessage.error('下载失败：' + (e?.message || '网络异常'));
  }
}
async function downloadFile(f: MaterialFileItem) {
  try {
    await downloadMaterialFile(f);
  } catch (e: any) {
    ElMessage.error('下载失败：' + (e?.message || '网络异常'));
  }
}

/** 视频：详情里拿 video_url */
const video = reactive({ open: false, title: '', url: '' });
async function openVideo(it: LibraryMaterial) {
  video.title = it.title;
  video.url = '';
  video.open = true;
  try {
    const d = await fetchLibraryDetail(it.id);
    video.url = d.video_url || '';
    if (!video.url) ElMessage.warning('该视频资源暂不可用');
  } catch (e: any) {
    ElMessage.error('视频加载失败：' + (e?.message || '网络异常'));
  }
}

/** 去考试：进考试页（那里有「开始考试/继续考试」与历史成绩） */
function goExam(it: LibraryMaterial) {
  if (!canExam(it)) return;
  router.push('/student/papers');
}

watch(subject, () => loadAll());
onMounted(loadAll);
</script>

<style scoped>
.mp {
  min-height: 100vh;
  padding: 20px 28px 48px;
  background: #f5f7fb;
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: #1f2d3d;
}
/* ---------- 头部 ---------- */
.mp-head {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 18px 22px;
  background: #fff;
  border: 1px solid #e8ecf3;
  border-radius: 14px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.mp-title h1 {
  margin: 0;
  font-size: 20px;
  color: var(--c);
}
.mp-sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: #8896ab;
}
.mp-tabs {
  display: flex;
  gap: 8px;
  margin-left: auto;
}
.mp-tab {
  padding: 7px 20px;
  border-radius: 8px;
  border: 1px solid #e3e8f0;
  background: #fff;
  color: #5a6b85;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.15s;
}
.mp-tab.on {
  background: var(--c);
  border-color: var(--c);
  color: #fff;
}
.mp-progress {
  min-width: 180px;
  font-size: 13px;
  color: #5a6b85;
}
.mp-bar {
  height: 6px;
  border-radius: 3px;
  background: #e9edf6;
  margin-top: 6px;
  overflow: hidden;
}
.mp-bar i {
  display: block;
  height: 100%;
  background: var(--c);
  border-radius: 3px;
  transition: width 0.3s;
}
/* ---------- 分区 ---------- */
.mp-section {
  background: #fff;
  border: 1px solid #e8ecf3;
  border-radius: 14px;
  padding: 16px 20px 20px;
  margin-bottom: 16px;
}
.mp-sec-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.mp-sec-head h2 {
  margin: 0;
  font-size: 16px;
}
.mp-sec-icon {
  margin-right: 6px;
}
.mp-sec-tools {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}
.mp-hint {
  font-size: 12px;
  color: #8896ab;
}
.mp-more {
  border: none;
  background: none;
  color: var(--c);
  font-size: 13px;
  cursor: pointer;
}
/* ---------- 卡片 ---------- */
.mp-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}
.mp-grid--video {
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
}
.mp-card {
  border: 1px solid #e8ecf3;
  border-radius: 12px;
  padding: 14px 16px 16px;
  background: #fbfcff;
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.15s;
  display: flex;
  flex-direction: column;
  min-height: 150px;
}
.mp-card:hover {
  box-shadow: 0 6px 18px rgba(64, 84, 224, 0.1);
  transform: translateY(-1px);
}
.mp-card--lecture {
  border-color: #c7d2fe;
  background: #fbfcff;
}
.mp-card--paper {
  border-color: #a7f3d0;
  background: #fbfefc;
}
.mp-card h3 {
  margin: 8px 0 6px;
  font-size: 15px;
  line-height: 1.45;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.mp-card-meta {
  margin: 0 0 6px;
  font-size: 12px;
  color: #5a6b85;
  line-height: 1.5;
}
.mp-meta-line {
  color: #8896ab;
}
.mp-file-line {
  margin: 0 0 12px;
  font-size: 12px;
  color: #8896ab;
}
.mp-no-file {
  color: #c2410c;
}
.mp-card-cover {
  height: 84px;
  border-radius: 8px;
  background: #eef1f8;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
}
.mp-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  background: #eef1ff;
  color: #4054e0;
  font-size: 12px;
}
.mp-tag--kind {
  background: #e7f7f1;
  color: #0f766e;
  margin-left: 6px;
}
.mp-card-top {
  min-height: 20px;
}
/* ---------- 按钮 ---------- */
.mp-actions {
  display: flex;
  gap: 8px;
  margin-top: auto;
  flex-wrap: wrap;
}
.mp-btn {
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid var(--c);
  background: #fff;
  color: var(--c);
  font-size: 13px;
  cursor: pointer;
}
.mp-btn:disabled {
  border-color: #e3e8f0;
  color: #b6c0d1;
  background: #f7f8fb;
  cursor: not-allowed;
}
.mp-btn--primary {
  background: var(--c);
  color: #fff;
}
.mp-btn--primary:disabled {
  background: #f1f3f7;
  color: #b6c0d1;
}
.mp-btn--go {
  background: #10b981;
  border-color: #10b981;
  color: #fff;
}
.mp-btn--off {
  background: #f1f3f7;
  border-color: #f1f3f7;
  color: #8896ab;
}
.mp-btn--mini {
  padding: 3px 10px;
  font-size: 12px;
}
.mp-off-note {
  margin: 10px 0 0;
  font-size: 11px;
  color: #0f766e;
  line-height: 1.5;
}
/* ---------- 卡片翻转 ---------- */
.mp-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px;
}
.mp-flip {
  perspective: 1000px;
  height: 150px;
  cursor: pointer;
}
.mp-flip-inner {
  position: relative;
  width: 100%;
  height: 100%;
  transition: transform 0.45s;
  transform-style: preserve-3d;
}
.mp-flip.flipped .mp-flip-inner {
  transform: rotateY(180deg);
}
.mp-flip-face {
  position: absolute;
  inset: 0;
  backface-visibility: hidden;
  border-radius: 12px;
  border: 1px solid #e8ecf3;
  padding: 14px;
  background: #fff;
  overflow: auto;
  font-size: 13px;
  line-height: 1.6;
}
.mp-flip-face.back {
  transform: rotateY(180deg);
  background: #fbfcff;
}
.mp-flip-face i {
  position: absolute;
  bottom: 8px;
  right: 12px;
  font-size: 11px;
  color: #b6c0d1;
  font-style: normal;
}
/* ---------- 阅读器 ---------- */
/* 自绘弹层（不用 el-dialog，原因见模板里的注释） */
.mp-mask {
  position: fixed;
  inset: 0;
  background: rgba(17, 24, 39, 0.45);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 5vh 16px;
  z-index: 3000;
}
.mp-modal {
  width: min(820px, 100%);
  max-height: 88vh;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.24);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.mp-modal--wide {
  width: min(900px, 100%);
}
.mp-modal-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid #eef1f6;
}
.mp-modal-head h3 {
  margin: 0;
  font-size: 16px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mp-modal-x {
  border: none;
  background: none;
  font-size: 22px;
  line-height: 1;
  color: #8896ab;
  cursor: pointer;
}
.mp-modal-body {
  padding: 16px 18px;
  overflow: auto;
}
.mp-modal-foot {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  padding: 12px 18px;
  border-top: 1px solid #eef1f6;
}
.mp-article {
  max-height: 62vh;
  overflow: auto;
  line-height: 1.85;
  font-size: 14px;
}
.mp-article :deep(img) {
  max-width: 100%;
  border-radius: 6px;
}
.mp-reader-meta {
  font-size: 12px;
  color: #8896ab;
  margin-bottom: 10px;
}
.mp-reader-empty {
  padding: 28px 12px;
  text-align: center;
  color: #8896ab;
  font-size: 13px;
  background: #f7f8fb;
  border-radius: 10px;
}
.mp-reader-loading {
  padding: 40px;
  text-align: center;
  color: #8896ab;
}
.mp-reader-files {
  margin-top: 16px;
  border-top: 1px dashed #e3e8f0;
  padding-top: 12px;
}
.mp-reader-files-title {
  margin: 0 0 8px;
  font-size: 13px;
  color: #5a6b85;
}
.mp-reader-files ul {
  list-style: none;
  margin: 0;
  padding: 0;
}
.mp-reader-files li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  font-size: 13px;
}
.mp-reader-files li span {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mp-reader-files em {
  color: #8896ab;
  font-style: normal;
  font-size: 12px;
}
/* ---------- 空/骨架 ---------- */
.mp-skeleton {
  display: grid;
  gap: 14px;
}
.mp-skeleton-row {
  height: 120px;
  border-radius: 14px;
  background: linear-gradient(90deg, #eef1f8 25%, #f6f8fc 37%, #eef1f8 63%);
  background-size: 400% 100%;
  animation: mp-shimmer 1.4s ease infinite;
}
@keyframes mp-shimmer {
  0% { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}
.mp-empty {
  padding: 80px 20px;
  text-align: center;
  color: #8896ab;
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e8ecf3;
}
.mp-empty-icon {
  font-size: 44px;
  margin-bottom: 12px;
}
.mp-empty-btns {
  margin-top: 18px;
  display: flex;
  gap: 10px;
  justify-content: center;
}
.mp-empty-btns button {
  padding: 8px 18px;
  border-radius: 8px;
  border: 1px solid var(--c);
  background: var(--c);
  color: #fff;
  cursor: pointer;
}
.mp-empty-btns button.ghost {
  background: #fff;
  color: var(--c);
}
/* 平板/窄屏：双列 → 单列 */
@media (max-width: 768px) {
  .mp {
    padding: 12px 12px 32px;
  }
  .mp-head {
    gap: 12px;
  }
  .mp-tabs {
    margin-left: 0;
    width: 100%;
  }
  .mp-grid,
  .mp-grid--video,
  .mp-cards {
    grid-template-columns: 1fr;
  }
}
</style>
