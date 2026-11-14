<template>
  <!--
    构建戳：常驻右下角，显示「前端 SHA · 后端 SHA」。
    为什么需要它：2026-11-14 出现过「联考小智变成功能开发中」，真实原因是工作区被切到旧分支，
    而界面上没有任何"我现在跑的是哪份代码"的可视信号，只能靠翻 git 才查得出来。
    这个角标让版本不一致一眼可见，点击可复制完整信息用于排查。
  -->
  <div
    v-if="visible"
    class="build-stamp"
    :class="{ 'is-mismatch': isMismatch }"
    role="status"
    :title="tip"
    @click="copyInfo">
    <span class="dot"></span>
    <span class="sha">{{ shortSha }}</span>
    <span class="sep">·</span>
    <span class="be">{{ shortBackend }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';

interface AppBuild {
  sha?: string;
  time?: string;
  backend?: string;
}

const info = ref<AppBuild>({});
const visible = ref(false);
const copied = ref(false);
let timer: number | undefined;

function read() {
  const w = window as unknown as {
    __APP_BUILD__?: AppBuild;
    __VERSION_MISMATCH__?: { frontend: string; backend: string };
  };
  info.value = w.__APP_BUILD__ || {};
  // main.ts 在拿到 /health 后回填 backend；这里轮询到有值为止（最多 30 秒）
  if (info.value.sha) visible.value = true;
}

const shortSha = computed(() => (info.value.sha || 'dev').slice(0, 7));
const shortBackend = computed(() => {
  const b = info.value.backend;
  if (!b) return '后端…';
  return b === 'unknown' ? '未知' : b.slice(0, 7);
});

const isMismatch = computed(() => {
  const b = info.value.backend;
  if (!b || b === 'unknown') return false;
  const s = info.value.sha || '';
  return s !== '' && s !== 'dev' && s !== b;
});

const tip = computed(() => {
  const base = `前端 ${info.value.sha || 'dev'} @ ${info.value.time || '-'}\n后端 ${info.value.backend || '未获取'}`;
  return isMismatch.value ? base + '\n⚠️ 前后端版本不一致：页面可能是旧代码，请刷新或重启后端' : base;
});

async function copyInfo() {
  try {
    await navigator.clipboard.writeText(`${tip.value}\nUA: ${navigator.userAgent}`);
    copied.value = true;
    setTimeout(() => (copied.value = false), 1200);
  } catch {
    // 剪贴板不可用时静默：角标本身已能看见版本号
  }
}

onMounted(() => {
  read();
  timer = window.setInterval(read, 1000);
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
  gap: 4px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgb(0 0 0 / 55%);
  color: #fff;
  font-size: 12px;
  line-height: 1.4;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  cursor: pointer;
  user-select: none;
  opacity: 0.35;
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

/* 手机端不遮挡底部操作条 */
@media (width <= 700px) {
  .build-stamp {
    bottom: 64px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .build-stamp {
    transition: none;
  }
}
</style>
