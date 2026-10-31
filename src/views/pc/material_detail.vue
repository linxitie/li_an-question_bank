<template>
  <div class="md-page" :class="'theme-' + subject">
    <header class="md-top">
      <button class="md-back" @click="goBack">鈫?杩斿洖</button>
      <h1 class="md-title">{{ current ? current.title : '璧勬枡鍗＄墖' }}</h1>
      <span class="md-progress" v-if="cards.length">{{ index + 1 }} / {{ cards.length }}</span>
    </header>

    <div class="md-body">
      <!-- 宸︼細鐭ヨ瘑妯″潡锛坰ub_categories 鐪熷疄瀛愮被锛?+ 瀛楀彿 -->
      <aside class="md-side">
        <h2 class="md-side-title">鐭ヨ瘑妯″潡</h2>
        <ul class="md-mods">
          <li
            v-for="m in modules"
            :key="m.name"
            :class="['md-mod', { on: m.name === activeModule }]"
            @click="pickModule(m.name)"
          >
            <span class="md-mod-name">{{ m.name }}</span>
            <span class="md-mod-count">{{ m.count }} 寮?/span>
          </li>
        </ul>
        <h2 class="md-side-title md-fs-title">瀛楀彿</h2>
        <div class="md-fs">
          <button :class="{ on: scale === 0.9 }" @click="scale = 0.9">A-</button>
          <button :class="{ on: scale === 1 }" @click="scale = 1">A</button>
          <button :class="{ on: scale === 1.15 }" @click="scale = 1.15">A+</button>
        </div>
      </aside>

      <!-- 涓細5 灞傚爢鍙犲崱 + 3D 缈昏浆 -->
      <main class="md-stage" :style="{ '--sm-font-scale': String(scale) }">
        <div v-if="loading" class="md-empty">鍔犺浇涓€?/div>
        <div v-else-if="!cards.length" class="md-empty">璇ユā鍧楁殏鏃犲崱鐗?/div>
        <div v-else class="md-stack" :class="{ flipped }">
          <div
            v-for="(c, i) in stack"
            :key="c.id"
            class="md-card"
            :class="['lv' + i, { lift: i === 0 && lifting, leaving: i === 0 && leaving }]"
            :style="layerStyle(i)"
            @click="i === 0 && flip()"
          >
            <div class="md-inner">
              <section class="md-face front">
                <!-- 绉戠洰娓愬彉灏侀潰甯︼細琛屾祴钃?/ 鐢宠缁?/ 鍏笓绾紝涓庝富椤典笁鑹蹭竴鑷?-->
                <div class="md-cover" :class="'cover-' + subject">
                  <span class="md-chip-light">{{ c.category || activeModule || '璧勬枡鍗? }}</span>
                  <span class="md-idx-light">{{ index + i + 1 }} / {{ cards.length }}</span>
                </div>
                <!-- 閰嶅浘鍗★細瀵煎叆鏃跺甫灏侀潰鍒楋紙cover锛夌殑鍗＄墖鍦ㄨ繖閲屽嚭鍥撅紱鏃犲浘涓嶅崰浣?-->
                <div v-if="c.cover_image" class="md-card-cover">
                  <img :src="c.cover_image" :alt="c.title + ' 閰嶅浘'" loading="lazy" />
                </div>
                <h3 class="md-card-title">{{ c.title }}</h3>
                <!-- 棰樺共锛氭祬鐏板渾瑙掑潡锛岃秴闀挎椂鍧楀唴婊氬姩锛堜笉鎾戠牬鍗＄墖锛?-->
                <div class="md-quote">
                  <p class="md-quote-text">{{ c.card_front || c.title }}</p>
                </div>
                <!-- 淇℃伅涓夊垪锛氶鍨嬶紙category 浼樺厛锛? 闅惧害 / 寤鸿鐢ㄦ椂 -->
                <div class="md-meta">
                  <span class="md-meta-item"><em>棰樺瀷</em>{{ typeLabel(c) }}</span>
                  <span class="md-meta-item md-meta-diff"><em>闅惧害</em>{{ difficultyLabel(c.difficulty) }}</span>
                  <span class="md-meta-item md-meta-time"><em>寤鸿鐢ㄦ椂</em>{{ timeLabel(c) }}</span>
                </div>
                <div class="md-face-foot"><span class="md-hint">鐐瑰嚮鍗＄墖缈昏浆鐪嬭鐐?/span></div>
              </section>
              <section class="md-face back">
                <div class="md-face-head">
                  <span class="md-chip">瑕佺偣</span>
                  <span class="md-idx">鑳岄潰</span>
                </div>
                <p class="md-card-text">{{ c.card_back || '鏆傛棤鑳岄潰鍐呭' }}</p>
                <div class="md-face-foot"><span class="md-hint">鐐瑰嚮缈诲洖姝ｉ潰</span></div>
              </section>
            </div>
          </div>
        </div>

        <div class="md-actions">
          <button :disabled="index <= 0" @click="prev">涓婁竴寮?/button>
          <button class="primary" :disabled="busy" @click="flip">
            {{ flipped ? '鍐嶇炕涓€閬? : '缈昏浆鐪嬭鐐? }}
          </button>
          <button :disabled="index >= cards.length - 1" @click="next">涓嬩竴寮?/button>
        </div>
        <p class="md-tip">銆屼笅涓€寮犮€嶄负鐩存帴鍒囨崲骞跺浣嶇炕杞紱宸︿晶鍙垏鎹㈢煡璇嗘ā鍧?/p>
      </main>

      <!-- 鍙筹細鏈鐩叾浠栧崱鐗?-->
      <aside class="md-side md-side-right">
        <h2 class="md-side-title">鏈鐩叾浠栧崱鐗?/h2>
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
import { difficultyLabel, timeLabel, typeLabel } from '@/utils/materialCardMeta';

type Card = {
  id: number;
  title: string;
  category?: string | null;
  badge?: string | null;
  difficulty?: number | null;
  read_time?: number | null;
  card_front?: string | null;
  card_back?: string | null;
  subject?: string;
};

const route = useRoute();
const router = useRouter();

const subject = ref<string>((route.query.subject as string) || 'xingce');
const index = ref(0);
const flipped = ref(false);
const lifting = ref(false);   // 闃舵 A
const leaving = ref(false);   // 闃舵 D
const busy = ref(false);      // 鍔ㄧ敾涓姝㈣繛鐐?
const scale = ref(1);
const loading = ref(true);
const cards = ref<Card[]>([]);
const activeModule = ref<string>('');

const current = computed<Card | null>(() => cards.value[index.value] || null);
const stack = computed<Card[]>(() => cards.value.slice(index.value, index.value + 5));

const modules = computed(() => {
  const map = new Map<string, number>();
  for (const c of cards.value) {
    const k = c.category || '鏈垎绫?;
    map.set(k, (map.get(k) || 0) + 1);
  }
  return Array.from(map.entries()).map(([name, count]) => ({ name, count }));
});

const layerStyle = (i: number) => {
  // 绗?1 灞傦紙i=0锛変笉鍐?transform锛屼氦缁?CSS 鐨?lift/leaving 鎺у埗锛岄伩鍏嶅唴鑱旀牱寮忚鐩栧姩鐢?
  if (i === 0) return { zIndex: 10 };
  return {
    transform: `translate(${i * 11}px, ${-i * 15}px) scale(${1 - 0.012 * i})`,
    zIndex: 10 - i,
    opacity: 1 - i * 0.04
  };
};

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

// A 涓婃诞(0.25s) 鈫?B 缈昏浆(0.40s) 鈫?C 鑳岄潰鍋滅暀锛堟棤鑷姩鍒囧崱锛?
const flip = () => {
  if (!cards.value.length || busy.value) return;
  if (flipped.value) {
    // 宸茬炕鍒拌儗闈細鍙嶅悜缈诲洖锛圕 鈫?B 鍙嶅悜锛?
    busy.value = true;
    flipped.value = false;
    window.setTimeout(() => { busy.value = false; }, 400);
    return;
  }
  busy.value = true;
  lifting.value = true;                       // A
  window.setTimeout(() => {
    flipped.value = true;                     // B
    lifting.value = false;
    window.setTimeout(() => { busy.value = false; }, 400);   // C 鍋滅暀璧风偣
  }, 250);
};

// D 娌夊簳鎹㈠崱锛氬綋鍓嶅崱鍙充笅鏂归鍑?鈫?鏂板崱琛ヤ綅
const next = () => {
  if (busy.value) return;
  if (index.value >= cards.value.length - 1) return;
  leaving.value = true;
  busy.value = true;
  window.setTimeout(() => {
    index.value += 1;
    flipped.value = false;
    leaving.value = false;
    busy.value = false;
    activeModule.value = cards.value[index.value]?.category || activeModule.value;
  }, 350);
};
const prev = () => {
  if (busy.value) return;
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
.md-page {
  min-height: 100vh; background: #f5f7fb; color: #1a2a4a;
  /* 涓婚鑹诧細榛樿琛屾祴钃?*/
  --brand: #3b82f6;
  --brand-soft: #eef4ff;
  --brand-deep: #1d4ed8;
}
.md-page.theme-xingce    { --brand: #3b82f6; --brand-soft: #eef4ff; --brand-deep: #1d4ed8; }
.md-page.theme-shenlun   { --brand: #10b981; --brand-soft: #e9f9f2; --brand-deep: #047857; }
.md-page.theme-gongzhuan { --brand: #e11d48; --brand-soft: #fdeaef; --brand-deep: #9f1239; }
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
.md-mod.on, .md-other.on { background: var(--brand-soft); color: var(--brand); font-weight: 600; }
.md-mod-count, .md-other-cat { font-size: 12px; color: #8091a8; font-weight: 400; }
.md-other { flex-direction: column; align-items: flex-start; gap: 2px; }
.md-other-title { font-size: 14px; }

.md-fs { display: flex; gap: 8px; }
.md-fs button {
  flex: 1; height: 34px; border-radius: 9px; border: 1px solid #eef1f6;
  background: #fff; color: #5a6b85; cursor: pointer;
}
.md-fs button.on { border-color: var(--brand); color: var(--brand); }

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
.md-face.back { transform: rotateY(180deg); background: #fbfdff; }
.md-face-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.md-chip {
  font-size: 11px; color: var(--brand); background: var(--brand-soft);
  border-radius: 10px; padding: 4px 10px;
}
.md-idx { font-size: 12px; color: #66738a; }
.md-card-title { font-size: calc(24px * var(--sm-font-scale, 1)); font-weight: 700; margin: 0 0 14px; }
.md-card-text {
  font-size: calc(15px * var(--sm-font-scale, 1)); line-height: 1.7;
  color: #4a5a75; margin: 0; flex: 1; overflow-y: auto;
}
.md-face-foot { margin-top: 12px; }
.md-hint { font-size: 12px; color: var(--brand); }

.md-actions { display: flex; gap: 18px; margin-top: 22px; }
.md-actions button {
  width: 170px; height: 46px; border-radius: 12px; border: 1px solid #eef1f6;
  background: #fff; color: #5a6b85; font-size: 14px; cursor: pointer;
}
.md-actions button.primary { background: var(--brand); border-color: var(--brand); color: #fff; font-weight: 600; }
.md-actions button:disabled { opacity: 0.45; cursor: not-allowed; }
.md-tip { margin-top: 14px; font-size: 13px; color: #8091a8; }
.md-empty { padding: 80px 0; color: #8091a8; }

/* ===== 鍥涙鍔ㄦ晥锛圓 涓婃诞 / B 缈昏浆 / C 鍋滅暀 / D 娌夊簳锛?===== */
.md-card.lv0 {
  transition: transform 0.25s ease-out, box-shadow 0.25s ease-out, opacity 0.35s ease-in-out;
}
.md-card.lv0.lift {
  transform: translate(-20px, 30px) rotate(5deg) scale(1.02);
  box-shadow: 0 26px 60px rgba(26, 42, 74, 0.18);
}
.md-card.lv0.leaving {
  transform: translate(60px, 380px) scale(0.86);
  opacity: 0.35;
  transition: transform 0.35s ease-in-out, opacity 0.35s ease-in-out;
}
.md-inner {
  transition: transform 0.4s cubic-bezier(0.2, 0.8, 0.2, 1);
}
@media (prefers-reduced-motion: reduce) {
  .md-card.lv0.lift,
  .md-card.lv0.leaving { transform: none; opacity: 1; }
  .md-inner { transition: none; }
}

/* ===== 绉戠洰娓愬彉灏侀潰甯︼紙涓庝富椤典笁鑹蹭竴鑷达級 ===== */
.md-cover {
  height: 128px; margin: -22px -22px 16px -22px;
  border-radius: 18px 18px 0 0;
  display: flex; align-items: flex-start; justify-content: space-between;
  padding: 16px 20px; box-sizing: border-box;
}
.cover-xingce    { background: linear-gradient(160deg, #3b82f6 0%, #93c5fd 62%, #ffffff 100%); }
.cover-shenlun   { background: linear-gradient(160deg, #10b981 0%, #6ee7b7 62%, #ffffff 100%); }
.cover-gongzhuan { background: linear-gradient(160deg, #e11d48 0%, #fda4af 62%, #ffffff 100%); }
.md-chip-light {
  font-size: 12px; color: #fff; background: rgba(255,255,255,0.22);
  border: 1px solid rgba(255,255,255,0.35); border-radius: 12px; padding: 5px 12px;
  backdrop-filter: blur(2px);
}
.md-idx-light { font-size: 12px; color: #ffffff; opacity: 0.92; }
@media (prefers-reduced-motion: reduce) { .md-cover { transition: none; } }

/* ===== v2锛氶骞茬伆搴曞潡 + 涓夊垪淇℃伅 ===== */
.md-quote {
  flex: 1 1 auto;
  min-height: 120px;
  max-height: 210px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  background: #f7f9fc;
  border: 1px solid #eef2f9;
  border-radius: 14px;
  padding: 14px 16px;
  margin-bottom: 12px;
}
.md-quote-text {
  margin: 0;
  font-size: calc(14px * var(--sm-font-scale, 1));
  line-height: 1.75;
  color: #3d4d66;
  white-space: pre-wrap;
  word-break: break-word;
}
.md-meta {
  display: flex;
  align-items: baseline;
  gap: 18px;
  padding-top: 10px;
  border-top: 1px solid #eef2f9;
  font-size: 13px;
  color: #3d4d66;
}
.md-meta-item { display: inline-flex; align-items: baseline; gap: 6px; }
.md-meta-item em { font-style: normal; color: #8493a8; }
.md-meta-diff { font-weight: 600; color: #12a150; }
.md-meta-diff em { color: #8493a8; font-weight: 400; }
.md-meta-time { margin-left: auto; }
@media (max-width: 1180px) {
  .md-meta { flex-wrap: wrap; gap: 6px 16px; }
  .md-meta-time { margin-left: 0; }
}
/* 鍙充晶鍒楄〃褰撳墠椤癸細宸︿晶涓婚绔栨潯锛屼笌宸︽爮閫変腑鎬佷竴鑷?*/
.md-other.on {
  padding-left: 7px;
  border-left: 3px solid var(--brand);
  border-radius: 4px 10px 10px 4px;
}
/* 配图卡：封面图区域（无图时整块不渲染，不占位） */
.md-card-cover {
  margin: 10px 18px 0;
  border-radius: 12px;
  overflow: hidden;
  background: #f3f5f9;
  max-height: 190px;
}
.md-card-cover img {
  display: block;
  width: 100%;
  max-height: 190px;
  object-fit: cover;
}
</style>
