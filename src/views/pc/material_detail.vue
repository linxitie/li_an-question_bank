<template>
  <div class="md-page">
    <header class="md-top">
      <button class="md-back" @click="goBack">← 返回</button>
      <h1 class="md-title">{{ current ? current.title : '资料卡片' }}</h1>
      <span class="md-progress" v-if="cards.length">{{ index + 1 }} / {{ cards.length }}</span>
    </header>

    <div class="md-body">
      <!-- 左：知识模块（sub_categories 真实子类） + 字号 -->
      <aside class="md-side">
        <h2 class="md-side-title">知识模块</h2>
        <ul class="md-mods">
          <li
            v-for="m in modules"
            :key="m.name"
            :class="['md-mod', { on: m.name === activeModule }]"
            @click="pickModule(m.name)"
          >
            <span class="md-mod-name">{{ m.name }}</span>
            <span class="md-mod-count">{{ m.count }} 张</span>
          </li>
        </ul>
        <h2 class="md-side-title md-fs-title">字号</h2>
        <div class="md-fs">
          <button :class="{ on: scale === 0.9 }" @click="scale = 0.9">A-</button>
          <button :class="{ on: scale === 1 }" @click="scale = 1">A</button>
          <button :class="{ on: scale === 1.15 }" @click="scale = 1.15">A+</button>
        </div>
      </aside>

      <!-- 中：5 层堆叠卡 + 3D 翻转 -->
      <main class="md-stage" :style="{ '--sm-font-scale': String(scale) }">
        <div v-if="loading" class="md-empty">加载中…</div>
        <div v-else-if="!cards.length" class="md-empty">该模块暂无卡片</div>
        <div v-else class="md-stack" :class="{ flipped }">
          <div
            v-for="(c, i) in stack"
            :key="c.id"
            class="md-card"
            :class="'lv' + i"
            :style="layerStyle(i)"
            @click="i === 0 && (flipped = !flipped)"
          >
            <div class="md-inner">
              <section class="md-face front">
                <div class="md-face-head">
                  <span class="md-chip">{{ c.category || activeModule || '资料卡' }}</span>
                  <span class="md-idx">{{ index + i + 1 }} / {{ cards.length }}</span>
                </div>
                <h3 class="md-card-title">{{ c.title }}</h3>
                <p class="md-card-text">{{ c.card_front || c.title }}</p>
                <div class="md-face-foot"><span class="md-hint">点击卡片翻转看要点</span></div>
              </section>
              <section class="md-face back">
                <div class="md-face-head">
                  <span class="md-chip">要点</span>
                  <span class="md-idx">背面</span>
                </div>
                <p class="md-card-text">{{ c.card_back || '暂无背面内容' }}</p>
                <div class="md-face-foot"><span class="md-hint">点击翻回正面</span></div>
              </section>
            </div>
          </div>
        </div>

        <div class="md-actions">
          <button :disabled="index <= 0" @click="prev">上一张</button>
          <button class="primary" @click="flipped = !flipped">
            {{ flipped ? '再翻一遍' : '翻转看要点' }}
          </button>
          <button :disabled="index >= cards.length - 1" @click="next">下一张</button>
        </div>
        <p class="md-tip">「下一张」为直接切换并复位翻转；左侧可切换知识模块</p>
      </main>

      <!-- 右：本科目其他卡片 -->
      <aside class="md-side md-side-right">
        <h2 class="md-side-title">本科目其他卡片</h2>
        <ul class="md-others">
          <li
            v-for="(c, i) in cards"
            :key="c.id"
            :class="['md-other', { on: i === index }]"
            @click="jump(i)"
          >
            <span class="md-other-title">{{ c.title }}</span>
            <span class="md-other-cat">{{ c.category || '' }}</span>
          </li>
        </ul>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

type Card = {
  id: number;
  title: string;
  category?: string | null;
  card_front?: string | null;
  card_back?: string | null;
  subject?: string;
};

const route = useRoute();
const router = useRouter();

const subject = ref<string>((route.query.subject as string) || 'xingce');
const index = ref(0);
const flipped = ref(false);
const scale = ref(1);
const loading = ref(true);
const cards = ref<Card[]>([]);
const activeModule = ref<string>('');

const current = computed<Card | null>(() => cards.value[index.value] || null);
const stack = computed<Card[]>(() => cards.value.slice(index.value, index.value + 5));

const modules = computed(() => {
  const map = new Map<string, number>();
  for (const c of cards.value) {
    const k = c.category || '未分类';
    map.set(k, (map.get(k) || 0) + 1);
  }
  return Array.from(map.entries()).map(([name, count]) => ({ name, count }));
});

const layerStyle = (i: number) => ({
  transform: `translate(${i * 11}px, ${-i * 15}px) scale(${1 - 0.012 * i})`,
  zIndex: 10 - i,
  opacity: 1 - i * 0.04
});

const load = async () => {
  loading.value = true;
  flipped.value = false;
  index.value = 0;
  try {
    const qs = new URLSearchParams({ subject: subject.value, type: 'card' });
    const resp = await fetch(`/api/materials?${qs.toString()}`);
    const data = await resp.json();
    cards.value = (data.items || []) as Card[];
    const id = Number(route.query.id || 0);
    if (id) {
      const pos = cards.value.findIndex((c) => c.id === id);
      if (pos >= 0) index.value = pos;
    }
    activeModule.value = cards.value[index.value]?.category || '';
  } catch (e) {
    console.warn('[MaterialDetail] load failed:', (e as Error)?.message);
    cards.value = [];
  } finally {
    loading.value = false;
  }
};

const pickModule = (name: string) => {
  activeModule.value = name;
  const pos = cards.value.findIndex((c) => (c.category || '') === name);
  if (pos >= 0) {
    index.value = pos;
    flipped.value = false;
  }
};

const next = () => {
  if (index.value < cards.value.length - 1) {
    index.value += 1;
    flipped.value = false; // 直接切换 + 复位翻转
    activeModule.value = cards.value[index.value]?.category || activeModule.value;
  }
};
const prev = () => {
  if (index.value > 0) {
    index.value -= 1;
    flipped.value = false;
    activeModule.value = cards.value[index.value]?.category || activeModule.value;
  }
};
const jump = (i: number) => {
  index.value = i;
  flipped.value = false;
};
const goBack = () => router.back();

watch(subject, load);
onMounted(load);
</script>

<style scoped>
.md-page { min-height: 100vh; background: #f5f7fb; color: #1a2a4a; }
.md-top {
  display: flex; align-items: center; gap: 16px;
  height: 62px; padding: 0 36px; background: #fff; border-bottom: 1px solid #eef1f6;
}
.md-back { border: none; background: none; color: #5a6b85; font-size: 15px; cursor: pointer; }
.md-title { flex: 1; font-size: 18px; font-weight: 700; margin: 0; }
.md-progress { font-size: 13px; color: #66738a; }

.md-body { display: flex; gap: 16px; padding: 20px 28px; align-items: flex-start; }
.md-side { flex: 0 0 212px; width: 212px; background: #fff; border: 1px solid #eef1f6; border-radius: 16px; padding: 16px; }
.md-side-right { flex: 0 0 236px; width: 236px; }
.md-side-title { font-size: 15px; font-weight: 700; margin: 0 0 12px; }
.md-fs-title { margin-top: 18px; }
.md-mods, .md-others { list-style: none; margin: 0; padding: 0; }
.md-mod, .md-other {
  display: flex; align-items: center; justify-content: space-between;
  padding: 9px 10px; border-radius: 10px; cursor: pointer; font-size: 14px;
}
.md-mod:hover, .md-other:hover { background: #f7faff; }
.md-mod.on, .md-other.on { background: #eef4ff; color: #3b82f6; font-weight: 600; }
.md-mod-count, .md-other-cat { font-size: 12px; color: #8091a8; font-weight: 400; }
.md-other { flex-direction: column; align-items: flex-start; gap: 2px; }
.md-other-title { font-size: 14px; }

.md-fs { display: flex; gap: 8px; }
.md-fs button {
  flex: 1; height: 34px; border-radius: 9px; border: 1px solid #eef1f6;
  background: #fff; color: #5a6b85; cursor: pointer;
}
.md-fs button.on { border-color: #3b82f6; color: #3b82f6; }

.md-stage { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; align-items: center; }
.md-stack { position: relative; width: min(600px, 100%); height: 552px; perspective: 1200px; }
@media (max-width: 1360px) {
  .md-side-right { flex: 0 0 196px; width: 196px; }
}
@media (max-width: 1180px) {
  .md-side { flex: 0 0 184px; width: 184px; }
  .md-side-right { flex: 0 0 172px; width: 172px; }
}
.md-card {
  position: absolute; inset: 0; border-radius: 18px; background: #fff;
  border: 1px solid #eef1f6; box-shadow: 0 6px 18px rgba(26, 42, 74, 0.1);
  transition: transform 0.35s ease, box-shadow 0.35s ease;
}
.md-card.lv1 { background: #fdfdff; box-shadow: 0 5px 14px rgba(26, 42, 74, 0.07); }
.md-card.lv2 { background: #fbfcff; box-shadow: 0 4px 12px rgba(26, 42, 74, 0.05); }
.md-card.lv3 { background: #f9fbff; box-shadow: 0 3px 10px rgba(26, 42, 74, 0.04); }
.md-card.lv4 { background: #f8faff; box-shadow: 0 2px 8px rgba(26, 42, 74, 0.03); }
.md-card.lv0 { cursor: pointer; }
.md-inner {
  position: relative; width: 100%; height: 100%;
  transition: transform 0.4s ease; transform-style: preserve-3d;
}
.md-stack.flipped .md-card.lv0 .md-inner { transform: rotateY(180deg); }
.md-face {
  position: absolute; inset: 0; padding: 22px; border-radius: 18px;
  display: flex; flex-direction: column; backface-visibility: hidden;
  -webkit-backface-visibility: hidden; background: #fff;
}
.md-face.back { transform: rotateY(180deg); background: #f7fbff; }
.md-face-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.md-chip {
  font-size: 11px; color: #3b82f6; background: #eef4ff;
  border-radius: 10px; padding: 4px 10px;
}
.md-idx { font-size: 12px; color: #66738a; }
.md-card-title { font-size: calc(24px * var(--sm-font-scale, 1)); font-weight: 700; margin: 0 0 14px; }
.md-card-text {
  font-size: calc(15px * var(--sm-font-scale, 1)); line-height: 1.7;
  color: #4a5a75; margin: 0; flex: 1; overflow-y: auto;
}
.md-face-foot { margin-top: 12px; }
.md-hint { font-size: 12px; color: #3b82f6; }

.md-actions { display: flex; gap: 18px; margin-top: 22px; }
.md-actions button {
  width: 170px; height: 46px; border-radius: 12px; border: 1px solid #eef1f6;
  background: #fff; color: #5a6b85; font-size: 14px; cursor: pointer;
}
.md-actions button.primary { background: #3b82f6; border-color: #3b82f6; color: #fff; font-weight: 600; }
.md-actions button:disabled { opacity: 0.45; cursor: not-allowed; }
.md-tip { margin-top: 14px; font-size: 13px; color: #8091a8; }
.md-empty { padding: 80px 0; color: #8091a8; }
</style>
