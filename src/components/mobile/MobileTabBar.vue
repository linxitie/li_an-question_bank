<!--
  手机端底部导航栏 —— 全站唯一真源（单一事实来源）

  背景：此前 5 个手机页（home / question_bank / practice / forum / profile）各自内联
  一份几乎相同但并不完全相同的底栏（图标尺寸 20 与 22 混用、样式实现各异），
  导致「改一处漏三处」类缺陷（论坛 tab 文字被实心深底遮住即由此产生）。

  本组件收敛：
    - 图标 / 文案 / 路由 / 激活态配色 / 过渡动画 —— 只在此处定义一次
    - 激活态统一为「白底 + 深藏青文字与图标」，**严禁实心深底**（会遮住图标与文字）
    - 过渡统一使用 design-tokens 动画令牌
    - 触控区不小于 --touch-target-min（44px）

  用法：<MobileTabBar active="home" />
  组件内部自行处理跳转，调用方无需再实现 switchTab。
-->
<template>
  <nav class="mtb-bar">
    <div
      v-for="item in tabs"
      :key="item.key"
      :class="['mtb-item', { active: active === item.key }]"
      @click="go(item)"
    >
      <XIcon :icon="item.icon" :size="22" :color="active === item.key ? ACTIVE : INACTIVE"></XIcon>
      <span class="mtb-label">{{ item.label }}</span>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import { XIcon } from '@vtj/ui';
import { HomeFilled, Edit, ChatLineRound, User } from '@vtj/icons';

// 激活/未激活配色：与 design-tokens 主色保持一致
const ACTIVE = '#1A365D';
const INACTIVE = '#a0a4b8';

const props = defineProps<{ active: string }>();

/**
 * 导航项配置。顺序即显示顺序。
 * 依据决策 D2：底栏不再保留「题库」——其能力（三科目下钻、混合练习、备考资料、
 * 历年试卷、智能组卷、错题本）已下沉到「练习」页与「我的」页，题库页路由保留。
 */
const tabs = [
  { key: 'home', label: '首页', icon: HomeFilled, path: '/mobile/home' },
  { key: 'practice', label: '练习', icon: Edit, path: '/mobile/practice' },
  { key: 'forum', label: '论坛', icon: ChatLineRound, path: '/mobile/forum' },
  { key: 'profile', label: '我的', icon: User, path: '/mobile/profile' },
];

const router = useRouter();

const go = (item: { key: string; path: string }) => {
  if (item.key === props.active) return; // 已在当前页，避免重复跳转
  if (router.currentRoute.value.path === item.path) return;
  router.push(item.path);
};
</script>

<style scoped>
.mtb-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 60px;
  background: #ffffff;
  display: flex;
  justify-content: space-around;
  align-items: center;
  border-top: 1px solid #f0f2f5;
  padding-bottom: env(safe-area-inset-bottom, 0);
  z-index: 100;
}

.mtb-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  height: 100%;
  /* 触控区不小于 44px（design-tokens --touch-target-min） */
  min-height: var(--touch-target-min, 44px);
  cursor: pointer;
  background: transparent;
  /* 与全站统一：使用 design-tokens 动画令牌 */
  transition: color var(--duration-normal, 300ms) var(--easing-default, cubic-bezier(0.4, 0, 0.2, 1));
}

/* 激活态：白底 + 深藏青文字/图标。严禁加实心深底（会遮住图标与文字） */
.mtb-item.active {
  color: #1A365D;
  background: transparent;
}

.mtb-item:not(.active) {
  color: #a0a4b8;
}

.mtb-label {
  font-size: 10px;
  font-weight: 500;
  margin-top: 2px;
}

@supports (padding-bottom: env(safe-area-inset-bottom)) {
  .mtb-bar {
    height: calc(60px + env(safe-area-inset-bottom));
  }
}
</style>
