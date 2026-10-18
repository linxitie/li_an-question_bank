<!-- 手机端错题集（三科分类 + 答案红绿态 + 斩题 + 斩题记录倒计时） -->
<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">错题集</h1>
      <span class="spacer"></span>
    </header>

    <!-- 复习入口 -->
    <div class="review-bar">
      <button class="review-btn" @click="goReview">
        <span>🔁 错题复习</span>
        <span class="review-sub">按模式重练，答对3次自动斩题</span>
      </button>
    </div>

    <!-- Tab 切换 -->
    <div class="tabs">
      <div :class="['tab', { active: activeTab === 'wrong' }]" @click="switchTab('wrong')">错题</div>
      <div :class="['tab', { active: activeTab === 'chopped' }]" @click="switchTab('chopped')">斩题记录</div>
    </div>

    <!-- 分类筛选：固定三科（全部/行测/申论/公专）。
         申论当前无题目数据（question_subject 仅 1 行测 / 3 公专），故走空态而非报错。 -->
    <div class="subject-tabs" v-if="activeTab === 'wrong'">
      <div
        v-for="t in WRONG_TABS"
        :key="t.key"
        :class="['subj-tab', { active: currentSubject === t.key }]"
        @click="selectSubject(t.key)"
      >{{ t.name }}</div>
    </div>

    <!-- 错题列表 -->
    <main class="list" v-if="activeTab === 'wrong'">
      <div v-for="item in items" :key="item.wrong_id" class="card" @click="toggleDetail(item)">
        <div class="q-title">{{ renderQuestionSummary(item.question_content) }}</div>
        <div class="q-meta">
          <span class="tag">{{ item.subject_name || '未分类' }}</span>
          <span class="tag" v-if="item.sub_category">{{ item.sub_category }}</span>
          <span class="tag">{{ item.question_type_detail || '' }}</span>
          <span class="err">错 {{ item.error_count }} 次</span>
        </div>

        <div v-if="expandedId === item.wrong_id" class="detail" @click.stop>
          <!-- 选项渲染：正确项绿色，用户错选项红色 -->
          <div v-if="optionsOf(item).length" class="options">
            <div
              v-for="opt in optionsOf(item)"
              :key="opt.key"
              :class="optionClass(item, opt.key)"
            >
              <span class="opt-key">{{ opt.key }}</span>
              <span class="opt-text" v-html="renderQuestionContent(opt.text)"></span>
            </div>
          </div>
          <div v-else class="detail-row"><b>答案：</b>{{ item.answer || '无' }}</div>

          <div class="detail-row" v-if="item.user_answer">
            <b>我的作答：</b>{{ item.user_answer }}
          </div>
          <div class="detail-row" v-if="item.answer_analysis">
            <b>解析：</b><span class="detail-html" v-html="renderQuestionContent(item.answer_analysis)"></span>
          </div>
          <div class="detail-actions">
            <button class="chop-btn" @click="chopQuestion(item.wrong_id)">斩题（已掌握）</button>
          </div>
        </div>
      </div>

      <div v-if="!items.length && !loading" class="empty">{{ emptyText }}</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>

    <!-- 斩题记录 -->
    <main class="list" v-else>
      <div v-for="item in choppedItems" :key="item.wrong_id" class="card">
        <div class="q-title">{{ renderQuestionSummary(item.question_content) }}</div>
        <div class="q-meta">
          <span class="tag">{{ item.subject_name || '未分类' }}</span>
          <span class="tag" v-if="item.subcategory">{{ item.subcategory }}</span>
          <span class="tag" :class="{ expiring: isExpiring(item) }">{{ countdown(item) }}</span>
        </div>
        <button class="unchop-btn" @click="unchop(item.wrong_id)">恢复为错题</button>
      </div>
      <div v-if="!choppedItems.length && !loading" class="empty">暂无斩题记录</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { renderQuestionContent, renderQuestionSummary } from '@/utils/questionRender';
import { useWrongbookStore } from '@/modules/wrongbook/store';
import { emitWrongQuestionsChanged } from '@/modules/wrongbook/events';

const router = useRouter();
const auth: any = (window as any).__VTJ_AUTH__;
const wrongbook = useWrongbookStore();
const items = computed<any[]>(() => wrongbook.visibleItems);
const choppedItems = ref<any[]>([]);
const loading = ref(false);
const expandedId = ref<number | null>(null);
const activeTab = ref<'wrong' | 'chopped'>('wrong');
const currentSubject = ref(0);
let offWrongbookRefresh: (() => void) | null = null;

// 固定三科分类。不再使用「科目·子科目」组合 tab：
// 子科目来自 /wrong-questions/subcategories，会随错题内容漂移，
// 且同一科目下多个子科目会同时高亮（需额外比较逻辑），对用户无意义。
const WRONG_TABS = [
  { key: 0, name: '全部' },
  { key: 1, name: '行测' },
  { key: 2, name: '申论' },
  { key: 3, name: '公专' },
];

const emptyText = computed(() =>
  currentSubject.value === 2 ? '暂无申论错题' : '暂无错题，继续加油！'
);

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const toggleDetail = (item: any) => {
  expandedId.value = expandedId.value === item.wrong_id ? null : item.wrong_id;
};

const switchTab = (tab: 'wrong' | 'chopped') => {
  activeTab.value = tab;
  expandedId.value = null;
  if (tab === 'chopped') fetchChopped();
  else fetchWrong();
};

const selectSubject = (sid: number) => {
  if (currentSubject.value === sid) return;
  currentSubject.value = sid;
  expandedId.value = null;
  fetchWrong();
};

// ===== 选项与答案态 =====

/** options 在库中是 JSON 字符串，结构可能是 {"A":"..."} 或 [{"key":"A","text":"..."}]，两种都要兼容。 */
const optionsOf = (item: any): Array<{ key: string; text: string }> => {
  const raw = item?.options;
  if (!raw) return [];
  let data: any = raw;
  if (typeof raw === 'string') {
    try {
      data = JSON.parse(raw);
    } catch {
      return [];
    }
  }
  if (Array.isArray(data)) {
    return data.map((o: any, i: number) => {
      if (o && typeof o === 'object') {
        const key = String(o.key ?? o.label ?? o.name ?? String.fromCharCode(65 + i));
        const text = String(o.text ?? o.value ?? o.content ?? o.option ?? '');
        return { key, text };
      }
      return { key: String.fromCharCode(65 + i), text: String(o) };
    });
  }
  if (data && typeof data === 'object') {
    return Object.keys(data).map((k) => ({ key: String(k), text: String(data[k]) }));
  }
  return [];
};

/** 只取 A-H 字母，兼容 "A" / "ABC" / "A,C" 等多种答案写法。 */
const letters = (v: any) => String(v || '').replace(/[^A-H]/g, '').toUpperCase();

const optionClass = (item: any, key: string) => {
  const correct = letters(item.answer);
  const user = letters(item.user_answer);
  if (correct.includes(key)) return 'opt correct';
  if (user.includes(key)) return 'opt wrong';
  return 'opt';
};

// ===== 斩题记录倒计时 =====

// 后端返回的 days_left 是快照值，不刷新就永远不变 —— 这正是「倒计时不动」的根因。
// 改为前端按 auto_delete_time 本地推算，并用 1s 定时器驱动，真正走动。
const now = ref(Date.now());
let ticker: any = null;

const parseTime = (s: any) => {
  if (!s) return 0;
  // 'YYYY-MM-DD HH:MM' -> 'YYYY-MM-DDTHH:MM'，避免 Safari 解析失败
  const t = String(s).trim().replace(' ', 'T');
  const d = new Date(t).getTime();
  return isNaN(d) ? 0 : d;
};

const pad2 = (n: number) => (n < 10 ? '0' + n : String(n));

const remainingMs = (item: any) => {
  const del = parseTime(item?.auto_delete_time);
  if (!del) return -1; // 无截止时间，沿用电脑端默认值 10 天
  return del - now.value;
};

const countdown = (item: any) => {
  const ms = remainingMs(item);
  if (ms < 0) return '10 天后删除';
  if (ms <= 0) return '即将删除';
  const d = Math.ceil(ms / 86400000);
  const h = Math.floor(ms / 3600000) % 24;
  const m = Math.floor(ms / 60000) % 60;
  const s = Math.floor(ms / 1000) % 60;
  return `${d} 天 ${pad2(h)}:${pad2(m)}:${pad2(s)} 后删除`;
};

/** 与电脑端一致：剩余 <= 2 天进入观察期高亮。 */
const isExpiring = (item: any) => {
  const ms = remainingMs(item);
  if (ms < 0) return false;
  return ms <= 2 * 86400000;
};

const startTicker = () => {
  if (ticker) return;
  ticker = setInterval(() => { now.value = Date.now(); }, 1000);
};

const stopTicker = () => {
  if (ticker) {
    clearInterval(ticker);
    ticker = null;
  }
};

// ===== 数据加载 =====

async function fetchWrong() {
  loading.value = true;
  try {
    await wrongbook.setFilters({
      subjectId: currentSubject.value > 0 ? currentSubject.value : null
    });
  } catch (e) {
    console.error('获取错题失败:', e);
  } finally {
    loading.value = false;
  }
}

async function fetchChopped() {
  loading.value = true;
  try {
    const res = await auth.apiFetch('/api/wrong-questions/zhanti/list');
    const data = await res.json();
    if (res.ok) choppedItems.value = data.items || [];
    else choppedItems.value = [];
    // 立即按当前时间重算一次，避免沿用后端快照值
    now.value = Date.now();
  } catch (e) {
    console.error('获取斩题记录失败:', e);
    choppedItems.value = [];
  } finally {
    loading.value = false;
  }
}

const chopQuestion = async (wrongId: number) => {
  try {
    await wrongbook.chop(wrongId);
    ElMessage.success('已斩题，10天后自动删除');
    expandedId.value = null;
  } catch (e) {
    console.error('斩题失败:', e);
    ElMessage.error('斩题失败，请稍后重试');
  }
};

const unchop = async (wrongId: number) => {
  try {
    const res = await auth.apiFetch('/api/wrong-questions/' + wrongId + '/unchop', { method: 'POST' });
    if (!res.ok) {
      ElMessage.error('恢复失败，请稍后重试');
      return;
    }
    ElMessage.success('已恢复到错题列表');
    emitWrongQuestionsChanged({ action: 'added' });
    await fetchChopped();
  } catch (e) {
    console.error('恢复失败:', e);
    ElMessage.error('恢复失败，请稍后重试');
  }
};

const goReview = () => {
  router.push('/mobile/wrong-review');
};

onMounted(() => {
  fetchWrong();
  offWrongbookRefresh = wrongbook.bindRefresh();
  startTicker();
});

onBeforeUnmount(() => {
  if (offWrongbookRefresh) {
    offWrongbookRefresh();
    offWrongbookRefresh = null;
  }
  stopTicker();
});
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #F5F7FA;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 48px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #e8ecf1;
  position: sticky;
  top: 0;
  z-index: 10;
}
.back-btn { background: none; border: none; font-size: 22px; color: #1a2b5f; cursor: pointer; padding: 4px 8px; }
.title { font-size: 16px; font-weight: 600; color: #1a2b5f; margin: 0; }
.spacer { width: 32px; }

.review-bar { padding: 12px 12px 0; }
.review-btn {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 14px;
  background: linear-gradient(135deg, #1A365D 0%, #2a5298 100%);
  color: #fff;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}
.review-sub { font-size: 12px; font-weight: 400; opacity: 0.85; }

.tabs { display: flex; margin: 12px 12px 0; background: #fff; border-radius: 10px; padding: 4px; }
.tab { flex: 1; text-align: center; padding: 8px; font-size: 14px; color: #5a6488; cursor: pointer; border-radius: 8px; }
.tab.active { background: #1A365D; color: #fff; font-weight: 600; }

.subject-tabs { display: flex; gap: 8px; padding: 12px 12px 0; overflow-x: auto; }
.subj-tab { flex-shrink: 0; padding: 6px 14px; font-size: 13px; color: #5a6488; background: #fff; border-radius: 16px; cursor: pointer; }
.subj-tab.active { background: #1A365D; color: #fff; }

.list { flex: 1; padding: 12px; }
.card { background: #fff; border-radius: 12px; padding: 16px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04); cursor: pointer; }
.q-title { font-size: 15px; font-weight: 600; color: #1a2b5f; line-height: 1.5; margin-bottom: 8px; }
.q-meta { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.tag { font-size: 12px; color: #5a6488; background: #f0f3f7; padding: 3px 8px; border-radius: 6px; }
.tag.expiring { color: #c41e3a; background: #fff2f0; }
.err { font-size: 12px; color: #c41e3a; }
.detail { margin-top: 12px; padding-top: 12px; border-top: 1px solid #f0f2f5; }
.detail-row { font-size: 13px; color: #5a6488; line-height: 1.6; margin-bottom: 6px; }
.detail-row b { color: #1a2b5f; }
.detail-actions { display: flex; gap: 8px; margin-top: 8px; }

/* 选项红绿态 */
.options { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.opt {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 8px 10px;
  border: 1px solid #e8ecf1;
  border-radius: 8px;
  font-size: 13px;
  color: #33384d;
  line-height: 1.6;
  background: #fafbfd;
}
.opt-key { flex-shrink: 0; font-weight: 700; color: #5a6488; }
.opt-text { flex: 1; word-break: break-word; }
.opt.correct { border-color: #10b981; background: #ecfdf5; }
.opt.correct .opt-key { color: #059669; }
.opt.wrong { border-color: #f5222d; background: #fff1f0; }
.opt.wrong .opt-key { color: #cf1322; }

.detail-html :deep(img) { max-width: 100%; height: auto; }

.chop-btn { min-height: 36px; padding: 0 16px; background: #10b981; color: #fff; border: none; border-radius: 8px; font-size: 13px; cursor: pointer; }
.unchop-btn { min-height: 36px; padding: 0 16px; border: 1px solid #ffccc7; background: #fff2f0; color: #c41e3a; border-radius: 8px; font-size: 13px; cursor: pointer; margin-top: 8px; }
.empty { text-align: center; color: #8899aa; padding: 40px 0; }
</style>