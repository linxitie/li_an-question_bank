<template>
  <div class="page" :class="`theme-${activeSubject}`">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">备考资料</h1>
      <span class="spacer"></span>
    </header>

    <!-- 科目 Tab -->
    <div class="tabs">
      <div
        v-for="s in subjects"
        :key="s.key"
        :class="['tab', { active: activeSubject === s.key }]"
        @click="switchSubject(s.key)"
      >
        {{ s.name }}
      </div>
    </div>

      <!-- 卡片栈（B4）：5 层堆叠 + 3D 翻转 + 上一张/下一张 + 字号三档 -->
      <section v-if="cardItems.length" class="stack-wrap" :style="stackStyle">
        <div class="stack" :class="{ 'is-flipped': flipped, 'is-leaving': phase === 'leaving', 'is-entering': phase === 'entering' }">
          <div
            v-for="(c, i) in stackCards"
            :key="c.id"
            class="stack-card"
            :class="'lv' + i"
            :style="layerStyle(i)"
            @click="i === 0 && flip()"
          >
            <div class="card-inner">
              <div class="card-face front">
                <div class="card-head">
                  <span class="tag">{{ c.category || '资料卡' }}</span>
                  <span class="idx">{{ cardIndex + 1 }} / {{ cardItems.length }}</span>
                </div>
                <h3 class="card-title">{{ c.title }}</h3>
                <p class="card-text">{{ c.card_front || c.title }}</p>
                <div class="card-foot"><span class="hint">点击卡片翻转看要点</span></div>
              </div>
              <div class="card-face back">
                <div class="card-head">
                  <span class="tag">要点</span>
                  <span class="idx">背面</span>
                </div>
                <p class="card-text">{{ c.card_back || '暂无背面内容' }}</p>
                <div class="card-foot"><span class="hint">点击翻回正面</span></div>
              </div>
            </div>
          </div>
        </div>
        <div class="stack-bar">
          <button :disabled="cardIndex <= 0" @click="prevCard">上一张</button>
          <button class="primary" @click="flip">{{ flipped ? '再翻一遍' : '翻转看要点' }}</button>
          <button :disabled="cardIndex >= cardItems.length - 1" @click="nextCard">下一张</button>
        </div>
        <div class="font-row">
          <span>字号</span>
          <button :class="{ on: fontScale === 0.9 }" @click="setScale(0.9)">A-</button>
          <button :class="{ on: fontScale === 1 }" @click="setScale(1)">A</button>
          <button :class="{ on: fontScale === 1.15 }" @click="setScale(1.15)">A+</button>
        </div>
      </section>

    <main class="list">
      <div v-for="m in materials" :key="m.id" class="card" @click="toggleDetail(m)">
        <div class="m-title">{{ m.title }}</div>
        <div class="m-meta">
          <span class="tag">{{ typeName(m.type) }}</span>
          <span v-if="m.is_generic" class="tag tag-generic">通用技巧</span>
          <span v-if="m.duration" class="tag">⏱ {{ m.duration }}分钟</span>
          <span v-if="m.read_time" class="tag">阅读 {{ m.read_time }}分钟</span>
          <span v-if="m.is_studied" class="done">已学</span>
          <span v-if="m.progress_percent" class="progress">进度 {{ m.progress_percent }}%</span>
        </div>
        <div v-if="expandedId === m.id" class="detail" @click.stop>
          <p v-if="m.summary" class="summary">{{ m.summary }}</p>
          <button class="view-btn" @click="openDetail(m)">查看详情</button>
        </div>
      </div>
      <div v-if="!materials.length && !loading" class="empty">该科目暂无备考资料</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>

    <!-- 资料详情弹层（页内展示；原实现跳 /materials/{subject}?id= 该路由不存在，必然 404） -->
    <div v-if="detailVisible" class="modal-mask" @click="closeDetail">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <span class="modal-title">{{ detailData ? detailData.title : '' }}</span>
          <button class="modal-close" @click="closeDetail" aria-label="关闭">✕</button>
        </div>
        <div class="modal-body">
          <div v-if="detailLoading" class="empty">加载中...</div>
          <div v-else-if="detailError" class="empty">{{ detailError }}</div>
          <template v-else-if="detailData">
            <video
              v-if="detailData.video_url"
              class="detail-video"
              :src="detailData.video_url"
              controls
              playsinline
            ></video>
            <img
              v-if="detailData.cover_image"
              class="detail-cover"
              :src="detailData.cover_image"
              alt="资料封面"
            />
            <div class="m-meta">
              <span class="tag">{{ typeName(detailData.type) }}</span>
              <span v-if="detailData.read_time" class="tag">阅读 {{ detailData.read_time }}分钟</span>
            </div>
            <p v-if="detailData.summary" class="summary">{{ detailData.summary }}</p>
            <div class="detail-content" v-html="renderQuestionContent(detailData.content)"></div>
            <div v-if="detailData.card_back" class="detail-card-back" v-html="renderQuestionContent(detailData.card_back)"></div>
          </template>
        </div>
        <div class="modal-actions">
          <button class="action-btn" @click="markStudied">标记已学</button>
          <button class="action-btn" @click="closeDetail">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useRouter } from 'vue-router';
import { renderQuestionContent } from '@/utils/questionRender';
import { ElMessage } from 'element-plus';
import { useLibraryStore } from '@/modules/library/store';

const router = useRouter();
const library = useLibraryStore();
const { items: materials, loading, selected: detailData } = storeToRefs(library);

const subjects = [
  { key: 'xingce', name: '行测' },
  { key: 'shenlun', name: '申论' },
  { key: 'gongzhuan', name: '公专' }
] as const;
const activeSubject = ref<'xingce' | 'shenlun' | 'gongzhuan'>('xingce');
const expandedId = ref<number | null>(null);

// ===== 资料详情弹层 =====
const detailVisible = ref(false);
const detailLoading = ref(false);
const detailError = ref('');
const currentMaterial = ref<any>(null);

const closeDetail = () => {
  detailVisible.value = false;
  detailError.value = '';
  currentMaterial.value = null;
  library.clearSelection();
};

const loadDetail = async (id: number) => {
  detailLoading.value = true;
  detailError.value = '';
  try {
    const detail = await library.openMaterial(id);
    if (!detail) {
      detailError.value = library.error || '资料加载失败，请检查网络后重试';
    }
  } finally {
    detailLoading.value = false;
  }
};

// 上报学习进度（进度只存后端，不写 localStorage）
const markStudied = async () => {
  const m = currentMaterial.value;
  if (!m || m.id == null) return;
  const ok = await library.reportProgress(m.id, 100, true);
  if (ok) {
    ElMessage.success('已标记为学完');
    closeDetail();
  } else {
    ElMessage.error('提交进度失败，请稍后重试');
  }
};

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const typeName = (t: string) => {
  return {
    video_intro: '入门视频',
    video_advanced: '进阶视频',
    article: '文章',
    card: '知识卡片'
  }[t] || '资料';
};

const switchSubject = (key: 'xingce' | 'shenlun' | 'gongzhuan') => {
  activeSubject.value = key;
  expandedId.value = null;
  fetchMaterials();
};

const toggleDetail = (m: any) => {
  expandedId.value = expandedId.value === m.id ? null : m.id;
};

const fetchMaterials = async () => {
  await library.load({
    subject: activeSubject.value,
    page: 1,
    pageSize: 50
  });
};

const openDetail = async (m: any) => {
  if (!m || m.id == null) {
    ElMessage.info('该资料暂时无法打开');
    return;
  }
  currentMaterial.value = m;
  detailVisible.value = true;
  await loadDetail(m.id);
};

// ===== B4 卡片栈：5 层堆叠 + 翻转 + 切换 + 字号 =====
const STACK_LAYERS = 5;
const cardIndex = ref(0);
const flipped = ref(false);
const fontScale = ref(1);

const cardItems = computed(() =>
  (materials.value as any[]).filter((m) => m.type === 'card' && m.card_front)
);
const stackCards = computed(() =>
  cardItems.value.slice(cardIndex.value, cardIndex.value + STACK_LAYERS)
);
const flip = () => {
  if (cardItems.value.length) flipped.value = !flipped.value;
};
// 翻页动效（与电脑端 detail 页同构）：上一层走出 → 新卡片进入
const phase = ref<'idle' | 'leaving' | 'entering'>('idle');
let phaseTimer: number | undefined;
function playSwitch(delta: number) {
  if (phase.value !== 'idle') return;
  phase.value = 'leaving';
  phaseTimer = window.setTimeout(() => {
    cardIndex.value += delta;
    flipped.value = false;
    phase.value = 'entering';
    phaseTimer = window.setTimeout(() => { phase.value = 'idle'; }, 240);
  }, 200);
}
const nextCard = () => {
  if (cardIndex.value < cardItems.value.length - 1) playSwitch(1);
};
const prevCard = () => {
  if (cardIndex.value > 0) playSwitch(-1);
};
const setScale = (v: number) => {
  fontScale.value = v;
};
// 后层：逐层上移 15px、右移 11px、缩放 -1.2%，投影在 CSS 里按层号递减
const layerStyle = (i: number) => ({
  transform: `translate(${i * 11}px, ${-i * 15}px) scale(${1 - 0.012 * i})`,
  zIndex: 10 - i,
  opacity: 1 - i * 0.04
});
const stackStyle = computed(() => ({ '--sm-font-scale': String(fontScale.value) }));

onMounted(fetchMaterials);
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
}
.back-btn {
  background: none;
  border: none;
  font-size: 22px;
  color: #1a2b5f;
  cursor: pointer;
  padding: 4px 8px;
}
.title {
  font-size: 16px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0;
}
.spacer {
  width: 32px;
}
.tabs {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  background: #fff;
  border-bottom: 1px solid #f0f2f5;
}
.tab {
  flex: 1;
  text-align: center;
  padding: 8px 0;
  border-radius: 8px;
  font-size: 14px;
  color: #5a6488;
  background: #f0f3f7;
  cursor: pointer;
}
.tab.active {
  background: #1a2b5f;
  color: #fff;
}
.list {
  flex: 1;
  padding: 12px;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
}
.m-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  line-height: 1.5;
  margin-bottom: 8px;
}
/* A 方案：通用技巧标 */
.tag-generic { background: #fff7e6; color: #b45309; }
.m-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.tag {
  font-size: 12px;
  color: #5a6488;
  background: #f0f3f7;
  padding: 3px 8px;
  border-radius: 6px;
}
.done {
  font-size: 12px;
  color: #10b981;
  font-weight: 600;
}
.progress {
  font-size: 12px;
  color: #f59e0b;
}
.detail {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f2f5;
}
.summary {
  font-size: 13px;
  color: #5a6488;
  line-height: 1.6;
  margin: 0 0 10px;
}
.view-btn {
  min-height: 36px;
  padding: 0 16px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #1a2b5f, #1e3470);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}
.empty {
  text-align: center;
  color: #8899aa;
  padding: 40px 0;
}

/* ===== 资料详情弹层 ===== */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 1000;
}
.modal {
  background: #fff;
  border-radius: 14px;
  width: 100%;
  max-width: 560px;
  max-height: 82vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #eef1f5;
  flex-shrink: 0;
}
.modal-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  line-height: 1.4;
  padding-right: 8px;
}
.modal-close {
  background: none;
  border: none;
  font-size: 18px;
  color: #8899aa;
  cursor: pointer;
  min-width: 44px;
  min-height: 44px;
  flex-shrink: 0;
}
.modal-body {
  padding: 16px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  flex: 1;
}
.detail-video {
  width: 100%;
  max-height: 220px;
  border-radius: 8px;
  margin-bottom: 12px;
  background: #000;
}
.detail-cover {
  width: 100%;
  border-radius: 8px;
  margin-bottom: 12px;
}
.summary {
  font-size: 13px;
  color: #5a6488;
  line-height: 1.7;
  margin: 10px 0;
}
.detail-content {
  font-size: 14px;
  line-height: 1.8;
  color: #1a2a3a;
}
.detail-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
}
.detail-card-back {
  margin-top: 14px;
  padding: 12px;
  background: #f8f9fc;
  border-radius: 8px;
  font-size: 13px;
  color: #1a2b5f;
  line-height: 1.7;
}
.modal-actions {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid #eef1f5;
  flex-shrink: 0;
}
.action-btn {
  flex: 1;
  min-height: 44px;
  border: 1px solid #1a2b5f;
  background: #1a2b5f;
  color: #fff;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
}
.action-btn:active {
  opacity: 0.85;
}

/* ===== B4 卡片栈：5 层堆叠 + 3D 翻转 + 字号变量 ===== */
.stack-wrap { padding: 14px 16px 4px; }
.stack { position: relative; height: 252px; perspective: 1200px; }
.stack-card {
  position: absolute; left: 0; right: 0; top: 22px; height: 230px;
  border-radius: 16px; background: #fff; border: 1px solid #eef1f6;
  box-shadow: 0 6px 18px rgba(26, 42, 74, 0.10);
  transition: transform 0.35s ease, box-shadow 0.35s ease;
}
.stack-card.lv1 { box-shadow: 0 5px 14px rgba(26, 42, 74, 0.07); background: #fdfdff; }
.stack-card.lv2 { box-shadow: 0 4px 12px rgba(26, 42, 74, 0.05); background: #fbfcff; }
.stack-card.lv3 { box-shadow: 0 3px 10px rgba(26, 42, 74, 0.04); background: #f9fbff; }
.stack-card.lv4 { box-shadow: 0 2px 8px rgba(26, 42, 74, 0.03); background: #f8faff; }
.stack-card.lv0 { cursor: pointer; }
.card-inner {
  position: relative; width: 100%; height: 100%;
  transition: transform 0.4s ease; transform-style: preserve-3d;
}
.stack.is-flipped .stack-card.lv0 .card-inner { transform: rotateY(180deg); }
.card-face {
  position: absolute; inset: 0; padding: 14px 16px;
  display: flex; flex-direction: column;
  backface-visibility: hidden; -webkit-backface-visibility: hidden;
  border-radius: 16px;
}
.card-face.back { transform: rotateY(180deg); background: #f7fbff; }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.idx { font-size: 11px; color: #66738a; }
.card-title {
  font-size: calc(17px * var(--sm-font-scale, 1)); font-weight: 700;
  color: #1a2a4a; margin: 0 0 8px; line-height: 1.4;
}
.card-text {
  font-size: calc(13px * var(--sm-font-scale, 1)); line-height: 1.65;
  color: #4a5a75; margin: 0; flex: 1; overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}
.card-foot { margin-top: 8px; }
.hint { font-size: 11px; color: #3b82f6; }
.stack-bar { display: flex; gap: 10px; margin-top: 12px; }
.stack-bar button {
  flex: 1; height: 44px; border-radius: 10px; border: 1px solid #eef1f6;
  background: #fff; color: #5a6b85; font-size: 13px;
}
.stack-bar button.primary { background: #3b82f6; border-color: #3b82f6; color: #fff; font-weight: 600; }
.stack-bar button:disabled { opacity: 0.45; }
.font-row { display: flex; align-items: center; gap: 8px; margin: 10px 0 2px; font-size: 12px; color: #8899aa; }
.font-row button {
  height: 30px; min-width: 44px; border-radius: 8px;
  border: 1px solid #eef1f6; background: #fff; color: #5a6b85;
}
.font-row button.on { border-color: #3b82f6; color: #3b82f6; }

/* ===== 修复：科目三色主题（与电脑端 detail 页一致） ===== */
.theme-xingce { --c1: #1e3a8a; --c2: #3b82f6; --c-soft: #eef4ff; }
.theme-shenlun { --c1: #047857; --c2: #34d399; --c-soft: #ecfdf5; }
.theme-gongzhuan { --c1: #9f1239; --c2: #f43f5e; --c-soft: #fff1f4; }

/* 修复 1：科目栏不再被卡片盖住 */
.tabs {
  position: sticky;
  top: 56px;
  z-index: 30;
  background: #fff;
  box-shadow: 0 6px 14px rgba(26, 42, 74, 0.06);
}
.tab.active {
  background: var(--c1);
  border-color: var(--c1);
  color: #fff;
}
.stack-wrap { padding: 18px 16px 6px; }
.stack { z-index: 1; }

/* 修复 2：卡片头部改成科目渐变条，正文区收紧留白 */
.stack-card { background: #fff; }
.card-face { padding: 0; }
.card-face .card-head {
  margin: 0;
  padding: 12px 16px;
  background: linear-gradient(135deg, var(--c1), var(--c2));
  border-radius: 16px 16px 0 0;
}
.card-face .card-head .tag {
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
  border: none;
}
.card-face .card-head .idx { color: rgba(255, 255, 255, 0.85); }
.card-face .card-title { padding: 12px 16px 0; }
.card-face .card-text { padding: 6px 16px 0; }
.card-face .card-foot { padding: 6px 16px 12px; margin-top: 0; }
.card-face.back { background: var(--c-soft); }
.card-face.back .card-head {
  background: linear-gradient(135deg, var(--c1), var(--c2));
}

/* 修复 3：翻页动效（走出 / 进入） */
.stack-card.lv0 { transition: transform 0.2s ease, opacity 0.2s ease; }
.stack.is-leaving .stack-card.lv0 {
  transform: translateX(-118%) rotate(-7deg);
  opacity: 0;
}
.stack.is-entering .stack-card.lv0 {
  animation: sm-enter 0.24s ease-out both;
}
@keyframes sm-enter {
  from { transform: translateX(46%) rotate(5deg); opacity: 0; }
  to { transform: translateX(0) rotate(0); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .stack.is-leaving .stack-card.lv0,
  .stack.is-entering .stack-card.lv0 { animation: none; transform: none; opacity: 1; }
}
</style>
