<template>
  <div class="page" :class="`theme-${activeSubject}`">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">备考资料</h1>
      <button class="create-btn" @click="createOpen = true">
        <span class="create-plus">＋</span>创建
      </button>
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

      <!-- 卡片栈：后面是「真卡片」（翻转时能看到它的文字），顶层卡单独做 3D 翻转 -->
      <section v-if="cardItems.length" class="stack-wrap" :style="stackStyle">
        <div class="stack" :class="{ 'is-flipped': flipped, 'is-leaving': phase === 'leaving', 'is-entering': phase === 'entering', 'is-entering-prev': phase === 'entering-prev' }">
          <!-- 后面的卡：真内容，只露出一条渐变头；容器透明，不会出现白框 -->
          <div
            v-for="(c, i) in behindCards"
            :key="c.id"
            class="stack-card behind"
            :style="behindStyle(i)"
          >
            <div class="card-face front">
              <div class="card-head">
                <span class="tag">{{ c.category || '资料卡' }}</span>
                <span class="idx">{{ cardIndex + i + 2 }} / {{ cardItems.length }}</span>
              </div>
              <h3 class="card-title">{{ c.title }}</h3>
              <p class="card-text">{{ c.card_front || c.title }}</p>
            </div>
          </div>

          <div v-if="currentCard" class="stack-card lv0" @click="flip()">
            <div class="card-inner">
              <div class="card-face front">
                <div class="card-head">
                  <span class="tag">{{ currentCard.category || '资料卡' }}</span>
                  <span class="idx">{{ cardIndex + 1 }} / {{ cardItems.length }}</span>
                </div>
                <h3 class="card-title">{{ currentCard.title }}</h3>
                <p class="card-text">{{ currentCard.card_front || currentCard.title }}</p>
                <div class="card-foot">
                  <span class="hint">点击卡片翻转看要点</span>
                  <button class="card-act" @click.stop="openCardImages(currentCard)">
                    {{ actLabel }}
                  </button>
                </div>
              </div>
              <div class="card-face back">
                <div class="card-head">
                  <span class="tag">要点</span>
                  <span class="idx">背面</span>
                </div>
                <p class="card-text">{{ currentCard.card_back || '暂无背面内容' }}</p>
                <div class="card-foot">
                  <span class="hint">点击翻回正面</span>
                  <button class="card-act" @click.stop="openCardImages(currentCard)">
                    {{ actLabel }}
                  </button>
                </div>
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

    <!-- 创建卡片：选科目 → 填字段 + 1~2 张配图 → 保存即公开（免审批） -->
    <CardCreateForm
      :open="createOpen"
      :subject="activeSubject"
      @close="createOpen = false"
      @saved="onCardCreated"
    />

    <!-- 卡片上的「查看配图」直接打开全图，不用再去下面的列表里找 -->
    <ImageLightbox
      :open="lightbox.open"
      :images="lightbox.images"
      :start-index="lightbox.index"
      @close="lightbox.open = false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useRouter } from 'vue-router';
import { renderQuestionContent } from '@/utils/questionRender';
import { ElMessage } from 'element-plus';
import { useLibraryStore } from '@/modules/library/store';
import { collectCardImages } from '@/utils/materialImages';
import CardCreateForm from '@/components/materials/CardCreateForm.vue';
import ImageLightbox from '@/components/materials/ImageLightbox.vue';

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

// ===== 创建卡片（学生自建，免审批）=====
const createOpen = ref(false);
const onCardCreated = async (payload: Record<string, unknown>) => {
  createOpen.value = false;
  const subj = String(payload?.subject || activeSubject.value);
  if (subj !== activeSubject.value) activeSubject.value = subj as typeof activeSubject.value;
  ElMessage.success('卡片已创建并公开展示');
  await fetchMaterials();
};

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

// ===== 卡片栈：后面卡（真内容）+ 顶层卡 3D 翻转 + 切换 + 字号 =====
const BEHIND_MAX = 3;
const cardIndex = ref(0);
const flipped = ref(false);
const fontScale = ref(1);

const cardItems = computed(() =>
  (materials.value as any[]).filter((m) => m.type === 'card' && m.card_front)
);
const currentCard = computed(() => cardItems.value[cardIndex.value] || null);
/** 后面叠着的卡片（真内容，翻转时能看见它的文字） */
const behindCards = computed(() =>
  cardItems.value.slice(cardIndex.value + 1, cardIndex.value + 1 + BEHIND_MAX)
);
/** 当前卡的全部配图（封面 + 正文附图），用于卡片上的「查看配图」 */
const currentImages = computed(() => collectCardImages(currentCard.value as any));
const actLabel = computed(() =>
  currentImages.value.length ? `查看配图（${currentImages.value.length}）` : '查看详情'
);

/**
 * 后面卡片的定位：只往上露一条（-9px/层）并左右各内缩 6px/层，
 * 这样它的白色卡身完全被顶层卡盖住 —— 不会再出现「白框」，
 * 但翻转时顶层卡转开，后面的卡片正文就能看见。
 */
const behindStyle = (i: number) => ({
  top: `${30 - (i + 1) * 9}px`,
  left: `${(i + 1) * 6}px`,
  right: `${(i + 1) * 6}px`,
  zIndex: 8 - i
});

// 全图查看器（复用电脑端的同一个组件）
const lightbox = reactive({ open: false, index: 0, images: [] as string[] });
const openCardImages = (c: any) => {
  const list = collectCardImages(c);
  if (list.length) {
    lightbox.images = list;
    lightbox.index = 0;
    lightbox.open = true;
    return;
  }
  openDetail(c);
};

const flip = () => {
  if (cardItems.value.length) flipped.value = !flipped.value;
};
// 翻页动效：两个方向都朝「右」——下一页时当前卡向右飞走，上一页时上一张从右边飞回来
const phase = ref<'idle' | 'leaving' | 'entering' | 'entering-prev'>('idle');
let phaseTimer: number | undefined;
function playSwitch(delta: number) {
  if (phase.value !== 'idle') return;
  if (delta > 0) {
    // 下一页：当前卡向右飞出 → 换下一张 → 新卡轻微落定（它本来就在后面）
    phase.value = 'leaving';
    phaseTimer = window.setTimeout(() => {
      cardIndex.value += 1;
      flipped.value = false;
      phase.value = 'entering';
      phaseTimer = window.setTimeout(() => { phase.value = 'idle'; }, 240);
    }, 220);
  } else {
    // 上一页：先回退索引，再让上一张从右侧飞回来盖住
    cardIndex.value -= 1;
    flipped.value = false;
    phase.value = 'entering-prev';
    phaseTimer = window.setTimeout(() => { phase.value = 'idle'; }, 280);
  }
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
  flex: 1;
  text-align: center;
}
/* 创建卡片入口：放在顶栏右侧，避免右下角悬浮按钮遮挡列表 */
.create-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-width: 66px;
  height: 30px;
  padding: 0 10px;
  border: 1px solid #c9d9f8;
  border-radius: 15px;
  background: #eef4ff;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.create-btn:active {
  background: #dbe8ff;
}
.create-plus {
  font-size: 14px;
  line-height: 1;
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

/* ===== 卡片栈：后面真卡片 + 顶层卡 3D 翻转 ===== */
.stack-wrap { padding: 14px 16px 4px; }
.stack { position: relative; height: 256px; }
.stack-card {
  position: absolute;
  left: 0;
  right: 0;
  top: 30px;
  height: 226px;
  border-radius: 16px;
  /* 容器必须透明：白色由正/反两面提供，否则翻转时会露出这块白底 */
  background: transparent;
  border: none;
  transition: transform 0.35s ease, box-shadow 0.35s ease, opacity 0.22s ease;
  z-index: 1;
  /* 3D 透视必须挂在「旋转元素的父级」上：card-inner 是 .stack-card 的子元素 */
  perspective: 900px;
  perspective-origin: 50% 45%;
}
/* 后面的卡：不投影、不可点，只作为「翻过去能看到的那张」 */
.stack-card.behind {
  z-index: 1;
  pointer-events: none;
  box-shadow: none;
}
.stack-card.behind .card-face { box-shadow: 0 6px 14px rgba(26, 42, 74, 0.08); }
.stack-card.lv0 { cursor: pointer; box-shadow: 0 10px 24px rgba(26, 42, 74, 0.14); z-index: 10; }
.card-inner {
  position: relative;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  transition: transform 0.5s cubic-bezier(0.35, 0.1, 0.25, 1);
  will-change: transform;
}
.stack.is-flipped .stack-card.lv0 .card-inner { transform: rotateY(180deg); }
.stack.is-flipped .stack-card.lv0 { box-shadow: 0 16px 34px rgba(26, 42, 74, 0.2); }
.card-face {
  position: absolute;
  inset: 0;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  border-radius: 16px;
  overflow: hidden;
  background: #fff;
}
.card-face.back {
  transform: rotateY(180deg) translateZ(1px);
  background: #f7fbff;
}
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

/* 修复 2：卡片头部改成科目渐变条，正文区收紧留白
   注意：.stack-card 容器必须保持透明（白色由 .card-face 提供），
   否则翻转时会在原地露出一块白底 —— 这正是之前「白框」的来源。 */
.stack-card { background: transparent; }
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

/* 卡片底部：翻转提示 + 「查看配图 / 查看详情」入口（不再去下面列表里找） */
.card-face .card-foot {
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-face .card-foot .hint { flex: 1 1 auto; min-width: 0; }
.card-act {
  flex: none;
  height: 28px;
  padding: 0 12px;
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: 14px;
  background: var(--c1);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
}
.card-act:active { opacity: 0.82; }
.card-face.back .card-act {
  border-color: transparent;
  background: var(--c1);
}

/* 翻页动效：两个方向都朝右
   · 下一页：当前卡向右飞走（translateX +118%），换过来的新卡轻轻落定
   · 上一页：上一张从右侧飞回来（translateX 60% → 0）盖住当前卡 */
.stack-card.lv0 { transition: transform 0.22s ease, opacity 0.22s ease; }
.stack.is-leaving .stack-card.lv0 {
  transform: translateX(118%) rotate(7deg);
  opacity: 0;
}
.stack.is-entering .stack-card.lv0 {
  animation: sm-enter 0.24s ease-out both;
}
@keyframes sm-enter {
  from { transform: scale(0.97); opacity: 0.55; }
  to { transform: scale(1); opacity: 1; }
}
.stack.is-entering-prev .stack-card.lv0 {
  animation: sm-enter-right 0.28s cubic-bezier(0.25, 0.9, 0.3, 1) both;
}
@keyframes sm-enter-right {
  from { transform: translateX(62%) rotate(-5deg); opacity: 0.25; }
  to { transform: translateX(0) rotate(0); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .stack.is-leaving .stack-card.lv0,
  .stack.is-entering .stack-card.lv0,
  .stack.is-entering-prev .stack-card.lv0 { animation: none; transform: none; opacity: 1; }
}
</style>
