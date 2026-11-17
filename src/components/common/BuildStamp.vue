<template>
  <!--
    版本角标：常驻右下角，统一显示「应用版本号」。
    为什么改成版本号而不是两串 SHA：2026-11-14 用户实拍到的角标是「c4639296 · f88b771」——
    前端是 vite 启动那一刻的提交、后端是后端启动那一刻的提交，两串字面永不相同，
    用户只能读成"版本不一致"。现在两端都读仓库根 VERSION 文件，角标只有一个值；
    SHA / 构建时间 / 后端 SHA 全部降级到 tooltip，供排查时才看。
  -->
  <div
    v-if="visible && showStamp"
    class="build-stamp"
    :class="{ 'is-mismatch': isMismatch }"
    role="status"
    :title="tip"
    @click="copyInfo">
    <span class="dot"></span>
    <span class="ver">v{{ version || '—' }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRoute } from 'vue-router';

interface AppBuild {
  version?: string;
  sha?: string;
  time?: string;
  backend?: string;
  backendVersion?: string;
}

const route = useRoute();
const info = ref<AppBuild>({});
const visible = ref(false);
let timer: number | undefined;

function read() {
  const w = window as unknown as { __APP_BUILD__?: AppBuild };
  info.value = w.__APP_BUILD__ || {};
  // main.ts 在拿到 /health 前就会写入 version；有值即可显示
  if (info.value.version) visible.value = true;
}

const version = computed(() => info.value.version || '');
const backendVersion = computed(() => info.value.backendVersion || '');

// 只有版本号（VERSION 文件）不同才是真不一致；SHA 差异是 dev 常态，不报警
const isMismatch = computed(() => {
  const b = backendVersion.value;
  if (!b || b === '0.0.0' || !version.value) return false;
  return b !== version.value;
});

// 答题页底部有「上一题 / 下一题 / 交卷」满宽操作条，角标会压住按钮；
// 但版本真的不一致时必须继续显示（这是排查线索，不能因为页面类型被藏掉）
const isAnswering = computed(() => route.path.indexOf('/exercise') === 0);
const showStamp = computed(() => !isAnswering.value || isMismatch.value);

const tip = computed(() => {
  const lines = [
    `应用版本 v${version.value || '—'}`,
    `前端构建 ${info.value.sha || 'dev'} @ ${info.value.time || '-'}`,
    `后端版本 v${backendVersion.value || '未获取'}（提交 ${info.value.backend || '未获取'}）`,
  ];
  if (isMismatch.value) {
    lines.push('⚠️ 前后端版本号不一致：页面可能是旧产物，请刷新；仍不一致则重启后端');
  }
  lines.push('点击复制排查信息');
  return lines.join('\n');
});

async function copyInfo() {
  try {
    await navigator.clipboard.writeText(`${tip.value}\nUA: ${navigator.userAgent}`);
  } catch {
    // 剪贴板不可用时静默：角标本身已能看见版本号
  }
}

onMounted(() => {
  read();
  timer = window.setInterval(read, 800);
  window.setTimeout(() => {
    if (timer) window.clearInterval(timer);
  }, 30000);
});

onUnmounted(() => {
  if (timer) window.clearInterval(timer);
});
</script>

<style scoped>
.build-stamp {
  position: fixed;
  right: 12px;
  bottom: 10px;
  z-index: 3000;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 999px;
  background: rgb(0 0 0 / 55%);
  color: #fff;
  font-size: 12px;
  line-height: 1.4;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  cursor: pointer;
  user-select: none;
  opacity: 0.4;
  transition: opacity 0.2s;
}

.build-stamp:hover,
.build-stamp:focus-visible {
  opacity: 1;
  outline: 2px solid #fff;
  outline-offset: 2px;
}

.build-stamp.is-mismatch {
  background: #b91c1c;
  opacity: 1;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22c55e;
}

.is-mismatch .dot {
  background: #fbbf24;
}

/* 手机端贴底会盖住操作条，上移到安全区之上 */
@media (width <= 700px) {
  .build-stamp {
    bottom: 72px;
    right: 10px;
    font-size: 11px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .build-stamp {
    transition: none;
  }
}
</style>
